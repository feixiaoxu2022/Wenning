/**
 * 主应用逻辑
 * 整合SSE和UI模块
 */

// 初始化
const sseClient = new SSEClient();
const ui = new UI();
let currentModel = 'gpt-5';
let currentConversationId = null;
let isSending = false; // 防止重复发送
let stopBtnEl = null;
let mentionAutocomplete = null; // @mention autocomplete 实例

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[App] 应用初始化');
    await checkAuthAndInit();
    try {
        initResizableLayout();
    } catch (e) {
        console.warn('resizable init failed', e);
    }
    // 兜底：无论鉴权状态如何，都绑定一次登录/注册按钮
    try {
        if (!authHandlersWired) {
            wireAuthHandlers();
        }
    } catch (e) {
        console.warn('wireAuthHandlers fallback failed', e);
    }
});

let authHandlersWired = false;
let allowRegisterCache = true;
let currentUser = null;

async function checkAuthAndInit() {
    try {
        const resp = await fetch('/auth/me', { method: 'GET' });
        if (resp.ok) {
            // 登录状态或无需登录
            const data = await resp.json().catch(() => ({}));
            hideAuthOverlay();
            currentUser = data.user || null;
            updateAccountUI(currentUser);
            allowRegisterCache = typeof data.allow_register === 'boolean' ? data.allow_register : true;
            await initAppAfterAuth();
        } else if (resp.status === 401) {
            // 未登录且需要登录
            showAuthOverlay();
            if (!authHandlersWired) wireAuthHandlers();
            ui.setInputEnabled(false);
            // 读取config决定是否显示注册
            try {
                const cfg = await fetch('/auth/config').then(r => r.json()).catch(() => ({}));
                allowRegisterCache = !!cfg.allow_register;
                const regBtn = document.getElementById('auth-register-btn');
                if (regBtn) regBtn.style.display = allowRegisterCache ? 'inline-block' : 'none';
            } catch {}
            // 仍然加载模型下拉，避免看起来"空白"
            try {
                await loadModels();
            } catch (_) {
                // Ignore errors
            }
        } else {
            // 其他错误，先继续初始化但提示
            console.warn('[Auth] /auth/me 非预期状态:', resp.status);
            hideAuthOverlay();
            await initAppAfterAuth();
        }
    } catch (e) {
        console.warn('[Auth] /auth/me 调用失败，继续初始化:', e);
        hideAuthOverlay();
        await initAppAfterAuth();
    }
}

async function initAppAfterAuth() {
    // 加载模型列表
    await loadModels();
    // 加载对话列表
    await loadConversationsList();
    // 创建或加载对话
    await ensureConversation();
    // 初始化@mention autocomplete
    if (typeof MentionAutocomplete !== 'undefined') {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            mentionAutocomplete = new MentionAutocomplete(chatInput);
            console.log('[App] @mention autocomplete已初始化');
        }
    }
    // 绑定事件
    bindEvents();
    // 配置SSE回调
    setupSSECallbacks();
    // 主题和侧栏
    initThemeToggle();
    initSidebarToggles();
    initFileListCollapse();
    // 初始化Showcase
    if (typeof ShowcaseManager !== 'undefined') {
        window.showcaseManager = new ShowcaseManager(ui);
        console.log('[App] Showcase已初始化');
    }
    console.log('[App] 应用就绪');

    // ✅ 只有在用户成功登录/认证后，才触发首次引导
    setTimeout(() => {
        if (productTour) {
            productTour.autoStartForFirstTime();
        }
    }, 1500);
}

function showAuthOverlay() {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) overlay.style.display = 'flex';
}

function hideAuthOverlay() {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) overlay.style.display = 'none';
    // 允许输入
    ui.setInputEnabled(true);
}

function wireAuthHandlers() {
    const loginBtn = document.getElementById('auth-login-btn');
    const registerBtn = document.getElementById('auth-register-btn');
    const userEl = document.getElementById('auth-username');
    const passEl = document.getElementById('auth-password');
    const errEl = document.getElementById('auth-error');

    if (loginBtn) {
        loginBtn.addEventListener('click', async () => {
            errEl.textContent = '';
            const username = (userEl.value || '').trim();
            const password = (passEl.value || '').trim();
            if (!username || !password) {
                errEl.textContent = '请输入用户名和密码';
                return;
            }
            try {
                const r = await fetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                if (r.ok) {
                    currentUser = username;
                    updateAccountUI(currentUser);
                    hideAuthOverlay();
                    await initAppAfterAuth();
                } else {
                    const data = await r.json().catch(() => ({ error: '登录失败' }));
                    errEl.textContent = data.error || '登录失败';
                }
            } catch (e) {
                errEl.textContent = '网络错误';
            }
        });
    }

    if (registerBtn) {
        registerBtn.addEventListener('click', async () => {
            errEl.textContent = '';
            const username = (userEl.value || '').trim();
            const password = (passEl.value || '').trim();
            if (!username || !password) {
                errEl.textContent = '请输入用户名和密码';
                return;
            }
            try {
                const r = await fetch('/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                if (r.ok) {
                    // 注册成功后尝试自动登录
                    const login = await fetch('/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    if (login.ok) {
                        currentUser = username;
                        updateAccountUI(currentUser);
                        hideAuthOverlay();
                        await initAppAfterAuth();
                    } else {
                        errEl.textContent = '注册成功，但自动登录失败，请手动登录';
                    }
                } else if (r.status === 403) {
                    const data = await r.json().catch(() => ({}));
                    errEl.textContent = data.error || '注册被禁用';
                } else {
                    const data = await r.json().catch(() => ({}));
                    errEl.textContent = data.error || '注册失败';
                }
            } catch (e) {
                errEl.textContent = '网络错误';
            }
        });
    }

    authHandlersWired = true;
}

// 账户UI：显示用户名、登出
function updateAccountUI(username) {
    const btn = document.getElementById('account-btn');
    const nameEl = document.getElementById('account-username');
    if (btn) btn.textContent = username ? `@${username}` : '👤';
    if (nameEl) nameEl.textContent = username ? `Signed in as ${username}` : 'Not signed in';

    // 同时更新欢迎消息的用户名
    const welcomeUsername = document.getElementById('welcome-username');
    if (welcomeUsername) {
        welcomeUsername.textContent = username || 'User';
    }
}

// 显示/隐藏欢迎消息的辅助函数
function updateWelcomeMessage() {
    const welcomeMsg = document.getElementById('welcome-message');
    if (!welcomeMsg) return;

    // 检查是否有消息
    const hasMessages = ui.chatMessages.querySelectorAll('.message').length > 0;

    if (hasMessages) {
        welcomeMsg.style.display = 'none';
    } else {
        welcomeMsg.style.display = 'block';
    }
}

// 账户菜单交互与登出
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('account-btn');
    const menu = document.getElementById('account-menu');
    const logout = document.getElementById('logout-btn');
    if (btn && menu) {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.style.display = menu.style.display === 'none' || !menu.style.display ? 'block' : 'none';
        });
        document.addEventListener('click', () => { menu.style.display = 'none'; });
    }
    if (logout) {
        logout.addEventListener('click', async () => {
            try {
                await fetch('/auth/logout', { method: 'POST' });
            } catch {
                // Ignore errors
            }
            currentUser = null;
            updateAccountUI(null);
            showAuthOverlay();
            ui.setInputEnabled(false);
        });
    }
});

/**
 * 加载模型列表
 */
async function loadModels() {
    try {
        const response = await fetch('/models');
        const data = await response.json();

        const modelSelect = document.getElementById('model-select');
        // 清空旧选项，避免重复或缓存残留
        while (modelSelect.firstChild) modelSelect.removeChild(modelSelect.firstChild);

        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            option.textContent = model.display_name;
            if (model.default) {
                option.selected = true;
                // 仅在 currentModel 还是初始值时才设置默认模型
                // 如果用户已经选择了模型，不要覆盖
                if (currentModel === 'gpt-5') {
                    currentModel = model.name;
                }
            }
            modelSelect.appendChild(option);
        });

        // 优先应用用户持久化的模型偏好
        try {
            const savedModel = localStorage.getItem('cf-model');
            if (savedModel && Array.from(modelSelect.options).some(o => o.value === savedModel)) {
                modelSelect.value = savedModel;
                currentModel = savedModel;
                console.log('[App] 应用本地持久化模型:', savedModel);
            }
        } catch (_) {}

        console.log('[App] 模型列表加载完成, currentModel:', currentModel);

    } catch (err) {
        console.error('[App] 加载模型列表失败:', err);
    }
}

/**
 * 加载对话列表（显示所有模型的对话）
 */
async function loadConversationsList() {
    try {
        // 不传model参数，显示所有模型的对话
        const response = await fetch(`/conversations`);
        const conversationsList = document.getElementById('conversations-list');
        let data = { conversations: [] };
        try {
            data = await response.json();
        } catch (_) {
            // Ignore errors
        }

        conversationsList.innerHTML = '';

        if (data.conversations && data.conversations.length > 0) {
            // 统一按更新时间降序显示，避免后端返回顺序不稳定
            try {
                data.conversations.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
            } catch (_) {}
            console.log(`[App] 加载对话列表: ${data.conversations.length}个对话`);

            data.conversations.forEach(conv => {
                const convItem = createConversationItem(conv);
                conversationsList.appendChild(convItem);
            });
        } else {
            let msg;
            if (response.ok) {
                msg = '暂无对话';
            } else if (response.status === 401) {
                msg = '未登录或会话过期，请登录';
            } else {
                msg = `加载失败 (HTTP ${response.status})`;
            }
            const style = 'text-align:center; color:#999; padding:20px; font-size:12px;';
            conversationsList.innerHTML = `<p style="${style}">${msg}</p>`;
        }

    } catch (err) {
        console.error('[App] 加载对话列表失败:', err);
        const conversationsList = document.getElementById('conversations-list');
        if (conversationsList) {
            conversationsList.innerHTML = '<p style="text-align:center; color:#999; padding:20px; font-size:12px;">加载失败（网络错误）</p>';
        }
    }
}

/**
 * 创建对话列表项
 */
function createConversationItem(conv) {
    const item = document.createElement('div');
    item.className = 'conversation-item';
    if (conv.id === currentConversationId) {
        item.classList.add('active');
    }
    item.dataset.convId = conv.id;

    item.innerHTML = `
        <div class="conversation-item-title">${conv.title}</div>
        <div class="conversation-item-meta">
            <span>${conv.updated_at.split(' ')[0]}</span>
            <span class="conversation-item-delete" data-conv-id="${conv.id}">🗑️</span>
        </div>
    `;

    // 点击切换对话
    item.addEventListener('click', (e) => {
        // 检查是否点击了删除按钮或其子元素
        if (!e.target.closest('.conversation-item-delete')) {
            // 先折叠历史浮层
            const overlay = document.getElementById('history-overlay');
            if (overlay) overlay.classList.remove('active');
            // 再切换对话
            switchConversation(conv.id);
        }
    });

    // 删除按钮
    const deleteBtn = item.querySelector('.conversation-item-delete');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            await deleteConversation(conv.id);
        });
    }

    return item;
}

/**
 * 确保有当前对话（优先加载有消息的最新对话）
 */
async function ensureConversation() {
    try {
        // 优先尝试从localStorage恢复上次的对话
        let lastConvId = null;
        try {
            lastConvId = localStorage.getItem('cf-last-conv');
        } catch (_) {}

        if (lastConvId) {
            // 验证该对话是否还存在
            try {
                const checkResp = await fetch(`/conversation/${encodeURIComponent(lastConvId)}`);
                if (checkResp.ok) {
                    console.log('[App] 从localStorage恢复上次对话:', lastConvId);
                    currentConversationId = lastConvId;
                    window.currentConversationId = currentConversationId; // 同步到window对象供ui.js使用
                    await loadConversation(currentConversationId);

                    // 恢复成功后设置输出路径
                    if (currentConversationId) {
                        ui.setOutputsBase(currentConversationId);
                    }

                    // 刷新左侧History列表
                    try {
                        await loadConversationsList();
                    } catch (_) {
                        // Ignore errors
                    }

                    console.log('[App] 当前对话ID:', currentConversationId);
                    return; // 恢复成功，直接返回
                }
            } catch (e) {
                console.warn('[App] 恢复上次对话失败，将使用默认逻辑:', e);
            }
        }

        // 获取所有对话（不过滤模型）
        const response = await fetch(`/conversations`);
        const data = await response.json();

        if (data.conversations && data.conversations.length > 0) {
            // 过滤出有消息的对话
            const conversationsWithMessages = [];

            for (const conv of data.conversations) {
                try {
                    // 加载对话详情检查是否有消息
                    const detailResp = await fetch(`/conversations/${conv.id}`);
                    if (detailResp.ok) {
                        const detail = await detailResp.json();
                        if (detail.messages && detail.messages.length > 0) {
                            conversationsWithMessages.push({
                                ...conv,
                                messageCount: detail.messages.length
                            });
                        }
                    }
                } catch (e) {
                    console.warn(`[App] 检查对话 ${conv.id} 失败:`, e);
                }
            }

            // 如果有消息的对话存在，选择最新的（updated_at最大）
            if (conversationsWithMessages.length > 0) {
                conversationsWithMessages.sort((a, b) => {
                    const at = String(a.updated_at || '');
                    const bt = String(b.updated_at || '');
                    return bt.localeCompare(at);
                });

                const latest = conversationsWithMessages[0];
                console.log(`[App] 加载最新的有消息对话: ${latest.id}, 消息数: ${latest.messageCount}, 更新时间: ${latest.updated_at}`);

                currentConversationId = latest.id;
                window.currentConversationId = currentConversationId; // 同步到window对象
                await loadConversation(currentConversationId);
            } else {
                // 所有对话都是空的，创建新对话
                console.log('[App] 所有对话都是空的，创建新对话');
                await createNewConversation();
            }
        } else {
            // 没有任何对话，创建新对话
            console.log('[App] 没有任何对话，创建新对话');
            await createNewConversation();
        }

        console.log('[App] 当前对话ID:', currentConversationId);

        // 兜底：确保右侧预览使用会话隔离路径，避免首次粘贴/上传预览404
        if (currentConversationId) {
            ui.setOutputsBase(currentConversationId);
        }

        // 刷新左侧History列表
        try {
            await loadConversationsList();
        } catch (_) {
            // Ignore errors
        }

    } catch (err) {
        console.error('[App] 确保对话失败:', err);
    }
}


/**
 * 加载对话内容
 */
async function loadConversation(convId) {
    try {
        console.log(`[App] loadConversation被调用: ${convId}`);
        const response = await fetch(`/conversations/${convId}`);
        const conv = await response.json();

        // 同步更新模型选择器为该对话创建时使用的模型
        if (conv.model) {
            const modelSelect = document.getElementById('model-select');
            if (modelSelect) {
                modelSelect.value = conv.model;
                currentModel = conv.model;
                console.log(`[App] 加载对话，同步模型为: ${conv.model}`);
            }
        }

        // 清空聊天区域
        console.log(`[App] 清空聊天区域, 当前消息数: ${ui.chatMessages.children.length}`);
        ui.chatMessages.innerHTML = '';
        console.log(`[App] 清空后消息数: ${ui.chatMessages.children.length}`);

        // 清空预览区域
        ui.clearAllFiles();

        // 设置文件基础路径为对话级隔离目录
        if (conv && conv.id) {
            ui.setOutputsBase(conv.id);
        }

        // 渲染历史消息(禁用打字机效果)
        if (conv.messages && conv.messages.length > 0) {
            // 去重相邻重复（相同role+content），合并文件列表（忽略顺序/去重/兼容undefined与[]）
            const normalize = (txt) => (txt || '')
                .replace(/\r\n/g, '\n') // 统一换行
                .replace(/\u00a0/g, ' ') // NBSP→空格
                .replace(/[ \t]+/g, ' ') // 连续空白折叠
                .trim(); // 去首尾空白
            const deduped = [];
            for (const m of conv.messages) {
                const prev = deduped[deduped.length - 1];
                if (prev && prev.role === m.role && normalize(prev.content) === normalize(m.content)) {
                    const prevFiles = Array.isArray(prev.generated_files) ? prev.generated_files : [];
                    const curFiles = Array.isArray(m.generated_files) ? m.generated_files : [];
                    const merged = Array.from(new Set([...prevFiles, ...curFiles]));
                    if (merged.length > 0) {
                        prev.generated_files = merged;
                    }
                    continue; // 合并后跳过当前条
                }
                // 规范化generated_files为数组或不设置
                if (m.generated_files && !Array.isArray(m.generated_files)) {
                    m.generated_files = [];
                }
                deduped.push(m);
            }

            console.log(`[App] 加载对话 ${convId}: 原始${conv.messages.length}条，去重后${deduped.length}条`);

            // 追踪当前迭代轮次（每次assistant调用工具时递增）
            let currentIter = 0;

            // 使用for...of替代forEach，支持async/await
            for (let i = 0; i < deduped.length; i++) {
                const msg = deduped[i];

                if (msg.role === 'user') {
                    // 每次遇到新的user消息，重置iter计数为0
                    currentIter = 0;
                    ui.addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    // 检查是否有工具调用 - 如果有，说明开始新的迭代轮次
                    if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
                        currentIter++; // 开始新的迭代轮次

                        // 有工具调用：显示执行过程（历史加载时不显示参数，保持UI简洁）
                        msg.tool_calls.forEach(toolCall => {
                            const toolName = toolCall.function?.name || 'unknown';

                            // 显示工具执行（不传args_preview，避免占用过多空间）
                            ui.appendExec(currentIter, {
                                phase: 'start',
                                tool: toolName
                            });

                            // 标记完成（从历史中加载都是已完成的）
                            ui.appendExec(currentIter, {
                                phase: 'done',
                                tool: toolName
                            });
                        });
                    }

                    // 历史列表中，LLM在调用工具时会产生一条content为空的assistant占位（仅包含tool_calls）
                    // 这类占位会在UI上渲染成一块空白。这里对空内容进行跳过，仅保留有实际文本的assistant消息。
                    const content = (msg.content || '').trim();

                    // 如果该条记录携带生成的文件，仍需加载预览（即使没有可显示的文本）
                    if (Array.isArray(msg.generated_files) && msg.generated_files.length > 0) {
                        console.log(`[App] 加载历史消息的文件:`, msg.generated_files);
                        ui.loadMultipleFiles(msg.generated_files);
                        // 显示生成的文件（使用当前迭代轮次，如果没有工具调用则为0）
                        ui.appendExec(currentIter || 1, {
                            phase: 'files',
                            files: msg.generated_files
                        });
                    }

                    if (!content) {
                        // 纯函数调用占位，跳过渲染文本，避免出现"大块空白"
                        continue;
                    }

                    // 关键修复：等待async方法完成
                    const resultBox = await ui.showResult({ status: 'success', result: content }, false); // 禁用打字机效果

                    // 判断是否应该添加反馈按钮：
                    // 只有当这条assistant消息是"最终回复"时才添加反馈按钮
                    // 判断标准：下一条消息是user消息，或者这是对话历史中的最后一条消息
                    const shouldAttachFeedback = (() => {
                        // 查找下一条非tool消息
                        for (let j = i + 1; j < deduped.length; j++) {
                            const nextMsg = deduped[j];
                            if (nextMsg.role === 'tool') {
                                continue; // 跳过tool消息
                            }
                            // 如果下一条是user消息，说明当前assistant是最终回复
                            if (nextMsg.role === 'user') {
                                return true;
                            }
                            // 如果下一条是assistant消息，说明当前不是最终回复
                            if (nextMsg.role === 'assistant') {
                                return false;
                            }
                        }
                        // 如果没有找到下一条消息，说明这是对话历史中的最后一条
                        return true;
                    })();

                    // 只为最终回复消息添加反馈按钮
                    if (shouldAttachFeedback && msg.id && resultBox) {
                        ui.attachFeedbackButtons(resultBox, msg.id, msg.feedback);
                    }

                } else if (msg.role === 'tool') {
                    // 提取tool消息content中的generated_files
                    try {
                        const contentObj = JSON.parse(msg.content);
                        if (contentObj && contentObj.data && Array.isArray(contentObj.data.generated_files) && contentObj.data.generated_files.length > 0) {
                            console.log(`[App] 从tool消息提取文件:`, contentObj.data.generated_files);
                            ui.loadMultipleFiles(contentObj.data.generated_files);
                        }
                    } catch (e) {
                        // content不是JSON或没有generated_files字段，忽略
                    }
                }
            }
        }

        // 更新激活状态
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.convId === convId) {
                item.classList.add('active');
            }
        });

        // 获取并更新上下文统计
        if (conv.context_stats) {
            updateContextIndicator(conv.context_stats);
        }

        // 兜底：扫描会话目录，补充未记录到消息里的可预览文件（如重启前未保存的最后一条）
        try {
            // 使用不与文件路由冲突的列表端点
            const listResp = await fetch(`/outputs/list/${encodeURIComponent(convId)}`);
            if (listResp.ok) {
                const data = await listResp.json();
                if (data && Array.isArray(data.files) && data.files.length) {
                    const shown = new Set((ui.files || []).map(f => f.filename));
                    const previewables = data.files.filter(fn => /\.(png|jpg|jpeg|xlsx|pptx|docx|doc|csv|html|pdf|json|mp3|wav|m4a|aac|ogg|flac|mp4|webm|mov|txt|md|log)$/i.test(fn));
                    const missing = previewables.filter(fn => !shown.has(fn));
                    if (missing.length) {
                        console.log('[App] 兜底补充会话文件:', missing);
                        ui.loadMultipleFiles(missing);
                    }
                }
            }
        } catch (e) {
            console.warn('[App] 兜底扫描会话文件失败', e);
        }

        // 加载该会话的Workspace文件（使用用户级API）
        try {
            ui.refreshWorkspace();
        } catch (e) {
            console.warn('[App] 加载Workspace失败:', e);
        }

        // 更新欢迎消息显示状态
        updateWelcomeMessage();

    } catch (err) {
        console.error('[App] 加载对话失败:', err);
    }
}

/**
 * 切换对话（暴露给全局供workspace使用）
 */
async function switchConversation(convId) {
    if (!convId || convId === currentConversationId) return;

    // 折叠历史浮层（防止遮挡左侧）
    const overlay = document.getElementById('history-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }

    currentConversationId = convId;
    window.currentConversationId = currentConversationId; // 同步到window对象
    try {
        localStorage.setItem('cf-last-conv', convId);
    } catch (_) {
        // Ignore errors
    }
    await loadConversation(convId);
    try {
        await loadConversationsList();
    } catch (_) {
        // Ignore errors
    }
}

// 暴露给全局
window.switchConversation = switchConversation;

/**
 * 创建新对话（使用当前选中的模型）
 */
async function createNewConversation() {
    try {
        // 确保使用模型选择器的实际值，而不是可能过时的 currentModel
        const modelSelect = document.getElementById('model-select');
        const actualModel = modelSelect ? modelSelect.value : currentModel;

        // 更新 currentModel 以保持同步
        currentModel = actualModel;

        console.log('[App] 创建新对话, 使用模型:', actualModel);

        const response = await fetch(`/conversations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: actualModel  // 使用确认后的模型值
            })
        });
        const data = await response.json();

        currentConversationId = data.conversation_id;
        window.currentConversationId = currentConversationId; // 同步到window对象
        try {
            localStorage.setItem('cf-last-conv', currentConversationId);
        } catch (_) {
            // Ignore errors
        }
        console.log('[App] 新对话创建成功:', currentConversationId, 'model:', actualModel);

        // 重新加载对话列表
        await loadConversationsList();

        // 清空聊天区域
        ui.chatMessages.innerHTML = '';

        // 清空预览区域
        ui.clearAllFiles();

        // 设置会话级文件基础路径，确保实时文件事件使用正确路径
        if (currentConversationId) {
            ui.setOutputsBase(currentConversationId);
        }

        // 更新激活状态
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.convId === currentConversationId) {
                item.classList.add('active');
            }
        });

        // 更新欢迎消息显示状态
        updateWelcomeMessage();

    } catch (err) {
        console.error('[App] 创建新对话失败:', err);
    }
}

/**
 * 删除对话
 */
async function deleteConversation(convId) {
    if (!confirm('确定要删除这个对话吗?')) {
        return;
    }

    try {
        await fetch(`/conversations/${convId}`, {
            method: 'DELETE'
        });

        console.log('[App] 删除对话:', convId);

        // 如果删除的是当前对话,切换到新对话
        if (convId === currentConversationId) {
            await createNewConversation();
        }

        // 重新加载对话列表
        await loadConversationsList();

    } catch (err) {
        console.error('[App] 删除对话失败:', err);
    }
}

/**
 * 绑定事件
 */
function bindEvents() {
    // 发送按钮点击
    ui.sendBtn.addEventListener('click', () => {
        sendMessage();
    });

    // 停止按钮
    stopBtnEl = document.getElementById('stop-btn');
    if (stopBtnEl) {
        stopBtnEl.addEventListener('click', () => {
            stopStreaming();
        });
    }

    // 输入框快捷键: Enter发送, Shift+Enter换行
    ui.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            // 如果正在使用输入法组合输入（如中文拼音），不发送
            if (e.isComposing) {
                return;
            }
            // 如果@mention下拉框正在显示，不发送消息（让mention处理）
            if (mentionAutocomplete && mentionAutocomplete.isShowing) {
                return;
            }
            e.preventDefault();
            sendMessage();
        }
        // ESC 停止
        if (e.key === 'Escape') {
            e.preventDefault();
            stopStreaming();
        }
    });

    // 粘贴剪贴板图片直接作为附件上传
    ui.chatInput.addEventListener('paste', async (e) => {
        try {
            const cd = e.clipboardData || window.clipboardData;
            if (!cd || !cd.items || cd.items.length === 0) return;
            const files = [];
            for (const item of cd.items) {
                if (item.kind === 'file') {
                    const blob = item.getAsFile();
                    if (blob && /^image\//.test(blob.type)) {
                        const ext = (blob.type.split('/')[1] || 'png').replace(/[^a-z0-9]/gi, '') || 'png';
                        const ts = new Date();
                        const pad = (n) => String(n).padStart(2, '0');
                        const name = `screenshot_${ts.getFullYear()}${pad(ts.getMonth()+1)}${pad(ts.getDate())}_${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}.${ext}`;
                        // 封装为File以便FormData追加文件名
                        const f = new File([blob], name, { type: blob.type });
                        files.push(f);
                    }
                }
            }
            if (files.length > 0) {
                // 不阻止默认行为，让文本仍可粘贴到输入框
                await uploadFiles(files);
            }
        } catch (err) {
            console.warn('[Paste] 处理剪贴板失败:', err);
        }
    });

    // 兜底：当输入框未聚焦时也允许粘贴图片（例如用户直接在页面按下 Cmd+V）
    document.addEventListener('paste', async (e) => {
        try {
            // 若输入框已经处理过，则跳过
            if (document.activeElement === ui.chatInput) return;
            const cd = e.clipboardData || window.clipboardData;
            if (!cd || !cd.items || cd.items.length === 0) return;
            const files = [];
            for (const item of cd.items) {
                if (item.kind === 'file') {
                    const blob = item.getAsFile();
                    if (blob && /^image\//.test(blob.type)) {
                        const ext = (blob.type.split('/')[1] || 'png').replace(/[^a-z0-9]/gi, '') || 'png';
                        const ts = new Date();
                        const pad = (n) => String(n).padStart(2, '0');
                        const name = `screenshot_${ts.getFullYear()}${pad(ts.getMonth()+1)}${pad(ts.getDate())}_${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}.${ext}`;
                        const f = new File([blob], name, { type: blob.type });
                        files.push(f);
                    }
                }
            }
            if (files.length > 0) {
                await uploadFiles(files);
            }
        } catch (err) {
            console.warn('[Paste] 页面级粘贴处理失败:', err);
        }
    });

    // 模型选择变化：同步并持久化，并更新后端对话模型
    document.getElementById('model-select').addEventListener('change', async (e) => {
        const newModel = e.target.value;
        const previousModel = currentModel;

        // 如果当前有对话且对话不为空，阻止切换
        // 直接检查DOM中的user消息数量，更可靠
        if (currentConversationId) {
            const userMessages = ui.chatMessages.querySelectorAll('.message.user');
            if (userMessages.length > 0) {
                // 恢复之前的选择
                e.target.value = previousModel;

                // 提示用户
                alert('当前对话已有历史消息，无法切换模型。\n\n如需使用其他模型，请点击左上角"New Chat"创建新对话。');

                console.log('[App] 阻止切换模型: 对话已有历史消息');
                return;
            }
        }

        // 更新全局变量
        currentModel = newModel;

        try {
            localStorage.setItem('cf-model', currentModel);
        } catch (_) {
            // Ignore errors
        }

        console.log('[App] 用户切换模型:', currentModel);

        // 如果当前有对话（但是空对话），更新后端对话的模型
        if (currentConversationId) {
            try {
                const response = await fetch(`/conversations/${currentConversationId}/model`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        model: newModel
                    })
                });

                if (response.ok) {
                    console.log('[App] 空对话模型已更新:', newModel);
                } else {
                    console.warn('[App] 更新对话模型失败:', await response.text());
                }
            } catch (err) {
                console.error('[App] 更新对话模型请求失败:', err);
            }
        }
    });

    // 新建对话按钮
    document.getElementById('new-conversation-btn').addEventListener('click', async () => {
        await createNewConversation();
    });

    // Chat 输入区附件按钮
    const attachBtn = document.getElementById('attach-btn');
    const attachInput = document.getElementById('attach-input');
    if (attachBtn && attachInput) {
        attachBtn.addEventListener('click', () => attachInput.click());
        attachInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (files && files.length > 0) {
                await uploadFiles(files);
                attachInput.value = '';
            }
        });
    }

    // 拖拽上传功能
    const chatInputBox = document.querySelector('.chat-input-box');
    const chatMessages = document.getElementById('chat-messages');

    // 拖拽区域可以是输入框或消息区域
    const dropZones = [chatInputBox, chatMessages].filter(Boolean);

    dropZones.forEach(dropZone => {
        // 阻止默认拖拽行为
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // 拖拽进入时添加高亮效果
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('drag-over');
            });
        });

        // 拖拽离开时移除高亮效果
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('drag-over');
            });
        });

        // 文件放下时处理上传
        dropZone.addEventListener('drop', async (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files && files.length > 0) {
                console.log('[App] 拖拽上传文件:', files.length, '个文件');
                await uploadFiles(files);
            }
        });
    });
}

/**
 * 左侧历史对话浮层切换
 */
function initSidebarToggles() {
    const overlay = document.getElementById('history-overlay');
    const openBtn = document.getElementById('history-toggle');
    const closeBtn = document.getElementById('history-close');
    if (!overlay || !openBtn || !closeBtn) return;

    openBtn.addEventListener('click', () => overlay.classList.add('active'));
    closeBtn.addEventListener('click', () => overlay.classList.remove('active'));
}

/**
 * 文件列表折叠/展开功能
 */
function initFileListCollapse() {
    const fileTabsContainer = document.getElementById('file-tabs-container');
    const collapseBtn = document.getElementById('file-list-collapse-btn');
    const fileContentsContainer = document.getElementById('file-contents-container');

    if (!fileTabsContainer || !collapseBtn || !fileContentsContainer) return;

    // 动态创建展开按钮（确保一定存在）
    let expandBtn = document.getElementById('file-list-expand-btn');
    if (!expandBtn) {
        expandBtn = document.createElement('button');
        expandBtn.id = 'file-list-expand-btn';
        expandBtn.className = 'file-list-expand-btn';
        expandBtn.title = '展开文件列表';
        expandBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
        `;
        fileContentsContainer.insertBefore(expandBtn, fileContentsContainer.firstChild);
    }

    // 折叠按钮：添加collapsed类
    collapseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileTabsContainer.classList.add('collapsed');
        console.log('[文件列表] 已折叠，展开按钮应该显示在预览区域左上角');
        console.log('[调试] collapsed类已添加:', fileTabsContainer.classList.contains('collapsed'));
        console.log('[调试] 展开按钮元素:', expandBtn);
        console.log('[调试] 展开按钮display样式:', window.getComputedStyle(expandBtn).display);
        try {
            localStorage.setItem('fileListCollapsed', 'true');
        } catch (_) {}
    });

    // 展开按钮：移除collapsed类
    expandBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileTabsContainer.classList.remove('collapsed');
        console.log('[文件列表] 已展开');
        try {
            localStorage.setItem('fileListCollapsed', 'false');
        } catch (_) {}
    });

    // 恢复折叠状态
    const restoreCollapsedState = () => {
        try {
            if (fileTabsContainer.classList.contains('has-files')) {
                const collapsed = localStorage.getItem('fileListCollapsed') === 'true';
                if (collapsed) {
                    fileTabsContainer.classList.add('collapsed');
                }
            }
        } catch (_) {}
    };

    restoreCollapsedState();

    const observer = new MutationObserver(() => {
        if (fileTabsContainer.classList.contains('has-files')) {
            restoreCollapsedState();
            observer.disconnect();
        }
    });
    observer.observe(fileTabsContainer, { attributes: true, attributeFilter: ['class'] });
}

/**
 * 配置SSE回调
 */
function setupSSECallbacks() {
    // 思考过程更新（映射后端iter为前端显示iter）
    sseClient.onIterStart = (iter) => {
        try {
            console.log('[SSE] onIterStart received iter:', iter);
            const frontendIter = ui._mapSSEIter(iter);
            console.log('[SSE] Mapped to frontendIter:', frontendIter);

            // 每个新的iter开始时显示loading indicator
            ui.showLoadingIndicator();

            ui.ensureIterContainer(frontendIter);
        } catch (e) {
            console.error('[SSE] onIterStart error:', e);
        }
    };
    sseClient.onIterDone = (iter, status) => {
        try {
            const frontendIter = ui._mapSSEIter(iter);
            ui.finishIter(frontendIter, status);
        } catch (e) {
            console.error('[SSE] onIterDone error:', e);
        }
    };
    sseClient.onThinking = (content, iter) => {
        try {
            ui.hideLoadingIndicator();
            const frontendIter = ui._mapSSEIter(iter);
            ui.appendThinking(content, frontendIter);
        } catch (e) {
            console.error('[SSE] onThinking error:', e);
        }
    };

    // 工具调用时的accompanying text（打字机效果）
    sseClient.onNote = (delta, iter) => {
        try {
            ui.hideLoadingIndicator();
            const frontendIter = ui._mapSSEIter(iter);
            ui.appendNote(delta, frontendIter);
        } catch (e) {
            console.error('[SSE] onNote error:', e);
        }
    };

    // 进度更新
    sseClient.onExec = (evt) => {
        console.log('[App] onExec回调被调用, evt:', evt);
        try {
            ui.hideLoadingIndicator();
            const frontendIter = ui._mapSSEIter(evt.iter);
            console.log('[App] 映射后frontendIter:', frontendIter);
            ui.appendExec(frontendIter, evt);
            console.log('[App] appendExec完成');
        } catch (e) {
            console.error('[SSE] onExec error:', e);
            console.error('[SSE] onExec error stack:', e.stack);
        }
    };
    console.log('[App] onExec已设置, 类型:', typeof sseClient.onExec);
    // 兼容旧progress：按轮追加信息行（不会重复显示）
    sseClient.onProgress = (message, status, iter) => {
        try {
            ui.hideLoadingIndicator();
            const frontendIter = ui._mapSSEIter(iter);
            ui.showProgress(message, status, frontendIter);
        } catch (e) {
            console.error('[SSE] onProgress error:', e);
        }
    };

    // 最终结果
    sseClient.onFinal = (result) => {
        ui.hideLoadingIndicator();
        ui.showResult(result);  // 不需要等待Promise，resultBox已添加到DOM

        // 结果完成后兜底刷新一次会话文件，确保像 mp4/wav 等在未收到 files_generated 时也能展示
        (async () => {
            try {
                if (!currentConversationId) return;
                const listResp = await fetch(`/outputs/list/${encodeURIComponent(currentConversationId)}`);
                if (!listResp.ok) return;
                const data = await listResp.json();
                if (!data || !Array.isArray(data.files)) return;
                const shown = new Set((ui.files || []).map(f => f.filename));
                const previewables = data.files.filter(fn => /\.(png|jpg|jpeg|xlsx|csv|html|pdf|json|mp3|wav|m4a|aac|ogg|flac|mp4|webm|mov|txt|md|log)$/i.test(fn));
                const missing = previewables.filter(fn => !shown.has(fn));
                if (missing.length) {
                    try {
                        if (currentConversationId) {
                            ui.setOutputsBase(currentConversationId);
                        }
                    } catch (_) {
                        // Ignore errors
                    }
                    ui.loadMultipleFiles(missing);
                }
            } catch (e) {
                console.warn('[App] onFinal 刷新文件失败', e);
            }
        })();
    };

    // 错误处理
    sseClient.onError = (error) => {
        ui.hideLoadingIndicator();
        ui.showError(error);
        ui.setInputEnabled(true);
        isSending = false;
        toggleStop(false);
    };

    // 完成
    sseClient.onDone = async () => {
        ui.hideLoadingIndicator();
        ui.setInputEnabled(true);
        isSending = false;
        toggleStop(false);

        // 为刚生成的assistant消息添加反馈按钮
        try {
            if (currentConversationId) {
                // 直接查找DOM中最后一个result-box（不依赖Promise时序）
                const resultBoxes = document.querySelectorAll('.result-box');
                const resultBox = resultBoxes[resultBoxes.length - 1];

                if (resultBox) {
                    // 获取对话信息，找到最后一条assistant消息的id
                    const conv = await fetch(`/conversations/${currentConversationId}`).then(r => r.json());
                    if (conv && conv.messages && conv.messages.length > 0) {
                        // 找到最后一条assistant消息
                        for (let i = conv.messages.length - 1; i >= 0; i--) {
                            const msg = conv.messages[i];
                            if (msg.role === 'assistant' && msg.id) {
                                // 添加反馈按钮
                                ui.attachFeedbackButtons(resultBox, msg.id, msg.feedback);
                                break;
                            }
                        }
                    }
                } else {
                    console.warn('[App] 未找到result-box元素');
                }
            }
        } catch (e) {
            console.error('[App] 添加反馈按钮失败:', e);
        }
    };

    // Context统计更新
    sseClient.onContextStats = (stats) => {
        updateContextIndicator(stats);
    };

    // Context压缩开始
    sseClient.onCompressionStart = (message, stats) => {
        // 将💾 emoji替换为SVG图标
        const svgIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-right:4px;"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>';
        const displayMessage = message.replace(/💾\s*/, svgIcon);
        ui.showProgress(displayMessage, 'start');
        ui.setInputEnabled(false);
    };

    // Context压缩完成
    sseClient.onCompressionDone = (message, oldStats, newStats) => {
        // 将✓替换为SVG对勾图标
        const svgIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-right:4px;"><polyline points="20 6 9 17 4 12"/></svg>';
        const displayMessage = message.replace(/✓\s*/, svgIcon);
        ui.showProgress(displayMessage, 'done');
        updateContextIndicator(newStats);
    };

    // 文件生成通知
    sseClient.onFilesGenerated = (files, iter) => {
        console.log('[App] 收到生成文件列表:', files);
        // 兜底：确保文件预览以当前会话为作用域
        try {
            if (currentConversationId) {
                ui.setOutputsBase(currentConversationId);
            }
        } catch (_) {
            // Ignore errors
        }
        const frontendIter = ui._mapSSEIter(iter);
        try {
            ui.appendFilesGenerated(frontendIter, files);
        } catch (_) {
            // Ignore errors
        }
        // 延迟加载文件，给文件系统时间flush（避免覆盖写后瞬时404）
        setTimeout(() => {
            ui.loadMultipleFiles(files);
            // 覆盖写时强制刷新已存在的预览（带cache bust）
            try {
                ui.refreshFiles(files);
            } catch (e) {
                console.warn('refreshFiles failed', e);
            }
        }, 150);
    };

    // 计划进度更新
    sseClient.onPlanUpdate = (plan, summary) => {
        ui.renderPlan(plan, summary);
    };
}

/**
 * 上传文件到当前会话
 */
async function uploadFiles(fileList) {
    if (!currentConversationId) {
        alert('No conversation. Cannot upload.');
        return;
    }
    // 确保文件预览基路径已设置为当前会话
    try {
        ui.setOutputsBase(currentConversationId);
    } catch (_) {
        // Ignore errors
    }
    const fd = new FormData();
    Array.from(fileList).forEach(f => fd.append('files', f));
    // 粘贴/选择上传：默认不加入Workspace，由用户在预览中手动保存
    fd.append('add_to_workspace', 'false');

    try {
        const resp = await fetch(`/upload/${encodeURIComponent(currentConversationId)}`, {
            method: 'POST',
            body: fd
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        const saved = Array.isArray(data.files) ? data.files : [];
        if (saved.length) {
            // 仅添加输入侧缩略图与右侧预览，不自动加入Workspace
            saved.forEach(name => ui.addAttachmentChip(name));
            // 优先统一走列表加载逻辑，确保左侧文件栏状态一致
            try {
                ui.loadMultipleFiles(saved);
            } catch (_) {
                // Ignore errors
            }
            // 并刷新已存在的同名文件，防止覆盖写后仍显示旧内容
            try {
                ui.refreshFiles(saved);
            } catch (_) {
                // Ignore errors
            }
        }
    } catch (e) {
        console.error('[Upload] failed:', e);
        alert(`Upload failed: ${e.message || e}`);
    }
}

/**
 * 主题切换（明/暗）
 */
function initThemeToggle() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;

    const root = document.documentElement;
    const body = document.body;
    const saved = localStorage.getItem('cf-theme');
    if (saved === 'dark') {
        root.classList.add('theme-dark');
        if (body) body.classList.add('theme-dark');
        btn.textContent = '🌞';
    }

    btn.addEventListener('click', () => {
        const isDark = root.classList.toggle('theme-dark');
        if (body) {
            if (isDark) body.classList.add('theme-dark');
            else body.classList.remove('theme-dark');
        }
        btn.textContent = isDark ? '🌞' : '🌙';
        localStorage.setItem('cf-theme', isDark ? 'dark' : 'light');
    });
}

/**
 * 可拖拽布局：左(对话栏) | 中(聊天) | 右(预览)
 * 左右两条竖向splitter控制左右列宽度，聊天区自适应剩余空间
 */
function initResizableLayout() {
    const container = document.querySelector('.main-container');
    const left = document.getElementById('conversations-sidebar');
    const mid = document.getElementById('chat-panel');
    const right = document.getElementById('preview-panel');
    const splitL = document.getElementById('splitter-left');
    const splitR = document.getElementById('splitter-right');
    const preSplit = document.getElementById('splitter-preview');
    const preList = document.getElementById('file-tabs-container');
    const preContent = document.getElementById('file-contents-container');
    if (!container || !left || !mid || !right || !splitL || !splitR) return;

    // 读取持久化宽度（像素）并写入Grid CSS变量
    const savedLeft = parseInt(localStorage.getItem('layout:leftWidth') || '0', 10);
    const savedRight = parseInt(localStorage.getItem('layout:rightWidth') || '0', 10);
    if (savedLeft > 0) container.style.setProperty('--leftW', savedLeft + 'px');
    if (savedRight > 0) container.style.setProperty('--rightW', savedRight + 'px');

    const MIN_LEFT = 160;   // px
    const MIN_RIGHT = 320;  // px
    const MIN_MID = 360;    // px

    let dragging = null; // 'left' | 'right'
    let startX = 0;
    let startLeftW = 0;
    let startRightW = 0;
    let containerW = 0;
    let splitWidth = 0;

    function onMouseMove(e) {
        if (!dragging) return;
        const dx = e.clientX - startX;
        if (dragging === 'left') {
            // 用起始宽度 + 位移，方向直观：左拖左，变小；右拖右，变大
            let newLeft = startLeftW + dx;
            newLeft = Math.max(MIN_LEFT, newLeft);
            // 计算中间剩余宽度，保持右侧宽度恒定
            let newMid = containerW - newLeft - startRightW - splitWidth;
            if (newMid < MIN_MID) {
                newLeft = containerW - startRightW - splitWidth - MIN_MID;
                newLeft = Math.max(newLeft, MIN_LEFT);
            }
            container.style.setProperty('--leftW', newLeft + 'px');
            localStorage.setItem('layout:leftWidth', String(newLeft));
        } else if (dragging === 'right') {
            // 右侧：向右拖动增大 dx，使右侧变小（更直觉）
            let newRight = startRightW - dx;
            newRight = Math.max(MIN_RIGHT, newRight);
            // 读取当前左列宽（优先CSS变量）
            const cssLeft = parseInt(getComputedStyle(container).getPropertyValue('--leftW'));
            const currentLeftW = (isNaN(cssLeft) ? left.getBoundingClientRect().width : cssLeft);
            let newMid = containerW - currentLeftW - newRight - splitWidth;
            if (newMid < MIN_MID) {
                newRight = containerW - currentLeftW - splitWidth - MIN_MID;
                newRight = Math.max(newRight, MIN_RIGHT);
            }
            container.style.setProperty('--rightW', newRight + 'px');
            localStorage.setItem('layout:rightWidth', String(newRight));
        }
    }

    function onMouseUp() {
        if (dragging) {
            (dragging === 'left' ? splitL : splitR).classList.remove('active');
        }
        dragging = null;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }

    function startDrag(which, ev) {
        dragging = which;
        (which === 'left' ? splitL : splitR).classList.add('active');
        const rect = container.getBoundingClientRect();
        containerW = rect.width;
        splitWidth = (splitL.offsetWidth || 6) + (splitR.offsetWidth || 6);
        const cssLeft = parseInt(getComputedStyle(container).getPropertyValue('--leftW'));
        const cssRight = parseInt(getComputedStyle(container).getPropertyValue('--rightW'));
        startLeftW = (isNaN(cssLeft) ? left.getBoundingClientRect().width : cssLeft);
        startRightW = (isNaN(cssRight) ? right.getBoundingClientRect().width : cssRight);
        startX = ev.clientX;
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    splitL.addEventListener('mousedown', (e) => startDrag('left', e));
    splitR.addEventListener('mousedown', (e) => startDrag('right', e));

    // 双击复位
    splitL.addEventListener('dblclick', () => {
        container.style.setProperty('--leftW', '200px');
        localStorage.setItem('layout:leftWidth', '200');
    });
    splitR.addEventListener('dblclick', () => {
        container.style.setProperty('--rightW', '50%'); // 回到比例
        localStorage.setItem('layout:rightWidth', '0');
    });

    // ===== Inner splitter for preview panel =====
    if (preSplit && preList && preContent) {
        const P_MIN_LIST = 160;  // px
        const P_MIN_CONT = 360;  // px
        let pDragging = false;
        let pStartX = 0;
        let pStartListW = 0;

        // 读取保存的预览文件栏宽度
        const savedPLeft = parseInt(localStorage.getItem('layout:previewLeftW') || '0', 10);
        if (savedPLeft > 0) right.style.setProperty('--pLeftW', savedPLeft + 'px');

        function pOnMove(e) {
            if (!pDragging) return;
            const dx = e.clientX - pStartX;
            let newW = pStartListW + dx;
            newW = Math.max(P_MIN_LIST, newW);
            // 不能挤爆内容区
            const panelRect = right.getBoundingClientRect();
            const contentMin = P_MIN_CONT;
            if (newW > panelRect.width - contentMin - (preSplit.offsetWidth || 6)) {
                newW = panelRect.width - contentMin - (preSplit.offsetWidth || 6);
            }
            right.style.setProperty('--pLeftW', newW + 'px');
        }

        function pOnUp() {
            if (!pDragging) return;
            pDragging = false;
            document.removeEventListener('mousemove', pOnMove);
            document.removeEventListener('mouseup', pOnUp);
            const cssList = parseInt(getComputedStyle(right).getPropertyValue('--pLeftW'));
            if (!isNaN(cssList)) localStorage.setItem('layout:previewLeftW', String(cssList));
        }

        preSplit.addEventListener('mousedown', (e) => {
            pDragging = true;
            pStartX = e.clientX;
            const cssList = parseInt(getComputedStyle(right).getPropertyValue('--pLeftW'));
            pStartListW = (isNaN(cssList) ? preList.getBoundingClientRect().width : cssList);
            document.addEventListener('mousemove', pOnMove);
            document.addEventListener('mouseup', pOnUp);
        });
    }
}

/**
 * 更新Context指示器
 */
function updateContextIndicator(stats) {
    const contextText = document.getElementById('context-text');

    if (!contextText) return;

    const percent = stats.usage_percent || 0;
    const remaining = (100 - percent).toFixed(1);

    // 更新文本为剩余百分比
    contextText.textContent = `Context left until auto-compact: ${remaining}%`;

    console.log(`[App] Context使用率: ${percent}%`);
}

/**
 * 发送消息
 */
function sendMessage() {
    let message = ui.chatInput.value.trim();

    // 在用户消息末尾追加本次附件提示
    try {
        const atts = (ui.pendingAttachments || []).slice();
        if (atts.length > 0) {
            const line = `本次输入包含附件：${atts.join(', ')}`;
            message = message ? `${message}\n\n${line}` : line;
        }
    } catch (_) {
        // Ignore errors
    }

    if (!message) {
        return;
    }

    // 前端强保护：避免重复触发
    if (isSending) {
        console.warn('[App] 正在发送中，忽略重复触发');
        return;
    }

    // 防止重复发送（例如快速多次点击/按键）
    if (sseClient.isConnected && sseClient.isConnected()) {
        console.warn('[App] 已有请求进行中，忽略重复发送');
        return;
    }

    if (!currentConversationId) {
        console.error('[App] 没有当前对话ID');
        return;
    }

    // 确保输出基础路径已设置为当前会话（防止实时文件预览失败）
    ui.setOutputsBase(currentConversationId);

    console.log('[App] 发送消息:', message);

    // 标记发送中，尽早避免重复触发
    isSending = true;
    toggleStop(true);

    // 显示用户消息
    ui.addUserMessage(message);

    // 隐藏欢迎消息（因为现在有消息了）
    updateWelcomeMessage();

    // 显示加载指示器
    ui.showLoadingIndicator();

    // 清空输入与附件条
    ui.clearInput();
    ui.clearAllAttachments();

    // 禁用输入
    ui.setInputEnabled(false);

    // 发送SSE请求（幂等ID）
    const clientMsgId = genClientId();
    sseClient.send(message, currentModel, currentConversationId, clientMsgId);
}

/**
 * 停止当前流式执行
 */
function stopStreaming() {
    if (sseClient && sseClient.isConnected && sseClient.isConnected()) {
        console.log('[App] 手动停止流式连接');
        try {
            sseClient.close();
        } catch {
            // Ignore errors
        }
    }
    ui.setInputEnabled(true);
    isSending = false;
    toggleStop(false);
    // 给出提示
    ui.showProgress('Stopped current run', 'failed');
}

/**
 * 切换发送/停止按钮
 */
function toggleStop(inProgress) {
    const sendBtn = ui.sendBtn;
    const stopBtn = stopBtnEl || document.getElementById('stop-btn');
    if (!sendBtn || !stopBtn) return;
    if (inProgress) {
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'inline-flex';
    } else {
        stopBtn.style.display = 'none';
        sendBtn.style.display = 'inline-flex';
    }
}

/**
 * 全局错误处理
 */
window.addEventListener('error', (e) => {
    console.error('[App] 全局错误:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('[App] 未处理的Promise拒绝:', e.reason);
});

// 生成简易UUID（客户端幂等ID）
function genClientId() {
    const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1);
    return `${s4()}${s4()}-${s4()}-${s4()}-${s4()}-${s4()}${s4()}${s4()}`;
}

// ==================== 用户反馈功能 ====================

/**
 * 反馈模态框管理
 */
const feedbackModal = {
    overlay: null,
    typeSelect: null,
    contentTextarea: null,
    contactInput: null,
    submitBtn: null,
    cancelBtn: null,
    closeBtn: null,
    successMsg: null,
    errorMsg: null,

    init() {
        // 获取DOM元素
        this.overlay = document.getElementById('feedback-overlay');
        this.typeSelect = document.getElementById('feedback-type');
        this.contentTextarea = document.getElementById('feedback-content');
        this.contactInput = document.getElementById('feedback-contact');
        this.submitBtn = document.getElementById('feedback-submit-btn');
        this.cancelBtn = document.getElementById('feedback-cancel-btn');
        this.closeBtn = document.getElementById('feedback-close');
        this.successMsg = document.getElementById('feedback-success');
        this.errorMsg = document.getElementById('feedback-error');

        if (!this.overlay) {
            console.warn('[Feedback] 反馈模态框未找到');
            return;
        }

        // 绑定事件
        const feedbackBtn = document.getElementById('feedback-btn');
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', () => this.open());
        }

        // 关闭按钮
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }

        // 取消按钮
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => this.close());
        }

        // 提交按钮
        if (this.submitBtn) {
            this.submitBtn.addEventListener('click', () => this.submit());
        }

        // 点击遮罩关闭
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });

        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.style.display !== 'none') {
                this.close();
            }
        });

        console.log('[Feedback] 反馈功能已初始化');
    },

    open() {
        if (!this.overlay) return;

        // 重置表单
        this.reset();

        // 显示模态框
        this.overlay.style.display = 'flex';

        // 聚焦到类型选择
        if (this.typeSelect) {
            setTimeout(() => this.typeSelect.focus(), 100);
        }
    },

    close() {
        if (!this.overlay) return;
        this.overlay.style.display = 'none';
        this.reset();
    },

    reset() {
        // 重置表单
        if (this.typeSelect) this.typeSelect.value = '';
        if (this.contentTextarea) this.contentTextarea.value = '';
        if (this.contactInput) this.contactInput.value = '';

        // 隐藏消息
        if (this.successMsg) this.successMsg.style.display = 'none';
        if (this.errorMsg) this.errorMsg.style.display = 'none';

        // 启用按钮
        if (this.submitBtn) this.submitBtn.disabled = false;
    },

    showError(message) {
        if (!this.errorMsg) return;
        this.errorMsg.textContent = message;
        this.errorMsg.style.display = 'block';
        if (this.successMsg) this.successMsg.style.display = 'none';
    },

    showSuccess() {
        if (!this.successMsg) return;
        this.successMsg.style.display = 'block';
        if (this.errorMsg) this.errorMsg.style.display = 'none';
    },

    async submit() {
        // 验证必填项
        const type = this.typeSelect?.value;
        const content = this.contentTextarea?.value?.trim();

        if (!type) {
            this.showError('请选择反馈类型');
            return;
        }

        if (!content) {
            this.showError('请填写详细描述');
            return;
        }

        if (content.length < 10) {
            this.showError('描述内容至少需要10个字符');
            return;
        }

        // 禁用提交按钮
        if (this.submitBtn) this.submitBtn.disabled = true;

        // 准备反馈数据
        const feedbackData = {
            type: type,
            content: content,
            contact: this.contactInput?.value?.trim() || '',
            timestamp: new Date().toISOString(),
            conversation_id: currentConversationId || '',
            user_agent: navigator.userAgent
        };

        try {
            // 发送反馈到后端
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(feedbackData)
            });

            if (response.ok) {
                // 提交成功
                this.showSuccess();
                console.log('[Feedback] 反馈提交成功');

                // 2秒后自动关闭
                setTimeout(() => this.close(), 2000);
            } else {
                // 后端返回错误
                const error = await response.json().catch(() => ({}));
                this.showError(error.message || '提交失败，请稍后重试');
                if (this.submitBtn) this.submitBtn.disabled = false;
            }
        } catch (error) {
            console.error('[Feedback] 提交失败:', error);
            this.showError('网络错误，请稍后重试');
            if (this.submitBtn) this.submitBtn.disabled = false;
        }
    }
};

// 页面加载后初始化反馈功能
document.addEventListener('DOMContentLoaded', () => {
    feedbackModal.init();

    // 绑定帮助导览按钮（手动触发）
    const helpTourBtn = document.getElementById('help-tour-btn');
    if (helpTourBtn) {
        helpTourBtn.addEventListener('click', () => {
            if (productTour) {
                productTour.start();
            } else {
                console.warn('[Tour] 产品导览未初始化');
            }
        });
    }
});

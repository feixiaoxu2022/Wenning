/**
 * UI渲染模块
 * 负责所有DOM操作和视觉更新
 */

class UI {
    constructor() {
        this.chatMessages = document.getElementById('chat-messages');
        this.previewContent = document.getElementById('preview-content');
        this.chatInput = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('send-btn');
        this.attachmentsStrip = document.getElementById('attachments-strip');
        this.pendingAttachments = [];
        // 输出文件基础URL，默认根目录；app在切换对话时设置为 /outputs/{conversationId}
        this.outputsBaseUrl = '/outputs';

        // File tabs元素
        this.fileTabsContainer = document.getElementById('file-tabs-container');
        this.fileTabs = document.getElementById('file-tabs');
        this.fileContentsContainer = document.getElementById('file-contents-container');

        this.currentThinkingBox = null;
        this.currentProgressBox = null;
        this.currentToolCallTextBox = null;
        this.currentResultBox = null;
        this.chatHistory = [];

        // 文件管理
        this.files = []; // {filename, key, type, element}
        this.fileKeys = new Set();
        this.currentFileIndex = 0;

        // Plan 视图
        this.planBox = null;

        // Workspace 引用
        this.workspaceListEl = document.getElementById('workspace-list');
    }

    /** 强制刷新已存在文件的预览（用于覆盖写之后） */
    refreshFiles(filenames) {
        if (!Array.isArray(filenames) || !filenames.length) return;
        const map = new Map();
        (this.files || []).forEach((f, idx) => map.set((f.key || f.filename), { f, idx }));
        filenames.forEach((name) => {
            const key = this.normalizeFilename ? this.normalizeFilename(name) : (name || '').trim();
            const hit = map.get(key);
            if (!hit) return;
            const obj = hit.f;
            const el = obj.element;
            if (!el) return;
            const lower = (obj.filename || '').toLowerCase();
            try {
                if (lower.endsWith('.xlsx')) this.loadExcelIntoContainer(obj.filename, el);
                else if (/(\.png|\.jpg|\.jpeg)$/.test(lower)) this.loadImageIntoContainer(obj.filename, el);
                else if (/(\.mp3|\.wav|\.m4a|\.aac|\.ogg|\.flac)$/.test(lower)) this.loadAudioIntoContainer(obj.filename, el);
                else if (/(\.mp4|\.webm|\.mov)$/.test(lower)) this.loadVideoIntoContainer(obj.filename, el);
                else if (lower.endsWith('.html')) this.loadHtmlIntoContainer(obj.filename, el);
            } catch (e) {
                console.warn('[UI] refresh file failed:', obj.filename, e);
            }
        });
    }
    // 附件缩略图：添加
    addAttachmentChip(filename) {
        if (!this.attachmentsStrip || !filename) return;
        // 去重
        if (this.pendingAttachments.includes(filename)) return;
        this.pendingAttachments.push(filename);

        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        chip.dataset.filename = filename;

        const enc = encodeURIComponent(filename);
        // 强制使用会话ID路径（无会话ID时报错，避免静默失败）
        if (!this.currentConvId) {
            console.error('[UI] addAttachmentChip: 缺少currentConvId');
            return;
        }
        const src = `/outputs/${encodeURIComponent(this.currentConvId)}/${enc}`;
        const img = document.createElement('img');
        img.src = src;
        chip.appendChild(img);

        const rm = document.createElement('button');
        rm.className = 'att-remove';
        rm.type = 'button';
        rm.title = '删除附件';
        rm.textContent = '×';
        rm.addEventListener('click', async () => {
            await this.removeAttachmentAndDelete(filename);
        });
        chip.appendChild(rm);

        const name = document.createElement('div');
        name.className = 'att-name';
        name.textContent = filename;
        chip.appendChild(name);

        this.attachmentsStrip.appendChild(chip);
        this.updateAttachmentsPresence();
    }

    // 附件缩略图：移除
    removeAttachmentChip(filename) {
        if (!this.attachmentsStrip || !filename) return;
        this.pendingAttachments = this.pendingAttachments.filter(n => n !== filename);
        const el = this.attachmentsStrip.querySelector(`.attachment-chip[data-filename="${CSS.escape(filename)}"]`);
        if (el) el.remove();
        this.updateAttachmentsPresence();
    }

    async removeAttachmentAndDelete(filename) {
        // 先尝试删除服务器文件
        try {
            const convId = this.currentConvId;
            if (convId) {
                const resp = await fetch(`/upload/${encodeURIComponent(convId)}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
                if (!resp.ok) {
                    const data = await resp.json().catch(() => ({}));
                    throw new Error(data.error || `HTTP ${resp.status}`);
                }
            }
        } catch (e) {
            console.warn('[Attachment] 服务端删除失败:', e);
        }
        // 本地UI移除
        this.removeAttachmentChip(filename);
        // 从Workspace侧栏移除该项
        try {
            if (this.workspaceListEl) {
                const items = Array.from(this.workspaceListEl.querySelectorAll('.workspace-item'));
                for (const it of items) {
                    const nameEl = it.querySelector('.workspace-item-name');
                    if (nameEl && nameEl.textContent === filename) {
                        it.remove();
                    }
                }
            }
        } catch {}
    }

    // 根据是否存在附件调整输入框填充
    updateAttachmentsPresence() {
        if (!this.chatInput) return;
        if (this.pendingAttachments.length > 0) this.chatInput.classList.add('attachments-present');
        else this.chatInput.classList.remove('attachments-present');
    }

    // 清空所有附件缩略图
    clearAllAttachments() {
        this.pendingAttachments = [];
        if (this.attachmentsStrip) {
            this.attachmentsStrip.innerHTML = '';
        }
        this.updateAttachmentsPresence();
    }

    normalizeFilename(name) {
        if (!name) return '';
        try {
            const dec = decodeURIComponent(name);
            return dec.trim();
        } catch (_) {
            return String(name).trim();
        }
    }

    // 渲染Workspace视图：右侧预览面板显示已保存文件列表
    async renderWorkspaceView(convId) {
        try {
            const resp = await fetch(`/workspace/${encodeURIComponent(convId)}/files`);
            const data = await resp.json();
            const files = Array.isArray(data.files) ? data.files : [];

            // 右侧预览区域渲染列表
            const listHtml = [`
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items:center;">
                        <h4>Workspace</h4>
                        <div style="font-size:12px; color: var(--muted)">会话: ${convId}</div>
                    </div>
                </div>
            `];
            if (!files.length) {
                listHtml.push('<div style="padding:16px; color: var(--muted);">暂无保存的文件</div>');
            } else {
                listHtml.push('<div style="padding:8px 12px;">');
                listHtml.push('<div style="display:flex; flex-direction:column; gap:8px;">');
                for (const f of files) {
                    const enc = encodeURIComponent(f);
                    const openBtn = `<button class="link-button" data-open-file="${enc}" style="margin-right:8px;">Open</button>`;
                    const dlBtn = `<a class="file-download" href="${this.outputsBaseUrl}/${enc}" download="${f}">Download</a>`;
                    listHtml.push(`
                        <div style="display:flex; justify-content:space-between; align-items:center; border:1px solid var(--border); border-radius:8px; padding:8px 10px; background: var(--panel);">
                            <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:60%;">${f}</div>
                            <div>${openBtn}${dlBtn}</div>
                        </div>
                    `);
                }
                listHtml.push('</div></div>');
            }
            this.fileTabsContainer.classList.add('has-files');
            this.fileContentsContainer.innerHTML = `<div class="file-content-item active">${listHtml.join('')}</div>`;
            // 绑定 Open 按钮
            this.fileContentsContainer.querySelectorAll('[data-open-file]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const name = decodeURIComponent(btn.getAttribute('data-open-file'));
                    this.openFileByName(name);
                });
            });
        } catch (e) {
            this.fileContentsContainer.innerHTML = `
                <div class="error-box"><span class="error-label">错误:</span><div>加载Workspace失败: ${e.message}</div></div>`;
        }
    }

    // 根据文件名选择类型并打开
    openFileByName(filename) {
        const lower = (filename || '').toLowerCase();
        if (lower.endsWith('.xlsx') || lower.endsWith('.csv')) return this.addFileTab(filename, 'excel');
        if (/(\.png|\.jpg|\.jpeg)$/.test(lower)) return this.addFileTab(filename, 'image');
        if (/(\.mp3|\.wav|\.m4a|\.aac|\.ogg|\.flac)$/.test(lower)) return this.addFileTab(filename, 'audio');
        if (/(\.mp4|\.webm|\.mov)$/.test(lower)) return this.addFileTab(filename, 'video');
        if (lower.endsWith('.html')) return this.addFileTab(filename, 'html');
        if (lower.endsWith('.pdf')) return this.addFileTab(filename, 'pdf');
        if (lower.endsWith('.jsonl')) return this.addFileTab(filename, 'jsonl');
        if (lower.endsWith('.json')) return this.addFileTab(filename, 'json');
        if (lower.endsWith('.md')) return this.addFileTab(filename, 'markdown');
        if (/(\.txt|\.md|\.log)$/i.test(lower)) return this.addFileTab(filename, 'text');
        // 其它类型暂不内联预览
        alert('暂不支持该类型的内联预览');
    }

    setOutputsBase(conversationId) {
        if (conversationId) {
            this.outputsBaseUrl = `/outputs/${encodeURIComponent(conversationId)}`;
            this.currentConvId = conversationId;
        } else {
            this.outputsBaseUrl = '/outputs';
            this.currentConvId = null;
        }
    }

    /**
     * 添加用户消息
     */
    addUserMessage(message) {
        // 清理之前的thinking、progress和tool_call_text盒子的DOM元素
        if (this.currentThinkingBox && this.currentThinkingBox.parentElement) {
            const thinkingContainer = this.currentThinkingBox.closest('.thinking-box');
            if (thinkingContainer) thinkingContainer.remove();
        }
        // 删除整个progress box（包括按钮），而不是只删除content
        if (this._progress && this._progress.box && this._progress.box.parentElement) {
            this._progress.box.remove();
        }
        if (this.currentToolCallTextBox && this.currentToolCallTextBox.parentElement) {
            const toolCallContainer = this.currentToolCallTextBox.closest('.tool-call-text-box');
            if (toolCallContainer) toolCallContainer.remove();
        }

        // 重置thinking和progress状态
        this.currentThinkingBox = null;
        this.currentProgressBox = null;
        this.currentToolCallTextBox = null;
        this._progress = null;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.textContent = message;
        this.chatMessages.appendChild(messageDiv);

        // 保存到历史
        this.chatHistory.push({role: 'user', content: message});

        // 滚动到底部
        this.scrollToBottom();
    }

    /**
     * 创建思考过程盒子
     */
    createThinkingBox() {
        if (this.currentThinkingBox) {
            return; // 已经存在
        }

        const thinkingBox = document.createElement('div');
        thinkingBox.className = 'thinking-box';

        const label = document.createElement('span');
        label.className = 'thinking-label';
        label.textContent = '💭 思考过程:';
        thinkingBox.appendChild(label);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-content';
        thinkingBox.appendChild(contentDiv);

        this.chatMessages.appendChild(thinkingBox);
        this.currentThinkingBox = contentDiv;

        this.scrollToBottom();
    }

    /**
     * 追加思考内容
     */
    appendThinking(content) {
        if (!this.currentThinkingBox) {
            this.createThinkingBox();
        }

        // 每个thinking chunk之间加换行分隔,避免连成一片
        if (this.currentThinkingBox.textContent && content) {
            this.currentThinkingBox.textContent += '\n\n';
        }
        this.currentThinkingBox.textContent += content;

        // 自动滚动（如果用户在底部附近）
        this.smartScroll();
    }

    /**
     * 追加工具调用时的accompanying text（打字机效果）
     */
    appendToolCallText(delta) {
        // 创建或复用tool_call_text box
        if (!this.currentToolCallTextBox) {
            const toolCallBox = document.createElement('div');
            toolCallBox.className = 'tool-call-text-box';

            const label = document.createElement('div');
            label.className = 'tool-call-text-label';
            label.textContent = '💭 思考中';
            toolCallBox.appendChild(label);

            const contentDiv = document.createElement('div');
            contentDiv.className = 'tool-call-text-content';
            toolCallBox.appendChild(contentDiv);

            this.chatMessages.appendChild(toolCallBox);
            this.currentToolCallTextBox = contentDiv;
        }

        this.currentToolCallTextBox.textContent += delta;

        // 自动滚动
        this.smartScroll();
    }

    /**
     * 显示进度指示器
     */
    showProgress(message, status) {
        // 创建或获取进度区域(与thinking分离)
        if (!this.currentProgressBox) {
            const progressBox = document.createElement('div');
            progressBox.className = 'progress-box';

            const header = document.createElement('div');
            header.className = 'progress-header';

            const left = document.createElement('div');
            left.className = 'progress-left';
            const dot = document.createElement('span');
            dot.className = 'progress-dot spinner';
            const title = document.createElement('span');
            title.className = 'progress-title';
            title.textContent = '执行中…';
            left.appendChild(dot);
            left.appendChild(title);

            // 先创建 progressContent，再创建引用它的事件监听器
            const progressContent = document.createElement('div');
            progressContent.className = 'progress-content';
            // 初始状态：显示
            progressContent.style.display = 'block';

            const toggle = document.createElement('button');
            toggle.type = 'button'; // 明确指定type，防止意外提交
            toggle.className = 'progress-toggle';
            toggle.textContent = '隐藏详情'; // 初始文案：与显示状态对应
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                // 检查当前实际显示状态
                const currentDisplay = window.getComputedStyle(progressContent).display;
                const isCurrentlyHidden = currentDisplay === 'none';

                // 切换显示状态和按钮文案（同步更新）
                if (isCurrentlyHidden) {
                    // 当前隐藏 → 显示
                    progressContent.style.display = 'block';
                    toggle.textContent = '隐藏详情';
                } else {
                    // 当前显示 → 隐藏
                    progressContent.style.display = 'none';
                    toggle.textContent = '显示详情';
                }
            });

            header.appendChild(left);
            header.appendChild(toggle);
            progressBox.appendChild(header);
            progressBox.appendChild(progressContent);

            this.chatMessages.appendChild(progressBox);
            this.currentProgressBox = progressContent;
            // 记录引用用于状态更新
            this._progress = { box: progressBox, header, left, dot, title, toggle, content: progressContent };
        }

        // 状态更新（可选）
        if (status) {
            this.updateProgressStatus(status);
        }

        // 追加进度信息
        if (message) {
            const line = document.createElement('div');
            line.className = 'progress-line';
            line.textContent = message;
            this.currentProgressBox.appendChild(line);
        }

        this.smartScroll();
    }

    updateProgressStatus(status) {
        if (!this._progress) return;
        const s = String(status || '').toLowerCase();
        const { dot, title, content, toggle } = this._progress;

        // 默认running
        let state = 'running';
        if (s.includes('success') || s.includes('done') || s.includes('complete')) state = 'success';
        if (s.includes('fail') || s.includes('error')) state = 'failed';

        dot.classList.remove('spinner', 'success', 'failed');
        if (state === 'running') {
            dot.classList.add('spinner');
            title.textContent = '执行中…';
        } else if (state === 'success') {
            dot.classList.add('success');
            title.textContent = '已完成';
            // 自动收起 - 同步更新显示状态和按钮文案
            setTimeout(() => {
                // 再次检查this._progress是否仍然存在（可能已被清理）
                if (this._progress && content && toggle) {
                    // 同步操作：先隐藏内容，再更新按钮文案
                    content.style.display = 'none';
                    toggle.textContent = '显示详情';
                }
            }, 1500);
        } else if (state === 'failed') {
            dot.classList.add('failed');
            title.textContent = '失败';
        }
    }

    /**
     * 显示最终结果(打字机效果)
     */
    async showResult(result, useTypewriter = true) {
        // 仅在实时渲染时清理thinking/progress/tool_call_text（历史消息不需要）
        if (useTypewriter) {
            // 清理thinking box和tool_call_text box的DOM元素
            if (this.currentThinkingBox && this.currentThinkingBox.parentElement) {
                // 找到thinking-box容器并移除
                const thinkingContainer = this.currentThinkingBox.closest('.thinking-box');
                if (thinkingContainer) thinkingContainer.remove();
            }
            if (this.currentToolCallTextBox && this.currentToolCallTextBox.parentElement) {
                // 找到tool-call-text-box容器并移除
                const toolCallContainer = this.currentToolCallTextBox.closest('.tool-call-text-box');
                if (toolCallContainer) toolCallContainer.remove();
            }
            this.currentThinkingBox = null;
            this.currentToolCallTextBox = null;

            // 对话结束后不删除progress box，保留让用户可以查看执行过程
            // 自动隐藏会由updateProgressStatus的setTimeout处理（1.5秒后）
            // 不需要在这里删除DOM，按钮继续保持可用状态

            // 更新进度状态到完成/失败（在移除前显示状态）
            try {
                if (this._progress) {
                    if (result && result.status === 'failed') this.updateProgressStatus('failed');
                    else this.updateProgressStatus('success');
                }
            } catch {}
        }

        // 创建结果盒子
        const resultBox = document.createElement('div');

        if (result.status === 'failed') {
            // 错误结果(不需要打字机)
            resultBox.className = 'error-box';
            const label = document.createElement('span');
            label.className = 'error-label';
            label.textContent = '❌ 执行失败:';
            resultBox.appendChild(label);

            const errorMsg = document.createElement('div');
            errorMsg.textContent = result.error || '未知错误';
            resultBox.appendChild(errorMsg);

            this.chatMessages.appendChild(resultBox);
        } else {
            // 成功结果
            resultBox.className = 'result-box';

            const resultContent = document.createElement('div');
            resultContent.className = 'markdown-content';
            resultBox.appendChild(resultContent);

            this.chatMessages.appendChild(resultBox);
            this.scrollToBottom();

            if (useTypewriter) {
                // 打字机效果渲染
                await this.typewriterRender(resultContent, result.result || '');
            } else {
                // 直接渲染(用于历史消息)
                if (typeof marked !== 'undefined') {
                    resultContent.innerHTML = marked.parse(result.result || '');
                } else {
                    resultContent.textContent = result.result || '';
                }
            }

            // 文件加载由外部通过loadMultipleFiles显式调用
            // 不再使用checkAndLoadFiles的正则匹配逻辑
        }

        // 保存到历史
        this.chatHistory.push({
            role: 'assistant',
            content: result.result || result.error
        });

        this.scrollToBottom();
    }

    /**
     * 打字机效果渲染Markdown
     */
    async typewriterRender(element, text, speed = 10) {
        let currentText = '';
        const chars = text.split('');

        for (let i = 0; i < chars.length; i++) {
            currentText += chars[i];

            // 实时渲染Markdown
            if (typeof marked !== 'undefined') {
                element.innerHTML = marked.parse(currentText);
            } else {
                element.textContent = currentText;
            }

            // 智能滚动
            this.smartScroll();

            // 延迟(速度控制)
            if (i < chars.length - 1) {
                await new Promise(resolve => setTimeout(resolve, speed));
            }
        }
    }

    /**
     * 检测到文件路径,并加载预览
     */
    checkAndLoadFiles(resultText) {
        if (!resultText) return;

        // 匹配所有文件名(包括中文)
        const allFiles = [];

        // 匹配 xlsx 文件 - 修复正则,确保能匹配中文+数字的组合
        const xlsxPattern = /([\u4e00-\u9fa5\w\-_]+\.xlsx)/g;
        const xlsxMatches = resultText.matchAll(xlsxPattern);
        for (const match of xlsxMatches) {
            const filename = match[1];
            // 只保留文件名,不要路径
            if (!filename.includes('/')) {
                allFiles.push(filename);
            }
        }

        // 匹配图片文件 - 修复正则,确保能匹配中文+数字的组合
        const imgPattern = /([\u4e00-\u9fa5\w\-_]+\.(?:png|jpg|jpeg))/gi;
        const imgMatches = resultText.matchAll(imgPattern);
        for (const match of imgMatches) {
            const filename = match[1];
            // 只保留文件名,不要路径
            if (!filename.includes('/')) {
                allFiles.push(filename);
            }
        }

        // 去重
        const uniqueFiles = [...new Set(allFiles)];

        if (uniqueFiles.length > 0) {
            console.log('[UI] 检测到文件:', uniqueFiles);
            this.loadMultipleFiles(uniqueFiles);
        }
    }

    /**
     * 加载多个文件预览
     */
    async loadMultipleFiles(filenames) {
        console.log('[UI] loadMultipleFiles called with:', filenames);
        console.log('[UI] Current outputsBaseUrl:', this.outputsBaseUrl);
        // 本批次去重集合（与全局集合共同作用）
        const batchSeen = new Set();

        // 加载每个文件
        for (const filename of filenames) {
            console.log(`[UI] Processing file: ${filename}`);

            // 检查是否已经添加过该文件
            const key = this.normalizeFilename ? this.normalizeFilename(filename) : (filename || '').trim();
            const exists = this.fileKeys.has(key) || batchSeen.has(key) || this.files.some(f => (f.key || f.filename) === key);
            if (exists) {
                console.log(`[UI] 文件已存在,跳过: ${filename}`);
                continue;
            }

            // 标记本批次已见
            batchSeen.add(key);

            // 取消严格的HEAD存在性检查，直接尝试加载（加载逻辑自带cache-bust与错误处理）
            // 这样可避免刚上传或覆盖后的瞬时404导致文件不显示

            // 通过校验后再加载预览
            try {
                // 检测是否为在线URL（支持http/https）
                if (filename.match(/^https?:\/\//i)) {
                    console.log(`[UI] Adding Webpage tab: ${filename}`);
                    this.addFileTab(filename, 'webpage', key);
                } else if (filename.endsWith('.xlsx')) {
                    console.log(`[UI] Adding Excel tab: ${filename}`);
                    this.addFileTab(filename, 'excel', key);
                } else if (filename.match(/\.(png|jpg|jpeg)$/i)) {
                    console.log(`[UI] Adding Image tab: ${filename}`);
                    this.addFileTab(filename, 'image', key);
                } else if (filename.match(/\.(mp3|wav|m4a|aac|ogg|flac)$/i)) {
                    console.log(`[UI] Adding Audio tab: ${filename}`);
                    this.addFileTab(filename, 'audio', key);
                } else if (filename.match(/\.(mp4|webm|mov)$/i)) {
                    console.log(`[UI] Adding Video tab: ${filename}`);
                    this.addFileTab(filename, 'video', key);
                } else if (filename.toLowerCase().endsWith('.html')) {
                    console.log(`[UI] Adding HTML tab: ${filename}`);
                    this.addFileTab(filename, 'html', key);
                } else if (filename.toLowerCase().endsWith('.pdf')) {
                    console.log(`[UI] Adding PDF tab: ${filename}`);
                    this.addFileTab(filename, 'pdf', key);
                } else if (filename.toLowerCase().endsWith('.jsonl')) {
                    console.log(`[UI] Adding JSONL tab: ${filename}`);
                    this.addFileTab(filename, 'jsonl', key);
                } else if (filename.toLowerCase().endsWith('.json')) {
                    console.log(`[UI] Adding JSON tab: ${filename}`);
                    this.addFileTab(filename, 'json', key);
                } else if (filename.toLowerCase().endsWith('.md')) {
                    console.log(`[UI] Adding Markdown tab: ${filename}`);
                    this.addFileTab(filename, 'markdown', key);
                } else if (filename.match(/\.(txt|log)$/i)) {
                    console.log(`[UI] Adding Text tab: ${filename}`);
                    this.addFileTab(filename, 'text', key);
                }
            } catch (err) {
                console.error('[UI] 文件预览加载失败:', filename, err);
            }
        }
    }

    /**
     * 添加文件标签和内容
     */
    addFileTab(filename, type, key) {
        const normKey = key || (this.normalizeFilename ? this.normalizeFilename(filename) : (filename || '').trim());
        if (this.fileKeys.has(normKey)) {
            console.log(`[UI] 已存在标签: ${filename} -> 切换`);
            const idx = this.files.findIndex(f => (f.key || f.filename) === normKey);
            if (idx >= 0) this.switchToFile(idx);
            return;
        }
        const fileIndex = this.files.length;

        // 创建文件对象
        const fileObj = {
            filename: filename,
            key: normKey,
            type: type,
            element: null
        };

        // 创建标签
        const tab = document.createElement('li');
        tab.className = 'file-tab';
        tab.dataset.fileIndex = fileIndex;

        // 图标
        const icon = document.createElement('span');
        icon.className = 'file-tab-icon';
        icon.textContent = '';

        // 文件名
        const name = document.createElement('span');
        name.className = 'file-tab-name';
        name.textContent = filename;
        name.title = filename; // tooltip显示完整文件名

        tab.appendChild(icon);
        tab.appendChild(name);

        // 点击事件
        tab.addEventListener('click', () => {
            this.switchToFile(fileIndex);
        });

        this.fileTabs.appendChild(tab);

        // 创建内容容器
        const contentDiv = document.createElement('div');
        contentDiv.className = 'file-content-item';
        contentDiv.dataset.fileIndex = fileIndex;
        this.fileContentsContainer.appendChild(contentDiv);

        fileObj.element = contentDiv;
        this.files.push(fileObj);
        this.fileKeys.add(fileObj.key);

        // 显示tabs容器
        this.fileTabsContainer.classList.add('has-files');

        // 切换到双栏布局(移除center-mode)
        const mainContainer = document.querySelector('.main-container');
        if (mainContainer) {
            mainContainer.classList.remove('center-mode');
        }

        // 如果是第一个文件,自动激活
        if (this.files.length === 1) {
            this.switchToFile(0);
        } else {
            // 否则激活最新添加的文件
            this.switchToFile(fileIndex);
        }

        // 加载文件内容
        if (type === 'excel') {
            this.loadExcelIntoContainer(filename, contentDiv);
        } else if (type === 'image') {
            this.loadImageIntoContainer(filename, contentDiv);
        } else if (type === 'audio') {
            this.loadAudioIntoContainer(filename, contentDiv);
        } else if (type === 'video') {
            this.loadVideoIntoContainer(filename, contentDiv);
        } else if (type === 'html') {
            this.loadHtmlIntoContainer(filename, contentDiv);
        } else if (type === 'webpage') {
            this.loadWebpageIntoContainer(filename, contentDiv);
        } else if (type === 'text') {
            this.loadTextIntoContainer(filename, contentDiv);
        } else if (type === 'pdf') {
            this.loadPdfIntoContainer(filename, contentDiv);
        } else if (type === 'jsonl') {
            this.loadJsonlIntoContainer(filename, contentDiv);
        } else if (type === 'json') {
            this.loadJsonIntoContainer(filename, contentDiv);
        } else if (type === 'markdown') {
            this.loadMarkdownIntoContainer(filename, contentDiv);
        }

        console.log(`[UI] 添加文件标签: ${filename}`);
    }

    /**
     * 切换到指定文件
     */
    switchToFile(fileIndex) {
        this.currentFileIndex = fileIndex;

        // 更新标签激活状态
        const tabs = this.fileTabs.querySelectorAll('.file-tab');
        tabs.forEach((tab, index) => {
            if (index === fileIndex) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // 更新内容显示状态
        const contents = this.fileContentsContainer.querySelectorAll('.file-content-item');
        contents.forEach((content, index) => {
            if (index === fileIndex) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    /**
     * 清空所有文件
     */
    clearAllFiles() {
        this.files = [];
        this.currentFileIndex = 0;
        this.fileTabs.innerHTML = '';
        this.fileContentsContainer.innerHTML = '<div class="preview-content" id="preview-content"><p class="preview-placeholder">Waiting for files...</p></div>';
        this.fileTabsContainer.classList.remove('has-files');
        this.previewContent = document.getElementById('preview-content'); // 重新获取引用
        this.fileKeys.clear();
    }

    /**
     * 加载Excel预览 - 使用SheetJS
     */
    async loadExcelPreview(filename) {
        this.previewContent.innerHTML = '';
        await this.appendExcelPreview(filename);
    }

    /**
     * 加载图片预览
     */
    loadImagePreview(filename) {
        const encodedFilename = encodeURIComponent(filename);
        const src = `${this.outputsBaseUrl}/${encodedFilename}?t=${Date.now()}`;
        this.previewContent.innerHTML = `
            <div class="preview-info">
                <h4>${filename}</h4>
            </div>
            <img src="${src}" style="width: 100%; height: auto; border-radius: 8px; margin-top: 10px; object-fit: contain;" />
            <div style="margin-top: 15px;">
                <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
            </div>
        `;
    }

    /**
     * 追加图片预览(用于多图片)
     */
    appendImagePreview(filename) {
        const encodedFilename = encodeURIComponent(filename);
        const src = `${this.outputsBaseUrl}/${encodedFilename}?t=${Date.now()}`;
        const imgDiv = document.createElement('div');
        imgDiv.style.marginBottom = '20px';
        imgDiv.innerHTML = `
            <div class="preview-info">
                <h4>${filename}</h4>
            </div>
            <img src="${src}" style="width: 100%; height: auto; border-radius: 8px; margin-top: 10px; object-fit: contain;" />
            <div style="margin-top: 10px;">
                <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
            </div>
        `;
        this.previewContent.appendChild(imgDiv);
    }

    /**
     * 加载Excel到指定容器
     */
    async loadExcelIntoContainer(filename, container) {
        try {
            const encodedFilename = encodeURIComponent(filename);
            // 如果前端未加载SheetJS, 使用后端预览接口兜底
            if (typeof XLSX === 'undefined') {
                const convId = this.currentConvId;
                let previewUrl = convId
                    ? `/preview/excel/${encodeURIComponent(convId)}/${encodedFilename}`
                    : `/preview/excel/${encodedFilename}`;
                previewUrl += (previewUrl.includes('?') ? '&' : '?') + `t=${Date.now()}`;
                const preview = await fetch(previewUrl);
                if (!preview.ok) throw new Error(`HTTP ${preview.status}`);
                const data = await preview.json();

                container.innerHTML = `
                    <div class="excel-preview-container">
                        <div class="preview-info">
                            <div style="display:flex; justify-content: space-between; align-items:center;">
                                <h4>${filename}</h4>
                                <div style="display:flex; gap:12px; align-items:center;">
                                    <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                                    <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                                    <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                                </div>
                            </div>
                        </div>
                        <div class="excel-table-wrapper">${data.html || '<div style="padding:16px;">No preview</div>'}</div>
                    </div>
                `;
                const saveBtn = container.querySelector('.workspace-save');
                if (saveBtn) {
                    saveBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.workspaceSave(filename, saveBtn);
                    });
                }
                const delBtn = container.querySelector('.file-delete');
                if (delBtn) {
                    delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
                }
                return;
            }

            // 获取Excel文件（前端本地解析）
            const response = await fetch(`${this.outputsBaseUrl}/${encodedFilename}?t=${Date.now()}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const arrayBuffer = await response.arrayBuffer();
            const workbook = XLSX.read(arrayBuffer, { type: 'array' });

            // 清空容器
            container.innerHTML = '';

            // 创建预览容器
            const excelDiv = document.createElement('div');
            excelDiv.className = 'excel-preview-container';

            // 标题和下载按钮
            const headerDiv = document.createElement('div');
            headerDiv.className = 'preview-info';
            headerDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4>${filename}</h4>
                    <div style="display:flex; gap:12px; align-items:center;">
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                        <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                        <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                    </div>
                </div>
            `;
            excelDiv.appendChild(headerDiv);

            // Sheet标签页(如果有多个sheet)
            if (workbook.SheetNames.length > 1) {
                const tabsDiv = document.createElement('div');
                tabsDiv.className = 'excel-sheet-tabs';

                workbook.SheetNames.forEach((sheetName, index) => {
                    const tab = document.createElement('button');
                    tab.className = 'excel-sheet-tab' + (index === 0 ? ' active' : '');
                    tab.textContent = sheetName;
                    tab.dataset.sheetIndex = index;
                    tab.addEventListener('click', (e) => {
                        tabsDiv.querySelectorAll('.excel-sheet-tab').forEach(t => t.classList.remove('active'));
                        e.target.classList.add('active');

                        const wrappers = excelDiv.querySelectorAll('.excel-table-wrapper');
                        wrappers.forEach((w, i) => {
                            w.style.display = i === parseInt(e.target.dataset.sheetIndex) ? 'block' : 'none';
                        });
                    });
                    tabsDiv.appendChild(tab);
                });

                excelDiv.appendChild(tabsDiv);
            }

            // 渲染每个sheet
            workbook.SheetNames.forEach((sheetName, index) => {
                const worksheet = workbook.Sheets[sheetName];
                const html = XLSX.utils.sheet_to_html(worksheet, {
                    id: `sheet-${index}`,
                    editable: false,
                    header: ''
                });

                const wrapper = document.createElement('div');
                wrapper.className = 'excel-table-wrapper';
                wrapper.style.display = index === 0 ? 'block' : 'none';

                const styledHtml = html.replace(
                    /<table/g,
                    '<table class="excel-table"'
                );

                wrapper.innerHTML = styledHtml;
                excelDiv.appendChild(wrapper);
            });

            container.appendChild(excelDiv);
            const saveBtn2 = container.querySelector('.workspace-save');
            if (saveBtn2) {
                saveBtn2.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.workspaceSave(filename, saveBtn2);
                });
            }
            const delBtn2 = container.querySelector('.file-delete');
            if (delBtn2) {
                delBtn2.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
            }
        } catch (err) {
            console.error('[UI] Excel preview failed:', filename, err);
            container.innerHTML = `
                <div class="error-box">
                    <span class="error-label">Error:</span>
                    <div>Unable to preview ${filename}: ${err.message}</div>
                </div>
            `;
        }
    }

    /**
     * 加载图片到指定容器
     */
    loadImageIntoContainer(filename, container) {
        const encodedFilename = encodeURIComponent(filename);
        console.log(`[UI] loadImageIntoContainer: filename=${filename}, outputsBaseUrl=${this.outputsBaseUrl}`);
        const src = `${this.outputsBaseUrl}/${encodedFilename}?t=${Date.now()}`;
        container.innerHTML = `
            <div class="image-preview-container">
                <div class="preview-info">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div class="image-content">
                    <img src="${src}" alt="${filename}" />
                </div>
            </div>
        `;
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.workspaceSave(filename, saveBtn);
            });
        }
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) {
            delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
        }
    }

    /** 加载音频到指定容器 */
    loadAudioIntoContainer(filename, container) {
        const encoded = encodeURIComponent(filename);
        const bust = `?t=${Date.now()}`;
        const streamSrc = this.currentConvId
            ? `/stream/${encodeURIComponent(this.currentConvId)}/${encoded}${bust}`
            : `/stream/${encoded}${bust}`;
        const directSrc = `${this.outputsBaseUrl}/${encoded}${bust}`;
        container.innerHTML = `
            <div class="image-preview-container">
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items:center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div class="image-content">
                    <audio controls style="width:100%">
                        <source src="${streamSrc}" type="audio/wav" />
                        <source src="${directSrc}" type="audio/wav" />
                        您的浏览器不支持音频播放。
                    </audio>
                </div>
            </div>
        `;
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => { e.preventDefault(); this.workspaceSave(filename, saveBtn); });
        }
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) {
            delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
        }
    }

    /** 加载视频到指定容器 */
    loadVideoIntoContainer(filename, container) {
        const encoded = encodeURIComponent(filename);
        const streamSrc = this.currentConvId
            ? `/stream/${encodeURIComponent(this.currentConvId)}/${encoded}?t=${Date.now()}`
            : `/stream/${encoded}?t=${Date.now()}`;
        container.innerHTML = `
            <div class="image-preview-container">
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items:center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save">Save to Workspace</a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div class="image-content">
                    <video controls src="${streamSrc}" style="width:100%; max-height: 60vh; background:#000" preload="metadata"></video>
                </div>
            </div>
        `;
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => { e.preventDefault(); this.workspaceSave(filename, saveBtn); });
        }
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) {
            delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
        }
    }

    /**
     * 加载HTML索引页到指定容器（iframe）
     */
    loadHtmlIntoContainer(filename, container) {
        const encodedFilename = encodeURIComponent(filename);
        const src = `${this.outputsBaseUrl}/${encodedFilename}?t=${Date.now()}`;
        container.innerHTML = `
            <div class="preview-info">
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <h4>${filename}</h4>
                    <div style="display:flex; gap:12px; align-items:center;">
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                        <a href="${src}" target="_blank" rel="noopener" class="link-button">Open</a>
                        <a href="${src}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                        <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                    </div>
                </div>
            </div>
            <iframe src="${src}" class="html-preview-frame"></iframe>
        `;
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.workspaceSave(filename, saveBtn);
            });
        }
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) {
            delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
        }
    }

    /**
     * 加载在线网页到指定容器（iframe）
     */
    loadWebpageIntoContainer(url, container) {
        // 提取域名作为标题
        const displayTitle = (() => {
            try {
                const parsed = new URL(url);
                return parsed.hostname || url;
            } catch {
                return url;
            }
        })();

        // 判断是否为可信网站（主流视频、设计平台等）
        const isTrustedSite = (() => {
            try {
                const lower = url.toLowerCase();
                const trustedDomains = [
                    'youtube.com', 'youtu.be', 'youtube-nocookie.com',
                    'vimeo.com',
                    'spotify.com',
                    'codepen.io',
                    'figma.com',
                    'soundcloud.com',
                    'dailymotion.com',
                    'twitch.tv'
                ];
                return trustedDomains.some(domain => lower.includes(domain));
            } catch {
                return false;
            }
        })();

        // 对于YouTube等可信视频网站，完全移除sandbox限制
        const isVideoSite = url.toLowerCase().includes('youtube') || url.toLowerCase().includes('vimeo');

        let iframeAttrs = '';
        if (isVideoSite) {
            // 视频网站：不使用sandbox，添加所有必要的allow权限
            iframeAttrs = 'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen';
        } else if (isTrustedSite) {
            // 其他可信网站：使用宽松的sandbox
            iframeAttrs = 'sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-presentation allow-popups-to-escape-sandbox" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"';
        } else {
            // 不可信网站：严格的sandbox
            iframeAttrs = 'sandbox="allow-scripts allow-same-origin allow-forms allow-popups"';
        }

        container.innerHTML = `
            <div class="preview-info">
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <h4>🌐 ${this.escapeHtml(displayTitle)}</h4>
                    <div style="display:flex; gap:12px; align-items:center;">
                        <a href="${this.escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="link-button">
                            <span class="btn-ico">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                                    <polyline points="15 3 21 3 21 9"/>
                                    <line x1="10" y1="14" x2="21" y2="3"/>
                                </svg>
                            </span>
                            <span class="btn-text">在新窗口打开</span>
                        </a>
                    </div>
                </div>
            </div>
            <iframe src="${this.escapeHtml(url)}" class="html-preview-frame" ${iframeAttrs}></iframe>
        `;
    }

    /** 加载纯文本到指定容器（.txt/.md/.log等） */
    async loadTextIntoContainer(filename, container) {
        try {
            const encoded = encodeURIComponent(filename);
            const url = `${this.outputsBaseUrl}/${encoded}?t=${Date.now()}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const text = await resp.text();
            container.innerHTML = `
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <pre class="text-preview" style="white-space: pre-wrap; word-break: break-word; padding: 12px; background: var(--panel); border:1px solid var(--border); border-radius:8px; max-height: 60vh; overflow:auto;">${this.escapeHtml(text)}</pre>
            `;
            const saveBtn = container.querySelector('.workspace-save');
            if (saveBtn) {
                saveBtn.addEventListener('click', (e) => { e.preventDefault(); this.workspaceSave(filename, saveBtn); });
            }
            const delBtn = container.querySelector('.file-delete');
            if (delBtn) {
                delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
            }
        } catch (e) {
            console.warn('[UI] Text preview failed:', filename, e);
            container.innerHTML = `<div class="error-box"><span class="error-label">Error:</span><div>Unable to preview ${filename}: ${e.message || e}</div></div>`;
        }
    }

    escapeHtml(s) {
        return String(s)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/\"/g, '&quot;')
          .replace(/'/g, '&#39;');
    }

    /** 加载PDF到指定容器 */
    loadPdfIntoContainer(filename, container) {
        const encoded = encodeURIComponent(filename);
        const src = `${this.outputsBaseUrl}/${encoded}?t=${Date.now()}#view=FitH`;
        container.innerHTML = `
            <div class="preview-info">
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <h4>${filename}</h4>
                    <div style="display:flex; gap:12px; align-items:center;">
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                        <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                        <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                    </div>
                </div>
            </div>
            <iframe src="${src}" class="html-preview-frame" style="height:60vh;"></iframe>
        `;
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); this.workspaceSave(filename, saveBtn); });
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) delBtn.addEventListener('click', async (e)=>{ e.preventDefault(); await this.deleteFile(filename); });
    }

    /** 加载JSON到指定容器 */
    async loadJsonIntoContainer(filename, container) {
        try {
            const encoded = encodeURIComponent(filename);
            const resp = await fetch(`${this.outputsBaseUrl}/${encoded}?t=${Date.now()}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const obj = await resp.json();
            const pretty = this.escapeHtml(JSON.stringify(obj, null, 2));
            container.innerHTML = `
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <pre class="text-preview" style="white-space: pre; padding: 12px; background: var(--panel); border:1px solid var(--border); border-radius:8px; max-height: 60vh; overflow:auto;">${pretty}</pre>
            `;
            const saveBtn = container.querySelector('.workspace-save');
            if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); this.workspaceSave(filename, saveBtn); });
            const delBtn = container.querySelector('.file-delete');
            if (delBtn) delBtn.addEventListener('click', async (e)=>{ e.preventDefault(); await this.deleteFile(filename); });
        } catch (e) {
            console.warn('[UI] JSON preview failed:', filename, e);
            container.innerHTML = `<div class="error-box"><span class="error-label">Error:</span><div>Unable to preview ${filename}: ${e.message || e}</div></div>`;
        }
    }

    /** 加载Markdown到指定容器 */
    async loadMarkdownIntoContainer(filename, container) {
        try {
            const encoded = encodeURIComponent(filename);
            console.log(`[UI] loadMarkdownIntoContainer: filename=${filename}, outputsBaseUrl=${this.outputsBaseUrl}`);
            const resp = await fetch(`${this.outputsBaseUrl}/${encoded}?t=${Date.now()}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const md = await resp.text();
            const html = (typeof marked !== 'undefined') ? marked.parse(md) : this.escapeHtml(md);
            container.innerHTML = `
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div class="markdown-content" style="padding:12px; border:1px solid var(--border); border-radius:8px; max-height:60vh; overflow:auto;">${html}</div>
            `;
            const saveBtn = container.querySelector('.workspace-save');
            if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); this.workspaceSave(filename, saveBtn); });
            const delBtn = container.querySelector('.file-delete');
            if (delBtn) delBtn.addEventListener('click', async (e)=>{ e.preventDefault(); await this.deleteFile(filename); });
        } catch (e) {
            console.warn('[UI] Markdown preview failed:', filename, e);
            container.innerHTML = `<div class="error-box"><span class="error-label">Error:</span><div>Unable to preview ${filename}: ${e.message || e}</div></div>`;
        }
    }

    /** 加载JSONL到指定容器 */
    async loadJsonlIntoContainer(filename, container) {
        try {
            const encoded = encodeURIComponent(filename);
            const resp = await fetch(`${this.outputsBaseUrl}/${encoded}?t=${Date.now()}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const text = await resp.text();

            // 解析JSONL（每行一个JSON对象）
            const lines = text.trim().split('\n').filter(line => line.trim());
            const objects = [];
            let parseErrors = [];

            lines.forEach((line, idx) => {
                try {
                    objects.push(JSON.parse(line));
                } catch (e) {
                    parseErrors.push(`Line ${idx + 1}: ${e.message}`);
                }
            });

            // 生成HTML：每个对象一个折叠的卡片
            let cardsHtml = '';
            objects.forEach((obj, idx) => {
                const pretty = this.escapeHtml(JSON.stringify(obj, null, 2));
                cardsHtml += `
                    <div class="jsonl-item" style="margin-bottom:12px; border:1px solid var(--border); border-radius:8px; background:var(--panel);">
                        <div class="jsonl-header" style="padding:10px 12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border);">
                            <span style="font-weight:500;">Record ${idx + 1}</span>
                            <span class="jsonl-toggle" style="color:var(--muted);">▼</span>
                        </div>
                        <pre class="jsonl-content" style="padding:12px; margin:0; white-space:pre; overflow:auto; max-height:300px;">${pretty}</pre>
                    </div>
                `;
            });

            let errorHtml = '';
            if (parseErrors.length > 0) {
                errorHtml = `<div style="margin-top:12px; padding:12px; background:#fee; border:1px solid #fcc; border-radius:8px;">
                    <div style="font-weight:500; margin-bottom:8px;">Parse Errors:</div>
                    <pre style="white-space:pre-wrap; font-size:12px;">${this.escapeHtml(parseErrors.join('\n'))}</pre>
                </div>`;
            }

            container.innerHTML = `
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <span style="color:var(--muted); font-size:13px;">${objects.length} records</span>
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div style="padding:12px; max-height:60vh; overflow:auto;">
                    ${cardsHtml}
                    ${errorHtml}
                </div>
            `;

            // 绑定折叠/展开逻辑
            container.querySelectorAll('.jsonl-header').forEach(header => {
                header.addEventListener('click', () => {
                    const item = header.closest('.jsonl-item');
                    const content = item.querySelector('.jsonl-content');
                    const toggle = header.querySelector('.jsonl-toggle');
                    if (content.style.display === 'none') {
                        content.style.display = 'block';
                        toggle.textContent = '▼';
                    } else {
                        content.style.display = 'none';
                        toggle.textContent = '▶';
                    }
                });
            });

            const saveBtn = container.querySelector('.workspace-save');
            if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); this.workspaceSave(filename, saveBtn); });
            const delBtn = container.querySelector('.file-delete');
            if (delBtn) delBtn.addEventListener('click', async (e)=>{ e.preventDefault(); await this.deleteFile(filename); });
        } catch (e) {
            console.warn('[UI] JSONL preview failed:', filename, e);
            container.innerHTML = `<div class="error-box"><span class="error-label">Error:</span><div>Unable to preview ${filename}: ${e.message || e}</div></div>`;
        }
    }

    /** 保存到Workspace（显式保存才纳入） */
    workspaceSave(filename, btnEl) {
        if (!this.workspaceListEl) return;
        const convId = this.currentConvId || '';

        // 后端持久化
        if (convId) {
            fetch(`/workspace/${encodeURIComponent(convId)}/files`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            }).then(async (r) => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                // 前端去重避免重复条目
                const exists = Array.from(this.workspaceListEl.querySelectorAll('.workspace-item-name')).some(el => el.textContent === filename);
                if (!exists) this.workspaceAddFiles([filename], convId);
                if (btnEl) {
                    // 更新按钮为“已保存”样式（图标+短文案）
                    const t = btnEl.querySelector('.btn-text');
                    if (t) t.textContent = 'Saved';
                    const ico = btnEl.querySelector('.btn-ico');
                    if (ico) ico.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
                    btnEl.title = 'Saved to Workspace';
                    btnEl.classList.add('saved');
                    btnEl.style.pointerEvents = 'none';
                    btnEl.style.opacity = '0.7';
                }
            }).catch((e) => {
                console.warn('[Workspace] 保存失败: ', e);
                // 失败时仅更新UI但不持久化
                const exists = Array.from(this.workspaceListEl.querySelectorAll('.workspace-item-name')).some(el => el.textContent === filename);
                if (!exists) this.workspaceAddFiles([filename], convId);
                if (btnEl) {
                    const t = btnEl.querySelector('.btn-text');
                    if (t) t.textContent = 'Saved';
                    const ico = btnEl.querySelector('.btn-ico');
                    if (ico) ico.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
                    btnEl.title = 'Saved to Workspace';
                    btnEl.classList.add('saved');
                }
            });
        } else {
            // 无会话ID时仅更新UI
            const exists = Array.from(this.workspaceListEl.querySelectorAll('.workspace-item-name')).some(el => el.textContent === filename);
            if (!exists) this.workspaceAddFiles([filename], convId);
            if (btnEl) {
                const t = btnEl.querySelector('.btn-text');
                if (t) t.textContent = 'Saved';
                const ico = btnEl.querySelector('.btn-ico');
                if (ico) ico.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
                btnEl.title = 'Saved to Workspace';
                btnEl.classList.add('saved');
            }
        }
    }

    /**
     * 追加Excel预览(用于多文件) - 使用SheetJS
     */
    async appendExcelPreview(filename) {
        try {
            const encodedFilename = encodeURIComponent(filename);
            // 如果前端未加载SheetJS, 使用后端预览接口兜底
            if (typeof XLSX === 'undefined') {
                const convId = this.currentConvId;
                const previewUrl = convId
                    ? `/preview/excel/${encodeURIComponent(convId)}/${encodedFilename}`
                    : `/preview/excel/${encodedFilename}`;
                const preview = await fetch(previewUrl);
                if (!preview.ok) throw new Error(`HTTP ${preview.status}`);
                const data = await preview.json();

                const excelDiv = document.createElement('div');
                excelDiv.className = 'excel-preview-container';
                excelDiv.style.marginBottom = '20px';
                excelDiv.innerHTML = `
                    <div class="preview-info">
                        <div style="display:flex; justify-content: space-between; align-items: center;">
                            <h4>${filename}</h4>
                            <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                        </div>
                    </div>
                    <div class="excel-table-wrapper">${data.html || '<div style="padding:16px;">No preview</div>'}</div>
                `;
                this.previewContent.appendChild(excelDiv);
                return;
            }

            // 获取Excel文件（前端本地解析）
            const response = await fetch(`${this.outputsBaseUrl}/${encodedFilename}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const arrayBuffer = await response.arrayBuffer();
            const workbook = XLSX.read(arrayBuffer, { type: 'array' });

            // 创建预览容器
            const excelDiv = document.createElement('div');
            excelDiv.className = 'excel-preview-container';
            excelDiv.style.marginBottom = '20px';

            // 标题和下载按钮
            const headerDiv = document.createElement('div');
            headerDiv.className = 'preview-info';
            headerDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4>${filename}</h4>
                    <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                </div>
            `;
            excelDiv.appendChild(headerDiv);

            // Sheet标签页(如果有多个sheet)
            if (workbook.SheetNames.length > 1) {
                const tabsDiv = document.createElement('div');
                tabsDiv.className = 'excel-sheet-tabs';

                workbook.SheetNames.forEach((sheetName, index) => {
                    const tab = document.createElement('button');
                    tab.className = 'excel-sheet-tab' + (index === 0 ? ' active' : '');
                    tab.textContent = sheetName;
                    tab.dataset.sheetIndex = index;
                    tab.addEventListener('click', (e) => {
                        // 切换激活状态
                        tabsDiv.querySelectorAll('.excel-sheet-tab').forEach(t => t.classList.remove('active'));
                        e.target.classList.add('active');

                        // 显示对应sheet
                        const wrappers = excelDiv.querySelectorAll('.excel-table-wrapper');
                        wrappers.forEach((w, i) => {
                            w.style.display = i === parseInt(e.target.dataset.sheetIndex) ? 'block' : 'none';
                        });
                    });
                    tabsDiv.appendChild(tab);
                });

                excelDiv.appendChild(tabsDiv);
            }

            // 渲染每个sheet
            workbook.SheetNames.forEach((sheetName, index) => {
                const worksheet = workbook.Sheets[sheetName];
                const html = XLSX.utils.sheet_to_html(worksheet, {
                    id: `sheet-${index}`,
                    editable: false,
                    header: ''
                });

                const wrapper = document.createElement('div');
                wrapper.className = 'excel-table-wrapper';
                wrapper.style.display = index === 0 ? 'block' : 'none';

                // 替换table标签为带样式的版本
                const styledHtml = html.replace(
                    /<table/g,
                    '<table class="excel-table"'
                );

                wrapper.innerHTML = styledHtml;
                excelDiv.appendChild(wrapper);
            });

            this.previewContent.appendChild(excelDiv);
        } catch (err) {
            console.error('[UI] Excel preview failed:', filename, err);
            this.showPreviewError(`Unable to preview ${filename}: ${err.message}`);
        }
    }

    /**
     * 显示预览错误
     */
    showPreviewError(message) {
        this.previewContent.innerHTML = `
            <div class="error-box">
                <span class="error-label">Error:</span>
                <div>${message}</div>
            </div>
        `;
    }

    /**
     * 禁用/启用输入
     */
    setInputEnabled(enabled) {
        this.chatInput.disabled = !enabled;
        this.sendBtn.disabled = !enabled;

        if (!enabled) {
            this.sendBtn.innerHTML = '<span class="loading"></span> 处理中...';
        } else {
            this.sendBtn.textContent = 'Send';
        }
    }

    /**
     * 清空输入框
     */
    clearInput() {
        this.chatInput.value = '';
    }

    /**
     * 智能滚动 - 只在用户靠近底部时自动滚动
     */
    smartScroll() {
        const threshold = 100; // 距离底部100px内认为是"在底部"
        const isNearBottom =
            this.chatMessages.scrollHeight - this.chatMessages.scrollTop - this.chatMessages.clientHeight < threshold;

        if (isNearBottom) {
            this.scrollToBottom();
        }
    }

    /**
     * 滚动到底部
     */
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    /**
     * 显示错误消息
     */
    showError(error) {
        const errorBox = document.createElement('div');
        errorBox.className = 'error-box';

        const label = document.createElement('span');
        label.className = 'error-label';
        label.textContent = '❌ Error:';
        errorBox.appendChild(label);

        const errorMsg = document.createElement('div');
        errorMsg.textContent = error.message || '未知错误';
        errorBox.appendChild(errorMsg);

        this.chatMessages.appendChild(errorBox);
        this.scrollToBottom();
    }

    /**
     * 渲染/更新计划视图
     */
    renderPlan(plan, summary) {
        // 初始化容器
        if (!this.planBox) {
            const box = document.createElement('div');
            box.className = 'plan-box';
            box.innerHTML = `
                <div class="plan-header">
                    <div class="plan-title">Plan</div>
                    <div class="plan-progress"><div class="fill" style="width:0%"></div></div>
                    <div class="plan-actions">
                        <button type="button" data-action="toggle">Expand</button>
                    </div>
                </div>
                <div class="plan-summary"></div>
                <div class="plan-steps"></div>
            `;
            this.chatMessages.appendChild(box);
            this.planBox = box;

            // 绑定展开/收起
            const toggleBtn = this.planBox.querySelector('.plan-actions button[data-action="toggle"]');
            toggleBtn.addEventListener('click', () => {
                const anyCollapsed = Array.from(this.planBox.querySelectorAll('.plan-step')).some(el => !el.classList.contains('expanded'));
                Array.from(this.planBox.querySelectorAll('.plan-step')).forEach(el => {
                    if (anyCollapsed) el.classList.add('expanded');
                    else el.classList.remove('expanded');
                });
                toggleBtn.textContent = anyCollapsed ? 'Collapse' : 'Expand';
            });
        }

        // 解析 steps
        let steps = [];
        if (Array.isArray(plan)) steps = plan;
        else if (plan && Array.isArray(plan.steps)) steps = plan.steps;

        // 统计与进度条
        const total = steps.length || 0;
        const done = steps.filter(s => (s.status || '').toLowerCase() === 'completed').length;
        const percent = total ? Math.round((done / total) * 100) : 0;
        const fill = this.planBox.querySelector('.plan-progress .fill');
        if (fill) fill.style.width = `${percent}%`;

        const summaryEl = this.planBox.querySelector('.plan-summary');
        if (summaryEl) summaryEl.textContent = summary || `Progress: ${done}/${total} (${percent}%)`;

        // 渲染步骤
        const stepsEl = this.planBox.querySelector('.plan-steps');
        stepsEl.innerHTML = '';

        steps.forEach((s, idx) => {
            const status = (s.status || '').toLowerCase();
            const line = document.createElement('div');
            line.className = 'plan-step' + (status === 'in_progress' ? ' expanded' : '');

            const main = document.createElement('div');
            main.className = 'step-main';
            const badge = document.createElement('span');
            badge.className = `plan-badge ${status}`;
            badge.textContent = status === 'completed' ? '✓' : status === 'in_progress' ? '…' : status === 'failed' ? '✗' : '•';

            const text = document.createElement('span');
            text.className = 'plan-text';
            const title = (s.step ? `${s.step}. ` : `${idx + 1}. `) + (s.action || s.title || '');
            text.textContent = title;

            const meta = document.createElement('span');
            meta.className = 'step-meta';
            const eta = s.eta || s.duration || '';
            meta.textContent = eta ? String(eta) : '';

            main.appendChild(badge);
            main.appendChild(text);
            if (eta) main.appendChild(meta);

            const notesVal = s.notes || s.detail || s.desc || '';
            const notes = document.createElement('div');
            notes.className = 'step-notes';
            notes.textContent = notesVal;

            line.appendChild(main);
            if (notesVal) line.appendChild(notes);

            // 点击展开/收起详情
            line.addEventListener('click', (e) => {
                if (e.target.closest('a,button')) return;
                line.classList.toggle('expanded');
            });

            stepsEl.appendChild(line);
        });

        this.scrollToBottom();
    }

    /**
     * Workspace: 刷新并显示用户所有会话的分类文件列表
     */
    async refreshWorkspace() {
        if (!this.workspaceListEl) return;

        try {
            // 调用用户级API，获取所有会话的文件
            const resp = await fetch(`/workspace/user/all`);
            if (!resp.ok) {
                console.warn('[Workspace] 获取分类文件失败:', resp.status);
                return;
            }

            const data = await resp.json();
            let { categories, statistics } = data;
            // 兼容后端中文分类键，映射为英文键
            const keyMap = { '图片':'Images','视频':'Videos','音频':'Audio','表格':'Sheets','文档':'Docs','代码':'Code','其他':'Others' };
            const normalized = {};
            Object.keys(categories || {}).forEach(k => {
                const nk = keyMap[k] || k;
                normalized[nk] = categories[k];
            });
            categories = normalized;

            // 清空现有内容
            this.workspaceListEl.innerHTML = '';

            // 显示统计信息
            if (statistics && statistics.total_files > 0) {
                const stats = document.createElement('div');
                stats.className = 'workspace-stats';
                stats.innerHTML = `
                    <div class="workspace-stat-item">
                        <span class="workspace-stat-label">会话数:</span>
                        <span class="workspace-stat-value">${statistics.conversations}</span>
                    </div>
                    <div class="workspace-stat-item">
                        <span class="workspace-stat-label">文件总数:</span>
                        <span class="workspace-stat-value">${statistics.total_files}</span>
                    </div>
                    <div class="workspace-stat-item">
                        <span class="workspace-stat-label">总大小:</span>
                        <span class="workspace-stat-value">${statistics.total_size}</span>
                    </div>
                `;
                this.workspaceListEl.appendChild(stats);
            }

            // 显示分类文件
            let hasFiles = false;
            const categoryOrder = ['Images', 'Videos', 'Audio', 'Sheets', 'Docs', 'Code', 'Others'];

            categoryOrder.forEach(category => {
                const files = categories[category] || [];
                if (files.length === 0) return;

                hasFiles = true;

                // 创建分类容器
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'workspace-category';

                // 分类标题（可折叠）
                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'workspace-category-header';
                const icon = (p)=>`<svg class="ws-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
                const icons = {
                    Images: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-4-4-3 3-2-2-4 4"/>'),
                    Videos: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><polygon points="10 8 16 12 10 16 10 8"/>'),
                    Audio:  icon('<path d="M9 18V6l8-2v12"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="16" r="2"/>'),
                    Sheets: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h10M7 12h10M7 17h10"/>'),
                    Docs:   icon('<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12V7z"/><path d="M14 3v4h4"/>'),
                    Code:   icon('<polyline points="7 8 3 12 7 16"/><polyline points="17 8 21 12 17 16"/>'),
                    Others: icon('<path d="M3 7h5l2 3h11v9a2 2 0 0 1-2 2H3z"/><path d="M3 7V5a2 2 0 0 1 2-2h6l2 2h6a2 2 0 0 1 2 2v3"/>')
                };
                categoryHeader.innerHTML = `
                    <span class="workspace-category-icon">▼</span>
                    <span class="workspace-category-title">${icons[category] || ''}<span>${category}</span></span>
                    <span class="workspace-category-count">${files.length}</span>
                `;

                // 文件列表
                const fileList = document.createElement('div');
                fileList.className = 'workspace-category-files';

                files.forEach(fileInfo => {
                    const item = document.createElement('div');
                    item.className = 'workspace-file-item';
                    item.innerHTML = `
                        <div class="workspace-file-main">
                            <span class="workspace-file-name" title="${fileInfo.name}">${fileInfo.name}</span>
                            <span class="workspace-file-conv" title="Conversation: ${fileInfo.conversation_id}">${fileInfo.conversation_id.substring(0, 8)}</span>
                        </div>
                        <div class="workspace-file-actions">
                            <span class="workspace-file-size">${fileInfo.size_str}</span>
                            <button class="workspace-file-btn workspace-file-preview" title="Preview">👁️</button>
                            <button class="workspace-file-btn workspace-file-delete" title="Delete">🗑️</button>
                        </div>
                    `;

                    // 点击文件名或预览按钮 - 切换到对应会话并打开预览
                    const nameEl = item.querySelector('.workspace-file-name');
                    const previewBtn = item.querySelector('.workspace-file-preview');
                    const clickHandler = async () => {
                        // 切换到所属会话
                        if (window.switchConversation) {
                            await window.switchConversation(fileInfo.conversation_id);
                        }
                        // 打开并聚焦该文件（若已存在则切换到对应tab）
                        try { this.openFileByName(fileInfo.name); } catch (e) {
                            try { this.loadMultipleFiles([fileInfo.name]); } catch(_) {}
                        }
                    };
                    nameEl.addEventListener('click', clickHandler);
                    previewBtn.addEventListener('click', clickHandler);

                    // 删除按钮
                    const deleteBtn = item.querySelector('.workspace-file-delete');
                    deleteBtn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        // 临时切换到该文件所属会话进行删除
                        const originalConv = this.currentConvId;
                        this.currentConvId = fileInfo.conversation_id;
                        await this.deleteFile(fileInfo.name);
                        this.currentConvId = originalConv;
                        // 刷新workspace
                        await this.refreshWorkspace();
                    });

                    fileList.appendChild(item);
                });

                // 折叠/展开功能
                categoryHeader.addEventListener('click', () => {
                    const icon = categoryHeader.querySelector('.workspace-category-icon');
                    if (fileList.style.display === 'none') {
                        fileList.style.display = 'flex';
                        icon.textContent = '▼';
                    } else {
                        fileList.style.display = 'none';
                        icon.textContent = '▶';
                    }
                });

                categoryDiv.appendChild(categoryHeader);
                categoryDiv.appendChild(fileList);
                this.workspaceListEl.appendChild(categoryDiv);
            });

            // 如果没有文件，显示空状态
            if (!hasFiles) {
                const empty = document.createElement('div');
                empty.className = 'workspace-empty';
                empty.textContent = 'No files yet. Generated files will appear here.';
                this.workspaceListEl.appendChild(empty);
            }

        } catch (e) {
            console.warn('[Workspace] 刷新失败:', e);
        }
    }

    /**
     * Workspace: 增量添加文件（保留用于向后兼容）
     */
    workspaceAddFiles(_files, _convId) {
        // 直接刷新整个workspace来显示新文件
        this.refreshWorkspace();
    }

    /** 删除文件（调用后端并刷新文件列表与Workspace） */
    async deleteFile(filename) {
        try {
            const convId = this.currentConvId;
            if (!convId) { alert('当前无会话，无法删除'); return; }
            if (!filename) return;
            if (!confirm(`确定删除文件：${filename} ？`)) return;

            const resp = await fetch(`/upload/${encodeURIComponent(convId)}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.error || `HTTP ${resp.status}`);
            }

            // 从Workspace列表移除对应项
            try {
                if (this.workspaceListEl) {
                    Array.from(this.workspaceListEl.querySelectorAll('.workspace-item')).forEach((it) => {
                        const nameEl = it.querySelector('.workspace-item-name');
                        if (nameEl && nameEl.textContent === filename) it.remove();
                    });
                }
            } catch {}

            // 刷新文件标签
            await this.refreshFileTabs();
        } catch (e) {
            console.warn('[UI] 删除失败:', e);
            alert(`删除失败: ${e.message || e}`);
        }
    }

    /** 重新加载会话目录下的可预览文件，重建文件标签 */
    async refreshFileTabs() {
        try {
            const convId = this.currentConvId;
            if (!convId) return;
            const listResp = await fetch(`/outputs/list/${encodeURIComponent(convId)}`);
            if (!listResp.ok) return;
            const data = await listResp.json();
            const previewables = (data.files || []).filter(fn => /\.(png|jpg|jpeg|xlsx|html|mp3|wav|m4a|aac|ogg|flac|mp4|webm|mov|txt|md|log)$/i.test(fn));
            this.clearAllFiles();
            if (previewables.length) this.loadMultipleFiles(previewables);
        } catch (e) {
            console.warn('[UI] 刷新文件失败:', e);
        }
    }
}

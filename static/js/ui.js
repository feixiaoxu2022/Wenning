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
        this.attachmentsExpanded = false; // 附件是否展开显示
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

        // 迭代分组状态
        this._iterBoxes = new Map();
        this._thinkingSections = new Map();
        this._progressByIter = new Map();
        this._toolTextByIter = new Map();
        this._execLastByTool = new Map(); // iter -> Map(tool -> rowEl)

        // SSE iter重新编号机制
        this._sseIterBase = null;  // 记录本次用户消息开始时的后端iter
        this._sseIterMap = new Map();  // 后端iter -> 前端显示iter

        // 加载指示器
        this.loadingIndicator = null;
    }

    /** 创建通用的复制图标SVG */
    _copySvg() {
        // clipboard icon
        return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M15 9V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4"/></svg>';
    }

    /** 创建成功复制的checkmark图标SVG */
    _checkmarkSvg() {
        // check-circle icon
        return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    }

    /** 创建思考图标SVG */
    _thinkingSvg() {
        // message-circle icon (思考气泡)
        return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
    }

    /** 创建说明图标SVG */
    _noteSvg() {
        // paperclip icon (回形针)
        return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>';
    }

    /** 复制文本到剪贴板（带fallback） */
    async copyText(text) {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                return true;
            }
        } catch (_) {}
        // fallback
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            return ok;
        } catch (_) {
            return false;
        }
    }

    /** 创建一个悬浮复制按钮（用于右上角chip） */
    _createCopyChip(label = '复制') {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'copy-chip';
        btn.innerHTML = `${this._copySvg()} <span class="copy-text">${label}</span>`;
        btn.title = label || 'Copy';
        return btn;
    }

    /** 创建消息用的悬浮左侧 copy 按钮 */
    _createMsgCopyBtn(label = '复制') {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'msg-copy-btn';
        btn.innerHTML = this._copySvg();
        btn.title = label || 'Copy';
        return btn;
    }

    /** 给消息添加：hover 时左侧显示的复制图标 */
    attachHoverCopyForMessage(targetEl, getText, label = '复制') {
        if (!targetEl || typeof getText !== 'function') return;
        if (targetEl.querySelector(':scope > .msg-copy-btn')) return;
        const btn = this._createMsgCopyBtn(label);
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            try {
                const ok = await this.copyText(String(await getText() || ''));
                const oldTitle = btn.title;

                if (ok) {
                    // 复制成功 - 显示视觉反馈
                    const originalHTML = btn.innerHTML;
                    btn.innerHTML = this._checkmarkSvg();
                    btn.title = '已复制';
                    btn.style.color = '#22c55e'; // 绿色

                    // 1200ms后恢复原状
                    setTimeout(() => {
                        btn.innerHTML = originalHTML;
                        btn.title = oldTitle || '复制';
                        btn.style.color = '';
                    }, 1200);
                } else {
                    // 复制失败
                    btn.title = '复制失败';
                    setTimeout(() => { btn.title = oldTitle || '复制'; }, 1200);
                }
            } catch (_) {}
        });
        targetEl.appendChild(btn);
        // 粘滞显示：在消息或按钮上时保持可见，离开两者后延迟隐藏
        let hideTimer = null;
        const show = () => {
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
            targetEl.classList.add('show-copy');
        };
        const scheduleHide = () => {
            if (hideTimer) clearTimeout(hideTimer);
            hideTimer = setTimeout(() => {
                targetEl.classList.remove('show-copy');
            }, 180);
        };
        targetEl.addEventListener('mouseenter', show);
        targetEl.addEventListener('mouseleave', scheduleHide);
        btn.addEventListener('mouseenter', show);
        btn.addEventListener('mouseleave', scheduleHide);
        return btn;
    }

    /** 为给定元素附加右上角复制按钮 */
    attachCopyChip(targetEl, getText, label = '复制') {
        if (!targetEl || typeof getText !== 'function') return;
        // 避免重复添加
        if (targetEl.querySelector(':scope > .copy-chip')) return;
        const btn = this._createCopyChip(label);
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            try {
                const ok = await this.copyText(String(await getText() || ''));
                const oldTitle = btn.title;

                if (ok) {
                    // 复制成功 - 显示视觉反馈
                    const originalHTML = btn.innerHTML;
                    const textSpan = btn.querySelector('.copy-text');

                    // 更新图标和文字
                    btn.innerHTML = `${this._checkmarkSvg()} <span class="copy-text">已复制</span>`;
                    btn.title = '已复制';
                    btn.style.color = '#22c55e'; // 绿色

                    // 1200ms后恢复原状
                    setTimeout(() => {
                        btn.innerHTML = originalHTML;
                        btn.title = oldTitle || '复制';
                        btn.style.color = '';
                    }, 1200);
                } else {
                    // 复制失败
                    btn.title = '复制失败';
                    setTimeout(() => { btn.title = oldTitle || '复制'; }, 1200);
                }
            } catch (err) {}
        });
        targetEl.appendChild(btn);
    }

    /** 为markdown容器增强：给代码块添加复制按钮 */
    enhanceMarkdownCopy(container) {
        if (!container) return;
        const pres = container.querySelectorAll('pre');
        pres.forEach((pre) => {
            const getText = () => {
                // 优先code元素的纯文本
                const code = pre.querySelector('code');
                return (code ? code.innerText : pre.innerText) || '';
            };
            this.attachCopyChip(pre, getText, '复制代码');
        });
    }

    /** 获取容器内当前可见的Excel表格(table) */
    _getVisibleExcelTable(container) {
        if (!container) return null;
        const wrappers = container.querySelectorAll('.excel-table-wrapper');
        for (const w of wrappers) {
            const visible = w.style.display !== 'none';
            if (visible) {
                const t = w.querySelector('table');
                if (t) return t;
            }
        }
        // fallback: 找第一个table
        return container.querySelector('.excel-table-wrapper table') || container.querySelector('table');
    }

    /** 将HTMLTableElement序列化为CSV文本 */
    _tableToCSV(table, delimiter = ',') {
        if (!table) return '';
        const rows = Array.from(table.querySelectorAll('tr'));
        const esc = (v) => {
            const s = (v || '').replace(/\r?\n/g, '\n');
            const mustQuote = s.includes('"') || s.includes('\n') || s.includes(delimiter);
            const out = s.replace(/"/g, '""');
            return mustQuote ? `"${out}"` : out;
        };
        const lines = rows.map((tr) => {
            const cells = Array.from(tr.querySelectorAll('th,td'));
            return cells.map((c) => esc(c.innerText.trim())).join(delimiter);
        });
        return lines.join('\n');
    }

    /** 将HTMLTableElement序列化为Markdown表格 */
    _tableToMarkdown(table) {
        if (!table) return '';
        const rows = Array.from(table.querySelectorAll('tr'));
        if (rows.length === 0) return '';
        const toCells = (tr) => Array.from(tr.querySelectorAll('th,td')).map((c) => {
            const s = (c.innerText || '').replace(/\r?\n/g, ' ').trim();
            return s.replace(/\|/g, '\\|');
        });
        // header: thead>tr:first or first row
        let headerCells = [];
        const thead = table.querySelector('thead tr');
        if (thead) headerCells = toCells(thead);
        else headerCells = toCells(rows[0]);
        const headerLine = `| ${headerCells.join(' | ')} |`;
        const sepLine = `| ${headerCells.map(() => '---').join(' | ')} |`;
        const bodyRows = [];
        const startIdx = thead ? 0 : 1; // if no thead, skip first row as header
        rows.forEach((tr, idx) => {
            if (!thead && idx === 0) return;
            if (thead && tr.closest('thead')) return; // skip any header rows
            const cells = toCells(tr);
            bodyRows.push(`| ${cells.join(' | ')} |`);
        });
        return [headerLine, sepLine, ...bodyRows].join('\n');
    }

    /** 为markdown内容中的表格添加复制按钮（仅 Markdown 表格） */
    enhanceMarkdownTables(container) {
        if (!container) return;
        const tables = container.querySelectorAll('table');
        tables.forEach((table) => {
            // 避免重复：若已经有按钮则跳过
            if (table.querySelector(':scope > .copy-chip[data-kind="md"]')) return;
            // Markdown表格按钮
            const mdBtn = this._createCopyChip('复制Markdown');
            mdBtn.setAttribute('data-kind', 'md');
            mdBtn.title = 'Copy Markdown Table';
            mdBtn.style.right = '8px';
            mdBtn.addEventListener('click', async (e) => {
                e.preventDefault(); e.stopPropagation();
                const md = this._tableToMarkdown(table);
                const ok = await this.copyText(md);
                const oldTitle = mdBtn.title;
                mdBtn.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { mdBtn.title = oldTitle || 'Copy Markdown Table'; }, 1200);
            });
            table.appendChild(mdBtn);
        });
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
                // Excel文件
                if (lower.endsWith('.xlsx')) {
                    this.loadExcelIntoContainer(obj.filename, el);
                }
                // 图片文件
                else if (/(\.png|\.jpg|\.jpeg|\.svg|\.gif|\.webp|\.avif)$/.test(lower)) {
                    this.loadImageIntoContainer(obj.filename, el);
                }
                // 音频文件
                else if (/(\.mp3|\.wav|\.m4a|\.aac|\.ogg|\.flac)$/.test(lower)) {
                    this.loadAudioIntoContainer(obj.filename, el);
                }
                // 视频文件
                else if (/(\.mp4|\.webm|\.mov)$/.test(lower)) {
                    this.loadVideoIntoContainer(obj.filename, el);
                }
                // HTML文件
                else if (lower.endsWith('.html')) {
                    this.loadHtmlIntoContainer(obj.filename, el);
                }
                // PowerPoint文件
                else if (lower.endsWith('.pptx')) {
                    this.loadPptxIntoContainer(obj.filename, el);
                }
                // Word文档
                else if (/(\.doc|\.docx)$/.test(lower)) {
                    this.loadWordIntoContainer(obj.filename, el);
                }
                // PDF文件
                else if (lower.endsWith('.pdf')) {
                    this.loadPdfIntoContainer(obj.filename, el);
                }
                // ZIP文件
                else if (lower.endsWith('.zip')) {
                    this.loadZipIntoContainer(obj.filename, el);
                }
                // JSONL文件
                else if (lower.endsWith('.jsonl')) {
                    this.loadJsonlIntoContainer(obj.filename, el);
                }
                // JSON文件
                else if (lower.endsWith('.json')) {
                    this.loadJsonIntoContainer(obj.filename, el);
                }
                // Markdown文件
                else if (lower.endsWith('.md')) {
                    this.loadMarkdownIntoContainer(obj.filename, el);
                }
                // 文本文件（支持多种扩展名）
                else if (/\.(txt|log|yaml|yml|toml|ini|cfg|conf|xml|py|js|ts|tsx|jsx|java|go|rs|c|cpp|h|cs|rb|php|sh|bash|zsh|sql|csv)$/i.test(lower)) {
                    this.loadTextIntoContainer(obj.filename, el);
                }
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
        this.renderAttachmentsStrip();
    }

    // 渲染附件条（支持省略号展示）
    renderAttachmentsStrip() {
        if (!this.attachmentsStrip) return;

        // 清空现有内容
        this.attachmentsStrip.innerHTML = '';

        const totalCount = this.pendingAttachments.length;
        const maxVisible = 5;

        // 决定显示哪些附件
        let displayAttachments = [];
        let showEllipsis = false;

        if (totalCount <= maxVisible || this.attachmentsExpanded) {
            // 显示全部
            displayAttachments = this.pendingAttachments;
        } else {
            // 显示前4个 + 省略号
            displayAttachments = this.pendingAttachments.slice(0, 4);
            showEllipsis = true;
        }

        // 渲染每个附件chip
        displayAttachments.forEach(filename => {
            const chip = this._createAttachmentChipElement(filename);
            this.attachmentsStrip.appendChild(chip);
        });

        // 添加省略号chip
        if (showEllipsis) {
            const ellipsisChip = document.createElement('div');
            ellipsisChip.className = 'attachment-chip attachment-ellipsis';
            ellipsisChip.innerHTML = `
                <div class="att-icon" style="background: rgba(100,116,139,0.1);">
                    <div style="font-size: 18px; color: #64748b;">+${totalCount - 4}</div>
                </div>
            `;
            ellipsisChip.title = `点击查看全部 ${totalCount} 个附件`;
            ellipsisChip.addEventListener('click', () => {
                this.attachmentsExpanded = true;
                this.renderAttachmentsStrip();
            });
            this.attachmentsStrip.appendChild(ellipsisChip);
        }

        this.updateAttachmentsPresence();
    }

    // 创建单个附件chip元素
    _createAttachmentChipElement(filename) {
        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        chip.dataset.filename = filename;

        const enc = encodeURIComponent(filename);
        if (!this.currentConvId) {
            console.error('[UI] _createAttachmentChipElement: 缺少currentConvId');
            return chip;
        }
        const src = `/outputs/${encodeURIComponent(this.currentConvId)}/${enc}`;

        // 根据文件类型决定显示方式
        const ext = filename.toLowerCase().match(/\.([^.]+)$/)?.[1] || '';
        const isImage = /^(jpg|jpeg|png|gif|svg|webp|avif|bmp)$/.test(ext);

        // 设置文件类型
        const fileType = this._getFileType(ext);
        chip.dataset.type = fileType;

        if (isImage) {
            // 图片文件：显示缩略图
            const img = document.createElement('img');
            img.src = src;
            img.onerror = () => {
                // 图片加载失败时，也显示图标
                img.replaceWith(this._createFileIcon(filename));
            };
            chip.appendChild(img);
        } else {
            // 非图片文件：显示文件类型图标
            chip.appendChild(this._createFileIcon(filename));
        }

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

        return chip;
    }

    // 获取文件类型
    _getFileType(ext) {
        if (/^(jpg|jpeg|png|gif|svg|webp|avif|bmp)$/.test(ext)) {
            return 'image';
        } else if (/^(pdf)$/.test(ext)) {
            return 'pdf';
        } else if (/^(doc|docx)$/.test(ext)) {
            return 'word';
        } else if (/^(txt|md)$/.test(ext)) {
            return 'text';
        } else if (/^(ppt|pptx)$/.test(ext)) {
            return 'presentation';
        } else if (/^(xls|xlsx|csv)$/.test(ext)) {
            return 'spreadsheet';
        } else if (/^(zip|rar|7z|tar|gz)$/.test(ext)) {
            return 'archive';
        } else if (/^(mp3|wav|m4a|aac|ogg|flac)$/.test(ext)) {
            return 'audio';
        } else if (/^(mp4|webm|mov|avi|mkv)$/.test(ext)) {
            return 'video';
        } else {
            return 'other';
        }
    }

    // 创建文件类型图标
    _createFileIcon(filename) {
        const ext = filename.toLowerCase().match(/\.([^.]+)$/)?.[1] || '';
        const fileType = this._getFileType(ext);

        // 根据文件类型选择图标路径
        let iconPath = '';
        if (fileType === 'image') {
            iconPath = 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m14-7l-5-5m0 0L7 8m5-5v12';
        } else if (fileType === 'pdf') {
            // PDF文件图标 - 带PDF标识
            iconPath = 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z';
        } else if (fileType === 'word') {
            // Word文档图标 - 文字文档
            iconPath = 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z';
        } else if (fileType === 'text') {
            // 纯文本图标 - 简单文本行
            iconPath = 'M9 12h6M9 16h6M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z';
        } else if (fileType === 'presentation') {
            // PPT演示文稿图标 - 幻灯片样式
            iconPath = 'M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2zm0 4h10M7 11h10m-7 4h4';
        } else if (fileType === 'spreadsheet') {
            iconPath = 'M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z';
        } else if (fileType === 'archive') {
            iconPath = 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4';
        } else if (fileType === 'audio') {
            iconPath = 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3';
        } else if (fileType === 'video') {
            iconPath = 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z';
        } else {
            iconPath = 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z';
        }

        const container = document.createElement('div');
        container.className = 'att-icon';
        container.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="${iconPath}"/>
            </svg>
        `;

        return container;
    }

    // 附件缩略图：移除
    removeAttachmentChip(filename) {
        if (!this.attachmentsStrip || !filename) return;
        this.pendingAttachments = this.pendingAttachments.filter(n => n !== filename);
        this.renderAttachmentsStrip();
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
        this.attachmentsExpanded = false; // 重置展开状态
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
        if (lower.endsWith('.pptx')) return this.addFileTab(filename, 'pptx');
        if (/\.(doc|docx)$/.test(lower)) return this.addFileTab(filename, 'word');
        if (/(\.png|\.jpg|\.jpeg|\.svg|\.gif|\.webp|\.avif)$/.test(lower)) return this.addFileTab(filename, 'image');
        if (/(\.mp3|\.wav|\.m4a|\.aac|\.ogg|\.flac)$/.test(lower)) return this.addFileTab(filename, 'audio');
        if (/(\.mp4|\.webm|\.mov)$/.test(lower)) return this.addFileTab(filename, 'video');
        if (lower.endsWith('.html')) return this.addFileTab(filename, 'html');
        if (lower.endsWith('.pdf')) return this.addFileTab(filename, 'pdf');
        if (lower.endsWith('.zip')) return this.addFileTab(filename, 'zip');
        if (lower.endsWith('.jsonl')) return this.addFileTab(filename, 'jsonl');
        if (lower.endsWith('.json')) return this.addFileTab(filename, 'json');
        if (lower.endsWith('.md')) return this.addFileTab(filename, 'markdown');
        if (/(\.txt|\.md|\.log|\.yaml|\.yml|\.toml|\.ini|\.cfg|\.conf|\.xml|\.py|\.js|\.ts|\.tsx|\.jsx|\.java|\.go|\.rs|\.[ch](pp)?|\.cs|\.rb|\.php|\.sh|\.bash|\.zsh|\.sql)$/i.test(lower)) return this.addFileTab(filename, 'text');
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
        // 重置SSE iter映射（新用户消息开始）
        this._sseIterBase = null;
        this._sseIterMap.clear();

        // 清理未完成的thinking、progress和tool_call_text盒子，但保留已有内容的历史记录
        try {
            // 策略：只删除最新的、还在执行中的iter-box（空内容或只有spinner）
            const iterBoxes = Array.from(this.chatMessages.querySelectorAll('.iter-box'));

            // 从后往前检查，只删除最新的未完成的
            if (iterBoxes.length > 0) {
                const lastIterBox = iterBoxes[iterBoxes.length - 1];
                const statusDot = lastIterBox.querySelector('.iter-status-dot');

                // 只有当最后一个iter-box仍在执行中（spinner状态）且内容为空时才删除
                if (statusDot && statusDot.classList.contains('spinner')) {
                    // 检查是否有实质内容（thinking、exec-list等）
                    const hasContent = lastIterBox.querySelector('.thinking-box, .exec-list, .progress-box');
                    if (!hasContent) {
                        // 空的执行中iter，删除
                        lastIterBox.remove();
                        const key = lastIterBox.dataset.iterKey;
                        if (key) {
                            this._iterBoxes.delete(key);
                            this._thinkingSections.delete(key);
                            this._toolTextByIter.delete(key);
                            this._progressByIter.delete(key);
                        }
                    }
                    // 有内容的保留，即使还是spinner状态（被stop的情况）
                }
            }

            // 清理独立的thinking-box、tool-call-text-box、progress-box（旧版遗留）
            this.chatMessages.querySelectorAll('.thinking-box:not(.iter-box .thinking-box), .tool-call-text-box, .progress-box:not(.iter-box .progress-box)').forEach(el => el.remove());

            this._lastProgressIter = null;
        } catch (e) {
            console.warn('[UI] 清理未完成容器失败:', e);
        }

        // 删除独立的progress box（如果有）
        if (this._progress && this._progress.box && this._progress.box.parentElement) {
            this._progress.box.remove();
        }
        if (this.currentToolCallTextBox && this.currentToolCallTextBox.parentElement) {
            const toolCallContainer = this.currentToolCallTextBox.closest('.tool-call-text-box');
            if (toolCallContainer) toolCallContainer.remove();
        }

        // 重置thinking和progress状态（但不清空Map，因为已完成的iter还在）
        this.currentThinkingBox = null;
        this.currentProgressBox = null;
        this.currentToolCallTextBox = null;
        this._progress = null;

        // 🔧 重置SSE迭代映射状态，确保新请求的iter从1开始正确映射到新容器
        this._resetSSEIterMapping();

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.textContent = message;
        this.chatMessages.appendChild(messageDiv);
        // 消息整体复制按钮（hover 左侧，不遮挡内容）
        this.attachHoverCopyForMessage(messageDiv, () => messageDiv.textContent || '', '复制');

        // 保存到历史
        this.chatHistory.push({role: 'user', content: message});

        // 滚动到底部
        this.scrollToBottom();
    }

    /**
     * 显示加载指示器（Agent推理中）
     */
    showLoadingIndicator() {
        // 如果已存在，先移除
        this.hideLoadingIndicator();

        const indicator = document.createElement('div');
        indicator.className = 'loading-indicator';
        indicator.innerHTML = `
            <div class="loading-spinner"></div>
            <span class="loading-text">Agent正在执行任务...</span>
        `;
        this.chatMessages.appendChild(indicator);
        this.loadingIndicator = indicator;
        this.scrollToBottom();
    }

    /**
     * 隐藏加载指示器
     */
    hideLoadingIndicator() {
        if (this.loadingIndicator && this.loadingIndicator.parentElement) {
            this.loadingIndicator.remove();
            this.loadingIndicator = null;
        }
    }

    /**
     * 将后端iter映射为前端显示的iter
     * 用于SSE实时流，将ReAct循环的累计iter转换为用户轮次
     */
    _mapSSEIter(backendIter) {
        if (!backendIter && backendIter !== 0) return 1;

        // 如果已经映射过，直接返回
        if (this._sseIterMap.has(backendIter)) {
            return this._sseIterMap.get(backendIter);
        }

        // 第一次遇到iter，记录base
        if (this._sseIterBase === null) {
            this._sseIterBase = backendIter;
        }

        // 计算前端显示的iter：从1开始递增
        const frontendIter = backendIter - this._sseIterBase + 1;
        this._sseIterMap.set(backendIter, frontendIter);
        return frontendIter;
    }

    /**
     * 重置SSE迭代映射状态（在新请求开始时调用）
     * 确保每次新请求的后端iter都能正确映射到新的前端iter容器
     */
    _resetSSEIterMapping() {
        console.log('[UI] 重置SSE迭代映射状态');
        this._sseIterBase = null;
        this._sseIterMap.clear();
        // 🔧 关键：也要清空_iterBoxes，否则新请求会复用旧容器
        // 注意：已append到DOM的容器元素不会被删除，只是Map引用被清空
        if (this._iterBoxes) {
            this._iterBoxes.clear();
        }
        // 同时清空相关的辅助Map
        if (this._thinkingSections) {
            this._thinkingSections.clear();
        }
        if (this._execLastByTool) {
            this._execLastByTool.clear();
        }
        if (this._progressByIter) {
            this._progressByIter.clear();
        }
    }

    // 获取/创建迭代分组容器
    ensureIterContainer(iter) {
        const key = String(iter || '1');
        if (this._iterBoxes.has(key)) return this._iterBoxes.get(key);
        const wrap = document.createElement('div');
        wrap.className = 'iter-box';
        wrap.dataset.iterKey = key;  // 添加key标识，用于清理时查找
        const hdr = document.createElement('div');
        hdr.className = 'iter-header';
        hdr.textContent = `第${key}轮`;
        // 状态点（默认spinner）
        const dot = document.createElement('span');
        dot.className = 'progress-dot spinner iter-status-dot';  // 添加iter-status-dot class
        dot.style.marginLeft = '8px';
        hdr.appendChild(dot);
        wrap._statusDot = dot;
        wrap.appendChild(hdr);
        this.chatMessages.appendChild(wrap);
        this._iterBoxes.set(key, wrap);
        return wrap;
    }

    /**
     * 创建思考过程盒子
     */
    // 思考分组（按迭代轮次）
    startThinkingSection(iter) {
        if (!this._thinkingSections) this._thinkingSections = new Map();
        const key = String(iter || '1');
        if (this._thinkingSections.has(key)) return;

        // 容器
        const wrap = this.ensureIterContainer(key);
        const thinkingBox = document.createElement('div');
        thinkingBox.className = 'thinking-box';
        const label = document.createElement('span');
        label.className = 'thinking-label';
        label.innerHTML = `${this._thinkingSvg()}思考（第${key}轮）：`;
        thinkingBox.appendChild(label);
        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-content';
        thinkingBox.appendChild(contentDiv);
        wrap.appendChild(thinkingBox);
        this._thinkingSections.set(key, contentDiv);
        this.currentThinkingBox = contentDiv;
        this.scrollToBottom();
    }

    /**
     * 追加思考内容
     */
    appendThinking(content, iter) {
        if (!this._thinkingSections) this._thinkingSections = new Map();
        const key = String(iter || '1');
        if (!this._thinkingSections.has(key)) {
            this.startThinkingSection(key);
        }
        const target = this._thinkingSections.get(key) || this.currentThinkingBox;
        if (!target) return;
        if (target.textContent && content) target.textContent += '\n\n';
        target.textContent += content;
        this.smartScroll();
    }

    /**
     * 追加工具调用时的accompanying text（打字机效果）
     */
    appendToolCallText(delta, iter) {
        if (!this._toolTextByIter) this._toolTextByIter = new Map();
        const key = String(iter || '1');
        let contentDiv = this._toolTextByIter.get(key);
        if (!contentDiv) {
            // 容器
            let wrap = this._iterBoxes && this._iterBoxes.get(key);
            if (!wrap) {
                this.startThinkingSection(key); // 也会创建iter容器
                wrap = this._iterBoxes.get(key);
            }
            const toolCallBox = document.createElement('div');
            toolCallBox.className = 'tool-call-text-box';
            const label = document.createElement('div');
            label.className = 'tool-call-text-label';
            label.innerHTML = `${this._thinkingSvg()}思考`;
            toolCallBox.appendChild(label);
            contentDiv = document.createElement('div');
            contentDiv.className = 'tool-call-text-content';
            toolCallBox.appendChild(contentDiv);
            wrap.appendChild(toolCallBox);
            this._toolTextByIter.set(key, contentDiv);
        }
        contentDiv.textContent += delta;
        this.smartScroll();
    }

    // 新的 note 接口（等效于 tool_call_text）
    appendNote(delta, iter) {
        if (!delta) return;
        const key = String(iter || '1');
        let contentDiv = this._toolTextByIter.get(key);
        if (!contentDiv) {
            const wrap = this.ensureIterContainer(key);
            const box = document.createElement('div');
            box.className = 'tool-call-text-box';
            const label = document.createElement('div');
            label.className = 'tool-call-text-label';
            // 如果本轮还没有任何思考块，则把note也当作"思考"展示，文案统一为"思考"。
            const hasThinking = this._thinkingSections && this._thinkingSections.has(key);
            label.innerHTML = hasThinking ? `${this._noteSvg()}说明` : `${this._thinkingSvg()}思考`;
            box.appendChild(label);
            contentDiv = document.createElement('div'); contentDiv.className = 'tool-call-text-content'; box.appendChild(contentDiv);
            wrap.appendChild(box);
            this._toolTextByIter.set(key, contentDiv);
        }
        contentDiv.textContent += (contentDiv.textContent ? '\n' : '') + delta;
        this.smartScroll();
    }

    // 按轮次追加执行行
    appendExec(iter, evt) {
        const key = String(iter || '1');
        const wrap = this.ensureIterContainer(key);
        let list = wrap.querySelector('.exec-list');
        if (!list) { list = document.createElement('div'); list.className = 'exec-list'; wrap.appendChild(list); }
        if (!this._execLastByTool) this._execLastByTool = new Map();
        if (!this._execLastByTool.has(key)) this._execLastByTool.set(key, new Map());
        const toolMap = this._execLastByTool.get(key);

        const phase = evt.phase || 'info';
        if (phase === 'start') {
            const item = document.createElement('div'); item.className = 'exec-item';
            const head = document.createElement('div'); head.className = 'exec-head';
            head.innerHTML = `🛠 执行工具: <span class="exec-tool">${this.escapeHtml(evt.tool || 'unknown')}</span>`;
            const status = document.createElement('span'); status.className = 'exec-status'; head.appendChild(status);
            item.appendChild(head);
            if (evt.args_preview) { const pre=document.createElement('pre'); pre.className='exec-args'; pre.textContent=evt.args_preview; item.appendChild(pre); }
            item._status = status;
            list.appendChild(item); toolMap.set(evt.tool || 'unknown', item);
        } else if (phase === 'heartbeat') {
            const k = evt.tool || 'unknown';
            let item = toolMap.get(k);
            if (!item) {
                item=document.createElement('div');
                item.className='exec-item exec-item-running';
                const head=document.createElement('div');
                head.className='exec-head';
                head.innerHTML=`<svg class="exec-icon exec-icon-running" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ${this.escapeHtml(k)} 执行中...`;
                const st=document.createElement('span');
                st.className='exec-status';
                head.appendChild(st);
                item._status=st;
                item.appendChild(head);
                list.appendChild(item);
                toolMap.set(k,item);
            }
            const s=item._status || item.querySelector('.exec-status'); if (s) s.textContent=` 已等待 ${evt.elapsed_sec||0}s`;
        } else if (phase === 'done') {
            const k = evt.tool || 'unknown'; const item = toolMap.get(k);
            if (item) {
                item.className='exec-item exec-item-success';
                const head = item.querySelector('.exec-head');
                if (head) {
                    const icon = head.querySelector('.exec-icon');
                    if (icon) {
                        icon.outerHTML = '<svg class="exec-icon exec-icon-success" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg>';
                    }
                }
                const s=item._status || item.querySelector('.exec-status');
                if (s) s.textContent=' 完成';
            }
            else { const r=document.createElement('div'); r.className='progress-line exec-line-success'; r.innerHTML=`<svg class="exec-icon exec-icon-success" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg> ${k} 执行完成`; list.appendChild(r); }
            toolMap.delete(k);
        } else if (phase === 'error') {
            const k = evt.tool || 'unknown'; const item = toolMap.get(k);
            // 不显示具体错误信息，避免过长导致UI变形
            if (item) {
                item.className='exec-item exec-item-error';
                const head = item.querySelector('.exec-head');
                if (head) {
                    const icon = head.querySelector('.exec-icon');
                    if (icon) {
                        icon.outerHTML = '<svg class="exec-icon exec-icon-error" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
                    }
                }
                const s=item._status || item.querySelector('.exec-status');
                if (s) s.textContent=' 失败';
            }
            else { const r=document.createElement('div'); r.className='progress-line exec-line-error'; r.innerHTML=`<svg class="exec-icon exec-icon-error" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ${k} 执行失败`; list.appendChild(r); }
            toolMap.delete(k);
        } else if (phase === 'files') {
            // 去重：检查是否已经显示过相同的文件列表
            const filesKey = (evt.files || []).sort().join(',');
            const existingFilesLines = Array.from(list.querySelectorAll('.exec-line-files'));
            const isDuplicate = existingFilesLines.some(line => {
                const text = line.textContent || '';
                const match = text.match(/生成文件:\s*(.+)$/);
                if (!match) return false;
                const existingFiles = match[1].split(',').map(f => f.trim()).sort().join(',');
                return existingFiles === filesKey;
            });

            if (!isDuplicate) {
                const r = document.createElement('div');
                r.className='progress-line exec-line-files';
                r.innerHTML = `<svg class="exec-icon exec-icon-files" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12V7z"/><path d="M14 3v4h4"/></svg> 生成文件: ${(evt.files||[]).join(', ')}`;
                list.appendChild(r);
            }
        } else if (phase === 'info') {
            if (evt.message) { const r=document.createElement('div'); r.className='progress-line'; r.textContent = evt.message; list.appendChild(r); }
        }
        this.smartScroll();
    }

    appendFilesGenerated(iter, files) {
        if (!files || !files.length) return;
        this.appendExec(iter, {phase:'files', files});
    }

    finishIter(iter, status) {
        const key = String(iter || '1');
        const wrap = this._iterBoxes.get(key);
        if (!wrap) return;

        // 检查该轮次是否有实质内容（工具执行、思考过程等）
        const hasExecList = wrap.querySelector('.exec-list');
        const hasThinking = wrap.querySelector('.thinking-box');
        const hasProgress = wrap.querySelector('.progress-box');

        // 如果没有任何实质内容，移除这个空容器
        if (!hasExecList && !hasThinking && !hasProgress) {
            console.log(`[UI] 第${key}轮没有实质内容，移除空容器`);
            wrap.remove();
            this._iterBoxes.delete(key);
            return;
        }

        // 停止thinking-label的动画（标记为completed）
        const thinkingLabel = wrap.querySelector('.thinking-label');
        if (thinkingLabel) {
            thinkingLabel.classList.add('completed');
        }

        // 也停止tool-call-text-label的动画
        const toolCallLabel = wrap.querySelector('.tool-call-text-label');
        if (toolCallLabel) {
            toolCallLabel.classList.add('completed');
        }

        const dot = wrap._statusDot;
        if (!dot) return;
        dot.classList.remove('spinner','success','failed');
        const s = String(status||'').toLowerCase();
        if (s.includes('fail') || s.includes('error')) dot.classList.add('failed');
        else dot.classList.add('success');
    }

    /**
     * 显示进度指示器
     */
    showProgress(message, status, iter) {
        const key = String(iter || '1');
        if (!this._progressByIter) this._progressByIter = new Map();
        let rec = this._progressByIter.get(key);
        if (!rec) {
            // ensure iter container exists
            this.startThinkingSection(key); // also sets up iter-box
            // create progress box under this iter
            const wrap = this._iterBoxes.get(key) || this.chatMessages;
            const progressBox = document.createElement('div');
            progressBox.className = 'progress-box';
            const header = document.createElement('div'); header.className = 'progress-header';
            const left = document.createElement('div'); left.className = 'progress-left';
            const dot = document.createElement('span'); dot.className = 'progress-dot spinner';
            const title = document.createElement('span'); title.className = 'progress-title'; title.textContent = '执行中…';
            left.appendChild(dot); left.appendChild(title);
            const progressContent = document.createElement('div'); progressContent.className = 'progress-content'; progressContent.style.display = 'block';
            const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'progress-toggle'; toggle.textContent = '隐藏详情';
            toggle.addEventListener('click', (e) => {
                e.preventDefault(); e.stopPropagation();
                const currentDisplay = window.getComputedStyle(progressContent).display;
                const hidden = currentDisplay === 'none';
                progressContent.style.display = hidden ? 'block' : 'none';
                toggle.textContent = hidden ? '隐藏详情' : '显示详情';
            });
            header.appendChild(left); header.appendChild(toggle);
            progressBox.appendChild(header); progressBox.appendChild(progressContent);
            wrap.appendChild(progressBox);
            rec = { box: progressBox, header, left, dot, title, toggle, content: progressContent };
            this._progressByIter.set(key, rec);
            this._lastProgressIter = key;
        }
        // 状态更新
        if (status) this.updateProgressStatus(status, iter);
        // 追加行
        if (message) {
            const line = document.createElement('div');
            line.className = 'progress-line';
            // 使用innerHTML以支持SVG图标等HTML内容
            line.innerHTML = message;
            rec.content.appendChild(line);
        }
        this.smartScroll();
    }

    updateProgressStatus(status, iter) {
        const key = iter ? String(iter) : (this._lastProgressIter || null);
        let rec = null;
        if (key && this._progressByIter && this._progressByIter.has(key)) rec = this._progressByIter.get(key);
        else rec = this._progress || null;
        if (!rec) return;
        const s = String(status || '').toLowerCase();
        const { dot, title, content, toggle } = rec;

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
            // 移除所有thinking容器
            try {
                this.chatMessages.querySelectorAll('.thinking-box').forEach(el => el.remove());
            } catch (_) {
                // Ignore errors
            }
            this._thinkingSections = new Map();
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
                    // 修复markdown中的相对路径图片链接
                    this.fixMarkdownImagePaths(resultContent);
                } else {
                    resultContent.textContent = result.result || '';
                }
            }

            // 添加复制按钮：
            // 1) 整条消息复制
            this.attachCopyChip(resultBox, () => {
                // 复制纯文本，避免复制HTML
                return resultContent.innerText || '';
            }, '复制');
            // 2) 代码块复制
            this.enhanceMarkdownCopy(resultContent);
            // 3) Markdown表格复制（CSV/MD）
            this.enhanceMarkdownTables(resultContent);

            // 文件加载由外部通过loadMultipleFiles显式调用
            // 不再使用checkAndLoadFiles的正则匹配逻辑
        }

        // 保存到历史
        this.chatHistory.push({
            role: 'assistant',
            content: result.result || result.error
        });

        this.scrollToBottom();

        // 返回resultBox供外部添加反馈按钮
        return resultBox;
    }

    /**
     * 为assistant消息添加反馈按钮
     * @param {HTMLElement} messageBox - 消息容器元素
     * @param {string} messageId - 消息ID
     * @param {string} existingFeedback - 已有的反馈("positive"/"neutral"/"negative")
     */
    attachFeedbackButtons(messageBox, messageId, existingFeedback = null) {
        if (!messageBox || !messageId) return;

        // 检查是否已经有反馈按钮
        if (messageBox.querySelector('.message-feedback')) return;

        // 创建反馈容器
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'message-feedback';
        feedbackDiv.dataset.messageId = messageId;

        // 添加标签
        const label = document.createElement('span');
        label.className = 'message-feedback-label';
        label.textContent = '这次回答对您有帮助吗？';
        feedbackDiv.appendChild(label);

        // 创建三个反馈按钮（使用SVG图标）
        const buttons = [
            {
                value: 'positive',
                label: '满意',
                class: 'positive',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>'
            },
            {
                value: 'neutral',
                label: '一般',
                class: 'neutral',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="8" y1="15" x2="16" y2="15"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>'
            },
            {
                value: 'negative',
                label: '不满意',
                class: 'negative',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>'
            }
        ];

        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.className = `feedback-btn ${btn.class}`;
            button.dataset.feedback = btn.value;
            button.title = btn.label; // tooltip
            button.innerHTML = btn.icon;

            // 如果有已存在的反馈，标记选中状态并禁用
            if (existingFeedback && existingFeedback === btn.value) {
                button.classList.add('selected');
                button.disabled = true;
            }

            button.addEventListener('click', async () => {
                await this.handleFeedbackClick(feedbackDiv, messageId, btn.value);
            });

            feedbackDiv.appendChild(button);
        });

        // 添加感谢消息（初始隐藏）
        const thanks = document.createElement('span');
        thanks.className = 'feedback-thanks';
        thanks.textContent = '✓ 感谢您的反馈！';
        feedbackDiv.appendChild(thanks);

        // 添加到消息框
        messageBox.appendChild(feedbackDiv);
    }

    /**
     * 处理反馈按钮点击
     */
    async handleFeedbackClick(feedbackDiv, messageId, feedbackValue) {
        try {
            // 禁用所有按钮
            const buttons = feedbackDiv.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => btn.disabled = true);

            // 发送反馈到后端
            const conversationId = window.currentConversationId || '';
            const response = await fetch(`/conversations/${conversationId}/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message_id: messageId,
                    feedback: feedbackValue
                })
            });

            if (response.ok) {
                // 标记选中的按钮
                buttons.forEach(btn => {
                    if (btn.dataset.feedback === feedbackValue) {
                        btn.classList.add('selected');
                    }
                });

                // 显示感谢消息
                const thanks = feedbackDiv.querySelector('.feedback-thanks');
                if (thanks) {
                    thanks.classList.add('show');
                    // 3秒后隐藏感谢消息
                    setTimeout(() => {
                        thanks.classList.remove('show');
                    }, 3000);
                }

                console.log(`[UI] 反馈已提交: ${feedbackValue}`);
            } else {
                // 失败时重新启用按钮
                buttons.forEach(btn => btn.disabled = false);
                console.error('[UI] 提交反馈失败');
            }
        } catch (error) {
            console.error('[UI] 提交反馈出错:', error);
            // 重新启用按钮
            const buttons = feedbackDiv.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => btn.disabled = false);
        }
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

        // 打字机渲染完成后，修复markdown中的相对路径图片链接
        if (typeof marked !== 'undefined') {
            this.fixMarkdownImagePaths(element);
        }
    }

    /**
     * 修复markdown渲染后的图片相对路径
     * 将 ![img](filename.png) 渲染出的 <img src="filename.png"> 修正为 <img src="/outputs/{conversationId}/filename.png">
     */
    fixMarkdownImagePaths(element) {
        if (!element) return;

        // 查找所有img标签
        const images = element.querySelectorAll('img');

        images.forEach(img => {
            const originalSrc = img.getAttribute('src');

            // 只处理相对路径（不是http://或https://开头，也不是/开头）
            if (originalSrc &&
                !originalSrc.startsWith('http://') &&
                !originalSrc.startsWith('https://') &&
                !originalSrc.startsWith('/')) {

                // 构造完整的URL路径
                const fullUrl = `${this.outputsBaseUrl}/${encodeURIComponent(originalSrc)}`;
                console.log(`[UI] 修复图片路径: ${originalSrc} → ${fullUrl}`);
                img.setAttribute('src', fullUrl);

                // 添加cache-bust参数（防止缓存问题）
                const cacheBustUrl = `${fullUrl}?t=${Date.now()}`;
                img.setAttribute('src', cacheBustUrl);
            }
        });
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

        // 匹配图片文件 - 修复正则,确保能匹配中文+数字的组合（扩展: svg/gif/webp/avif）
        const imgPattern = /([\u4e00-\u9fa5\w\-_]+\.(?:png|jpg|jpeg|svg|gif|webp|avif))/gi;
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
                } else if (filename.toLowerCase().endsWith('.pptx')) {
                    console.log(`[UI] Adding PPTX tab: ${filename}`);
                    this.addFileTab(filename, 'pptx', key);
                } else if (filename.match(/\.(doc|docx)$/i)) {
                    console.log(`[UI] Adding Word tab: ${filename}`);
                    this.addFileTab(filename, 'word', key);
                } else if (filename.match(/\.(png|jpg|jpeg|svg|gif|webp|avif)$/i)) {
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
                } else if (filename.match(/\.(txt|log|yaml|yml|toml|ini|cfg|conf|xml|py|js|ts|tsx|jsx|java|go|rs|c|cpp|h|cs|rb|php|sh|bash|zsh|sql)$/i)) {
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
            element: null,
            tabElement: null  // 标签元素（将在renderFileTabsGrouped中创建）
        };

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
        } else if (type === 'pptx') {
            this.loadPptxIntoContainer(filename, contentDiv);
        } else if (type === 'word') {
            this.loadWordIntoContainer(filename, contentDiv);
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
        } else if (type === 'zip') {
            this.loadZipIntoContainer(filename, contentDiv);
        } else if (type === 'jsonl') {
            this.loadJsonlIntoContainer(filename, contentDiv);
        } else if (type === 'json') {
            this.loadJsonIntoContainer(filename, contentDiv);
        } else if (type === 'markdown') {
            this.loadMarkdownIntoContainer(filename, contentDiv);
        }

        // 重新渲染分组视图
        this.renderFileTabsGrouped();

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
            const tabFileIndex = parseInt(tab.dataset.fileIndex);
            if (tabFileIndex === fileIndex) {
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
     * 按文件类型分组渲染文件标签
     */
    renderFileTabsGrouped() {
        // 清空现有标签
        this.fileTabs.innerHTML = '';

        // SVG 图标生成函数（与 workspace 保持一致）
        const icon = (p) => `<svg class="file-group-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;

        // 定义文件分组配置（与 workspace 保持一致）
        const groups = {
            image: {
                label: 'Images',
                icon: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-4-4-3 3-2-2-4 4"/>'),
                types: ['image'],
                files: []
            },
            video: {
                label: 'Videos',
                icon: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><polygon points="10 8 16 12 10 16 10 8"/>'),
                types: ['video'],
                files: []
            },
            table: {
                label: 'Sheets',
                icon: icon('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h10M7 12h10M7 17h10"/>'),
                types: ['excel'],
                files: []
            },
            document: {
                label: 'Docs',
                icon: icon('<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12V7z"/><path d="M14 3v4h4"/>'),
                types: ['word', 'pdf', 'markdown'],
                files: []
            },
            audio: {
                label: 'Audio',
                icon: icon('<path d="M9 18V6l8-2v12"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="16" r="2"/>'),
                types: ['audio'],
                files: []
            },
            code: {
                label: 'Code',
                icon: icon('<polyline points="7 8 3 12 7 16"/><polyline points="17 8 21 12 17 16"/>'),
                types: ['text', 'json', 'jsonl', 'html'],
                files: []
            },
            webpage: {
                label: 'Web',
                icon: icon('<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'),
                types: ['webpage', 'pptx'],
                files: []
            },
            other: {
                label: 'Others',
                icon: icon('<path d="M3 7h5l2 3h11v9a2 2 0 0 1-2 2H3z"/><path d="M3 7V5a2 2 0 0 1 2-2h6l2 2h6a2 2 0 0 1 2 2v3"/>'),
                types: [],
                files: []
            }
        };

        // 将文件分类到各个分组
        this.files.forEach((file, index) => {
            file.index = index;  // 保存原始索引
            let matched = false;
            for (const groupKey in groups) {
                if (groupKey === 'other') continue; // 跳过"其他"分组，最后处理
                if (groups[groupKey].types.includes(file.type)) {
                    groups[groupKey].files.push(file);
                    matched = true;
                    break;
                }
            }
            // 未匹配到任何分组的文件归入"其他"
            if (!matched) {
                groups.other.files.push(file);
            }
        });

        // 渲染各个分组
        for (const groupKey in groups) {
            const group = groups[groupKey];
            if (group.files.length === 0) continue;

            // 创建分组标题
            const groupHeader = document.createElement('div');
            groupHeader.className = 'file-group-header';
            groupHeader.innerHTML = `
                <span class="file-group-collapse-icon">▼</span>
                <span class="file-group-title">${group.icon}<span>${group.label}</span></span>
                <span class="file-group-count">${group.files.length}</span>
            `;
            this.fileTabs.appendChild(groupHeader);

            // 创建该分组的文件列表容器
            const groupList = document.createElement('div');
            groupList.className = 'file-group-list';

            // 创建文件标签
            group.files.forEach(file => {
                const tab = document.createElement('div');
                tab.className = 'file-tab';
                tab.dataset.fileIndex = file.index;

                const name = document.createElement('span');
                name.className = 'file-tab-name';
                name.textContent = file.filename;
                name.title = file.filename;

                tab.appendChild(name);

                // 点击事件
                tab.addEventListener('click', () => {
                    this.switchToFile(file.index);
                });

                // 保存tab元素引用
                file.tabElement = tab;

                groupList.appendChild(tab);
            });

            this.fileTabs.appendChild(groupList);

            // 添加折叠/展开功能
            groupHeader.addEventListener('click', () => {
                const icon = groupHeader.querySelector('.file-group-collapse-icon');
                if (groupList.style.display === 'none') {
                    groupList.style.display = 'flex';
                    icon.textContent = '▼';
                } else {
                    groupList.style.display = 'none';
                    icon.textContent = '▶';
                }
            });
        }

        // 更新当前激活的标签样式
        const tabs = this.fileTabs.querySelectorAll('.file-tab');
        tabs.forEach((tab) => {
            const tabFileIndex = parseInt(tab.dataset.fileIndex);
            if (tabFileIndex === this.currentFileIndex) {
                tab.classList.add('active');
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

        // 恢复center-mode（对话框居中，预览区滑出）
        const mainContainer = document.querySelector('.main-container');
        if (mainContainer) {
            mainContainer.classList.add('center-mode');
        }
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
            // 强制要求会话ID，不允许兜底
            if (!this.currentConvId) {
                container.innerHTML = '<div style="padding:20px; text-align:center; color:#999;">错误: 当前无会话ID，无法加载文件</div>';
                console.error('[UI] 无会话ID，无法加载Excel:', filename);
                return;
            }

            const encodedFilename = encodeURIComponent(filename);
            // 如果前端未加载SheetJS, 使用后端预览接口
            if (typeof XLSX === 'undefined') {
                const previewUrl = `/preview/excel/${encodeURIComponent(this.currentConvId)}/${encodedFilename}?t=${Date.now()}`;
                const preview = await fetch(previewUrl);
                if (!preview.ok) throw new Error(`HTTP ${preview.status}`);
                const data = await preview.json();

                container.innerHTML = `
                    <div class="excel-preview-container">
                        <div class="preview-info">
                            <div style="display:flex; justify-content: space-between; align-items:center;">
                                <h4>${filename}</h4>
                                <div style="display:flex; gap:12px; align-items:center;">
                                    <button class="copy-inline-btn" data-action="copy-table-md" title="Copy Markdown Table"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy MD</span></button>
                                    <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                                    <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                                    <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                                </div>
                            </div>
                        </div>
                        <div class="excel-table-wrapper">${data.html || '<div style="padding:16px;">No preview</div>'}</div>
                    </div>
                `;
                // 复制表格（CSV）
                const copyBtn = container.querySelector('[data-action="copy-table"]');
                if (copyBtn) {
                    copyBtn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(container);
                        const csv = this._tableToCSV(table, ',');
                        const ok = await this.copyText(csv);
                        const oldTitle = copyBtn.title;
                        copyBtn.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtn.title = oldTitle || 'Copy CSV'; }, 1200);
                    });
                }
                const copyBtnTsv = container.querySelector('[data-action="copy-table-tsv"]');
                if (copyBtnTsv) {
                    copyBtnTsv.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(container);
                        const tsv = this._tableToCSV(table, '\t');
                        const ok = await this.copyText(tsv);
                        const oldTitle = copyBtnTsv.title;
                        copyBtnTsv.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtnTsv.title = oldTitle || 'Copy TSV'; }, 1200);
                    });
                }
                const copyBtnMd = container.querySelector('[data-action="copy-table-md"]');
                if (copyBtnMd) {
                    copyBtnMd.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(container);
                        const md = this._tableToMarkdown(table);
                        const ok = await this.copyText(md);
                        const oldTitle = copyBtnMd.title;
                        copyBtnMd.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtnMd.title = oldTitle || 'Copy Markdown Table'; }, 1200);
                    });
                }
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
                        <button class="copy-inline-btn" data-action="copy-table-md" title="Copy Markdown Table"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy MD</span></button>
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                        <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                        <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                    </div>
                </div>
            `;
            excelDiv.appendChild(headerDiv);
            // 复制表格（CSV/TSV/Markdown）
            const hdrCsv = headerDiv.querySelector('[data-action="copy-table"]');
            if (hdrCsv) hdrCsv.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const csv = this._tableToCSV(table, ',');
                const ok = await this.copyText(csv);
                const old = hdrCsv.title; hdrCsv.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { hdrCsv.title = old || 'Copy CSV'; }, 1200);
            });
            const hdrTsv = headerDiv.querySelector('[data-action="copy-table-tsv"]');
            if (hdrTsv) hdrTsv.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const tsv = this._tableToCSV(table, '\t');
                const ok = await this.copyText(tsv);
                const old = hdrTsv.title; hdrTsv.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { hdrTsv.title = old || 'Copy TSV'; }, 1200);
            });
            const hdrMd = headerDiv.querySelector('[data-action="copy-table-md"]');
            if (hdrMd) hdrMd.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const md = this._tableToMarkdown(table);
                const ok = await this.copyText(md);
                const old = hdrMd.title; hdrMd.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { hdrMd.title = old || 'Copy Markdown Table'; }, 1200);
            });

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
        // 强制要求会话ID，不允许兜底
        if (!this.currentConvId) {
            container.innerHTML = '<div style="padding:20px; text-align:center; color:#999;">错误: 当前无会话ID，无法加载文件</div>';
            console.error('[UI] 无会话ID，无法加载音频:', filename);
            return;
        }

        const encoded = encodeURIComponent(filename);
        const bust = `?t=${Date.now()}`;
        const streamSrc = `/stream/${encodeURIComponent(this.currentConvId)}/${encoded}${bust}`;
        const directSrc = `${this.outputsBaseUrl}/${encoded}${bust}`;

        // 根据文件扩展名确定MIME类型
        const ext = filename.toLowerCase().split('.').pop();
        const mimeTypes = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'm4a': 'audio/mp4',
            'aac': 'audio/aac',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac'
        };
        const mimeType = mimeTypes[ext] || 'audio/mpeg';

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
                        <source src="${streamSrc}" type="${mimeType}" />
                        <source src="${directSrc}" type="${mimeType}" />
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
        // 强制要求会话ID，不允许兜底
        if (!this.currentConvId) {
            container.innerHTML = '<div style="padding:20px; text-align:center; color:#999;">错误: 当前无会话ID，无法加载文件</div>';
            console.error('[UI] 无会话ID，无法加载视频:', filename);
            return;
        }

        const encoded = encodeURIComponent(filename);
        const streamSrc = `/stream/${encodeURIComponent(this.currentConvId)}/${encoded}?t=${Date.now()}`;
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

    /** 加载PPTX到指定容器（下载预览） */
    loadPptxIntoContainer(filename, container) {
        // 强制要求会话ID，不允许兜底
        if (!this.currentConvId) {
            container.innerHTML = '<div style="padding:20px; text-align:center; color:#999;">错误: 当前无会话ID，无法加载文件</div>';
            console.error('[UI] 无会话ID，无法加载PPTX:', filename);
            return;
        }

        const encoded = encodeURIComponent(filename);
        const downloadUrl = `${this.outputsBaseUrl}/${encoded}`;

        container.innerHTML = `
            <div class="pptx-preview-container">
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items:center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${downloadUrl}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div style="padding:60px 40px; text-align:center; background:var(--panel); border:1px solid var(--border); border-radius:8px; margin-top:16px;">
                    <div style="font-size:64px; margin-bottom:24px;">📊</div>
                    <div style="font-size:18px; font-weight:500; margin-bottom:12px; color:var(--text);">${filename}</div>
                    <div style="font-size:14px; color:var(--muted); margin-bottom:32px;">PowerPoint 演示文稿</div>
                    <a href="${downloadUrl}" download="${filename}"
                       style="display:inline-block; padding:14px 32px; background:#007bff; color:white;
                              text-decoration:none; border-radius:6px; font-size:15px; font-weight:500;
                              transition: background 0.2s;">
                        📥 下载查看
                    </a>
                    <div style="margin-top:24px; font-size:13px; color:var(--muted); line-height:1.6;">
                        PowerPoint 文件需要下载后使用 Microsoft PowerPoint、<br>
                        LibreOffice Impress 或其他兼容软件查看
                    </div>
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

    /** 加载Word文件到指定容器（使用后端mammoth转换） */
    async loadWordIntoContainer(filename, container) {
        // 强制要求会话ID，不允许兜底
        if (!this.currentConvId) {
            container.innerHTML = '<div style="padding:20px; text-align:center; color:#999;">错误: 当前无会话ID，无法加载文件</div>';
            console.error('[UI] 无会话ID，无法加载Word:', filename);
            return;
        }

        const encoded = encodeURIComponent(filename);
        const downloadUrl = `${this.outputsBaseUrl}/${encoded}`;

        // 显示加载中
        container.innerHTML = `
            <div class="word-preview-container">
                <div class="preview-info">
                    <div style="display:flex; justify-content: space-between; align-items:center;">
                        <h4>${filename}</h4>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${downloadUrl}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div style="padding:20px; text-align:center; color:var(--muted);">
                    <div style="margin-bottom:12px;">📄 正在加载Word文档...</div>
                </div>
            </div>
        `;

        try {
            // 调用后端API转换Word为HTML
            const previewUrl = `/preview/word/${encodeURIComponent(this.currentConvId)}/${encoded}`;
            const response = await fetch(previewUrl);

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            // 渲染转换后的HTML
            container.innerHTML = `
                <div class="word-preview-container">
                    <div class="preview-info">
                        <div style="display:flex; justify-content: space-between; align-items:center;">
                            <h4>${filename}</h4>
                            <div style="display:flex; gap:12px; align-items:center;">
                                <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                                <a href="${downloadUrl}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                                <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                            </div>
                        </div>
                    </div>
                    ${data.warnings && data.warnings.length > 0 ? `
                        <div style="padding:10px 16px; background:#fff3cd; border:1px solid #ffc107; border-radius:8px; margin:12px 16px; font-size:13px; color:#856404;">
                            ⚠️ 转换警告: ${data.warnings.join('; ')}
                        </div>
                    ` : ''}
                    <div class="word-content markdown-content" style="padding:16px; background:var(--bg); border:1px solid var(--border); border-radius:8px; margin:12px; max-height:70vh; overflow:auto;">
                        ${data.html || '<div style="padding:20px; text-align:center; color:var(--muted);">文档内容为空</div>'}
                    </div>
                </div>
            `;

            // 绑定按钮事件
            const saveBtn = container.querySelector('.workspace-save');
            if (saveBtn) {
                saveBtn.addEventListener('click', (e) => { e.preventDefault(); this.workspaceSave(filename, saveBtn); });
            }
            const delBtn = container.querySelector('.file-delete');
            if (delBtn) {
                delBtn.addEventListener('click', async (e) => { e.preventDefault(); await this.deleteFile(filename); });
            }

        } catch (error) {
            console.error('[UI] Word预览失败:', error);
            container.innerHTML = `
                <div class="word-preview-container">
                    <div class="preview-info">
                        <div style="display:flex; justify-content: space-between; align-items:center;">
                            <h4>${filename}</h4>
                            <div style="display:flex; gap:12px; align-items:center;">
                                <a href="${downloadUrl}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            </div>
                        </div>
                    </div>
                    <div class="error-box" style="margin:16px;">
                        <span class="error-label">预览失败:</span>
                        <div>${error.message || error}</div>
                        <div style="margin-top:12px; font-size:13px;">请下载文件后使用 Microsoft Word、LibreOffice 或其他兼容软件查看。</div>
                    </div>
                </div>
            `;
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
                            <button class="copy-inline-btn" data-action="copy-text" title="Copy"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy</span></button>
                            <button class="copy-inline-btn" data-action="copy-text-selection" title="Copy Selection"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy Selection</span></button>
                            <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <pre class="text-preview" style="white-space: pre-wrap; word-break: break-word; padding: 12px; background: var(--panel); border:1px solid var(--border); border-radius:8px; max-height: 60vh; overflow:auto;">${this.escapeHtml(text)}</pre>
            `;
            // 绑定复制按钮
            const copyBtn = container.querySelector('[data-action="copy-text"]');
            if (copyBtn) {
                copyBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const ok = await this.copyText(text);
                    const oldTitle = copyBtn.title;
                    copyBtn.title = ok ? 'Copied' : 'Failed';
                    setTimeout(() => { copyBtn.title = oldTitle || 'Copy'; }, 1200);
                });
            }
            // 复制选中片段
            const copySelBtn = container.querySelector('[data-action="copy-text-selection"]');
            if (copySelBtn) {
                const pre = container.querySelector('.text-preview');
                copySelBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    let s = '';
                    try {
                        const sel = window.getSelection();
                        if (sel && sel.toString()) {
                            const an = sel.anchorNode, fn = sel.focusNode;
                            if (pre && an && fn && pre.contains(an) && pre.contains(fn)) {
                                s = sel.toString();
                            }
                        }
                    } catch (_){ }
                    if (!s) {
                        const old = copySelBtn.title;
                        copySelBtn.title = 'No selection';
                        setTimeout(() => { copySelBtn.title = old || 'Copy Selection'; }, 1200);
                        return;
                    }
                    const ok = await this.copyText(s);
                    const oldTitle = copySelBtn.title;
                    copySelBtn.title = ok ? 'Copied' : 'Failed';
                    setTimeout(() => { copySelBtn.title = oldTitle || 'Copy Selection'; }, 1200);
                });
            }

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

    /** 加载ZIP到指定容器 */
    async loadZipIntoContainer(filename, container) {
        const encoded = encodeURIComponent(filename);

        // 先显示基本信息和加载提示
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
            <div id="zip-content-area" style="padding: 20px;">
                <div style="text-align:center; color: var(--muted); padding: 40px;">正在加载ZIP文件内容...</div>
            </div>
        `;

        // 绑定按钮
        const saveBtn = container.querySelector('.workspace-save');
        if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); this.workspaceSave(filename, saveBtn); });
        const delBtn = container.querySelector('.file-delete');
        if (delBtn) delBtn.addEventListener('click', async (e)=>{ e.preventDefault(); await this.deleteFile(filename); });

        // 获取ZIP文件内容列表
        try {
            const listUrl = `${this.outputsBaseUrl}/zip_list/${encoded}`;
            const resp = await fetch(listUrl);

            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}`);
            }

            const data = await resp.json();
            const contentArea = container.querySelector('#zip-content-area');

            if (!data.files || data.files.length === 0) {
                contentArea.innerHTML = '<div style="text-align:center; color: var(--muted); padding: 40px;">ZIP文件为空</div>';
                return;
            }

            // 格式化文件大小
            const formatSize = (bytes) => {
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            };

            // 渲染文件列表
            let html = `
                <div style="background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                    <div style="padding: 12px 16px; border-bottom: 1px solid var(--border); background: var(--bg); font-weight: 600; color: var(--text);">
                        ZIP文件内容（共 ${data.files.length} 个文件）
                    </div>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: var(--bg); border-bottom: 1px solid var(--border);">
                            <tr>
                                <th style="padding: 10px 16px; text-align: left; font-size: 13px; color: var(--muted); font-weight: 600;">文件名</th>
                                <th style="padding: 10px 16px; text-align: right; font-size: 13px; color: var(--muted); font-weight: 600; width: 120px;">大小</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            data.files.forEach((file, index) => {
                const bgColor = index % 2 === 0 ? 'var(--panel)' : 'var(--bg)';
                html += `
                    <tr style="background: ${bgColor}; border-bottom: 1px solid var(--border);">
                        <td style="padding: 10px 16px; font-size: 13px; color: var(--text); font-family: monospace;">
                            ${this.escapeHtml(file.name)}
                        </td>
                        <td style="padding: 10px 16px; text-align: right; font-size: 13px; color: var(--muted); font-family: monospace;">
                            ${formatSize(file.size)}
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;

            contentArea.innerHTML = html;

        } catch (err) {
            console.error('[UI] 加载ZIP内容失败:', err);
            const contentArea = container.querySelector('#zip-content-area');
            contentArea.innerHTML = `
                <div class="error-box">
                    <span class="error-label">错误:</span>
                    <div>无法加载ZIP文件内容: ${err.message}</div>
                    <div style="margin-top: 8px; font-size: 12px;">请下载文件后使用本地工具查看</div>
                </div>
            `;
        }
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
                            <button class="copy-inline-btn" data-action="copy-json" title="Copy"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy</span></button>
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <pre class="text-preview" style="white-space: pre; padding: 12px; background: var(--panel); border:1px solid var(--border); border-radius:8px; max-height: 60vh; overflow:auto;">${pretty}</pre>
            `;
            // 绑定复制按钮（复制原始JSON字符串，保持缩进）
            const copyBtn = container.querySelector('[data-action="copy-json"]');
            if (copyBtn) {
                const raw = JSON.stringify(obj, null, 2);
                copyBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const ok = await this.copyText(raw);
                    const oldTitle = copyBtn.title;
                    copyBtn.title = ok ? 'Copied' : 'Failed';
                    setTimeout(() => { copyBtn.title = oldTitle || 'Copy'; }, 1200);
                });
            }
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
                        <button class="copy-inline-btn" data-action="copy-markdown" title="Copy"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy</span></button>
                        <a href="#" class="link-button workspace-save" title="Save to Workspace"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M9 3v6h6"/><path d="M9 18h6"/></svg></span><span class="btn-text">Save</span></a>
                            <a href="${this.outputsBaseUrl}/${encoded}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                            <a href="#" class="link-button file-delete" title="Delete"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6v-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span><span class="btn-text">Delete</span></a>
                        </div>
                    </div>
                </div>
                <div class="markdown-content" style="padding:12px; border:1px solid var(--border); border-radius:8px; max-height:60vh; overflow:auto;">${html}</div>
            `;
            // 绑定复制按钮（复制原始Markdown文本）
            const copyBtn = container.querySelector('[data-action="copy-markdown"]');
            if (copyBtn) {
                copyBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const ok = await this.copyText(md);
                    const oldTitle = copyBtn.title;
                    copyBtn.title = ok ? 'Copied' : 'Failed';
                    setTimeout(() => { copyBtn.title = oldTitle || 'Copy'; }, 1200);
                });
            }
            // 代码块复制
            const mdContainer = container.querySelector('.markdown-content');
            this.enhanceMarkdownCopy(mdContainer);
            this.enhanceMarkdownTables(mdContainer);
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
                            <button class="copy-inline-btn" data-action="copy-jsonl" title="Copy"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy</span></button>
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

            // 绑定复制按钮（复制原始JSONL文本）
            const copyBtn = container.querySelector('[data-action="copy-jsonl"]');
            if (copyBtn) {
                copyBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const ok = await this.copyText(text);
                    const oldTitle = copyBtn.title;
                    copyBtn.title = ok ? 'Copied' : 'Failed';
                    setTimeout(() => { copyBtn.title = oldTitle || 'Copy'; }, 1200);
                });
            }

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
                            <div style=\"display:flex; gap:12px; align-items:center;\">
                        <button class=\"copy-inline-btn\" data-action=\"copy-table-md\" title=\"Copy Markdown Table\"><span class=\"btn-ico\">${this._copySvg()}</span><span class=\"btn-text\">Copy MD</span></button>
                                <a href=\"${this.outputsBaseUrl}/${encodedFilename}\" download=\"${filename}\" class=\"file-download\" title=\"Download\"><span class=\"btn-ico\"><svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 3v12\"/><path d=\"M8 11l4 4 4-4\"/><path d=\"M5 21h14\"/></svg></span><span class=\"btn-text\">Download</span></a>
                            </div>
                        </div>
                    </div>
                    <div class="excel-table-wrapper">${data.html || '<div style="padding:16px;">No preview</div>'}</div>
                `;
                this.previewContent.appendChild(excelDiv);
                // 复制表格（CSV/TSV/Markdown）
                const copyBtn = excelDiv.querySelector('[data-action="copy-table"]');
                if (copyBtn) {
                    copyBtn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(excelDiv);
                        const csv = this._tableToCSV(table, ',');
                        const ok = await this.copyText(csv);
                        const oldTitle = copyBtn.title;
                        copyBtn.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtn.title = oldTitle || 'Copy CSV'; }, 1200);
                    });
                }
                const copyBtnTsv2 = excelDiv.querySelector('[data-action="copy-table-tsv"]');
                if (copyBtnTsv2) {
                    copyBtnTsv2.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(excelDiv);
                        const tsv = this._tableToCSV(table, '\t');
                        const ok = await this.copyText(tsv);
                        const oldTitle = copyBtnTsv2.title;
                        copyBtnTsv2.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtnTsv2.title = oldTitle || 'Copy TSV'; }, 1200);
                    });
                }
                const copyBtnMd2 = excelDiv.querySelector('[data-action="copy-table-md"]');
                if (copyBtnMd2) {
                    copyBtnMd2.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const table = this._getVisibleExcelTable(excelDiv);
                        const md = this._tableToMarkdown(table);
                        const ok = await this.copyText(md);
                        const oldTitle = copyBtnMd2.title;
                        copyBtnMd2.title = ok ? 'Copied' : 'Failed';
                        setTimeout(() => { copyBtnMd2.title = oldTitle || 'Copy Markdown Table'; }, 1200);
                    });
                }
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
                    <div style="display:flex; gap:12px; align-items:center;">
                        <button class="copy-inline-btn" data-action="copy-table-md" title="Copy Markdown Table"><span class="btn-ico">${this._copySvg()}</span><span class="btn-text">Copy MD</span></button>
                    <a href="${this.outputsBaseUrl}/${encodedFilename}" download="${filename}" class="file-download" title="Download"><span class="btn-ico"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 21h14"/></svg></span><span class="btn-text">Download</span></a>
                    </div>
                </div>
            `;
            excelDiv.appendChild(headerDiv);
            // 复制表格（CSV/TSV/Markdown）
            const btnCsv = headerDiv.querySelector('[data-action="copy-table"]');
            if (btnCsv) btnCsv.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const csv = this._tableToCSV(table, ',');
                const ok = await this.copyText(csv);
                const old = btnCsv.title; btnCsv.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { btnCsv.title = old || 'Copy CSV'; }, 1200);
            });
            const btnTsv = headerDiv.querySelector('[data-action="copy-table-tsv"]');
            if (btnTsv) btnTsv.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const tsv = this._tableToCSV(table, '\\t');
                const ok = await this.copyText(tsv);
                const old = btnTsv.title; btnTsv.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { btnTsv.title = old || 'Copy TSV'; }, 1200);
            });
            const btnMd = headerDiv.querySelector('[data-action="copy-table-md"]');
            if (btnMd) btnMd.addEventListener('click', async (e) => {
                e.preventDefault();
                const table = this._getVisibleExcelTable(excelDiv);
                const md = this._tableToMarkdown(table);
                const ok = await this.copyText(md);
                const old = btnMd.title; btnMd.title = ok ? 'Copied' : 'Failed';
                setTimeout(() => { btnMd.title = old || 'Copy Markdown Table'; }, 1200);
            });

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
                            <button class="workspace-file-btn workspace-file-preview" title="Preview">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                    <circle cx="12" cy="12" r="3"/>
                                </svg>
                            </button>
                            <button class="workspace-file-btn workspace-file-delete" title="Delete">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="3 6 5 6 21 6"/>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                    <line x1="10" y1="11" x2="10" y2="17"/>
                                    <line x1="14" y1="11" x2="14" y2="17"/>
                                </svg>
                            </button>
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
                        try {
                            this.openFileByName(fileInfo.name);
                        } catch (e) {
                            try {
                                this.loadMultipleFiles([fileInfo.name]);
                            } catch(_) {
                                // Ignore errors
                            }
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
            const previewables = (data.files || []).filter(fn => /\.(png|jpg|jpeg|svg|gif|webp|avif|xlsx|pptx|html|mp3|wav|m4a|aac|ogg|flac|mp4|webm|mov|txt|md|log|yaml|yml|toml|ini|cfg|conf|xml|py|js|ts|tsx|jsx|java|go|rs|c|cpp|h|cs|rb|php|sh|bash|zsh|sql)$/i.test(fn));
            this.clearAllFiles();
            if (previewables.length) this.loadMultipleFiles(previewables);
        } catch (e) {
            console.warn('[UI] 刷新文件失败:', e);
        }
    }
}

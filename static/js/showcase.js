/**
 * Showcase模块 - 展示最佳实践案例
 */

class ShowcaseManager {
    constructor(ui) {
        this.ui = ui;
        this.cases = [];
        this.currentCase = null;

        // DOM元素
        this.buttonsContainer = document.getElementById('showcase-buttons');
        this.modal = document.getElementById('showcase-modal');
        this.modalOverlay = document.getElementById('showcase-modal-overlay');
        this.closeBtn = document.getElementById('showcase-modal-close');
        this.caseTitle = document.getElementById('showcase-case-title');
        this.caseDescription = document.getElementById('showcase-case-description');
        this.promptContent = document.getElementById('showcase-prompt-content');
        this.previewContainer = document.getElementById('showcase-preview-container');
        this.copyBtn = document.getElementById('showcase-copy-btn');
        this.tryBtn = document.getElementById('showcase-try-btn');

        this.init();
    }

    async init() {
        try {
            // 加载案例数据（添加时间戳防止缓存）
            const timestamp = new Date().getTime();
            const response = await fetch(`/static/data/showcase_cases.json?v=${timestamp}`);
            const data = await response.json();
            this.cases = data.cases;

            console.log('[Showcase] 加载案例数据:', this.cases); // 调试日志

            // 渲染showcase按钮
            this.renderButtons();

            // 绑定事件
            this.bindEvents();
        } catch (error) {
            console.error('[Showcase] 初始化失败:', error);
        }
    }

    renderButtons() {
        if (!this.cases || this.cases.length === 0) return;

        this.buttonsContainer.innerHTML = '';

        this.cases.forEach((caseItem, index) => {
            const chip = document.createElement('button');
            chip.className = 'showcase-chip';
            chip.dataset.caseId = caseItem.id;

            // 设置素雅渐变背景
            chip.style.setProperty('--gradient', caseItem.gradient);
            chip.style.backgroundImage = caseItem.gradient;
            chip.style.backgroundSize = '200% 200%';
            chip.style.animation = 'gradientShift 5s ease infinite';

            // 创建图标容器
            const iconSpan = document.createElement('span');
            iconSpan.className = 'showcase-chip-icon';
            iconSpan.innerHTML = caseItem.icon; // SVG字符串会被正确解析

            // 创建文本容器
            const textSpan = document.createElement('span');
            textSpan.className = 'showcase-chip-text';
            textSpan.textContent = caseItem.subtitle;

            chip.appendChild(iconSpan);
            chip.appendChild(textSpan);

            chip.addEventListener('click', () => this.showCase(caseItem));

            this.buttonsContainer.appendChild(chip);
        });
    }

    bindEvents() {
        // 关闭modal
        this.closeBtn?.addEventListener('click', () => this.closeModal());
        this.modalOverlay?.addEventListener('click', () => this.closeModal());

        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                this.closeModal();
            }
        });

        // 复制prompt
        this.copyBtn?.addEventListener('click', () => this.copyPrompt());

        // 试试按钮
        this.tryBtn?.addEventListener('click', () => this.tryPrompt());
    }

    async showCase(caseItem) {
        this.currentCase = caseItem;

        // 更新标题和描述
        if (this.caseTitle) this.caseTitle.textContent = caseItem.title;
        if (this.caseDescription) this.caseDescription.textContent = caseItem.description;
        if (this.promptContent) this.promptContent.textContent = caseItem.prompt;

        // 加载预览
        this.loadPreview(caseItem);

        // 显示modal
        this.modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    loadPreview(caseItem) {
        if (!this.previewContainer) return;

        const fileUrl = `/static/showcase/${caseItem.output_file}`;

        // 根据文件类型加载预览
        if (caseItem.output_type === 'video') {
            this.previewContainer.innerHTML = `
                <video controls autoplay style="width: 100%; height: 100%; object-fit: contain; background: #000;">
                    <source src="${fileUrl}" type="video/mp4">
                    您的浏览器不支持视频播放
                </video>
            `;
        } else if (caseItem.output_type === 'html') {
            this.previewContainer.innerHTML = `
                <iframe src="${fileUrl}" style="width: 100%; height: 100%; border: none;"></iframe>
            `;
        } else if (caseItem.output_type === 'pptx') {
            // PPTX使用Office Online Viewer
            const viewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(window.location.origin + fileUrl)}`;
            this.previewContainer.innerHTML = `
                <div style="padding: 20px; text-align: center;">
                    <p style="color: var(--muted); margin-bottom: 16px;">PPTX文件预览</p>
                    <a href="${fileUrl}" download="${caseItem.output_file}" class="showcase-btn showcase-btn-primary">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        下载查看
                    </a>
                </div>
            `;
        } else if (caseItem.output_type === 'word' || caseItem.output_type === 'docx') {
            // Word文档使用后端mammoth转换预览
            this.previewContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--muted);">📄 正在加载Word文档...</div>';

            // 调用后端API转换Word为HTML
            fetch(`/preview/showcase/word/${encodeURIComponent(caseItem.output_file)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        throw new Error(data.error);
                    }

                    // 渲染转换后的HTML（不显示转换警告）
                    this.previewContainer.innerHTML = `
                        <div class="word-preview-container">
                            <div class="word-content" style="background: #fff; padding: 40px; border-radius: 8px; max-width: 800px; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                                ${data.html}
                            </div>
                        </div>
                    `;
                })
                .catch(err => {
                    console.error('[Showcase] Word预览失败:', err);
                    const fileUrl = `/static/showcase/${caseItem.output_file}`;
                    this.previewContainer.innerHTML = `
                        <div style="text-align: center; padding: 40px; color: #999;">
                            <p style="margin-bottom: 16px;">Word文档预览失败: ${err.message}</p>
                            <a href="${fileUrl}" download="${caseItem.output_file}" class="showcase-btn showcase-btn-primary">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                    <polyline points="7 10 12 15 17 10"></polyline>
                                    <line x1="12" y1="15" x2="12" y2="3"></line>
                                </svg>
                                下载查看
                            </a>
                        </div>
                    `;
                });
        } else if (caseItem.output_type === 'pdf') {
            // PDF文档使用浏览器原生预览
            this.previewContainer.innerHTML = `
                <iframe src="${fileUrl}" style="width: 100%; height: 100%; border: none;"></iframe>
            `;
        }
    }

    async copyPrompt() {
        if (!this.currentCase) return;

        try {
            await navigator.clipboard.writeText(this.currentCase.prompt);

            // 临时改变按钮文本
            const originalText = this.copyBtn.innerHTML;
            this.copyBtn.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                已复制
            `;

            setTimeout(() => {
                this.copyBtn.innerHTML = originalText;
            }, 2000);
        } catch (error) {
            console.error('[Showcase] 复制失败:', error);
            alert('复制失败，请手动复制');
        }
    }

    tryPrompt() {
        if (!this.currentCase) return;

        // 关闭modal
        this.closeModal();

        // 填充prompt到输入框
        const chatInput = this.ui.chatInput;
        if (chatInput) {
            chatInput.value = this.currentCase.prompt;
            chatInput.focus();

            // 触发input事件以调整高度
            chatInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }

    closeModal() {
        this.modal.classList.remove('show');
        document.body.style.overflow = '';

        // 清理视频播放
        const video = this.previewContainer.querySelector('video');
        if (video) {
            video.pause();
        }
    }
}

// 导出供app.js使用
window.ShowcaseManager = ShowcaseManager;

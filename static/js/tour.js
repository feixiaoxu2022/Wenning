/**
 * 新手引导配置
 * 使用Driver.js实现产品导览功能
 */

class ProductTour {
    constructor() {
        console.log('[Tour] ProductTour实例创建中...');
        this.driver = null;
        this.hasSeenTour = this.checkTourStatus();
        this.autoAdvanceTimer = null; // 自动切换定时器
        this.autoAdvanceDelay = 5000; // 5秒后自动切换
        console.log('[Tour] 已看过引导:', this.hasSeenTour);
        this.initDriver();
    }

    /**
     * 清除自动切换定时器
     */
    clearAutoAdvanceTimer() {
        if (this.autoAdvanceTimer) {
            clearTimeout(this.autoAdvanceTimer);
            this.autoAdvanceTimer = null;
            console.log('[Tour] 清除自动切换定时器');
        }
    }

    /**
     * 启动自动切换定时器
     */
    startAutoAdvanceTimer() {
        // 先清除已有的定时器
        this.clearAutoAdvanceTimer();

        // 设置新的定时器
        this.autoAdvanceTimer = setTimeout(() => {
            if (this.driver) {
                console.log('[Tour] 自动切换到下一步');
                this.driver.moveNext();
            }
        }, this.autoAdvanceDelay);

        console.log('[Tour] 启动自动切换定时器 (5秒)');
    }

    /**
     * 检查用户是否已看过引导
     */
    checkTourStatus() {
        try {
            return localStorage.getItem('wenning_tour_completed') === 'true';
        } catch (e) {
            return false;
        }
    }

    /**
     * 标记引导已完成
     */
    markTourCompleted() {
        try {
            localStorage.setItem('wenning_tour_completed', 'true');
        } catch (e) {
            console.warn('[Tour] 无法保存引导状态');
        }
    }

    /**
     * 重置引导状态（用于测试或用户重新查看）
     */
    resetTourStatus() {
        try {
            localStorage.removeItem('wenning_tour_completed');
            this.hasSeenTour = false;
        } catch (e) {
            console.warn('[Tour] 无法重置引导状态');
        }
    }

    /**
     * 生成SVG图标HTML（内联样式，确保在Driver popover中正常显示）
     */
    icon(name) {
        const icons = {
            wave: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M5.5 8.5 L2 12"/><path d="m12 2-1.5 2.5L13 7l-1.5 2.5"/><path d="m18 6-1.5 2.5L19 11l-1.5 2.5"/><path d="M3 20v-4 4c0-1.7.7-3.3 2-4.5"/></svg>',
            plus: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M12 5v14M5 12h14"/></svg>',
            folder: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
            clock: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
            edit: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
            paperclip: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
            send: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>',
            cpu: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/></svg>',
            eye: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
            moon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>',
            message: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>',
            check: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:middle;margin-right:8px;"><path d="M20 6 9 17l-5-5"/></svg>'
        };
        return icons[name] || '';
    }

    /**
     * 初始化Driver实例
     */
    initDriver() {
        // 检查Driver.js是否加载（IIFE版本暴露为window.driver.js.driver）
        if (typeof window.driver === 'undefined' ||
            typeof window.driver.js === 'undefined' ||
            typeof window.driver.js.driver !== 'function') {
            console.error('[Tour] Driver.js未正确加载');
            console.error('[Tour] window.driver:', typeof window.driver);
            console.error('[Tour] window.driver.js:', typeof (window.driver && window.driver.js));
            return;
        }

        console.log('[Tour] Driver.js已加载，开始初始化');

        try {
            // Driver.js IIFE版本的正确调用方式
            this.driver = window.driver.js.driver({
            showProgress: true,
            showButtons: ['next', 'previous', 'close'],
            nextBtnText: '下一步',
            prevBtnText: '上一步',
            doneBtnText: '完成',
            closeBtnText: '跳过',
            progressText: '第 {{current}} 步，共 {{total}} 步',

            // 自定义样式
            popoverClass: 'wenning-tour-popover',

            // 步骤高亮后的回调 - 启动自动切换
            onHighlighted: (element, step, options) => {
                // 检查是否是最后一步（最后一步有popover但没有element，或者是最后的有element的步骤）
                const activeIndex = this.driver.getActiveIndex();
                const totalSteps = this.driver.getConfig().steps.length;
                const isLastStep = (activeIndex === totalSteps - 1);

                console.log('[Tour] 步骤高亮，当前步骤:', activeIndex + 1, '/', totalSteps);

                // 最后一步不启动自动切换
                if (!isLastStep) {
                    console.log('[Tour] 启动自动切换 (5秒)');
                    this.startAutoAdvanceTimer();
                } else {
                    console.log('[Tour] 最后一步，不启动自动切换');
                }
            },

            // 下一步按钮点击回调 - 清除自动切换（用户手动控制）
            onNextClick: (element, step, options) => {
                console.log('[Tour] 用户点击下一步');
                this.clearAutoAdvanceTimer();
            },

            // 上一步按钮点击回调 - 清除自动切换
            onPrevClick: (element, step, options) => {
                console.log('[Tour] 用户点击上一步');
                this.clearAutoAdvanceTimer();
            },

            // 关闭按钮点击回调
            onCloseClick: (element, step, options) => {
                console.log('[Tour] 用户点击关闭按钮');
                this.clearAutoAdvanceTimer();
                this.markTourCompleted();
                if (this.driver) {
                    this.driver.destroy();
                }
            },

            // 完成或跳过时的回调
            onDestroyStarted: () => {
                console.log('[Tour] 引导销毁开始');
                this.clearAutoAdvanceTimer();
                this.markTourCompleted();
                // 不要在这里调用destroy()，会导致清理不完全
                // Driver.js会自动完成销毁流程
            },

            // 销毁完成后的回调 - 恢复页面状态
            onDestroyed: () => {
                console.log('[Tour] 引导销毁完成，恢复页面状态');
                this.clearAutoAdvanceTimer(); // 清除可能残留的定时器

                // 强制刷新布局，确保所有元素恢复正常显示
                setTimeout(() => {
                    // 移除所有Driver.js可能添加的类名
                    document.querySelectorAll('.driver-highlighted-element, .driver-active-element, .driver-no-interaction').forEach(el => {
                        el.classList.remove('driver-highlighted-element', 'driver-active-element', 'driver-no-interaction');
                    });

                    // 完全移除所有元素上的内联样式（让CSS接管）
                    document.querySelectorAll('[style]').forEach(el => {
                        // 只清除Driver.js添加的样式属性
                        const style = el.style;
                        if (style.length > 0) {
                            // 保存可能需要保留的样式
                            const preservedStyles = {};

                            // 移除Driver.js相关的样式
                            style.removeProperty('pointer-events');
                            style.removeProperty('z-index');

                            // 如果没有其他样式了，直接移除style属性
                            if (style.length === 0) {
                                el.removeAttribute('style');
                            }
                        }
                    });

                    // 关键：检查并强制恢复正确的布局模式
                    const mainContainer = document.querySelector('.main-container');
                    const sidebar = document.querySelector('.conversations-sidebar');
                    const preview = document.querySelector('.preview-panel');
                    const fileTabsContainer = document.getElementById('file-tabs-container');

                    // 移除所有可能残留的内联样式，让CSS规则生效
                    if (sidebar) {
                        sidebar.removeAttribute('style');
                    }

                    if (preview) {
                        preview.removeAttribute('style');
                    }

                    if (mainContainer) {
                        // 先移除所有内联样式
                        mainContainer.removeAttribute('style');

                        // 关键修复：检查是否应该处于center-mode（没有文件时）
                        const hasFiles = fileTabsContainer && fileTabsContainer.classList.contains('has-files');
                        const shouldBeCenterMode = !hasFiles;
                        const isCenterMode = mainContainer.classList.contains('center-mode');

                        console.log('[Tour] 文件状态:', hasFiles ? '有文件' : '无文件');
                        console.log('[Tour] 应该是center-mode:', shouldBeCenterMode);
                        console.log('[Tour] 当前是center-mode:', isCenterMode);

                        // 强制恢复正确的center-mode状态
                        if (shouldBeCenterMode && !isCenterMode) {
                            console.log('[Tour] 强制添加center-mode类');
                            mainContainer.classList.add('center-mode');
                        } else if (!shouldBeCenterMode && isCenterMode) {
                            console.log('[Tour] 强制移除center-mode类');
                            mainContainer.classList.remove('center-mode');
                        }

                        console.log('[Tour] 布局状态已恢复');
                    }

                    // 额外清理：移除所有splitter和布局相关元素的内联样式
                    document.querySelectorAll('.v-splitter, .chat-panel, .file-tabs-container, .file-contents-container').forEach(el => {
                        el.removeAttribute('style');
                    });

                    // 清除Driver.js可能添加的aria属性
                    document.querySelectorAll('[aria-haspopup], [aria-expanded], [aria-controls]').forEach(el => {
                        el.removeAttribute('aria-haspopup');
                        el.removeAttribute('aria-expanded');
                        el.removeAttribute('aria-controls');
                    });

                    // 触发resize事件，让布局重新计算
                    window.dispatchEvent(new Event('resize'));

                    // 再次触发resize（某些浏览器需要两次）
                    setTimeout(() => {
                        window.dispatchEvent(new Event('resize'));
                    }, 50);

                    console.log('[Tour] 页面状态恢复完成');
                }, 100);
            },

            steps: this.getSteps()
            });
            console.log('[Tour] Driver初始化成功');
        } catch (error) {
            console.error('[Tour] Driver初始化失败:', error);
        }
    }

    /**
     * 获取引导步骤配置
     */
    getSteps() {
        return [
            {
                element: '.logo-container',
                popover: {
                    title: this.icon('wave') + '欢迎使用Wenning AI助手',
                    description: 'Wenning是您的智能助手，支持多模型对话、文件处理、代码执行等强大功能。让我带您快速了解各个功能区域。',
                    side: 'bottom',
                    align: 'start'
                }
            },
            {
                element: '#new-conversation-btn',
                popover: {
                    title: this.icon('plus') + '新建对话',
                    description: '点击这里创建新的对话。每个对话独立保存，您可以同时进行多个不同主题的讨论。',
                    side: 'right',
                    align: 'start'
                }
            },
            {
                element: '.workspace-panel',
                popover: {
                    title: this.icon('folder') + 'Workspace工作区',
                    description: '这里显示您保存的所有文件，按类型分类管理（图片、文档、表格等）。点击文件名可以快速预览和下载。',
                    side: 'right',
                    align: 'start'
                }
            },
            {
                element: '#history-toggle',
                popover: {
                    title: this.icon('clock') + '对话历史',
                    description: '点击这里查看所有历史对话记录。可以快速切换到之前的会话，继续之前的讨论。',
                    side: 'right',
                    align: 'end'
                }
            },
            {
                element: '#chat-input',
                popover: {
                    title: this.icon('edit') + '消息输入框',
                    description: '在这里输入您的问题或指令。Wenning支持多轮对话，能够理解上下文并给出准确回答。',
                    side: 'top',
                    align: 'center'
                }
            },
            {
                element: '.add-file-wrapper',
                popover: {
                    title: this.icon('paperclip') + '附件上传',
                    description: '点击这里可以上传文件（图片、Excel、Word、PDF等）。Wenning可以分析文档内容、处理表格数据、识别图片中的信息。',
                    side: 'top',
                    align: 'start'
                }
            },
            {
                element: '.send-btn',
                popover: {
                    title: this.icon('send') + '发送消息',
                    description: '输入完成后点击发送按钮（或按Enter键）即可提交。如果正在处理，这里会变成「停止」按钮。',
                    side: 'top',
                    align: 'end'
                }
            },
            {
                element: '#model-select',
                popover: {
                    title: this.icon('cpu') + '模型选择',
                    description: '这里可以切换不同的AI模型。不同模型有各自的特点：GPT-4擅长推理，Claude善于编程，Gemini支持超长上下文等。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                element: '.preview-panel',
                // 步骤开始前的回调：临时移除center-mode以显示预览区
                onHighlightStarted: () => {
                    const mainContainer = document.querySelector('.main-container');
                    if (mainContainer && mainContainer.classList.contains('center-mode')) {
                        mainContainer.classList.remove('center-mode');
                        mainContainer.dataset.tempCenterMode = 'true'; // 标记需要恢复
                        console.log('[Tour] 步骤9（预览区）：临时移除center-mode以高亮预览区');
                    }
                },
                // 步骤结束后的回调：立即恢复center-mode
                onDeselected: () => {
                    const mainContainer = document.querySelector('.main-container');
                    if (mainContainer && mainContainer.dataset.tempCenterMode === 'true') {
                        mainContainer.classList.add('center-mode');
                        delete mainContainer.dataset.tempCenterMode;
                        console.log('[Tour] 步骤9结束：恢复center-mode');
                    }
                },
                popover: {
                    title: this.icon('eye') + '文件预览区',
                    description: 'AI生成的文件会自动显示在这里。支持Excel表格、图片、代码、HTML等多种格式的实时预览。您可以直接复制、下载或保存到Workspace。',
                    side: 'left',
                    align: 'start'
                }
            },
            {
                element: '#theme-toggle',
                popover: {
                    title: this.icon('moon') + '主题切换',
                    description: '点击这里可以切换亮色/暗色主题，保护您的眼睛。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                element: '#feedback-btn',
                popover: {
                    title: this.icon('message') + '反馈与帮助',
                    description: '有任何问题或建议？点击这里提交反馈。您也可以随时点击右上角的帮助按钮重新查看本引导。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                popover: {
                    title: this.icon('check') + '准备好了吗？',
                    description: '恭喜您完成新手引导！现在开始与Wenning对话吧。记住：您可以随时通过右上角的帮助按钮重新查看本引导。祝您使用愉快！',
                    side: 'over',
                    // 最后一步的完成按钮回调
                    onNextClick: (element, step, options) => {
                        console.log('[Tour] 用户点击完成按钮');
                        this.markTourCompleted();
                        if (this.driver) {
                            this.driver.destroy();
                        }
                    }
                }
            }
        ];
    }

    /**
     * 启动引导
     */
    start() {
        console.log('[Tour] 尝试启动引导...');

        if (!this.driver) {
            console.warn('[Tour] Driver实例未初始化，尝试重新初始化');
            this.initDriver();
        }

        if (!this.driver) {
            console.error('[Tour] Driver实例仍然未初始化，无法启动引导');
            alert('引导功能初始化失败，请检查网络连接后刷新页面重试');
            return;
        }

        try {
            console.log('[Tour] 开始启动Driver引导');
            this.driver.drive();
            console.log('[Tour] Driver引导已启动');
        } catch (error) {
            console.error('[Tour] 启动引导失败:', error);
            alert('启动引导失败: ' + error.message);
        }
    }

    /**
     * 首次访问自动启动（需要在DOM完全加载后调用）
     */
    autoStartForFirstTime() {
        if (!this.hasSeenTour) {
            // 延迟1秒启动，确保页面渲染完成
            setTimeout(() => {
                this.start();
            }, 1000);
        }
    }
}

// 全局实例
let productTour = null;

// DOM加载完成后初始化
console.log('[Tour] 开始初始化全局ProductTour实例, document.readyState:', document.readyState);

if (document.readyState === 'loading') {
    console.log('[Tour] 等待DOMContentLoaded事件');
    document.addEventListener('DOMContentLoaded', () => {
        console.log('[Tour] DOMContentLoaded触发，创建ProductTour实例');
        productTour = new ProductTour();
        console.log('[Tour] 全局productTour实例已创建');
    });
} else {
    console.log('[Tour] DOM已加载，直接创建ProductTour实例');
    productTour = new ProductTour();
    console.log('[Tour] 全局productTour实例已创建');
}

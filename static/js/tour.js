/**
 * 新手引导配置
 * 使用Driver.js实现产品导览功能
 */

class ProductTour {
    constructor() {
        this.driver = null;
        this.hasSeenTour = this.checkTourStatus();
        this.initDriver();
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
     * 初始化Driver实例
     */
    initDriver() {
        if (typeof driver === 'undefined') {
            console.warn('[Tour] Driver.js未加载');
            return;
        }

        this.driver = driver({
            showProgress: true,
            showButtons: ['next', 'previous', 'close'],
            nextBtnText: '下一步',
            prevBtnText: '上一步',
            doneBtnText: '完成',
            closeBtnText: '跳过',
            progressText: '第 {{current}} 步，共 {{total}} 步',

            // 自定义样式
            popoverClass: 'wenning-tour-popover',

            // 完成或跳过时的回调
            onDestroyStarted: () => {
                this.markTourCompleted();
                if (this.driver) {
                    this.driver.destroy();
                }
            },

            steps: this.getSteps()
        });
    }

    /**
     * 获取引导步骤配置
     */
    getSteps() {
        return [
            {
                element: '.logo-container',
                popover: {
                    title: '欢迎使用Wenning AI助手 👋',
                    description: 'Wenning是您的智能助手，支持多模型对话、文件处理、代码执行等强大功能。让我带您快速了解各个功能区域。',
                    side: 'bottom',
                    align: 'start'
                }
            },
            {
                element: '.conversations-sidebar',
                popover: {
                    title: '对话历史 📚',
                    description: '这里显示您的所有对话记录。点击「新建对话」开始新的会话，点击历史记录可以切换到之前的对话。',
                    side: 'right',
                    align: 'start'
                }
            },
            {
                element: '#chat-input',
                popover: {
                    title: '消息输入框 ✍️',
                    description: '在这里输入您的问题或指令。Wenning支持多轮对话，能够理解上下文并给出准确回答。',
                    side: 'top',
                    align: 'center'
                }
            },
            {
                element: '.add-file-wrapper',
                popover: {
                    title: '附件上传 📎',
                    description: '点击这里可以上传文件（图片、Excel、Word、PDF等）。Wenning可以分析文档内容、处理表格数据、识别图片中的信息。',
                    side: 'top',
                    align: 'start'
                }
            },
            {
                element: '.send-btn',
                popover: {
                    title: '发送消息 🚀',
                    description: '输入完成后点击发送按钮（或按Enter键）即可提交。如果正在处理，这里会变成「停止」按钮。',
                    side: 'top',
                    align: 'end'
                }
            },
            {
                element: '#model-select',
                popover: {
                    title: '模型选择 🤖',
                    description: '这里可以切换不同的AI模型。不同模型有各自的特点：GPT-4擅长推理，Claude善于编程，Gemini支持超长上下文等。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                element: '.workspace-panel',
                popover: {
                    title: 'Workspace工作区 📁',
                    description: '这里显示您保存的所有文件，按类型分类管理（图片、文档、表格等）。点击文件名可以快速预览和下载。',
                    side: 'left',
                    align: 'start'
                }
            },
            {
                element: '.preview-panel',
                popover: {
                    title: '文件预览区 👁️',
                    description: 'AI生成的文件会自动显示在这里。支持Excel表格、图片、代码、HTML等多种格式的实时预览。您可以直接复制、下载或保存到Workspace。',
                    side: 'left',
                    align: 'start'
                }
            },
            {
                element: '#theme-toggle',
                popover: {
                    title: '主题切换 🌙',
                    description: '点击这里可以切换亮色/暗色主题，保护您的眼睛。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                element: '#feedback-btn',
                popover: {
                    title: '反馈与帮助 💬',
                    description: '有任何问题或建议？点击这里提交反馈。您也可以随时点击右上角的帮助按钮重新查看本引导。',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                popover: {
                    title: '准备好了吗？🎉',
                    description: '恭喜您完成新手引导！现在开始与Wenning对话吧。记住：您可以随时通过右上角的帮助按钮重新查看本引导。祝您使用愉快！',
                    side: 'over'
                }
            }
        ];
    }

    /**
     * 启动引导
     */
    start() {
        if (!this.driver) {
            console.warn('[Tour] Driver实例未初始化');
            return;
        }

        // 重新初始化以获取最新的步骤配置（防止DOM变化）
        this.initDriver();
        this.driver.drive();
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
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        productTour = new ProductTour();
    });
} else {
    productTour = new ProductTour();
}

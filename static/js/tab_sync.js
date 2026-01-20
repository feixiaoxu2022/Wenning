/**
 * 多标签页同步模块
 *
 * 功能：防止多个标签页在同一对话上同时发送消息，避免对话内容混乱
 *
 * 实现原理：
 * 1. 使用 localStorage 作为标签页间的通信机制
 * 2. 当标签页开始发送消息时，标记 "conv_{conv_id}:sending"
 * 3. 其他标签页通过 storage 事件监听到变化，检查是否冲突
 * 4. 如果检测到冲突，显示提示并禁用输入
 * 5. 消息发送完成后清除标记
 */

class TabSyncManager {
    constructor() {
        this.currentConvId = null;
        this.isSending = false;
        this.isBlocked = false;

        // 监听 localStorage 变化（其他标签页的操作）
        window.addEventListener('storage', (e) => this.handleStorageChange(e));

        // 页面可见性变化时重新检查状态
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkConflict();
            }
        });

        // 页面卸载时清理
        window.addEventListener('beforeunload', () => {
            if (this.isSending) {
                this.markSendingEnd();
            }
        });

        console.log('[TabSync] 初始化完成');
    }

    /**
     * 设置当前对话ID
     */
    setConversationId(convId) {
        const oldConvId = this.currentConvId;
        this.currentConvId = convId;

        // 切换对话时，检查新对话是否有冲突
        if (convId && convId !== oldConvId) {
            this.checkConflict();
        }
    }

    /**
     * 标记开始发送消息
     */
    markSendingStart() {
        if (!this.currentConvId) {
            console.warn('[TabSync] 无当前对话ID，跳过标记');
            return false;
        }

        // 先检查是否已经有其他标签页在发送
        if (this.checkConflict()) {
            console.warn('[TabSync] 检测到其他标签页正在发送，阻止当前操作');
            return false;
        }

        this.isSending = true;
        const key = `conv_${this.currentConvId}:sending`;
        const value = {
            tabId: this.getTabId(),
            timestamp: Date.now()
        };

        try {
            localStorage.setItem(key, JSON.stringify(value));
            console.log(`[TabSync] 标记发送开始: ${key}`);
            return true;
        } catch (e) {
            console.error('[TabSync] 标记失败:', e);
            return false;
        }
    }

    /**
     * 标记发送结束
     */
    markSendingEnd() {
        if (!this.currentConvId) {
            return;
        }

        this.isSending = false;
        const key = `conv_${this.currentConvId}:sending`;

        try {
            // 只有当前标签页的标记才能清除（避免误清其他标签页的标记）
            const stored = localStorage.getItem(key);
            if (stored) {
                const data = JSON.parse(stored);
                if (data.tabId === this.getTabId()) {
                    localStorage.removeItem(key);
                    console.log(`[TabSync] 清除发送标记: ${key}`);
                }
            }
        } catch (e) {
            console.error('[TabSync] 清除标记失败:', e);
        }

        // 清除阻塞状态
        if (this.isBlocked) {
            this.unblockInput();
        }
    }

    /**
     * 检查是否与其他标签页冲突
     * @returns {boolean} true表示有冲突
     */
    checkConflict() {
        if (!this.currentConvId) {
            return false;
        }

        const key = `conv_${this.currentConvId}:sending`;
        const stored = localStorage.getItem(key);

        if (!stored) {
            // 没有标记，无冲突
            if (this.isBlocked) {
                this.unblockInput();
            }
            return false;
        }

        try {
            const data = JSON.parse(stored);
            const isOtherTab = data.tabId !== this.getTabId();

            // 检查标记是否过期（超过5分钟认为是僵尸标记）
            const isExpired = (Date.now() - data.timestamp) > 5 * 60 * 1000;

            if (isExpired) {
                console.warn('[TabSync] 检测到过期标记，清除');
                localStorage.removeItem(key);
                if (this.isBlocked) {
                    this.unblockInput();
                }
                return false;
            }

            if (isOtherTab && !this.isBlocked) {
                console.warn('[TabSync] 检测到其他标签页正在发送');
                this.blockInput();
                return true;
            }

            return isOtherTab;

        } catch (e) {
            console.error('[TabSync] 检查冲突失败:', e);
            return false;
        }
    }

    /**
     * 处理 storage 事件（其他标签页的操作）
     */
    handleStorageChange(e) {
        if (!e.key || !e.key.startsWith('conv_')) {
            return;
        }

        // 提取对话ID
        const match = e.key.match(/^conv_([^:]+):sending$/);
        if (!match) {
            return;
        }

        const convId = match[1];

        // 只关心当前对话的变化
        if (convId !== this.currentConvId) {
            return;
        }

        // 检查新值
        if (e.newValue) {
            // 其他标签页开始发送
            try {
                const data = JSON.parse(e.newValue);
                if (data.tabId !== this.getTabId()) {
                    console.warn('[TabSync] 其他标签页开始发送');
                    this.blockInput();
                }
            } catch (err) {
                console.error('[TabSync] 解析storage数据失败:', err);
            }
        } else {
            // 其他标签页结束发送
            console.log('[TabSync] 其他标签页结束发送');
            if (this.isBlocked) {
                this.unblockInput();
            }
        }
    }

    /**
     * 阻塞输入
     */
    blockInput() {
        this.isBlocked = true;

        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        if (chatInput) {
            chatInput.disabled = true;
            chatInput.placeholder = '⚠️ 其他标签页正在此对话中发送消息，请稍候...';
        }

        if (sendBtn) {
            sendBtn.disabled = true;
        }

        // 显示提示横幅
        this.showWarningBanner();

        console.log('[TabSync] 已阻塞输入');
    }

    /**
     * 解除阻塞
     */
    unblockInput() {
        this.isBlocked = false;

        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        if (chatInput) {
            chatInput.disabled = false;
            chatInput.placeholder = '输入消息...';
        }

        if (sendBtn) {
            sendBtn.disabled = false;
        }

        // 隐藏提示横幅
        this.hideWarningBanner();

        console.log('[TabSync] 已解除阻塞');
    }

    /**
     * 显示警告横幅
     */
    showWarningBanner() {
        // 检查是否已存在
        let banner = document.getElementById('tab-conflict-banner');
        if (banner) {
            return;
        }

        banner = document.createElement('div');
        banner.id = 'tab-conflict-banner';
        banner.className = 'tab-conflict-banner';
        banner.innerHTML = `
            <span class="banner-icon">⚠️</span>
            <span class="banner-text">其他标签页正在此对话中发送消息，请等待完成或切换到该标签页</span>
        `;

        const chatContainer = document.querySelector('.chat-main');
        if (chatContainer) {
            chatContainer.insertBefore(banner, chatContainer.firstChild);
        }
    }

    /**
     * 隐藏警告横幅
     */
    hideWarningBanner() {
        const banner = document.getElementById('tab-conflict-banner');
        if (banner) {
            banner.remove();
        }
    }

    /**
     * 获取当前标签页ID（使用 sessionStorage 保证每个标签页唯一）
     */
    getTabId() {
        let tabId = sessionStorage.getItem('tab_id');
        if (!tabId) {
            tabId = `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            sessionStorage.setItem('tab_id', tabId);
        }
        return tabId;
    }
}

// 创建全局实例
window.tabSyncManager = new TabSyncManager();

/**
 * @mention Autocomplete 功能
 * 在输入框中输入@时弹出工作区文件列表
 */

class MentionAutocomplete {
    constructor(inputElement) {
        this.input = inputElement;
        this.dropdown = null;
        this.files = [];  // 工作区文件列表缓存
        this.currentQuery = '';  // 当前搜索词
        this.selectedIndex = -1;  // 当前选中项索引
        this.isShowing = false;
        this.atPosition = -1;  // @符号的位置

        this.init();
    }

    init() {
        // 创建dropdown DOM
        this.createDropdown();

        // 绑定输入事件
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));

        // 点击外部关闭dropdown
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target) && e.target !== this.input) {
                this.hide();
            }
        });

        // 加载工作区文件列表
        this.loadWorkspaceFiles();
    }

    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'mention-autocomplete-dropdown';
        this.dropdown.style.display = 'none';
        document.body.appendChild(this.dropdown);
    }

    async loadWorkspaceFiles() {
        try {
            const response = await fetch('/workspace/files/autocomplete');
            if (response.ok) {
                const data = await response.json();
                this.files = data.files || [];
                console.log('[MentionAutocomplete] 已加载工作区文件:', this.files.length, '个');
            }
        } catch (error) {
            console.error('[MentionAutocomplete] 加载工作区文件失败:', error);
        }
    }

    handleInput(e) {
        const value = this.input.value;
        const cursorPos = this.input.selectionStart;

        // 查找最近的@符号（在光标之前）
        const textBeforeCursor = value.substring(0, cursorPos);
        const lastAtIndex = textBeforeCursor.lastIndexOf('@');

        if (lastAtIndex === -1) {
            this.hide();
            return;
        }

        // 检查@后面是否有空格（如果有，说明已经完成输入）
        const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
        if (textAfterAt.includes(' ')) {
            this.hide();
            return;
        }

        // 提取查询词
        this.currentQuery = textAfterAt.toLowerCase();
        this.atPosition = lastAtIndex;

        // 过滤匹配的文件
        const matches = this.files.filter(f =>
            f.filename.toLowerCase().includes(this.currentQuery)
        );

        if (matches.length > 0) {
            this.show(matches);
        } else {
            this.hide();
        }
    }

    handleKeydown(e) {
        if (!this.isShowing) return;

        const items = this.dropdown.querySelectorAll('.mention-item');
        if (items.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                this.updateSelection(items);
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.updateSelection(items);
                break;

            case 'Enter':
            case 'Tab':
                if (this.selectedIndex >= 0) {
                    e.preventDefault();
                    e.stopImmediatePropagation();  // 阻止其他监听器（如app.js的回车发送）
                    this.selectFile(items[this.selectedIndex].dataset.filename);
                }
                break;

            case 'Escape':
                e.preventDefault();
                this.hide();
                break;
        }
    }

    updateSelection(items) {
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
                // 滚动到可见区域
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    show(matches) {
        // 限制显示数量
        const displayMatches = matches.slice(0, 8);

        // 构建dropdown内容
        this.dropdown.innerHTML = displayMatches.map((file, index) => `
            <div class="mention-item" data-filename="${file.filename}" data-index="${index}">
                <span class="mention-item-name">${this.highlightMatch(file.filename)}</span>
            </div>
        `).join('');

        // 绑定点击事件
        this.dropdown.querySelectorAll('.mention-item').forEach(item => {
            item.addEventListener('click', () => {
                this.selectFile(item.dataset.filename);
            });
        });

        // 定位dropdown（在输入框上方或下方）
        this.positionDropdown();

        this.dropdown.style.display = 'block';
        this.isShowing = true;
        this.selectedIndex = 0;  // 默认选中第一项
        this.updateSelection(this.dropdown.querySelectorAll('.mention-item'));
    }

    hide() {
        this.dropdown.style.display = 'none';
        this.isShowing = false;
        this.selectedIndex = -1;
        this.atPosition = -1;
    }

    positionDropdown() {
        // 获取输入框位置
        const inputRect = this.input.getBoundingClientRect();

        // 计算dropdown位置（在输入框上方）
        const dropdownHeight = Math.min(8 * 40, this.dropdown.scrollHeight);  // 每项约40px

        // 默认显示在上方
        let top = inputRect.top - dropdownHeight - 5;

        // 如果上方空间不够，显示在下方
        if (top < 10) {
            top = inputRect.bottom + 5;
        }

        this.dropdown.style.position = 'fixed';
        this.dropdown.style.left = inputRect.left + 'px';
        this.dropdown.style.top = top + 'px';
        this.dropdown.style.width = Math.max(300, inputRect.width) + 'px';
        this.dropdown.style.maxHeight = dropdownHeight + 'px';
    }

    selectFile(filename) {
        // 获取当前输入值
        const value = this.input.value;
        const cursorPos = this.input.selectionStart;

        // 替换@mention部分
        const before = value.substring(0, this.atPosition);
        const after = value.substring(cursorPos);

        // 如果文件名包含空格，用引号包裹
        const needsQuotes = filename.includes(' ');
        const mentionText = needsQuotes ? `@"${filename}" ` : `@${filename} `;

        const newValue = before + mentionText + after;
        const newCursorPos = before.length + mentionText.length;

        // 更新输入框
        this.input.value = newValue;
        this.input.setSelectionRange(newCursorPos, newCursorPos);

        // 触发input事件（让其他监听器知道值变了）
        this.input.dispatchEvent(new Event('input', { bubbles: true }));

        // 聚焦回输入框
        this.input.focus();

        // 隐藏dropdown
        this.hide();
    }

    highlightMatch(filename) {
        if (!this.currentQuery) return filename;

        const index = filename.toLowerCase().indexOf(this.currentQuery);
        if (index === -1) return filename;

        const before = filename.substring(0, index);
        const match = filename.substring(index, index + this.currentQuery.length);
        const after = filename.substring(index + this.currentQuery.length);

        return `${before}<strong>${match}</strong>${after}`;
    }

    // 刷新文件列表（当用户保存新文件到工作区时调用）
    refresh() {
        this.loadWorkspaceFiles();
    }
}

// 导出给全局使用
window.MentionAutocomplete = MentionAutocomplete;

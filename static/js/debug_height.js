/**
 * 高度诊断工具
 * 在浏览器控制台运行: debugHeight()
 */
function debugHeight() {
    const elements = [
        'body',
        '.header',
        '.main-container',
        '.preview-panel',
        '.file-tabs-container',
        '.file-contents-container',
        '.file-content-item.active'
    ];

    console.log('=== 高度诊断报告 ===');
    console.log(`窗口高度: ${window.innerHeight}px`);
    console.log('');

    elements.forEach(selector => {
        const el = document.querySelector(selector);
        if (el) {
            const rect = el.getBoundingClientRect();
            const computed = window.getComputedStyle(el);
            console.log(`${selector}:`);
            console.log(`  实际高度: ${rect.height.toFixed(2)}px`);
            console.log(`  顶部位置: ${rect.top.toFixed(2)}px`);
            console.log(`  底部位置: ${rect.bottom.toFixed(2)}px`);
            console.log(`  距离窗口底部: ${(window.innerHeight - rect.bottom).toFixed(2)}px`);
            console.log(`  CSS height: ${computed.height}`);
            console.log(`  CSS flex: ${computed.flex}`);
            console.log(`  CSS display: ${computed.display}`);
            console.log('');
        } else {
            console.log(`${selector}: 未找到元素`);
            console.log('');
        }
    });

    // 检查是否有center-mode
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        console.log('main-container classes:', mainContainer.className);
    }
}

// 暴露到全局
window.debugHeight = debugHeight;

console.log('诊断工具已加载。请在控制台运行: debugHeight()');

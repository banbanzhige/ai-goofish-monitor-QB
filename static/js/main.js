document.addEventListener('DOMContentLoaded', function () {
    const mainContent = document.getElementById('main-content');

    if (typeof initUIShell === 'function') {
        initUIShell(mainContent);
    }
    if (typeof initAppInteractions === 'function') {
        initAppInteractions(mainContent);
    }
    if (typeof initNavigation === 'function') {
        initNavigation(mainContent);
    }

    setupTaskAccountCellEvents();

    // 初始化任务字段行内编辑事件
    setupTaskInlineEditEvents();

    // 使用MutationObserver监控DOM变化，自动填充账号display_name
    const accountCellObserver = new MutationObserver(async (mutations) => {
        for (const mutation of mutations) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // 检查是否有新添加的account-cell
                const cells = document.querySelectorAll('.account-cell');
                if (cells.length > 0) {
                    // 异步填充账号显示名称
                    populateTaskAccountSelectors();
                    break;
                }
            }
        }
    });

    // 开始观察mainContent的变化
    if (mainContent) {
        accountCellObserver.observe(mainContent, { childList: true, subtree: true });
    }

    
});


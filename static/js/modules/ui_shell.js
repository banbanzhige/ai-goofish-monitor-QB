﻿﻿﻿// UI壳层与下拉定位
var uiMainContent = null;
var uiShellInitialized = false;

const resetDropdownMenuStyle = (menu) => {
    if (!menu) return;
    menu.style.position = '';
    menu.style.left = '';
    menu.style.top = '';
    menu.style.right = '';
    menu.style.bottom = '';
    menu.style.marginTop = '';
    menu.style.marginBottom = '';
    menu.style.maxHeight = '';
    menu.style.overflowY = '';
    menu.style.zIndex = '';
};

const positionDropdownMenu = (dropdownMenu, dropdownBtn) => {
    if (!dropdownMenu || !dropdownBtn) return;
    dropdownMenu.style.position = 'fixed';
    dropdownMenu.style.left = '0px';
    dropdownMenu.style.top = '0px';
    dropdownMenu.style.right = 'auto';
    dropdownMenu.style.bottom = 'auto';
    dropdownMenu.style.marginTop = '0px';
    dropdownMenu.style.marginBottom = '0px';
    dropdownMenu.style.zIndex = '3000';

    const menuRect = dropdownMenu.getBoundingClientRect();
    const buttonRect = dropdownBtn.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    const containerRect = uiMainContent ? uiMainContent.getBoundingClientRect() : null;
    const containerTop = containerRect ? Math.max(containerRect.top, 0) : 0;
    const containerBottom = containerRect ? Math.min(containerRect.bottom, viewportHeight) : viewportHeight;
    const spaceBelow = containerBottom - buttonRect.bottom;
    const spaceAbove = buttonRect.top - containerTop;
    const shouldOpenUp = spaceBelow < menuRect.height && spaceAbove >= spaceBelow;

    dropdownMenu.classList.toggle('open-up', shouldOpenUp);

    const verticalGap = 6;
    let top = shouldOpenUp
        ? buttonRect.top - menuRect.height - verticalGap
        : buttonRect.bottom + verticalGap;
    const minTop = containerTop + 4;
    const maxTop = containerBottom - menuRect.height - 4;
    if (maxTop >= minTop) {
        top = Math.min(Math.max(top, minTop), maxTop);
    } else {
        top = Math.min(Math.max(top, 4), viewportHeight - menuRect.height - 4);
    }

    let left = buttonRect.right - menuRect.width;
    const minLeft = 8;
    const maxLeft = viewportWidth - menuRect.width - 8;
    left = Math.min(Math.max(left, minLeft), maxLeft);

    dropdownMenu.style.left = `${Math.round(left)}px`;
    dropdownMenu.style.top = `${Math.round(top)}px`;

    const maxMenuHeight = Math.max(containerBottom - containerTop - 8, 120);
    dropdownMenu.style.maxHeight = `${Math.floor(maxMenuHeight)}px`;
    dropdownMenu.style.overflowY = 'auto';
};

const resetAdvancedPanelStyle = (panel) => {
    if (!panel) return;
    panel.style.position = '';
    panel.style.left = '';
    panel.style.top = '';
    panel.style.right = '';
    panel.style.bottom = '';
    panel.style.marginTop = '';
    panel.style.transform = '';
    panel.style.zIndex = '';
    panel.style.maxHeight = '';
    panel.style.overflowY = '';
    delete panel.dataset.fixed;
};

const positionAdvancedPanel = (panel, anchor) => {
    if (!panel || !anchor) return;
    panel.style.position = 'fixed';
    panel.style.left = '0px';
    panel.style.top = '0px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
    panel.style.marginTop = '0px';
    panel.style.transform = 'none';
    panel.style.zIndex = '3000';

    const panelRect = panel.getBoundingClientRect();
    const anchorRect = anchor.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
    const containerRect = uiMainContent ? uiMainContent.getBoundingClientRect() : null;
    const containerTop = containerRect ? Math.max(containerRect.top, 0) : 0;
    const containerBottom = containerRect ? Math.min(containerRect.bottom, viewportHeight) : viewportHeight;
    const spaceBelow = containerBottom - anchorRect.bottom;
    const spaceAbove = anchorRect.top - containerTop;
    const shouldOpenUp = spaceBelow < panelRect.height && spaceAbove >= spaceBelow;
    const verticalGap = 6;

    let top = shouldOpenUp
        ? anchorRect.top - panelRect.height - verticalGap
        : anchorRect.bottom + verticalGap;
    const minTop = containerTop + 4;
    const maxTop = containerBottom - panelRect.height - 4;
    if (maxTop >= minTop) {
        top = Math.min(Math.max(top, minTop), maxTop);
    } else {
        top = Math.min(Math.max(top, 4), viewportHeight - panelRect.height - 4);
    }

    let left = anchorRect.left + (anchorRect.width / 2) - (panelRect.width / 2);
    const minLeft = 8;
    const maxLeft = viewportWidth - panelRect.width - 8;
    left = Math.min(Math.max(left, minLeft), maxLeft);

    panel.style.left = `${Math.round(left)}px`;
    panel.style.top = `${Math.round(top)}px`;
    panel.style.maxHeight = `${Math.floor(containerBottom - containerTop - 8)}px`;
    panel.style.overflowY = 'auto';
    panel.dataset.fixed = 'true';
};

const closeAllDropdownMenus = () => {
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.classList.remove('show');
        menu.classList.remove('open-up');
        resetDropdownMenuStyle(menu);
    });
    document.querySelectorAll('#accounts-section .accounts-table tbody tr.dropdown-open').forEach(row => {
        row.classList.remove('dropdown-open');
    });
};

const updateAdvancedPanelPositions = () => {
    document.querySelectorAll('.editable-advanced-panel.open').forEach(panel => {
        if (panel.dataset.fixed !== 'true') return;
        const cell = panel.closest('.editable-advanced-filter');
        if (!cell) return;
        positionAdvancedPanel(panel, cell);
    });
};

function initUIShell(mainContent) {
    if (uiShellInitialized) return;
    uiShellInitialized = true;
    uiMainContent = mainContent || null;

    window.addEventListener('resize', updateAdvancedPanelPositions);
    document.addEventListener('scroll', updateAdvancedPanelPositions, true);

    function setAdvancedFilterPlaceholder(cell) {
        if (!cell) return;
        const display = cell.querySelector('.editable-display');
        if (!display) return;
        display.classList.add('advanced-filter-placeholder');
        display.style.display = display.classList.contains('filter-tags') ? 'inline-flex' : 'inline-block';
    }

    function restoreAdvancedFilterDisplay(cell) {
        if (!cell) return;
        const display = cell.querySelector('.editable-display');
        if (!display) return;
        display.classList.remove('advanced-filter-placeholder');
        display.style.visibility = '';
        display.style.pointerEvents = '';
        display.style.display = display.classList.contains('filter-tags') ? 'inline-flex' : 'inline-block';
    }

    const closeAllAdvancedPanels = () => {
        const panels = document.querySelectorAll('.editable-advanced-panel.open');
        panels.forEach(panel => {
            panel.style.display = 'none';
            panel.classList.remove('open');
            resetAdvancedPanelStyle(panel);
            const cell = panel.closest('.editable-advanced-filter');
            const card = panel.closest('.task-card');
            restoreAdvancedFilterDisplay(cell);
            if (card) {
                const wrapper = panel.closest('.task-card-filter-panel');
                if (wrapper) wrapper.style.display = 'none';
            }
        });
    };

    // 供任务编辑模块调用
    window.closeAllAdvancedPanels = closeAllAdvancedPanels;
    window.setAdvancedFilterPlaceholder = setAdvancedFilterPlaceholder;
    window.restoreAdvancedFilterDisplay = restoreAdvancedFilterDisplay;

    // 下拉菜单交互逻辑
    document.addEventListener('click', function(event) {
        const dropdownBtn = event.target.closest('.dropdown-btn');

        // 点击下拉按钮
        if (dropdownBtn) {
            event.stopPropagation();

            const dropdownContainer = dropdownBtn.closest('.dropdown-container');
            const dropdownMenu = dropdownContainer.querySelector('.dropdown-menu');
            const accountRow = dropdownContainer.closest('#accounts-section .accounts-table tbody tr');

            // 切换当前下拉菜单的显示/隐藏
            const isOpen = dropdownMenu.classList.toggle('show');
            dropdownMenu.classList.remove('open-up');
            resetDropdownMenuStyle(dropdownMenu);
            if (accountRow) {
                accountRow.classList.toggle('dropdown-open', isOpen);
            }
            if (isOpen) {
                positionDropdownMenu(dropdownMenu, dropdownBtn);
            } else {
                resetDropdownMenuStyle(dropdownMenu);
            }

            // 关闭其他所有下拉菜单
            document.querySelectorAll('.dropdown-container').forEach(container => {
                if (container !== dropdownContainer) {
                    const menu = container.querySelector('.dropdown-menu');
                    menu.classList.remove('show');
                    menu.classList.remove('open-up');
                    resetDropdownMenuStyle(menu);
                    const row = container.closest('#accounts-section .accounts-table tbody tr');
                    if (row) {
                        row.classList.remove('dropdown-open');
                    }
                }
            });
        } else {
            // 点击外部区域，关闭所有下拉菜单
            closeAllDropdownMenus();
        }
    });

    // 为下拉菜单项添加点击事件，点击后关闭菜单
    document.addEventListener('click', function(event) {
        const dropdownItem = event.target.closest('.dropdown-item');

        if (dropdownItem) {
            const dropdownMenu = dropdownItem.closest('.dropdown-menu');
            dropdownMenu.classList.remove('show');
            dropdownMenu.classList.remove('open-up');
            resetDropdownMenuStyle(dropdownMenu);
            const row = dropdownMenu.closest('#accounts-section .accounts-table tbody tr');
            if (row) {
                row.classList.remove('dropdown-open');
            }
        }
    });

    document.addEventListener('change', function(event) {
        const checkbox = event.target.closest('.result-select-checkbox');
        if (checkbox && typeof window.updateSelectionControls === 'function') {
            window.updateSelectionControls();
        }
    });

    if (uiMainContent) {
        uiMainContent.addEventListener('scroll', closeAllDropdownMenus);
    }
    window.addEventListener('resize', closeAllDropdownMenus);

    const navLinks = document.querySelectorAll('.nav-link');
    const headerTitle = document.querySelector('.logo-container h1');
    const desktopTitleText = headerTitle ? headerTitle.textContent.trim() : '';
    const mobileTitleText = '咸鱼AI监控机器人';


    const mobileMenuBtn = document.getElementById('mobile-menu-toggle');
    const sidebar = document.querySelector('aside');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
    const layoutContainer = document.querySelector('.container');
    const SIDEBAR_COLLAPSED_KEY = 'sidebarCollapsed';

        const applySidebarCollapsed = (collapsed) => {
        if (!layoutContainer || !sidebarToggleBtn) return;
        layoutContainer.classList.toggle('sidebar-collapsed', collapsed);
        sidebarToggleBtn.textContent = collapsed ? '>>' : '<<';
        sidebarToggleBtn.title = collapsed ? '\u5c55\u5f00\u4fa7\u8fb9\u680f' : '\u6536\u8d77\u4fa7\u8fb9\u680f';
        sidebarToggleBtn.setAttribute('aria-label', sidebarToggleBtn.title);
    };

    if (sidebarToggleBtn && layoutContainer) {
        const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
        applySidebarCollapsed(stored === '1');
        sidebarToggleBtn.addEventListener('click', () => {
            const next = !layoutContainer.classList.contains('sidebar-collapsed');
            applySidebarCollapsed(next);
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? '1' : '0');
        });
    }

    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        function toggleMobileMenu() {
            sidebar.classList.toggle('active');
            sidebarOverlay.classList.toggle('active');
        }

        mobileMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMobileMenu();
        });

        sidebarOverlay.addEventListener('click', () => {
            toggleMobileMenu();
        });


        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (window.matchMedia("(max-width: 1366px) and (hover: none) and (pointer: coarse)").matches) {
                    sidebar.classList.remove('active');
                    sidebarOverlay.classList.remove('active');
                }
            });
        });
    }

    if (headerTitle) {
        const updateHeaderTitle = () => {
            if (window.matchMedia("(max-width: 1366px) and (hover: none) and (pointer: coarse)").matches) {
                headerTitle.textContent = mobileTitleText;
            } else if (desktopTitleText) {
                headerTitle.textContent = desktopTitleText;
            }
        };
        updateHeaderTitle();
        window.addEventListener('resize', updateHeaderTitle);
    }

    // 填充任务表格中的账号选择器（新版：点击显示下拉框）
}

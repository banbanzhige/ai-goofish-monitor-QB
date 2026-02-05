﻿// 任务编辑与高级筛选
async function populateTaskAccountSelectors(tasks) {
    try {
        const accounts = await fetchAccounts();
        const cells = document.querySelectorAll('.account-cell');

        // 创建accounts的name到display_name的映射
        const accountMap = {};
        if (accounts && accounts.length > 0) {
            accounts.forEach(acc => {
                accountMap[acc.name] = acc.display_name;
            });
        }

        cells.forEach(cell => {
            const currentAccount = cell.dataset.boundAccount || '';
            const select = cell.querySelector('.account-select');
            const display = cell.querySelector('.account-display');

            if (!select) return;

            select.innerHTML = '<option value="">未绑定</option>';

            if (accounts && accounts.length > 0) {
                accounts.forEach(account => {
                    const option = document.createElement('option');
                    option.value = account.name;
                    option.textContent = account.display_name;
                    if (account.name === currentAccount) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
            }

            // 更新显示标签的文本为display_name
            if (display && currentAccount) {
                const displayName = accountMap[currentAccount] || currentAccount;
                display.textContent = displayName;
                cell.dataset.displayName = displayName;
            } else if (display && !currentAccount) {
                display.textContent = '未绑定';
            }
        });

        document.querySelectorAll('.task-card').forEach(card => {
            try {
                const rowData = JSON.parse(card.dataset.task);
                const displayName = accountMap[rowData.bound_account] || rowData.bound_account || '未绑定';
                const accountValue = card.querySelector('[data-field="bound_account"]');
                if (accountValue) {
                    accountValue.textContent = displayName;
                    accountValue.classList.add('account-display');
                    if (rowData.bound_account) {
                        accountValue.classList.add('has-account');
                        accountValue.classList.remove('no-account');
                        accountValue.style.backgroundColor = getAccountColorByName(rowData.bound_account);
                        accountValue.style.color = '#fff';
                    } else {
                        accountValue.classList.add('no-account');
                        accountValue.classList.remove('has-account');
                        accountValue.style.backgroundColor = '';
                        accountValue.style.color = '';
                    }
                }
            } catch (error) {
                console.error('更新任务卡账号显示失败:', error);
            }
        });
    } catch (error) {
        console.error('填充任务账号选择器失败:', error);
    }
}

// 设置任务账号选择器点击切换事件
function setupTaskAccountCellEvents() {
    // 点击显示标签时显示下拉框（浮动样式）
    document.addEventListener('click', async (event) => {
        const display = event.target.closest('.account-display');
        if (display) {
            const cell = display.closest('.account-cell');
            if (!cell) return;

            const select = cell.querySelector('.account-select');
            if (!select) return;

            // 暂停定时刷新，防止编辑时被刷新打断
            if (taskRefreshInterval) {
                clearInterval(taskRefreshInterval);
                taskRefreshInterval = null;
            }

            // 先填充选项
            const accounts = await fetchAccounts();
            const currentAccount = cell.dataset.boundAccount || '';

            select.innerHTML = '<option value="">未绑定</option>';
            if (accounts && accounts.length > 0) {
                accounts.forEach(account => {
                    const option = document.createElement('option');
                    option.value = account.name;
                    option.textContent = account.display_name;
                    if (account.name === currentAccount) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
            }

            // 显示浮动下拉框（不隐藏标签，让它浮在上方）
            const selectContainer = cell.querySelector('.editable-account-select');
            selectContainer.style.display = 'block';
            select.style.display = 'block';
            select.focus();
        }
    });

    // 下拉框选择变更时保存并隐藏下拉框
    document.addEventListener('change', async (event) => {
        if (event.target.matches('.account-select')) {
            const select = event.target;
            const cell = select.closest('.account-cell');
            if (!cell) return;

            const taskId = cell.dataset.taskId;
            const newAccount = select.value;
            const display = cell.querySelector('.account-display');

            try {
                const result = await updateTask(taskId, { bound_account: newAccount || null });
                if (result) {
                    // 更新数据属性
                    cell.dataset.boundAccount = newAccount;

                    // 更新显示标签
                    if (newAccount) {
                        const selectedOption = select.options[select.selectedIndex];
                        display.textContent = selectedOption.textContent;
                        display.className = 'account-display has-account';
                        display.style.backgroundColor = getAccountColor(newAccount);
                        display.style.color = '#fff';
                    } else {
                        display.textContent = '未绑定';
                        display.className = 'account-display no-account';
                        display.style.backgroundColor = '';
                        display.style.color = '';
                    }
                }
            } catch (error) {
                console.error('更新任务账号失败:', error);
                Notification.error('更新账号绑定失败，请重试');
            }

            // 隐藏下拉框
            const selectContainer = cell.querySelector('.editable-account-select');
            selectContainer.style.display = 'none';
            select.style.display = 'none';

            // 刷新任务列表并重新开启定时刷新
            await refreshTasksAndRestartInterval();
        }
    });

    // 下拉框失去焦点时也隐藏下拉框
    document.addEventListener('blur', (event) => {
        if (event.target.matches('.account-select')) {
            const select = event.target;
            const cell = select.closest('.account-cell');
            if (cell) {
                const selectContainer = cell.querySelector('.editable-account-select');
                setTimeout(() => {
                    selectContainer.style.display = 'none';
                    select.style.display = 'none';
                    // 重新开启定时刷新
                    refreshTasksAndRestartInterval();
                }, 150);
            }
        }
    }, true);
}

// 刷新任务列表并重新开启定时刷新的函数
async function refreshTasksAndRestartInterval() {
    const container = document.getElementById('tasks-table-container');
    const tasks = await fetchTasks();
    container.innerHTML = renderTasksTable(tasks);
    // 重新开启定时刷新
    if (!taskRefreshInterval) {
        taskRefreshInterval = setInterval(async () => {
            const tasks = await fetchTasks();
            if (container && !container.querySelector('tr.editing') && !document.querySelector('.editable-input:focus') && !document.querySelector('.account-select:focus')) {
                renderTasksInto(container, tasks);
            }
        }, 5000);
    }
}

// 输入框宽度自适应内容
function autoResizeInput(input) {
    // 创建一个临时的span元素来测量文本尺寸
    const tempSpan = document.createElement('span');
    tempSpan.style.visibility = 'hidden';
    tempSpan.style.position = 'absolute';
    tempSpan.style.fontSize = window.getComputedStyle(input).fontSize;
    tempSpan.style.fontFamily = window.getComputedStyle(input).fontFamily;
    tempSpan.style.padding = window.getComputedStyle(input).padding;

    // 设置最小和最大宽度
    const field = input.closest('.editable-cell')?.dataset.field;
    let minWidth = 80;
    let maxWidth = 200; // 增加最大宽度，允许更长的文本

    // 测量文本宽度（不换行）
    tempSpan.style.whiteSpace = 'nowrap';
    tempSpan.textContent = input.value;
    document.body.appendChild(tempSpan);
    const textWidth = tempSpan.offsetWidth;
    document.body.removeChild(tempSpan);

    // 计算所需宽度
    const newWidth = Math.max(minWidth, Math.min(textWidth + 20, maxWidth));
    input.style.width = `${newWidth}px`;

    // 对于任务名称和关键词输入框，高度自适应以贴合文案
    if (field === 'task_name' || field === 'keyword') {
        input.style.height = 'auto'; // 高度自适应
        input.style.whiteSpace = 'nowrap'; // 禁止换行
        input.style.overflow = 'hidden';
        input.style.textOverflow = 'ellipsis';
    }
}

// 设置任务字段点击编辑事件
function setupTaskInlineEditEvents() {
    let isSelectingText = false;


    document.addEventListener('mousedown', (e) => {
        if (e.target.closest('.editable-cell')) {
            isSelectingText = true;
        }
    });

    document.addEventListener('mouseup', () => {
        setTimeout(() => {
            isSelectingText = false;
        }, 50);
    });



    document.addEventListener('click', async (event) => {
        if (event.target.closest('.editable-advanced-panel')) {
            return;
        }
        const display = event.target.closest('.editable-display');
        if (!display) return;

        const cell = display.closest('.editable-cell');
        if (!cell) return;

        const field = cell.dataset.field;
        const taskId = cell.dataset.taskId;

        // 停止定时刷新，防止编辑时被刷新打断
        if (taskRefreshInterval) {
            clearInterval(taskRefreshInterval);
            taskRefreshInterval = null;
        }


        if (cell.classList.contains('editable-toggle')) {
            const row = cell.closest('tr');
            const taskData = JSON.parse(row.dataset.task);
            const newValue = !taskData.personal_only;

            try {
                const result = await updateTask(taskId, { personal_only: newValue });
                if (result) {

                    display.textContent = newValue ? '个人闲置' : '不限';
                    display.className = 'editable-display ' + (newValue ? 'tag personal' : '');

                    taskData.personal_only = newValue;
                    row.dataset.task = JSON.stringify(taskData);
                    // 刷新任务列表并重新开启定时刷新
                    await refreshTasksAndRestartInterval();
                }
            } catch (error) {
                console.error('更新筛选条件失败:', error);
                Notification.error('更新失败，请重试');
                // 即使失败也重新开启定时刷新
                await refreshTasksAndRestartInterval();
            }
            return;
        }

        if (cell.classList.contains('editable-advanced-filter')) {
            const panel = cell.querySelector('.editable-advanced-panel');
            if (panel) {
                closeAllAdvancedPanels();
                setAdvancedFilterPlaceholder(cell);
                panel.style.display = 'flex';
                panel.classList.add('open');
                resetAdvancedPanelStyle(panel);
                if (!panel.closest('.task-card-filter-panel')) {
                    positionAdvancedPanel(panel, cell);
                }
                const row = cell.closest('tr');
                if (row) {
                    await hydrateAdvancedFilterSelectors(cell, JSON.parse(row.dataset.task));
                }
            }
            return;
        }

        const tags = event.target.closest('.filter-tags');
        if (tags && tags.closest('.task-card')) {
            const card = tags.closest('.task-card');
            await openMobileFilterPanel(card);
            return;
        }


        if (field === 'price_range') {
            const priceInputs = cell.querySelector('.editable-price-inputs');
            if (priceInputs) {
                display.style.display = 'none';
                priceInputs.style.display = 'inline-flex';
                priceInputs.style.alignItems = 'center';
                priceInputs.style.gap = '5px';
                priceInputs.querySelector('.price-min').focus();
            }
            return;
        }


        const input = cell.querySelector('.editable-input');
        if (input) {
            display.style.display = 'none';
            input.style.display = 'inline-block';
            // 自动调整输入框宽度
            autoResizeInput(input);
            input.focus();
            input.select();
            // 添加输入事件监听，实时调整宽度
            input.addEventListener('input', function () {
                autoResizeInput(input);
            });
        }
    });

    // 刷新任务列表并重新开启定时刷新的函数
    async function refreshTasksAndRestartInterval() {
        const container = document.getElementById('tasks-table-container');
        const tasks = await fetchTasks();
        renderTasksInto(container, tasks);
        // 重新开启定时刷新
        if (!taskRefreshInterval) {
            taskRefreshInterval = setInterval(async () => {
                const tasks = await fetchTasks();
                if (container && !container.querySelector('tr.editing') && !document.querySelector('.editable-input:focus')) {
                    renderTasksInto(container, tasks);
                }
            }, 5000);
        }
    }


    document.addEventListener('blur', async (event) => {
        const input = event.target;
        if (!input.classList.contains('editable-input')) return;


        if (isSelectingText) {
            setTimeout(() => {
                input.focus();
            }, 10);
            return;
        }

        const cell = input.closest('.editable-cell');
        if (!cell) return;

        const field = cell.dataset.field;
        const taskId = cell.dataset.taskId;
        const display = cell.querySelector('.editable-display');
        const row = cell.closest('tr');
        const taskData = JSON.parse(row.dataset.task);


        if (field === 'price_range') {
            const priceInputs = cell.querySelector('.editable-price-inputs');

            setTimeout(async () => {
                const activeElement = document.activeElement;
                if (priceInputs.contains(activeElement)) return;

                const minInput = cell.querySelector('.price-min');
                const maxInput = cell.querySelector('.price-max');
                const minPrice = minInput.value ? minInput.value : null;
                const maxPrice = maxInput.value ? maxInput.value : null;

                try {
                    const result = await updateTask(taskId, { min_price: minPrice, max_price: maxPrice });
                    if (result) {
                        const minDisplay = minPrice !== null ? minPrice : '不限';
                        const maxDisplay = maxPrice !== null ? maxPrice : '不限';
                        display.textContent = `${minDisplay} - ${maxDisplay}`;
                    }
                    // 刷新任务列表并重新开启定时刷新
                    await refreshTasksAndRestartInterval();
                } catch (error) {
                    console.error('更新价格范围失败:', error);
                    Notification.error('更新失败，请重试');
                    // 即使失败也重新开启定时刷新
                    await refreshTasksAndRestartInterval();
                }

                priceInputs.style.display = 'none';
                display.style.display = 'inline-block';
            }, 100);
            return;
        }


        const newValue = input.value.trim();
        let updateData = {};

        if (field === 'task_name') {
            if (!newValue) {
                Notification.warning('任务名称不能为空');
                // 恢复原始值并切换到显示模式
                input.value = taskData.task_name;
                input.style.display = 'none';
                if (field === 'keyword') {
                    display.className = 'editable-display tag';
                } else {
                    display.className = 'editable-display';
                }
                display.textContent = taskData.task_name;
                display.style.display = 'inline-block';
                // 重新开启定时刷新
                await refreshTasksAndRestartInterval();
                return;
            }
            updateData = { task_name: newValue };
        } else if (field === 'keyword') {
            if (!newValue) {
                Notification.warning('关键词不能为空');
                // 恢复原始值并切换到显示模式
                input.value = taskData.keyword;
                input.style.display = 'none';
                display.className = 'editable-display tag';
                display.textContent = taskData.keyword;
                display.style.display = 'inline-block';
                // 重新开启定时刷新
                await refreshTasksAndRestartInterval();
                return;
            }
            updateData = { keyword: newValue };
        } else if (field === 'max_pages') {
            const pages = parseInt(newValue) || 3;
            updateData = { max_pages: Math.max(1, pages) };
        } else if (field === 'cron') {
            updateData = { cron: newValue || null };
        }

        try {
            const result = await updateTask(taskId, updateData);
            if (result) {

                if (field === 'cron') {
                    display.textContent = newValue || '未设置';
                } else if (field === 'max_pages') {
                    display.textContent = updateData.max_pages;
                    input.value = updateData.max_pages;
                } else {
                    display.textContent = newValue;
                }
                // 刷新任务列表并重新开启定时刷新
                await refreshTasksAndRestartInterval();
            }
        } catch (error) {
            console.error(`更新${field}失败:`, error);
            Notification.error('更新失败，请重试');
            // 即使失败也重新开启定时刷新
            await refreshTasksAndRestartInterval();
        }

        input.style.display = 'none';
        display.style.display = 'inline-block';
    }, true);


    document.addEventListener('keypress', (event) => {
        if (event.key !== 'Enter') return;
        const input = event.target;
        if (!input.classList.contains('editable-input')) return;

        isSelectingText = false;
        input.blur();
    });


    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        const input = event.target;
        if (!input.classList.contains('editable-input')) return;

        const cell = input.closest('.editable-cell');
        if (!cell) return;

        const display = cell.querySelector('.editable-display');
        const field = cell.dataset.field;

        if (field === 'price_range') {
            const priceInputs = cell.querySelector('.editable-price-inputs');
            if (priceInputs) priceInputs.style.display = 'none';
        } else {
            input.style.display = 'none';
        }
        if (display) display.style.display = 'inline-block';
    });


    document.addEventListener('click', (event) => {
        if (event.target.closest('.editable-advanced-panel')) return;
        if (event.target.closest('.editable-advanced-filter')) return;
        if (event.target.closest('.task-card-filter-panel')) return;

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
    });


    document.addEventListener('click', async (event) => {
        const saveBtn = event.target.closest('.filter-save-btn');
        const cancelBtn = event.target.closest('.filter-cancel-btn');
        const panel = event.target.closest('.editable-advanced-panel');
        if (!panel) return;

        const cell = panel.closest('.editable-advanced-filter');
        const card = panel.closest('.task-card');
        if (!cell && !card) return;

        if (cancelBtn) {
            panel.style.display = 'none';
            panel.classList.remove('open');
            resetAdvancedPanelStyle(panel);
            restoreAdvancedFilterDisplay(cell);
            if (card) {
                const wrapper = panel.closest('.task-card-filter-panel');
                if (wrapper) wrapper.style.display = 'none';
            }
            return;
        }

        if (!saveBtn) return;

        const row = cell ? cell.closest('tr') : null;
        const taskId = cell ? cell.dataset.taskId : card.dataset.taskId;
        const taskData = row ? JSON.parse(row.dataset.task) : JSON.parse(card.dataset.task);

        const personalOnly = panel.querySelector('.filter-personal-only')?.checked || false;
        const inspectionService = panel.querySelector('.filter-inspection-service')?.checked || false;
        const accountAssurance = panel.querySelector('.filter-account-assurance')?.checked || false;
        const freeShipping = panel.querySelector('.filter-free-shipping')?.checked || false;
        const superShop = panel.querySelector('.filter-super-shop')?.checked || false;
        const brandNew = panel.querySelector('.filter-brand-new')?.checked || false;
        const strictSelected = panel.querySelector('.filter-strict-selected')?.checked || false;
        const resale = panel.querySelector('.filter-resale')?.checked || false;
        const publishOption = panel.querySelector('.filter-publish-option')?.value || null;
        const province = panel.querySelector('.filter-region-province')?.value || '';
        const city = panel.querySelector('.filter-region-city')?.value || '';
        const district = panel.querySelector('.filter-region-district')?.value || '';
        const regionValue = buildRegionValue(province, city, district);

        try {
            const result = await updateTask(taskId, {
                personal_only: personalOnly,
                free_shipping: freeShipping,
                inspection_service: inspectionService,
                account_assurance: accountAssurance,
                super_shop: superShop,
                brand_new: brandNew,
                strict_selected: strictSelected,
                resale: resale,
                new_publish_option: publishOption,
                region: regionValue || null,
            });
            try {
                const scheduledContainer = document.getElementById('scheduled-table-container');
                if (scheduledContainer && scheduledContainer.closest('.content-section.active')) {
                    const jobs = await fetchScheduledJobs();
                    if (jobs) {
                        const refreshScheduled = async () => {
                            const updatedJobs = await fetchScheduledJobs();
                            if (updatedJobs) {
                                renderScheduledInto(scheduledContainer, updatedJobs, refreshScheduled);
                            }
                        };
                        renderScheduledInto(scheduledContainer, jobs, refreshScheduled);
                    }
                }
            } catch (err) {
                console.warn('Scheduled jobs reload skipped:', err);
            }
            if (result) {
                taskData.personal_only = personalOnly;
                taskData.free_shipping = freeShipping;
                taskData.inspection_service = inspectionService;
                taskData.account_assurance = accountAssurance;
                taskData.super_shop = superShop;
                taskData.brand_new = brandNew;
                taskData.strict_selected = strictSelected;
                taskData.resale = resale;
                taskData.new_publish_option = publishOption;
                taskData.region = regionValue || null;
                if (row) {
                    row.dataset.task = JSON.stringify(taskData);
                }
                await refreshTasksAndRestartInterval();
            }
        } catch (error) {
            console.error('更新高级筛选失败:', error);
            Notification.error('更新失败，请重试');
            await refreshTasksAndRestartInterval();
        }

        panel.style.display = 'none';
        panel.classList.remove('open');
        resetAdvancedPanelStyle(panel);
        restoreAdvancedFilterDisplay(cell);
        if (card) {
            const wrapper = panel.closest('.task-card-filter-panel');
            if (wrapper) wrapper.style.display = 'none';
        }
    });
}

async function openMobileFilterPanel(card) {
    const wrapper = card.querySelector('.task-card-filter-panel');
    const panel = card.querySelector('.task-card-filter-panel .editable-advanced-panel');
    if (!panel) return;
    closeAllAdvancedPanels();
    if (wrapper) {
        wrapper.style.display = 'block';
    }
    resetAdvancedPanelStyle(panel);
    panel.style.display = 'flex';
    panel.classList.add('open');
    await hydrateAdvancedFilterSelectors(panel.closest('.editable-advanced-filter') || card, JSON.parse(card.dataset.task));
}



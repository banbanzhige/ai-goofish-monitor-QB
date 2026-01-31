﻿﻿﻿// 调度渲染与排序
    function formatScheduledNextRunTime(nextRunTime) {
        if (!nextRunTime) return '未知';
        return new Date(nextRunTime).toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    function renderScheduledJobsTable(data) {
        if (!data || !data.jobs || data.jobs.length === 0) {
            return '<p>当前没有调度中的定时任务。请在"任务管理"中启用带有 Cron 表达式的任务。</p>';
        }

        const isMobile = isMobileLayout();
        if (isMobile) {
            const cards = data.jobs.map(job => {
                const nextRunTime = formatScheduledNextRunTime(job.next_run_time);
                const executionOrder = job.execution_order || '-';
                return `
                <div class="scheduled-card" data-job-id="${job.job_id}" data-task-id="${job.task_id}">
                    <div class="scheduled-card-header">
                        <div class="scheduled-title">${job.task_name}</div>
                        <span class="scheduled-order-pill">执行顺序 ${executionOrder}</span>
                    </div>
                    <div class="scheduled-card-body">
                        <div class="scheduled-row">
                            <span>Cron 定时</span>
                            <input type="text" class="cron-input scheduled-cron-input" value="${job.cron || ''}" placeholder="分 时 日 月 周">
                        </div>
                        <div class="scheduled-row">
                            <span>下一次执行时间</span>
                            <span class="scheduled-next-time">${nextRunTime}</span>
                        </div>
                    </div>
                    <div class="scheduled-card-actions">
                        <button class="action-btn run-now-btn scheduled-action-btn is-run" data-job-id="${job.job_id}">立刻执行</button>
                        <button class="action-btn skip-job-btn scheduled-action-btn is-skip" data-job-id="${job.job_id}">跳过本次</button>
                        <button class="action-btn cancel-job-btn scheduled-action-btn is-cancel" data-task-id="${job.task_id}">取消任务</button>
                    </div>
                </div>`;
            }).join('');

            return `<div class="scheduled-cards">${cards}</div>`;
        }

        const tableHeader = `
            <thead>
                <tr>
                    <th></th>
                    <th>执行顺序</th>
                    <th>任务名称</th>
                    <th>Cron 定时</th>
                    <th>下一次执行时间</th>
                    <th>操作</th>
                </tr>
            </thead>`;

        const tableBody = data.jobs.map(job => {
            const nextRunTime = formatScheduledNextRunTime(job.next_run_time);

            return `
            <tr data-job-id="${job.job_id}" data-task-id="${job.task_id}">
                <td style="text-align: center;" class="drag-handle-cell">
                    <span class="drag-handle" draggable="true" title="Drag">::</span>
                </td>
                <td style="text-align: center; font-weight: bold; color: #1890ff;">${job.execution_order || '-'}</td>
                <td style="text-align: center;">${job.task_name}</td>
                <td style="text-align: center;">
                    <input type="text" class="cron-input" value="${job.cron || ''}" 
                           placeholder="分 时 日 月 周" style="width: 120px; text-align: center;">
                </td>
                <td style="text-align: center;">${nextRunTime}</td>
                <td style="text-align: center;">
                    <div class="scheduled-action-buttons">
                        <button class="action-btn run-now-btn scheduled-action-btn is-run" data-job-id="${job.job_id}">立刻执行</button>
                        <button class="action-btn skip-job-btn scheduled-action-btn is-skip" data-job-id="${job.job_id}">跳过本次</button>
                        <button class="action-btn cancel-job-btn scheduled-action-btn is-cancel" data-task-id="${job.task_id}">取消任务</button>
                    </div>
                </td>
            </tr>`;
        }).join('');

        return `<table class="tasks-table scheduled-table">${tableHeader}<tbody>${tableBody}</tbody></table>`;
    }

    function arraysEqual(a, b) {
        if (!Array.isArray(a) || !Array.isArray(b) || a.length != b.length) return false;
        for (let i = 0; i < a.length; i += 1) {
            if (a[i] !== b[i]) return false;
        }
        return true;
    }


    function createDragPlaceholder(type, options = {}) {
        if (type == 'row') {
            const row = document.createElement('tr');
            row.className = 'drag-placeholder row-placeholder';
            const cell = document.createElement('td');
            cell.colSpan = options.colSpan || 1;
            row.appendChild(cell);
            if (options.height) {
                row.style.setProperty('--placeholder-height', options.height + 'px');
            }
            return row;
        }
        const placeholder = document.createElement('div');
        placeholder.className = 'drag-placeholder card-placeholder';
        if (options.height) {
            placeholder.style.height = options.height + 'px';
        }
        return placeholder;
    }

    function applySortFeedback(element) {
        if (!element) return;
        element.classList.remove('sort-animate');
        void element.offsetHeight;
        element.classList.add('sort-animate');
    }

    function applyTaskOrderLocally(orderedIds) {
        if (!Array.isArray(latestTasks) || latestTasks.length === 0) return;
        const map = new Map(latestTasks.map(task => [task.id, task]));
        const next = orderedIds.map(id => map.get(id)).filter(Boolean);
        if (next.length === latestTasks.length) {
            latestTasks = next;
        }
    }

    function applyAccountOrderLocally(orderedNames) {
        if (!Array.isArray(latestAccounts) || latestAccounts.length === 0) return;
        const map = new Map(latestAccounts.map(account => [account.name, account]));
        const next = orderedNames.map(name => map.get(name)).filter(Boolean);
        if (next.length === latestAccounts.length) {
            latestAccounts = next;
        }
    }

    function getTaskOrderFromCards(cards) {
        return Array.from(cards.querySelectorAll('.task-card[data-task-id]'))
            .map(card => Number(card.dataset.taskId))
            .filter(id => Number.isFinite(id));
    }

    function getTaskOrderFromTable(table) {
        return Array.from(table.querySelectorAll('tbody tr[data-task-id]'))
            .map(row => Number(row.dataset.taskId))
            .filter(id => Number.isFinite(id));
    }

    function getScheduledOrderFromTable(table) {
        return Array.from(table.querySelectorAll('tbody tr[data-task-id]'))
            .map(row => Number(row.dataset.taskId))
            .filter(id => Number.isFinite(id));
    }

    function getScheduledOrderFromCards(container) {
        return Array.from(container.querySelectorAll('.scheduled-card[data-task-id]'))
            .map(card => Number(card.dataset.taskId))
            .filter(id => Number.isFinite(id));
    }

    function getAccountOrderFromTable(table) {
        return Array.from(table.querySelectorAll('tbody tr[data-account-name]'))
            .map(row => row.dataset.accountName)
            .filter(name => name);
    }

    function buildScheduledFullOrder(orderedScheduledIds) {
        if (!Array.isArray(latestTasks) || latestTasks.length === 0) return orderedScheduledIds;
        const scheduledSet = new Set(orderedScheduledIds);
        const next = [];
        let scheduledIndex = 0;
        latestTasks.forEach(task => {
            if (scheduledSet.has(task.id)) {
                next.push(orderedScheduledIds[scheduledIndex]);
                scheduledIndex += 1;
            } else {
                next.push(task.id);
            }
        });
        return next;
    }

    function setupTableReorder(container, options) {
        if (!container || !options) return;
        const flag = `reorderReady${options.key || ''}`;
        if (container.dataset[flag]) return;
        container.dataset[flag] = '1';

        let draggingRow = null;
        let startOrder = null;
        let placeholder = null;
        let lastOverRow = null;
        let didDrop = false;

        const ensurePlaceholder = (row) => {
            if (!placeholder) {
                const colSpan = row && row.children ? row.children.length : 1;
                placeholder = createDragPlaceholder('row', { colSpan: colSpan });
            }
        };

        const clearPlaceholder = () => {
            if (placeholder && placeholder.parentElement) {
                placeholder.parentElement.removeChild(placeholder);
            }
            placeholder = null;
            lastOverRow = null;
        };

        container.addEventListener('dragstart', (event) => {
            const handle = event.target.closest(options.handleSelector || '.drag-handle');
            if (!handle) return;
            const row = handle.closest(options.rowSelector);
            if (!row) return;
            draggingRow = row;
            startOrder = options.collectOrder(container);
            didDrop = false;
            draggingRow.classList.add('dragging');
            ensurePlaceholder(draggingRow);
            if (typeof options.onStart === 'function') {
                options.onStart();
            }
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', 'drag');
        });

        container.addEventListener('dragover', (event) => {
            if (!draggingRow) return;
            const row = event.target.closest(options.rowSelector);
            if (!row || row === draggingRow) return;
            event.preventDefault();
            const rect = row.getBoundingClientRect();
            const shouldMoveAfter = (event.clientY - rect.top) > rect.height / 2;
            ensurePlaceholder(row);
            if (shouldMoveAfter) {
                row.after(placeholder);
            } else {
                row.before(placeholder);
            }
            if (row !== lastOverRow) {
                applySortFeedback(row);
                lastOverRow = row;
            }
        });

        container.addEventListener('drop', (event) => {
            if (!draggingRow) return;
            event.preventDefault();
            if (placeholder && placeholder.parentElement) {
                placeholder.replaceWith(draggingRow);
                applySortFeedback(draggingRow);
                didDrop = true;
            }
        });

        container.addEventListener('dragend', async () => {
            if (!draggingRow) return;
            const movedRow = draggingRow;
            draggingRow.classList.remove('dragging');
            draggingRow = null;
            const order = options.collectOrder(container);
            const changed = !arraysEqual(order, startOrder);
            clearPlaceholder();
            if (changed && typeof options.onReorder === 'function') {
                await options.onReorder(order);
                if (!didDrop) {
                    applySortFeedback(movedRow);
                }
            }
            didDrop = false;
            if (typeof options.onEnd === 'function') {
                options.onEnd();
            }
        });
    }

    function setupTouchReorder(container, options) {
        if (!container || !options) return;
        const flag = `touchReorderReady${options.key || ''}`;
        if (container.dataset[flag]) return;
        container.dataset[flag] = '1';

        let pressTimer = null;
        let draggingEl = null;
        let startOrder = null;
        let startPoint = null;
        let pointerId = null;
        let isDragging = false;
        let placeholder = null;
        let lastTarget = null;
        let lastMovePoint = null;
        let moveDirection = 0;
        let scrollLockSnapshot = null;
        let touchMoveBlocker = null;
        const bodyStyle = document.body ? document.body.style : null;
        const docElStyle = document.documentElement ? document.documentElement.style : null;
        const prevUserSelect = bodyStyle ? bodyStyle.userSelect : '';

        const ensurePlaceholder = (item) => {
            if (!placeholder) {
                if (options.placeholderType == 'row') {
                    const colSpan = item && item.children ? item.children.length : 1;
                    const height = item ? item.offsetHeight : 0;
                    placeholder = createDragPlaceholder('row', { colSpan: colSpan, height: height });
                } else {
                    const height = item ? item.offsetHeight : 0;
                    placeholder = createDragPlaceholder('card', { height: height });
                }
            }
        };

        const clearPlaceholder = () => {
            if (placeholder && placeholder.parentElement) {
                placeholder.parentElement.removeChild(placeholder);
            }
            placeholder = null;
            lastTarget = null;
        };

        const clearPress = () => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
        };

        const setReorderActive = (active) => {
            if (document.body) {
                document.body.classList.toggle('reorder-active', active);
            }
            container.classList.toggle('reorder-active', active);
        };

        const lockScroll = () => {
            if (!bodyStyle || !docElStyle || scrollLockSnapshot) {
                return;
            }
            scrollLockSnapshot = {
                bodyOverflow: bodyStyle.overflow,
                bodyTouchAction: bodyStyle.touchAction,
                bodyOverscrollBehavior: bodyStyle.overscrollBehavior,
                htmlOverflow: docElStyle.overflow,
                htmlTouchAction: docElStyle.touchAction,
                htmlOverscrollBehavior: docElStyle.overscrollBehavior
            };
            bodyStyle.overflow = 'hidden';
            bodyStyle.touchAction = 'none';
            bodyStyle.overscrollBehavior = 'none';
            docElStyle.overflow = 'hidden';
            docElStyle.touchAction = 'none';
            docElStyle.overscrollBehavior = 'none';
            if (!touchMoveBlocker) {
                touchMoveBlocker = (event) => {
                    if (isDragging) {
                        event.preventDefault();
                    }
                };
                document.addEventListener('touchmove', touchMoveBlocker, { passive: false });
            }
        };

        const unlockScroll = () => {
            if (touchMoveBlocker) {
                document.removeEventListener('touchmove', touchMoveBlocker);
                touchMoveBlocker = null;
            }
            if (!scrollLockSnapshot) return;
            bodyStyle.overflow = scrollLockSnapshot.bodyOverflow;
            bodyStyle.touchAction = scrollLockSnapshot.bodyTouchAction;
            bodyStyle.overscrollBehavior = scrollLockSnapshot.bodyOverscrollBehavior;
            docElStyle.overflow = scrollLockSnapshot.htmlOverflow;
            docElStyle.touchAction = scrollLockSnapshot.htmlTouchAction;
            docElStyle.overscrollBehavior = scrollLockSnapshot.htmlOverscrollBehavior;
            scrollLockSnapshot = null;
        };

        const updateMoveDirection = (event) => {
            if (!lastMovePoint) {
                lastMovePoint = { x: event.clientX, y: event.clientY };
                return;
            }
            const dy = event.clientY - lastMovePoint.y;
            if (Math.abs(dy) >= 3) {
                moveDirection = dy > 0 ? 1 : -1;
            }
            lastMovePoint = { x: event.clientX, y: event.clientY };
        };

        const finishDrag = async () => {
            clearPress();
            if (!draggingEl) return;
            if (placeholder && placeholder.parentElement) {
                placeholder.replaceWith(draggingEl);
                applySortFeedback(draggingEl);
            }
            draggingEl.classList.remove('dragging');
            if (bodyStyle) {
                bodyStyle.userSelect = prevUserSelect || '';
            }
            setReorderActive(false);
            unlockScroll();
            if (draggingEl.releasePointerCapture && pointerId !== null) {
                try {
                    draggingEl.releasePointerCapture(pointerId);
                } catch (e) {

                }
            }
            clearPlaceholder();
            const order = options.collectOrder(container);
            if (!arraysEqual(order, startOrder) && typeof options.onReorder === 'function') {
                await options.onReorder(order);
            }
            draggingEl = null;
            startOrder = null;
            startPoint = null;
            pointerId = null;
            isDragging = false;
            lastMovePoint = null;
            moveDirection = 0;
            if (typeof options.onEnd === 'function') {
                options.onEnd();
            }
        };

        container.addEventListener('pointerdown', (event) => {
            if (event.pointerType === 'mouse') return;
            if (event.target.closest(options.cancelSelector || 'button, a, input, select, textarea')) return;
            const item = event.target.closest(options.itemSelector);
            if (!item) return;
            startPoint = { x: event.clientX, y: event.clientY };
            pointerId = event.pointerId;
            pressTimer = setTimeout(() => {
                draggingEl = item;
                startOrder = options.collectOrder(container);
                draggingEl.classList.add('dragging');
                if (bodyStyle) {
                    bodyStyle.userSelect = 'none';
                }
                ensurePlaceholder(draggingEl);
                if (placeholder) {
                    draggingEl.after(placeholder);
                }
                if (draggingEl.setPointerCapture) {
                    draggingEl.setPointerCapture(pointerId);
                }
                isDragging = true;
                lastMovePoint = startPoint ? { x: startPoint.x, y: startPoint.y } : null;
                moveDirection = 0;
                setReorderActive(true);
                lockScroll();
                if (navigator.vibrate) {
                    navigator.vibrate(12);
                }
                if (typeof options.onStart === 'function') {
                    options.onStart();
                }
            }, options.delay || 320);
        }, { passive: true });

        container.addEventListener('pointermove', (event) => {
            if (!pressTimer && !isDragging) return;
            if (!isDragging) {
                if (!startPoint) return;
                const dx = Math.abs(event.clientX - startPoint.x);
                const dy = Math.abs(event.clientY - startPoint.y);
                if (dx > 8 || dy > 8) {
                    clearPress();
                }
                return;
            }
            event.preventDefault();
            updateMoveDirection(event);
            const target = document.elementFromPoint(event.clientX, event.clientY);
            if (!target) return;
            const item = target.closest(options.itemSelector);
            if (!item || item == draggingEl) return;
            const rect = item.getBoundingClientRect();
            let shouldMoveAfter = (event.clientY - rect.top) > rect.height / 2;
            if (moveDirection > 0) {
                shouldMoveAfter = true;
            } else if (moveDirection < 0) {
                shouldMoveAfter = false;
            }
            ensurePlaceholder(item);
            if (shouldMoveAfter) {
                item.after(placeholder);
            } else {
                item.before(placeholder);
            }
            if (item !== lastTarget) {
                applySortFeedback(item);
                lastTarget = item;
            }
        }, { passive: false });

        container.addEventListener('pointerup', () => {
            finishDrag();
        });

        container.addEventListener('pointercancel', () => {
            finishDrag();
        });
    }

function setupTaskReorder(container) {
        if (!container) return;
        const isTouch = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
        const cards = container.querySelector('.task-cards');
        const table = container.querySelector('table.tasks-table');

        const handleReorder = async (order) => {
            const result = await reorderTasksOrder(order);
            if (result) {
                const tasks = await fetchTasks();
                if (tasks) {
                    renderTasksInto(container, tasks);
                } else {
                    applyTaskOrderLocally(order);
                }
            }
        };

        if (isTouch && cards) {
            setupTouchReorder(cards, {
                key: 'TaskCards',
                itemSelector: '.task-card',
                cancelSelector: 'button, a, input, select, textarea, .dropdown-container, .dropdown-btn, .dropdown-menu, .action-btn, .switch, .filter-tag',
                collectOrder: getTaskOrderFromCards,
                onStart: () => { isTaskReordering = true; },
                onEnd: () => { isTaskReordering = false; },
                onReorder: handleReorder
            });
            return;
        }

        if (table) {
            setupTableReorder(table, {
                key: 'TaskTable',
                rowSelector: 'tbody tr[data-task-id]',
                handleSelector: '.drag-handle',
                collectOrder: getTaskOrderFromTable,
                onStart: () => { isTaskReordering = true; },
                onEnd: () => { isTaskReordering = false; },
                onReorder: handleReorder
            });
        }
    }

    function setupAccountsReorder(container) {
        if (!container) return;
        const isTouch = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
        const table = container.querySelector('table.accounts-table');
        if (!table) return;

        const options = {
            key: 'AccountTable',
            rowSelector: 'tbody tr[data-account-name]',
            handleSelector: '.drag-handle',
            itemSelector: 'tbody tr[data-account-name]',
            placeholderType: 'row',
            cancelSelector: 'button, a, input, select, textarea, .dropdown-container, .dropdown-btn, .dropdown-menu, .action-btn',
            collectOrder: getAccountOrderFromTable,
            onReorder: async (order) => {
                const result = await reorderAccountsOrder(order);
                if (result) {
                    applyAccountOrderLocally(order);
                }
            }
        };

        if (isTouch) {
            setupTouchReorder(table, options);
        } else {
            setupTableReorder(table, options);
        }
    }

    function setupScheduledReorder(container, refreshCallback) {
        if (!container) return;
        const isTouch = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
        const table = container.querySelector('table.scheduled-table');
        const cards = container.querySelector('.scheduled-cards');

        if (isTouch && cards) {
            const options = {
                key: 'ScheduledCards',
                itemSelector: '.scheduled-card',
                cancelSelector: 'button, a, input, select, textarea, .scheduled-action-btn',
                placeholderType: 'card',
                collectOrder: getScheduledOrderFromCards,
                onReorder: async (order) => {
                    if (!Array.isArray(latestTasks) || latestTasks.length === 0) {
                        await fetchTasks();
                    }
                    const fullOrder = buildScheduledFullOrder(order);
                    if (!Array.isArray(fullOrder) || fullOrder.length !== latestTasks.length) {
                        alert('Reorder failed: incomplete order');
                        return;
                    }
                    const result = await reorderTasksOrder(fullOrder);
                    if (result) {
                        const tasks = await fetchTasks();
                        if (!tasks) {
                            applyTaskOrderLocally(fullOrder);
                        }
                        if (typeof refreshCallback === 'function') {
                            await refreshCallback();
                        }
                    }
                }
            };

            setupTouchReorder(cards, options);
            return;
        }
        if (!table) return;

        const options = {
            key: 'ScheduledTable',
            rowSelector: 'tbody tr[data-task-id]',
            handleSelector: '.drag-handle',
            itemSelector: 'tbody tr[data-task-id]',
            placeholderType: 'row',
            cancelSelector: 'button, a, input, select, textarea, .scheduled-action-btn',
            collectOrder: getScheduledOrderFromTable,
            onReorder: async (order) => {
                if (!Array.isArray(latestTasks) || latestTasks.length === 0) {
                    await fetchTasks();
                }
                const fullOrder = buildScheduledFullOrder(order);
                if (!Array.isArray(fullOrder) || fullOrder.length !== latestTasks.length) {
                    alert('Reorder failed: incomplete order');
                    return;
                }
                const result = await reorderTasksOrder(fullOrder);
                if (result) {
                    const tasks = await fetchTasks();
                    if (!tasks) {
                        applyTaskOrderLocally(fullOrder);
                    }
                    if (typeof refreshCallback === 'function') {
                        await refreshCallback();
                    }
                }
            }
        };

        if (isTouch) {
            setupTouchReorder(table, options);
        } else {
            setupTableReorder(table, options);
        }
    }

    function renderTasksInto(container, tasks) {
        if (!container) return;
        container.innerHTML = renderTasksTable(tasks);
        setupTaskReorder(container);
    }

    function renderAccountsInto(container, accounts) {
        if (!container) return;
        container.innerHTML = renderAccountsTable(accounts);
        setupAccountsReorder(container);
    }

    function renderScheduledInto(container, data, refreshCallback) {
        if (!container) return;
        container.innerHTML = renderScheduledJobsTable(data);
        setupScheduledReorder(container, refreshCallback);
    }



﻿// 日志视图
async function initializeLogsView() {
    const logContainer = document.getElementById('log-content-container');
    const refreshBtn = document.getElementById('refresh-logs-btn');
    const autoRefreshCheckbox = document.getElementById('auto-refresh-logs-checkbox');
    const clearBtn = document.getElementById('clear-logs-btn');
    const taskFilter = document.getElementById('log-task-filter');
    const limitFilter = document.getElementById('log-display-limit');
    let currentLogSize = 0;

    const updateLogs = async (isFullRefresh = false) => {
        // 对于增量更新，在添加新内容之前检查用户是否在底部。
        const shouldAutoScroll = isFullRefresh || (logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 5);
        const selectedTaskName = taskFilter ? taskFilter.value : '';

        if (isFullRefresh) {
            currentLogSize = 0;
            logContainer.textContent = '正在加载...';
        }

        const logData = await fetchLogs(currentLogSize, selectedTaskName, parseInt(limitFilter ? limitFilter.value : 100));

        if (isFullRefresh) {
            // 如果日志为空，显示消息而不是空白屏幕。
            logContainer.textContent = logData.new_content || '日志为空，等待内容...';
        } else if (logData.new_content) {
            // 如果它正在显示空消息，替换它。
            if (logContainer.textContent === '正在加载...' || logContainer.textContent === '日志为空，等待内容...') {
                logContainer.textContent = logData.new_content;
            } else {
                logContainer.textContent += logData.new_content;
            }
        }
        currentLogSize = logData.new_pos;

        // 如果是完全刷新或用户已经在底部，则滚动到底部。
        if (shouldAutoScroll) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    };

    refreshBtn.addEventListener('click', () => updateLogs(true));

    // 条数筛选器change事件
    if (limitFilter) {
        limitFilter.addEventListener('change', () => updateLogs(true));
    }

    clearBtn.addEventListener('click', async () => {
        if (confirm('你确定要清空所有运行日志吗？此操作不可恢复。')) {
            const result = await clearLogs();
            if (result) {
                await updateLogs(true);
                alert('日志已清空。');
            }
        }
    });

    // 用唯一任务名称填充任务筛选器的函数
    async function populateTaskFilter() {
        if (!taskFilter) return;

        // 从服务器获取所有任务
        const tasks = await fetchTasks();

        if (tasks && tasks.length > 0) {
            // 获取唯一任务名称
            const uniqueTaskNames = [...new Set(tasks.map(task => task.task_name))].sort();

            // 保存当前选中的值
            const currentValue = taskFilter.value;

            // 清除除第一个选项外的所有现有选项 ("所有任务")
            taskFilter.innerHTML = '<option value="">所有任务</option>';

            // 添加系统选项
            const systemOption = document.createElement('option');
            systemOption.value = '系统';
            systemOption.textContent = '系统通知';
            if (systemOption.value === currentValue) {
                systemOption.selected = true;
            }
            taskFilter.appendChild(systemOption);

            // 添加新选项
            uniqueTaskNames.forEach(taskName => {
                const option = document.createElement('option');
                option.value = taskName;
                option.textContent = taskName;

                // 恢复当前选择
                if (option.value === currentValue) {
                    option.selected = true;
                }

                taskFilter.appendChild(option);
            });
        }
    }

    // 添加任务筛选器变化事件监听器
    if (taskFilter) {
        taskFilter.addEventListener('change', () => updateLogs(true));
    }

    // 初始化日志视图时填充任务筛选器
    await populateTaskFilter();

    // 点击刷新按钮时也填充任务筛选器
    refreshBtn.addEventListener('click', async () => {
        await populateTaskFilter();
        updateLogs(true);
    });

    const autoRefreshHandler = () => {
        if (autoRefreshCheckbox.checked) {
            if (logRefreshInterval) clearInterval(logRefreshInterval);
            logRefreshInterval = setInterval(() => updateLogs(false), 1000);
        } else {
            if (logRefreshInterval) {
                clearInterval(logRefreshInterval);
                logRefreshInterval = null;
            }
        }
    };

    autoRefreshCheckbox.addEventListener('change', autoRefreshHandler);

    // 默认启用自动刷新
    autoRefreshCheckbox.checked = true;
    autoRefreshHandler();
    await updateLogs(true);
}


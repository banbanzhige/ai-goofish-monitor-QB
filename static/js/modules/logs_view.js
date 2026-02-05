﻿// 日志视图 - 增强版
async function initializeLogsView() {
    const logContainer = document.getElementById('log-content-container');
    const refreshBtn = document.getElementById('refresh-logs-btn');
    const autoRefreshCheckbox = document.getElementById('auto-refresh-logs-checkbox');
    const clearBtn = document.getElementById('clear-logs-btn');
    const taskFilter = document.getElementById('log-task-filter');
    const limitFilter = document.getElementById('log-display-limit');
    const fileSelector = document.getElementById('log-file-selector');
    const levelFilter = document.getElementById('log-level-filter');
    const exportBtn = document.getElementById('export-logs-btn');
    let currentLogSize = 0;
    let hasRenderedContent = false;
    let lastRenderedLevel = '';

    const escapeHtml = (text) => {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    const isSeparatorLine = (line) => {
        const trimmed = line ? line.trim() : '';
        if (!trimmed) return false;
        return /^[-=]{6,}$/.test(trimmed);
    };

    const detectLogLevel = (line) => {
        if (!line) return '';
        if (isSeparatorLine(line)) {
            return 'separator';
        }
        const bracketMatch = line.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]/i);
        if (bracketMatch && bracketMatch[1]) {
            return bracketMatch[1].toLowerCase();
        }
        const jsonMatch = line.match(/"level"\s*:\s*"(DEBUG|INFO|WARNING|ERROR|CRITICAL)"/i);
        if (jsonMatch && jsonMatch[1]) {
            return jsonMatch[1].toLowerCase();
        }
        const prefixMatch = line.match(/^\s*(LOG|WARN|WARNING|ERR|ERROR)\s*[:：]/i);
        if (prefixMatch && prefixMatch[1]) {
            const normalized = prefixMatch[1].toLowerCase();
            if (normalized === 'log') {
                return 'info';
            }
            if (normalized === 'warn' || normalized === 'warning') {
                return 'warning';
            }
            if (normalized === 'err' || normalized === 'error') {
                return 'error';
            }
        }
        if (/^\s*(->|→)/.test(line)) {
            return 'info';
        }
        if (/(失败|异常|错误|超时|无法|不可用|未找到)/.test(line)) {
            return 'error';
        }
        if (/(警告|注意|告警|风险)/.test(line)) {
            return 'warning';
        }
        if (/(提示|请在|请先|开始|结束|完成|加载|加入执行队列|发送成功|通知)/.test(line)) {
            return 'info';
        }
        return '';
    };

    const buildLogHtml = (rawText, lastLevel = '') => {
        if (!rawText) return '';
        const rawLines = rawText.split('\n');
        let previousLevel = lastLevel;
        const htmlLines = rawLines.map((line) => {
            const detectedLevel = detectLogLevel(line);
            let effectiveLevel = detectedLevel;
            if (!effectiveLevel && previousLevel && previousLevel !== 'separator') {
                effectiveLevel = previousLevel;
            }
            if (detectedLevel && detectedLevel !== 'separator') {
                previousLevel = detectedLevel;
            }
            const levelClass = effectiveLevel ? ` log-level-${effectiveLevel}` : '';
            const safeLine = escapeHtml(line);
            return `<span class="log-line${levelClass}">${safeLine}</span>`;
        });
        return { html: htmlLines.join('<br>'), lastLevel: previousLevel };
    };

    const updateLogs = async (isFullRefresh = false) => {
        // 对于增量更新，在添加新内容之前检查用户是否在底部。
        const shouldAutoScroll = isFullRefresh || (logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 5);
        const selectedTaskName = taskFilter ? taskFilter.value : '';
        const selectedFile = fileSelector ? fileSelector.value : 'fetcher';
        const selectedLevel = levelFilter ? levelFilter.value : '';

        if (isFullRefresh) {
            currentLogSize = 0;
            logContainer.textContent = '正在加载...';
            hasRenderedContent = false;
            lastRenderedLevel = '';
        }

        const logData = await fetchLogs(
            currentLogSize,
            selectedTaskName,
            parseInt(limitFilter ? limitFilter.value : 100),
            selectedFile,
            selectedLevel
        );

        if (isFullRefresh) {
            // 如果日志为空，显示消息而不是空白屏幕。
            if (logData.new_content) {
                const rendered = buildLogHtml(logData.new_content, '');
                logContainer.innerHTML = rendered.html;
                lastRenderedLevel = rendered.lastLevel;
                hasRenderedContent = true;
            } else {
                logContainer.textContent = '日志为空，等待内容...';
                hasRenderedContent = false;
                lastRenderedLevel = '';
            }
        } else if (logData.new_content) {
            // 如果它正在显示空消息，替换它。
            const rendered = buildLogHtml(logData.new_content, lastRenderedLevel);
            if (!hasRenderedContent || logContainer.textContent === '正在加载...' || logContainer.textContent === '日志为空，等待内容...') {
                logContainer.innerHTML = rendered.html;
                hasRenderedContent = true;
            } else {
                logContainer.innerHTML += `<br>${rendered.html}`;
            }
            lastRenderedLevel = rendered.lastLevel;
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

    // 文件选择器change事件
    if (fileSelector) {
        fileSelector.addEventListener('change', () => updateLogs(true));
    }

    // 日志等级筛选器change事件
    if (levelFilter) {
        levelFilter.addEventListener('change', () => updateLogs(true));
    }

    // 导出日志包按钮
    if (exportBtn) {
        exportBtn.addEventListener('click', async () => {
            exportBtn.disabled = true;
            exportBtn.textContent = '⏳ 导出中...';
            try {
                const result = await exportLogs();
                if (result) {
                    Notification.success('日志导出成功');
                }
            } catch (e) {
                Notification.error('导出失败: ' + e.message);
            } finally {
                exportBtn.disabled = false;
                exportBtn.textContent = '📦 导出';
            }
        });
    }

    clearBtn.addEventListener('click', async () => {
        const selectedFile = fileSelector ? fileSelector.value : 'fetcher';
        const fileNames = {
            'fetcher': '运行日志',
            'system': '系统日志',
            'error': '错误日志'
        };
        const confirmResult = await Notification.confirm(`你确定要清空${fileNames[selectedFile] || selectedFile}吗？此操作不可恢复。`);
        if (confirmResult.isConfirmed) {
            const clearResult = await clearLogs(selectedFile);
            if (clearResult) {
                await updateLogs(true);
                Notification.info('日志已清空。');
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

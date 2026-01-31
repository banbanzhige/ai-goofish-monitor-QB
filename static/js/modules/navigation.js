﻿﻿﻿// 导航与路由
var navMainContent = null;
var navLinks = [];
var navigationInitialized = false;

async function navigateTo(hash) {
    if (logRefreshInterval) {
        clearInterval(logRefreshInterval);
        logRefreshInterval = null;
    }
    if (taskRefreshInterval) {
        clearInterval(taskRefreshInterval);
        taskRefreshInterval = null;
    }
    if (resultsRefreshInterval) {
        if (typeof resultsRefreshInterval.stop === 'function') {
            resultsRefreshInterval.stop();
        } else {
            clearInterval(resultsRefreshInterval);
        }
        resultsRefreshInterval = null;
    }
    const sectionId = hash.substring(1) || 'tasks';

    // 更新导航链接的激活状态
    navLinks.forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === `#${sectionId}`);
    });

    // 更新主要内容
    if (templates[sectionId]) {
        navMainContent.innerHTML = templates[sectionId]();
        // 使新内容可见
        const newSection = navMainContent.querySelector('.content-section');
        if (newSection) {
            requestAnimationFrame(() => {
                newSection.classList.add('active');
            });
        }


        if (sectionId === 'tasks') {
            const container = document.getElementById('tasks-table-container');
            const refreshTasks = async () => {
                if (isTaskReordering) return;
                const tasks = await fetchTasks();
                // 如果处于编辑模式，避免重新渲染以避免丢失用户输入
                if (container && !container.querySelector('tr.editing')) {
                    renderTasksInto(container, tasks);
                }
            };
            await refreshTasks();
            taskRefreshInterval = setInterval(refreshTasks, 5000);
        } else if (sectionId === 'results') {
            await initializeResultsView();
        } else if (sectionId === 'logs') {
            await initializeLogsView();
        } else if (sectionId === 'notifications') {
            await initializeNotificationsView();
        } else if (sectionId === 'model-management') {
            await initializeModelManagementView();
        } else if (sectionId === 'settings') {
            await initializeSettingsView();
        } else if (sectionId === 'scheduled') {
            await initializeScheduledView();
        } else if (sectionId === 'accounts') {
            await initializeAccountsView();
        }

    } else {
        navMainContent.innerHTML = '<section class="content-section active"><h2>页面未找到</h2></section>';
    }
}

async function initializeScheduledView() {
    const container = document.getElementById('scheduled-table-container');
    const refreshBtn = document.getElementById('refresh-scheduled-btn');

    const refreshScheduledJobs = async () => {
        const data = await fetchScheduledJobs();
        if (container) {
            renderScheduledInto(container, data, refreshScheduledJobs);
            attachScheduledEventListeners();
        }
    };

    const attachScheduledEventListeners = () => {
        // Cron 输入框失去焦点时保存
        container.querySelectorAll('.cron-input').forEach(input => {
            let isSelectingText = false;
            let originalValue = input.value;


            input.addEventListener('mousedown', () => {
                isSelectingText = true;
                originalValue = input.value;
            });


            const handleMouseUp = () => {

                setTimeout(() => {
                    isSelectingText = false;
                }, 50);
            };
            document.addEventListener('mouseup', handleMouseUp);

            input.addEventListener('blur', async (e) => {

                if (isSelectingText) {
                    e.preventDefault();

                    setTimeout(() => {
                        input.focus();
                    }, 10);
                    return;
                }

                const row = e.target.closest('[data-task-id]');
                const taskId = row.dataset.taskId;
                const newCron = e.target.value.trim();

                const result = await updateScheduledJobCron(taskId, newCron);
                if (result) {
                    await refreshScheduledJobs();
                }
            });

            // 按回车键也保存
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    isSelectingText = false;
                    e.target.blur();
                }
            });
        });

        // 跳过本次按钮
        container.querySelectorAll('.skip-job-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const jobId = btn.dataset.jobId;
                const result = await skipScheduledJob(jobId);
                if (result) {
                    await refreshScheduledJobs();
                }
            });
        });

        // 立刻执行按钮
        container.querySelectorAll('.run-now-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const jobId = btn.dataset.jobId;
                const result = await runScheduledJobNow(jobId);
                if (result) {
                    alert(result.message);
                }
            });
        });

        // 取消任务按钮
        container.querySelectorAll('.cancel-job-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const taskId = btn.dataset.taskId;
                if (confirm('任务将从定时调度中移除，确定要取消此任务吗？')) {
                    const result = await cancelScheduledTask(taskId);
                    if (result) {
                        alert(result.message);
                        await refreshScheduledJobs();
                    }
                }
            });
        });
    };

    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshScheduledJobs);
    }

    await refreshScheduledJobs();
}

// --- 账号管理视图 ---

function initNavigation(mainContent) {
    if (typeof navigateTo !== 'function') return;
    if (navigationInitialized) return;
    navigationInitialized = true;
    navMainContent = mainContent || null;
    navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const hash = this.getAttribute('href');
            if (window.location.hash !== hash) {
                window.location.hash = hash;
            }
        });
    });

    window.addEventListener('hashchange', () => {
        navigateTo(window.location.hash);
    });

    navigateTo(window.location.hash || '#tasks');
}

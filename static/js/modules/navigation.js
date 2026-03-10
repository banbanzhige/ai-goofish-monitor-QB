﻿// 导航与路由
var navMainContent = null;
var navLinks = [];
var navigationInitialized = false;
var navPagePermissionInfo = null;
var navPagePermissionPromise = null;
var navStatsRefreshTimer = null;
var navStatsLoading = false;
const NAV_STATS_REFRESH_INTERVAL_MS = 30000;

function setSidebarCountBadge(elementId, count) {
    const badge = document.getElementById(elementId);
    if (!badge) return;

    const safeCount = Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
    badge.textContent = safeCount > 99 ? '99+' : String(safeCount);
    badge.classList.toggle('nav-count-muted', safeCount === 0);
}

function countRunningTasks(tasks) {
    if (!Array.isArray(tasks)) return 0;
    return tasks.filter(task => Boolean(task && task.is_running === true)).length;
}

function countValidAccounts(accounts) {
    if (!Array.isArray(accounts)) return 0;
    return accounts.filter(account => account && account.cookie_status === 'valid').length;
}

function countQueuedSchedules(scheduledJobs) {
    if (!Array.isArray(scheduledJobs)) return 0;
    return scheduledJobs.filter(job => !Boolean(job && job.is_running === true)).length;
}

function refreshSidebarStatsBadges() {
    setSidebarCountBadge('nav-count-tasks', countRunningTasks(latestTasks));
    setSidebarCountBadge('nav-count-accounts', countValidAccounts(latestAccounts));
    setSidebarCountBadge('nav-count-scheduled', countQueuedSchedules(latestScheduledJobs));
}

async function refreshSidebarStatsData() {
    if (navStatsLoading) return;
    navStatsLoading = true;
    try {
        const requests = [];
        if (canAccessSection('tasks')) {
            requests.push(fetchTasks());
        }
        if (canAccessSection('accounts')) {
            requests.push(fetchAccounts());
        }
        if (canAccessSection('scheduled')) {
            requests.push(fetchScheduledJobs());
        }
        if (requests.length > 0) {
            // 并行刷新三类统计数据，避免阻塞导航交互
            await Promise.all(requests);
        }
    } catch (_) {
        // 统计拉取失败时保持静默，避免打断页面使用
    } finally {
        navStatsLoading = false;
        refreshSidebarStatsBadges();
    }
}

function getSectionIdFromLink(link) {
    if (!link) return '';
    const href = link.getAttribute('href') || '';
    return href.startsWith('#') ? href.substring(1) : href;
}

function canAccessSection(sectionId) {
    if (!navPagePermissionInfo || !navPagePermissionInfo.accessible_pages) {
        return true;
    }
    if (!Object.prototype.hasOwnProperty.call(navPagePermissionInfo.accessible_pages, sectionId)) {
        return true;
    }
    return Boolean(navPagePermissionInfo.accessible_pages[sectionId]);
}

function getFirstAccessibleSection() {
    for (const link of navLinks) {
        const sectionId = getSectionIdFromLink(link);
        if (sectionId && canAccessSection(sectionId)) {
            return sectionId;
        }
    }
    return '';
}

function applyNavigationPermissions() {
    navLinks.forEach(link => {
        const sectionId = getSectionIdFromLink(link);
        const navItem = link.closest('li');
        if (!navItem || !sectionId) return;
        navItem.style.display = canAccessSection(sectionId) ? '' : 'none';
    });
}

async function ensureNavPagePermissionsLoaded() {
    if (navPagePermissionInfo) {
        return navPagePermissionInfo;
    }
    if (!navPagePermissionPromise) {
        navPagePermissionPromise = (async () => {
            try {
                const response = await fetch('/api/users/page-permissions');
                if (!response.ok) {
                    return null;
                }
                return await response.json();
            } catch (error) {
                return null;
            }
        })();
    }
    navPagePermissionInfo = await navPagePermissionPromise;
    return navPagePermissionInfo;
}

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
    await ensureNavPagePermissionsLoaded();
    applyNavigationPermissions();

    const rawSectionId = hash.substring(1) || 'tasks';
    const sectionId = canAccessSection(rawSectionId) ? rawSectionId : '';
    if (!sectionId) {
        const fallbackSection = getFirstAccessibleSection();
        if (fallbackSection && fallbackSection !== rawSectionId) {
            window.location.hash = `#${fallbackSection}`;
            return;
        }
        navMainContent.innerHTML = '<section class="content-section active"><h2>权限不足</h2><p>当前账号无法访问此页面。</p></section>';
        return;
    }

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
        } else if (sectionId === 'user-data') {
            await initializeUsersView();
        } else if (sectionId === 'profile') {
            await initializeProfileView();
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
                    Notification.success(result.message || '已触发立刻执行');
                }
            });
        });

        // 取消任务按钮
        container.querySelectorAll('.cancel-job-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const taskId = btn.dataset.taskId;
                const confirmResult = await Notification.confirm('任务将从定时调度中移除，确定要取消此任务吗？');
                if (confirmResult.isConfirmed) {
                    const cancelResult = await cancelScheduledTask(taskId);
                    if (cancelResult) {
                        Notification.success(cancelResult.message || '定时任务已取消');
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

    refreshSidebarStatsBadges();
    refreshSidebarStatsData();
    if (navStatsRefreshTimer) {
        clearInterval(navStatsRefreshTimer);
    }
    navStatsRefreshTimer = setInterval(refreshSidebarStatsData, NAV_STATS_REFRESH_INTERVAL_MS);

    navigateTo(window.location.hash || '#tasks');
}

﻿// --- API 函数 ---
async function fetchNotificationSettings() {
    try {
        const response = await fetch('/api/settings/notifications');
        if (!response.ok) throw new Error('无法获取通知设置');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function fetchAISettings() {
    try {
        const response = await fetch('/api/settings/ai');
        if (!response.ok) throw new Error('无法获取AI设置');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function updateAISettings(settings) {
    try {
        const response = await fetch('/api/settings/ai', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新AI设置失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法更新AI设置:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchProxySettings() {
    try {
        const response = await fetch('/api/settings/proxy');
        if (!response.ok) throw new Error('无法获取代理设置');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function updateProxySettings(settings) {
    try {
        const response = await fetch('/api/settings/proxy', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新代理设置失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法更新代理设置:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function testAISettings(settings, options = {}) {
    const { silent = false } = options;
    try {
        const response = await fetch('/api/settings/ai/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '测试AI设置失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法测试AI设置:', error);
        if (!silent) {
            alert(`错误: ${error.message}`);
        }
        return null;
    }
}

async function updateNotificationSettings(settings) {
    try {
        const response = await fetch('/api/settings/notifications', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新通知设置失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法更新通知设置:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchPrompts() {
    try {
        const response = await fetch('/api/prompts');
        if (!response.ok) throw new Error('无法获取Prompt列表');
        return await response.json();
    } catch (error) {
        console.error(error);
        return [];
    }
}

async function fetchPromptContent(filename) {
    try {
        const response = await fetch(`/api/prompts/${filename}`);
        if (!response.ok) throw new Error(`无法获取Prompt文件 ${filename} 的内容`);
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function updatePrompt(filename, content) {
    try {
        const response = await fetch(`/api/prompts/${filename}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新Prompt失败');
        }
        return await response.json();
    } catch (error) {
        console.error(`无法更新Prompt ${filename}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchBayesProfiles() {
    try {
        const response = await fetch('/api/bayes');
        if (!response.ok) throw new Error('无法获取Bayes列表');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function fetchBayesGuide() {
    try {
        const response = await fetch('/api/guides/bayes');
        if (!response.ok) throw new Error('无法获取Bayes指引');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function fetchBayesContent(filename) {
    try {
        const response = await fetch(`/api/bayes/${filename}`);
        if (!response.ok) throw new Error(`无法获取Bayes文件 ${filename} 的内容`);
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function updateBayes(filename, content) {
    try {
        const response = await fetch(`/api/bayes/${filename}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新Bayes失败');
        }
        return await response.json();
    } catch (error) {
        console.error(`无法更新Bayes ${filename}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function createBayesProfile(filename, content) {
    try {
        const response = await fetch('/api/bayes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, content }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '创建Bayes文件失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法创建Bayes文件:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function deleteBayesProfile(filename) {
    try {
        const response = await fetch(`/api/bayes/${filename}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '删除Bayes文件失败');
        }
        return await response.json();
    } catch (error) {
        console.error('无法删除Bayes文件:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function createTaskWithAI(data) {
    try {
        const response = await fetch(`/api/tasks/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '通过AI创建任务失败');
        }
        console.log(`AI任务创建成功!`);
        return await response.json();
    } catch (error) {
        console.error(`无法通过AI创建任务:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function startSingleTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/start/${taskId}`, {
            method: 'POST',
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '启动任务失败');
        }
        return await response.json();
    } catch (error) {
        console.error(`无法启动任务 ${taskId}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function stopSingleTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/stop/${taskId}`, {
            method: 'POST',
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '停止任务失败');
        }
        return await response.json();
    } catch (error) {
        console.error(`无法停止任务 ${taskId}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '删除任务失败');
        }
        console.log(`任务 ${taskId} 删除成功!`);
        return await response.json();
    } catch (error) {
        console.error(`无法删除任务 ${taskId}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function updateTask(taskId, data) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新任务失败');
        }
        console.log(`任务 ${taskId} 更新成功!`);
        return await response.json();
    } catch (error) {
        console.error(`无法更新任务 ${taskId}:`, error);

        let errorMessage = '更新任务失败';
        if (error && error.message) {
            errorMessage = error.message;
        } else if (typeof error === 'string') {
            errorMessage = error;
        } else if (typeof error === 'object') {
            errorMessage = JSON.stringify(error);
        }
        alert(`错误: ${errorMessage}`);
        return null;
    }
}

async function fetchTasks() {
    try {
        const response = await fetch('/api/tasks');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const tasks = await response.json();
        latestTasks = Array.isArray(tasks) ? tasks.slice() : [];
        return tasks;
    } catch (error) {
        console.error("无法获取任务列表:", error);
        return null;
    }
}

async function reorderTasksOrder(orderedIds) {
    try {
        const response = await fetch('/api/tasks/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordered_ids: orderedIds })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Reorder failed');
        }
        return await response.json();
    } catch (error) {
        console.error('Reorder tasks failed:', error);
        alert(`Reorder failed: ${error.message}`);
        return null;
    }
}

async function fetchResultFiles() {
    try {
        const response = await fetch('/api/results/files');
        if (!response.ok) throw new Error('无法获取结果文件列表');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function deleteResultFile(filename) {
    try {
        const response = await fetch(`/api/results/files/${filename}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '删除结果文件失败');
        }
        return await response.json();
    } catch (error) {
        console.error(`无法删除结果文件 ${filename}:`, error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function deleteResultsBatch(payload) {
    try {
        const response = await fetch('/api/results/delete-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '批量删除结果失败');
        }
        return await response.json();
    } catch (error) {
        console.error('批量删除结果失败:', error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchResultContent(filename, recommendedOnly, taskName, keyword, aiCriteria, sortBy, sortOrder, manualKeyword) {
    try {
        const params = new URLSearchParams({
            page: 1,
            limit: 100, // 获取足够数量的条目
            recommended_only: recommendedOnly,
            task_name: taskName,
            keyword: keyword,
            ai_criteria: aiCriteria,
            sort_by: sortBy,
            sort_order: sortOrder,
            manual_keyword: manualKeyword || ''
        });
        const response = await fetch(`/api/results/${filename}?${params}`);
        if (!response.ok) throw new Error(`无法获取文件 ${filename} 的内容`);
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/settings/status');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("无法获取系统状态:", error);
        return null;
    }
}

async function clearLogs() {
    try {
        const response = await fetch('/api/logs', { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '清空日志失败');
        }
        return await response.json();
    } catch (error) {
        console.error("无法清空日志:", error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function sendNotification(itemData) {
    try {
        const response = await fetch('/api/notifications/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(itemData),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '发送通知失败');
        }
        return await response.json();
    } catch (error) {
        console.error("无法发送通知:", error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchLogs(fromPos = 0, taskName = '', limit = 100) {
    try {
        const params = new URLSearchParams({
            from_pos: fromPos,
            limit: limit
        });
        if (taskName) {
            params.append('task_name', taskName);
        }
        const response = await fetch(`/api/logs?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("无法获取日志:", error);
        return { new_content: `\n加载日志失败: ${error.message}`, new_pos: fromPos };
    }
}

// --- 定时任务 API ---
async function fetchScheduledJobs() {
    try {
        const response = await fetch('/api/scheduled-jobs');
        if (!response.ok) throw new Error('无法获取定时任务列表');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}

async function skipScheduledJob(jobId) {
    try {
        const response = await fetch(`/api/scheduled-jobs/${jobId}/skip`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '跳过任务失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function runScheduledJobNow(jobId) {
    try {
        const response = await fetch(`/api/scheduled-jobs/${jobId}/run-now`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '立即执行失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function updateScheduledJobCron(taskId, cron) {
    try {
        const response = await fetch(`/api/scheduled-jobs/${taskId}/cron`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cron: cron })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '更新Cron失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function cancelScheduledTask(taskId) {
    try {
        const response = await fetch(`/api/scheduled-jobs/${taskId}/cancel`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '取消任务失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

// --- 账号管理 API ---
async function fetchAccounts() {
    try {
        const response = await fetch('/api/accounts');
        if (!response.ok) throw new Error('无法获取账号列表');
        const accounts = await response.json();
        latestAccounts = Array.isArray(accounts) ? accounts.slice() : [];
        return accounts;
    } catch (error) {
        console.error(error);
        return [];
    }
}

async function reorderAccountsOrder(orderedNames) {
    try {
        const response = await fetch('/api/accounts/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordered_names: orderedNames })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Reorder failed');
        }
        return await response.json();
    } catch (error) {
        console.error('Reorder accounts failed:', error);
        alert(`Reorder failed: ${error.message}`);
        return null;
    }
}

async function createAccount(data) {
    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '创建账号失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function updateAccount(name, data) {
    try {
        const response = await fetch(`/api/accounts/${name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '更新账号失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function deleteAccount(name) {
    try {
        const response = await fetch(`/api/accounts/${name}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '删除账号失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function cleanupExpiredAccounts() {
    try {
        const response = await fetch('/api/accounts/cleanup-expired', { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '批量清理失效账号失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function activateAccount(name) {
    try {
        const response = await fetch(`/api/accounts/${name}/activate`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '激活账号失败');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`错误: ${error.message}`);
        return null;
    }
}

async function fetchAccountDetail(name) {
    try {
        const response = await fetch(`/api/accounts/${name}`);
        if (!response.ok) throw new Error('无法获取账号详情');
        return await response.json();
    } catch (error) {
        console.error(error);
        return null;
    }
}


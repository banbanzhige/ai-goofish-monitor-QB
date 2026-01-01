document.addEventListener('DOMContentLoaded', function() {
    const mainContent = document.getElementById('main-content');
    const navLinks = document.querySelectorAll('.nav-link');
    let logRefreshInterval = null;
    let taskRefreshInterval = null;

        // --- 各部分的模板 ---
        const templates = {
        tasks: () => `
            <section id="tasks-section" class="content-section">
                <div class="section-header">
                    <h2>任务管理</h2>
                    <button id="add-task-btn" class="control-button primary-btn">➕ 创建新任务</button>
                </div>
                <div id="tasks-table-container">
                    <p>正在加载任务列表...</p>
                </div>
            </section>`,
            results: () => `
            <section id="results-section" class="content-section">
                <div class="section-header">
                    <h2>结果查看</h2>
                </div>
                <div class="results-filter-bar">
                    <div class="filter-group">
                        <div class="filter-label">结果文件</div>
                        <select id="result-file-selector">
                            <option value="">正在加载...</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">任务名称</div>
                        <select id="task-name-filter">
                            <option value="all">所有任务</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">关键词</div>
                        <select id="keyword-filter">
                            <option value="all">所有关键词</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">AI标准</div>
                        <select id="ai-criteria-filter">
                            <option value="all">所有AI标准</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">排序字段</div>
                        <select id="sort-by-selector">
                            <option value="crawl_time">按爬取时间</option>
                            <option value="publish_time">按发布时间</option>
                            <option value="price">按价格</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">排序方式</div>
                        <select id="sort-order-selector">
                            <option value="desc">降序</option>
                            <option value="asc">升序</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">手动筛选</div>
                        <input type="text" id="manual-keyword-filter" placeholder="输入关键词筛选" style="width: 250px; height: 36px; box-sizing: border-box; padding: 0 10px;">
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">删除</div>
                        <button id="delete-results-btn" class="control-button danger-btn" disabled>删除结果</button>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">刷新</div>
                        <button id="refresh-results-btn" class="control-button">🔄 刷新</button>
                    </div>
                    <div class="filter-group">
                        <div class="filter-label">仅看ai推荐</div>
                        <label class="switch">
                            <input type="checkbox" id="recommended-only-checkbox">
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <div id="results-grid-container">
                    <p>请先选择一个结果文件。</p>
                </div>
            </section>`,
        logs: () => `
            <section id="logs-section" class="content-section">
                <div class="section-header">
                    <h2>运行日志</h2>
                    <div class="log-controls">
                        <div class="filter-group">
                            <label for="auto-refresh-logs-checkbox">
                                <div class="switch">
                                    <input type="checkbox" id="auto-refresh-logs-checkbox" checked>
                                    <span class="slider round"></span>
                                </div>
                                自动刷新
                            </label>
                        </div>
                        <div class="filter-group">
                            <select id="log-task-filter">
                                <option value="">所有任务</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <button id="refresh-logs-btn" class="control-button">🔄 刷新</button>
                        </div>
                        <div class="filter-group">
                            <button id="clear-logs-btn" class="control-button danger-btn">🗑️ 清空日志</button>
                        </div>
                    </div>
                </div>
                <pre id="log-content-container">正在加载日志...</pre>
            </section>`,
        notifications: () => `
            <section id="notifications-section" class="content-section">
                <div class="section-header">
                    <h2>通知配置</h2>
                </div>
                <div class="settings-card">
                    <div id="notification-settings-container">
                        <p>正在加载通知配置...</p>
                    </div>
                </div>
            </section>`,
        settings: () => `
            <section id="settings-section" class="content-section">
                <h2>系统设置</h2>
                <div class="settings-card">
                    <h3>系统状态检查</h3>
                    <div id="system-status-container"><p>正在加载状态...</p></div>
                </div>
                <div class="settings-card">
                    <h3>Prompt 管理</h3>
                    <div class="prompt-manager">
                        <div class="prompt-list-container">
                            <label for="prompt-selector">选择要编辑的 Prompt:</label>
                            <select id="prompt-selector"><option>加载中...</option></select>
                        </div>
                        <div class="prompt-editor-container">
                            <textarea id="prompt-editor" spellcheck="false" disabled placeholder="请先从上方选择一个 Prompt 文件进行编辑..."></textarea>
                            <button id="save-prompt-btn" class="control-button primary-btn" disabled>保存更改</button>
                        </div>
                    </div>
                </div>
            </section>`
    };

        // --- API 函数 ---
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
                headers: {'Content-Type': 'application/json'},
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

    async function testAISettings(settings) {
        try {
            const response = await fetch('/api/settings/ai/test', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings),
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '测试AI设置失败');
            }
            return await response.json();
        } catch (error) {
            console.error('无法测试AI设置:', error);
            alert(`错误: ${error.message}`);
            return null;
        }
    }

    async function updateNotificationSettings(settings) {
        try {
            const response = await fetch('/api/settings/notifications', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
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
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({content: content}),
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
            // TODO: Use a more elegant notification system
            alert(`错误: ${error.message}`);
            return null;
        }
    }

    async function fetchTasks() {
        try {
            const response = await fetch('/api/tasks');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error("无法获取任务列表:", error);
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

    async function fetchResultContent(filename, recommendedOnly, taskName, keyword, aiCriteria, sortBy, sortOrder, manualKeyword) {
        try {
            const params = new URLSearchParams({
                page: 1,
                limit: 100, // Fetch a decent number of items
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
            const response = await fetch('/api/logs', {method: 'DELETE'});
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

    async function deleteLoginState() {
        try {
            const response = await fetch('/api/login-state', {method: 'DELETE'});
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '删除登录凭证失败');
            }
            return await response.json();
        } catch (error) {
            console.error("无法删除登录凭证:", error);
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

    async function fetchLogs(fromPos = 0, taskName = '') {
        try {
            const params = new URLSearchParams({
                from_pos: fromPos
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
            return {new_content: `\n加载日志失败: ${error.message}`, new_pos: fromPos};
        }
    }

        // --- 渲染函数 ---
        function renderLoginStatusWidget(status) {
        const container = document.getElementById('login-status-widget-container');
        if (!container) return;

        const loginState = status.login_state_file;
        let content = '';
        
        // Create manual login button HTML with dropdown for "已获取cookie" state
        let manualLoginBtnHtml = '';
        if (loginState && loginState.exists) {
                manualLoginBtnHtml = `
                <div class="login-status-widget">
                <div style="position: relative; display: inline-block; vertical-align: middle; margin-right: 15px;">
                        <button class="control-button primary-btn" style="background-color: #fff533; color: black; padding: 8px 12px; border: 1px solid #fff533;">
                            ✓ 已获取cookie
                        </button>
                        <div class="dropdown-menu">
                            <a href="#" class="dropdown-item" id="update-login-state-btn-widget">自动更新</a>
                            <a href="#" class="dropdown-item delete" id="delete-login-state-btn-widget">删除凭证</a>
                        </div>
                    </div>
                    <div style="position: relative; display: inline-block; vertical-align: middle;">
                        <button class="control-button primary-btn status-ok" style="background-color: #fff533; color: black; border: 1px solid #fff533;">✓ 已登录</button>
                        <div class="dropdown-menu">
                            <a href="#" class="dropdown-item" id="update-login-state-btn-widget">手动更新</a>
                            <a href="#" class="dropdown-item delete" id="delete-login-state-btn-widget">删除凭证</a>
                        </div>
                    </div>
                </div>
            `;
            content = manualLoginBtnHtml;
            } else {
            const loginBtnColor = '#dc3545';
            const loginBtnText = '点击自动获取cookie登录';
            manualLoginBtnHtml = `
                <button id="manual-login-btn-header" class="control-button primary-btn" style="background-color: ${loginBtnColor}; border: 1px solid ${loginBtnColor}; color: white; padding: 8px 12px; margin-right: 15px; display: inline-block; vertical-align: middle;">
                    ${loginBtnText}
                </button>
            `;
            content = `
                <div class="login-status-widget">
                    ${manualLoginBtnHtml}
                    <button id="update-login-state-btn-widget" class="control-button primary-btn status-error" style="background-color: #dc3545; border: 1px solid #dc3545; color: white; display: inline-block; vertical-align: middle;">! 闲鱼未登录 (手动登录)</button>
                </div>
            `;
        }
        container.innerHTML = content;
        
        // Add click event for manual login button (need to add it after setting innerHTML)
        const manualLoginBtn = document.getElementById('manual-login-btn-header');
        if (manualLoginBtn) {
            manualLoginBtn.addEventListener('click', async () => {
                // Show custom modal instead of browser confirm dialog
                const confirmModal = document.getElementById('manual-login-confirm-modal');
                if (!confirmModal) return;
                
                // Display the modal
                confirmModal.style.display = 'flex';
                setTimeout(() => confirmModal.classList.add('visible'), 10);
                
                // Get modal elements
                const confirmBtn = document.getElementById('confirm-manual-login-confirm-btn');
                const cancelBtn = document.getElementById('cancel-manual-login-confirm-btn');
                const closeBtn = document.getElementById('close-manual-login-confirm-modal');
                
                // Function to close the modal
                const closeModal = () => {
                    confirmModal.classList.remove('visible');
                    setTimeout(() => {
                        confirmModal.style.display = 'none';
                    }, 300); // Match the modal transition duration
                };
                
                    // Function to handle the confirmation action
                    const handleConfirmation = async () => {
                        try {
                            const response = await fetch('/api/manual-login', {
                                method: 'POST'
                            });
                            
                            if (!response.ok) {
                                const errorData = await response.json();
                                alert('启动失败: ' + (errorData.detail || '未知错误'));
                            } else {
                                // 开始轮询检查登录状态
                                const pollInterval = 2000; // 每 2 秒检查一次
                                const pollTimeout = 300000; // 300 秒后超时
                                let pollAttempts = 0;
                                const maxAttempts = pollTimeout / pollInterval;
                                
                                // 开始轮询检查登录状态
                                const intervalId = setInterval(async () => {
                                    pollAttempts++;
                                    
                                    try {
                                        const status = await fetchSystemStatus();
                                        if (status && status.login_state_file && status.login_state_file.exists) {
                                            // 登录状态已更新，刷新登录状态 widget
                                            await refreshLoginStatusWidget();
                                            // 停止轮询
                                            clearInterval(intervalId);
                                            return;
                                        }
                                    } catch (error) {
                                        console.error('轮询检查登录状态时出错:', error);
                                    }
                                    
                                    // 检查是否超时
                                    if (pollAttempts >= maxAttempts) {
                                        console.log('轮询检查登录状态超时');
                                        clearInterval(intervalId);
                                        return;
                                    }
                                }, pollInterval);
                            }
                            // No alert for success - directly close the modal
                        } catch (error) {
                            alert('启动失败: ' + error.message);
                        } finally {
                            closeModal();
                        }
                    };
                
                // Add event listeners with once: true to avoid memory leaks
                confirmBtn.addEventListener('click', handleConfirmation, { once: true });
                cancelBtn.addEventListener('click', closeModal, { once: true });
                closeBtn.addEventListener('click', closeModal, { once: true });
                
                    // Add click outside to close functionality
                    confirmModal.addEventListener('click', (e) => {
                        if (e.target === confirmModal) closeModal();
                    }, { once: true });
            });
        }
    }

    function renderNotificationSettings(settings) {
        if (!settings) return '<p>无法加载通知设置。</p>';

        return `
            <form id="notification-settings-form">
                <div class="notification-channel-card">
                    <h4>通用配置</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="pcurl-to-mobile" name="PCURL_TO_MOBILE" ${settings.PCURL_TO_MOBILE ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">将电脑版链接转换为手机版</div>
                                <p class="form-hint" style="margin: 2px 0;">在通知中将电脑版商品链接转换为手机版</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Ntfy 通知</h4>
                    <div class="form-group">
                        <label for="ntfy-topic-url">Topic URL</label>
                        <input type="text" id="ntfy-topic-url" name="NTFY_TOPIC_URL" value="${settings.NTFY_TOPIC_URL || ''}" placeholder="例如: https://ntfy.sh/your_topic">
                        <p class="form-hint">用于发送通知到 ntfy.sh 服务</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="ntfy" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Gotify 通知</h4>
                    <div class="form-group">
                        <label for="gotify-url">服务地址</label>
                        <input type="text" id="gotify-url" name="GOTIFY_URL" value="${settings.GOTIFY_URL || ''}" placeholder="例如: https://push.example.de">
                        <p class="form-hint">Gotify 服务地址</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="gotify-token">应用 Token</label>
                        <input type="text" id="gotify-token" name="GOTIFY_TOKEN" value="${settings.GOTIFY_TOKEN || ''}" placeholder="例如: your_gotify_token">
                        <p class="form-hint">Gotify 应用的 Token</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="gotify" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Bark 通知</h4>
                    <div class="form-group">
                        <label for="bark-url">推送地址</label>
                        <input type="text" id="bark-url" name="BARK_URL" value="${settings.BARK_URL || ''}" placeholder="例如: https://api.day.app/your_key">
                        <p class="form-hint">Bark 推送地址</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="bark" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>企业微信机器人通知</h4>
                    <div class="form-group">
                        <label for="wx-bot-url">Webhook URL</label>
                        <input type="text" id="wx-bot-url" name="WX_BOT_URL" value="${settings.WX_BOT_URL || ''}" placeholder="例如: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key">
                        <p class="form-hint">企业微信机器人的 Webhook 地址</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="wx_bot" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>企业微信应用通知</h4>
                    <div class="form-group">
                        <label for="wx-corp-id">企业 ID</label>
                        <input type="text" id="wx-corp-id" name="WX_CORP_ID" value="${settings.WX_CORP_ID || ''}" placeholder="例如: wwxxxxxxxxx">
                        <p class="form-hint">企业微信管理后台获取</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="wx-agent-id">应用 ID</label>
                        <input type="text" id="wx-agent-id" name="WX_AGENT_ID" value="${settings.WX_AGENT_ID || ''}" placeholder="例如: 1000001">
                        <p class="form-hint">企业微信管理后台获取</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="wx-secret">应用密钥</label>
                        <input type="text" id="wx-secret" name="WX_SECRET" value="${settings.WX_SECRET || ''}" placeholder="例如: your_app_secret">
                        <p class="form-hint">企业微信管理后台获取</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="wx-to-user">通知用户 (可选)</label>
                        <input type="text" id="wx-to-user" name="WX_TO_USER" value="${settings.WX_TO_USER || ''}" placeholder="例如: UserID1|UserID2 或 @all">
                        <p class="form-hint">接收通知的用户ID列表，用|分隔，或@all通知所有用户</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="wx_app" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Telegram 机器人通知</h4>
                    <div class="form-group">
                        <label for="telegram-bot-token">Bot Token</label>
                        <input type="text" id="telegram-bot-token" name="TELEGRAM_BOT_TOKEN" value="${settings.TELEGRAM_BOT_TOKEN || ''}" placeholder="例如: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789">
                        <p class="form-hint">Telegram 机器人的 Token，从 @BotFather 获取</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="telegram-chat-id">Chat ID</label>
                        <input type="text" id="telegram-chat-id" name="TELEGRAM_CHAT_ID" value="${settings.TELEGRAM_CHAT_ID || ''}" placeholder="例如: 123456789">
                        <p class="form-hint">Telegram Chat ID，从 @userinfobot 获取</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="telegram" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>通用 Webhook 通知</h4>
                    <div class="form-group">
                        <label for="webhook-url">URL 地址</label>
                        <input type="text" id="webhook-url" name="WEBHOOK_URL" value="${settings.WEBHOOK_URL || ''}" placeholder="例如: https://your-webhook-url.com/endpoint">
                        <p class="form-hint">通用 Webhook 的 URL 地址</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="webhook-method">请求方法</label>
                        <select id="webhook-method" name="WEBHOOK_METHOD">
                            <option value="POST" ${settings.WEBHOOK_METHOD === 'POST' ? 'selected' : ''}>POST</option>
                            <option value="GET" ${settings.WEBHOOK_METHOD === 'GET' ? 'selected' : ''}>GET</option>
                        </select>
                        <p class="form-hint">Webhook 请求方法</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="webhook-headers">请求头 (JSON)</label>
                        <textarea id="webhook-headers" name="WEBHOOK_HEADERS" rows="3" placeholder='例如: {"Authorization": "Bearer token"}'>${settings.WEBHOOK_HEADERS || ''}</textarea>
                        <p class="form-hint">必须是有效的 JSON 字符串</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="webhook-content-type">内容类型</label>
                        <select id="webhook-content-type" name="WEBHOOK_CONTENT_TYPE">
                            <option value="JSON" ${settings.WEBHOOK_CONTENT_TYPE === 'JSON' ? 'selected' : ''}>JSON</option>
                            <option value="FORM" ${settings.WEBHOOK_CONTENT_TYPE === 'FORM' ? 'selected' : ''}>FORM</option>
                        </select>
                        <p class="form-hint">POST 请求的内容类型</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="webhook-query-parameters">查询参数 (JSON)</label>
                        <textarea id="webhook-query-parameters" name="WEBHOOK_QUERY_PARAMETERS" rows="3" placeholder='例如: {"param1": "value1"}'>${settings.WEBHOOK_QUERY_PARAMETERS || ''}</textarea>
                        <p class="form-hint">GET 请求的查询参数，支持 \${title} 和 \${content} 占位符</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="webhook-body">请求体 (JSON)</label>
                        <textarea id="webhook-body" name="WEBHOOK_BODY" rows="3" placeholder='例如: {"message": "\${content}"}'>${settings.WEBHOOK_BODY || ''}</textarea>
                        <p class="form-hint">POST 请求的请求体，支持 \${title} 和 \${content} 占位符</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="webhook" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试通知</button>
                    </div>
                </div>
                
                <button type="submit" class="control-button primary-btn">保存通知设置</button>
            </form>
        `;
    }

    function renderAISettings(settings) {
        if (!settings) return '<p>无法加载AI设置。</p>';

        return `
            <form id="ai-settings-form">
                <div class="form-group">
                    <label for="openai-api-key">API Key *</label>
                    <input type="password" id="openai-api-key" name="OPENAI_API_KEY" value="${settings.OPENAI_API_KEY || ''}" placeholder="例如: sk-..." required>
                    <p class="form-hint">你的AI模型服务商提供的API Key</p>
                </div>
                
                <div class="form-group">
                    <label for="openai-base-url">API Base URL *</label>
                    <input type="text" id="openai-base-url" name="OPENAI_BASE_URL" value="${settings.OPENAI_BASE_URL || ''}" placeholder="例如: https://api.openai.com/v1/" required>
                    <p class="form-hint">AI模型的API接口地址，必须兼容OpenAI格式</p>
                </div>
                
                <div class="form-group">
                    <label for="openai-model-name">模型名称 *</label>
                    <input type="text" id="openai-model-name" name="OPENAI_MODEL_NAME" value="${settings.OPENAI_MODEL_NAME || ''}" placeholder="例如: gemini-2.5-pro" required>
                    <p class="form-hint">你要使用的具体模型名称，必须支持图片分析</p>
                </div>
                
                <div class="form-group">
                    <label for="proxy-url">代理地址 (可选)</label>
                    <input type="text" id="proxy-url" name="PROXY_URL" value="${settings.PROXY_URL || ''}" placeholder="例如: http://127.0.0.1:7890">
                    <p class="form-hint">HTTP/S代理地址，支持 http 和 socks5 格式</p>
                </div>
                
                <div class="form-group">
                    <button type="button" id="test-ai-settings-btn" class="control-button">测试连接（浏览器）</button>
                    <button type="button" id="test-ai-settings-backend-btn" class="control-button">测试连接（后端容器）</button>
                    <button type="submit" class="control-button primary-btn">保存AI设置</button>
                </div>
            </form>
        `;
    }

    async function refreshLoginStatusWidget() {
        const status = await fetchSystemStatus();
        if (status) {
            renderLoginStatusWidget(status);
            
        // Add click event for login status widget to toggle dropdowns for both "已获取cookie" and "已登录" buttons
        const loginStatusWidget = document.querySelector('.login-status-widget');
        if (loginStatusWidget) {
            // Select only the first two control buttons which have dropdowns
            const buttons = loginStatusWidget.querySelectorAll('.control-button');
            // Process only the first two buttons which should have dropdowns
            for (let i = 0; i < Math.min(buttons.length, 2); i++) {
                const btn = buttons[i];
                let dropdownMenu = btn.nextElementSibling;
                
                // Check if we found a dropdown menu
                if (dropdownMenu && dropdownMenu.classList.contains('dropdown-menu')) {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        // Toggle this dropdown
                        dropdownMenu.style.display = dropdownMenu.style.display === 'block' ? 'none' : 'block';
                        
                        // Close other dropdowns in the widget
                        loginStatusWidget.querySelectorAll('.dropdown-menu').forEach((menu) => {
                            if (menu !== dropdownMenu) {
                                menu.style.display = 'none';
                            }
                        });
                    });
                    
                    // Prevent event bubbling to avoid unexpected behavior
                    btn.addEventListener('click', (e) => e.stopPropagation());
                }
            }
            
            // Click outside to close all dropdowns
            document.addEventListener('click', (e) => {
                if (!loginStatusWidget.contains(e.target)) {
                    loginStatusWidget.querySelectorAll('.dropdown-menu').forEach((menu) => {
                        menu.style.display = 'none';
                    });
                }
            });
        }
        }
    }

    function renderSystemStatus(status) {
        if (!status) return '<p>无法加载系统状态。</p>';

        const renderStatusTag = (isOk) => isOk
            ? `<span class="tag status-ok">正常</span>`
            : `<span class="tag status-error">异常</span>`;

        const env = status.env_file || {};

        // Check if at least one notification channel is configured
        const hasAnyNotificationChannel = env.ntfy_topic_url_set || 
                                         (env.gotify_url_set && env.gotify_token_set) || 
                                         env.bark_url_set || 
                                         env.wx_bot_url_set || 
                                         (env.wx_corp_id_set && env.wx_agent_id_set && env.wx_secret_set) || 
                                         (env.telegram_bot_token_set && env.telegram_chat_id_set) || 
                                         env.webhook_url_set;

        return `
            <ul class="status-list">
                <li class="status-item">
                    <span class="label">环境变量文件 (.env)</span>
                    <span class="value">${renderStatusTag(env.exists)}</span>
                </li>
                <li class="status-item">
                    <span class="label">OpenAI API Key</span>
                    <span class="value">${renderStatusTag(env.openai_api_key_set)}</span>
                </li>
                <li class="status-item">
                    <span class="label">OpenAI Base URL</span>
                    <span class="value">${renderStatusTag(env.openai_base_url_set)}</span>
                </li>
                <li class="status-item">
                    <span class="label">OpenAI Model Name</span>
                    <span class="value">${renderStatusTag(env.openai_model_name_set)}</span>
                </li>
                <li class="status-item">
                    <span class="label">通知渠道配置</span>
                    <span class="value">${renderStatusTag(hasAnyNotificationChannel)}</span>
                </li>
            </ul>
        `;
    }

    function renderResultsGrid(data) {
        if (!data || !data.items || data.items.length === 0) {
            return '<p>没有找到符合条件的商品记录。</p>';
        }

            const manualKeyword = document.getElementById('manual-keyword-filter')?.value || '';
            const cards = data.items.map(item => {
            const info = item.商品信息 || {};
            const seller = item.卖家信息 || {};
            const ai = item.ai_analysis || {};

            const isRecommended = ai.is_recommended === true;
            const recommendationClass = isRecommended ? 'recommended' : 'not-recommended';
            const recommendationText = isRecommended ? '推荐' : (ai.is_recommended === false ? '不推荐' : '待定');

            // 尽量使用商品图片列表的第二张图片，没有的话使用第一张
            const imageUrl = (info.商品图片列表 && info.商品图片列表.length > 1) ? info.商品图片列表[1] : (info.商品图片列表 && info.商品图片列表[0]) ? info.商品图片列表[0] : '/logo/logo 2048x2048.png';
            const crawlTime = item.爬取时间 ? new Date(item.爬取时间).toLocaleString('sv-SE').slice(0, 16) : '未知';
            const publishTime = info.发布时间 || '未知';

            // Escape HTML to prevent XSS
            const escapeHtml = (unsafe) => {
                if (typeof unsafe !== 'string') return unsafe;
                const div = document.createElement('div');
                div.textContent = unsafe;
                return div.innerHTML;
            };

            // Highlight keywords in text
            const highlightKeyword = (text, keyword) => {
                if (!keyword || !text) return text;
                const regex = new RegExp(`(${escapeHtml(keyword)})`, 'gi');
                return text.replace(regex, '<span style="background-color: #fff3cd; color: #856404; padding: 2px 4px; border-radius: 3px; font-weight: bold;">$1</span>');
            };

            // 只存储必要的信息用于发送通知
            const notificationData = {
                商品信息: {
                    商品标题: info.商品标题,
                    当前售价: info.当前售价,
                    商品链接: info.商品链接,
                    卖家昵称: info.卖家昵称 || seller.卖家昵称,
                    发布时间: publishTime,
                    商品图片列表: info.商品图片列表 // 包含商品图片列表
                },
                ai_analysis: {
                    is_recommended: ai.is_recommended,
                    reason: ai.reason,
                    risk_tags: ai.risk_tags
                },
                爬取时间: item.爬取时间,
                搜索关键字: item.搜索关键字,
                任务名称: item.任务名称,
                AI标准: item.AI标准
            };
            
            return `
            <div class="result-card" data-notification='${escapeHtml(JSON.stringify(notificationData))}'>
            <button class="delete-card-btn" title="删除此商品"></button>
                <div class="card-image">
                    <a href="${escapeHtml(info.商品链接) || '#'}" target="_blank"><img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(info.商品标题) || '商品图片'}" loading="lazy" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuWbvueJhzwvdGV4dD48L3N2Zz4=';"></a>
                </div>
                <div class="card-content">
                <h3 class="card-title"><a href="${escapeHtml(info.商品链接) || '#'}" target="_blank" title="${escapeHtml(info.商品标题) || ''}">${highlightKeyword(escapeHtml(info.商品标题), manualKeyword) || '无标题'}</a></h3>
                    <p class="card-price">${highlightKeyword(escapeHtml(info.当前售价), manualKeyword) || '价格未知'}</p>
                    <div class="card-ai-summary ${recommendationClass}">
                        <strong>AI建议: ${escapeHtml(recommendationText)}</strong>
                        <p title="${escapeHtml(ai.reason) || ''}">原因: ${highlightKeyword(escapeHtml(ai.reason), manualKeyword) || '无分析'}</p>
                    </div>
                    <div class="card-footer">
                        <div class="seller-time-info">
                            <span class="seller-info" title="${escapeHtml(info.卖家昵称) || escapeHtml(seller.卖家昵称) || '未知'}">卖家: ${escapeHtml(info.卖家昵称) || escapeHtml(seller.卖家昵称) || '未知'}</span>
                            <div class="time-info">
                                <p>发布于: ${escapeHtml(publishTime)}</p>
                                <p>抓取于: ${escapeHtml(crawlTime)}</p>
                            </div>
                        </div>
                        <div class="card-buttons">
                            <button class="action-btn send-notification-btn" title="发送通知">发送通知</button>
                            <a href="${escapeHtml(info.商品链接) || '#'}" target="_blank" class="action-btn">查看详情</a>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }).join('');

        return `<div id="results-grid">${cards}</div>`;
    }

    function renderTasksTable(tasks) {
        if (!tasks || tasks.length === 0) {
            return '<p>没有找到任何任务。请点击右上角“创建新任务”来添加一个。</p>';
        }

        const tableHeader = `
            <thead>
                <tr>
                    <th>启用</th>
                    <th>任务名称</th>
                    <th>运行状态</th>
                    <th>关键词</th>
                    <th>价格范围</th>
                    <th>筛选条件</th>
                    <th>最大页数</th>
                    <th>AI 标准</th>
                    <th>定时规则</th>
                    <th>操作</th>
                </tr>
            </thead>`;

        const tableBody = tasks.map(task => {
        const isRunning = task.is_running === true;
        const isGeneratingAI = task.generating_ai_criteria === true;
        let statusBadge;
        if (isGeneratingAI) {
            statusBadge = `<span class="status-badge status-generating" style="background-color: orange;">生成中</span>`;
        } else if (isRunning) {
            statusBadge = `<span class="status-badge status-running" style="background-color: #28a745;">运行中</span>`;
        } else {
            // Check if criteria file exists
            const criteriaFile = task.ai_prompt_criteria_file || 'N/A';
            const criteriaBtnText = criteriaFile
                .replace(/^criteria\/(.*?)_criteria\.txt$/i, '$1') // 替换完整路径
                .replace(/^criteria\//i, '') // 替换前缀
                .replace(/_criteria\.txt$/i, '') // 替换后缀
                .replace(/^prompts\/(.*?)_criteria\.txt$/i, '$1') // 处理旧路径
                .replace(/_criteria$/i, '') // 处理不带.txt的情况
                .replace(/^requirement\/(.*?)_requirement\.txt$/i, '$1_requirement'); // 处理"requirement/名称_requirement.txt"路径，只显示"名称_requirement"
            if (criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement')) {
                statusBadge = `<span class="status-badge status-waiting" style="background-color: #007bff;">待生成标准</span>`;
            } else {
                statusBadge = `<span class="status-badge status-stopped">已停止</span>`;
            }
        }

            // Format criteria filename to show only the middle text without prefix/suffix
            const criteriaFile = task.ai_prompt_criteria_file || 'N/A';
            let criteriaBtnText = 'N/A';
            if (criteriaFile !== 'N/A') {
                criteriaBtnText = criteriaFile
                    .replace(/^criteria\/(.*?)_criteria\.txt$/i, '$1') // 替换完整路径
                    .replace(/^criteria\//i, '') // 替换前缀
                    .replace(/_criteria\.txt$/i, '') // 替换后缀
                    .replace(/^prompts\/(.*?)_criteria\.txt$/i, '$1') // 处理旧路径
                    .replace(/_criteria$/i, '') // 处理不带.txt的情况
                    .replace(/^requirement\/(.*?)_requirement\.txt$/i, '$1_requirement'); // 处理"requirement/名称_requirement.txt"路径，只显示"名称_requirement"
            }
            
            const actionButton = isRunning
                ? `<button class="action-btn stop-task-btn" data-task-id="${task.id}" ${isGeneratingAI ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>停止</button>`
                : `<button class="action-btn run-task-btn" data-task-id="${task.id}" ${!task.enabled || (criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement')) || isGeneratingAI ? 'disabled ' : ''} ${!task.enabled ? 'title="任务已禁用"' : (criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement')) ? 'title="请先点击生成"' : (isGeneratingAI ? 'title="正在生成AI标准"' : '')} ${isGeneratingAI ? 'style="background-color: #ccc; cursor: not-allowed;"' : (criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement')) ? 'style="background-color: #ccc; color: white;"' : ''}>运行</button>`;
            
            // Determine if buttons should be disabled
            const buttonDisabledAttr = isGeneratingAI ? 'disabled' : '';
            const buttonDisabledTitle = isGeneratingAI ? 'title="等待AI标准生成"' : '';
            const buttonDisabledStyle = isGeneratingAI ? 'style="background-color: #ccc; cursor: not-allowed;"' : '';

            return `
            <tr data-task-id="${task.id}" data-task='${JSON.stringify(task)}'>
                <td style="text-align: center;">
                    <label class="switch">
                        <input type="checkbox" ${task.enabled ? 'checked' : ''} ${isGeneratingAI ? 'disabled' : ''}>
                        <span class="slider round"></span>
                    </label>
                </td>
                <td style="text-align: center;">${task.task_name}</td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: center;"><span class="tag">${task.keyword}</span></td>
                <td style="text-align: center;">${task.min_price || '不限'} - ${task.max_price || '不限'}</td>
                <td style="text-align: center;">${task.personal_only ? '<span class="tag personal">个人闲置</span>' : ''}</td>
                <td style="text-align: center;">${task.max_pages || 3}</td>
                <td style="text-align: left !important;">
                    <div class="criteria" style="display: inline-block; text-align: left;">
${criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement') ? `
                            <div class="red-dot-container">
                                <button class="refresh-criteria success-btn" title="新生成AI标准" data-task-id="${task.id}" ${isGeneratingAI ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>待生成</button>
                                <span class="red-dot"></span>
                            </div>
                            <button class="criteria-btn danger-btn" title="编辑AI标准" data-task-id="${task.id}" data-criteria-file="${criteriaFile}" ${isGeneratingAI ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>
                                ${criteriaBtnText}
                            </button>
                        ` : `
                            <button class="refresh-criteria danger-btn" title="新生成AI标准" data-task-id="${task.id}" ${isGeneratingAI ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>重生成</button>
                            ${criteriaFile !== 'N/A' ? `
                                <button class="criteria-btn success-btn" title="编辑AI标准" data-task-id="${task.id}" data-criteria-file="${criteriaFile}" ${isGeneratingAI ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>
                                    ${criteriaBtnText}
                                </button>
                            ` : 'N/A'}
                        `}
                    </div>
                </td>
                <td style="text-align: center;">${task.cron || '未设置'}</td>
                <td style="text-align: center;">
                    ${actionButton}
                    <button class="action-btn edit-btn" ${buttonDisabledAttr} ${buttonDisabledTitle} ${buttonDisabledStyle}>编辑</button>
                    <button class="action-btn copy-btn" ${buttonDisabledAttr} ${buttonDisabledTitle} ${buttonDisabledStyle}>复制</button>
                    <button class="action-btn delete-btn" ${buttonDisabledAttr} ${buttonDisabledTitle} ${buttonDisabledStyle}>删除</button>
                </td>
            </tr>`
        }).join('');

        return `<table class="tasks-table">${tableHeader}<tbody>${tableBody}</tbody></table>`;
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
        const sectionId = hash.substring(1) || 'tasks';

        // Update nav links active state
        navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('href') === `#${sectionId}`);
        });

        // Update main content
        if (templates[sectionId]) {
            mainContent.innerHTML = templates[sectionId]();
            // Make the new content visible
            const newSection = mainContent.querySelector('.content-section');
            if (newSection) {
                requestAnimationFrame(() => {
                    newSection.classList.add('active');
                });
            }

            // --- Load data for the current section ---
            if (sectionId === 'tasks') {
                const container = document.getElementById('tasks-table-container');
                const refreshTasks = async () => {
                    const tasks = await fetchTasks();
                    // Avoid re-rendering if in edit mode to not lose user input
                    if (container && !container.querySelector('tr.editing')) {
                        container.innerHTML = renderTasksTable(tasks);
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
            } else if (sectionId === 'settings') {
                await initializeSettingsView();
            }

        } else {
            mainContent.innerHTML = '<section class="content-section active"><h2>页面未找到</h2></section>';
        }
    }

    async function initializeLogsView() {
        const logContainer = document.getElementById('log-content-container');
        const refreshBtn = document.getElementById('refresh-logs-btn');
        const autoRefreshCheckbox = document.getElementById('auto-refresh-logs-checkbox');
        const clearBtn = document.getElementById('clear-logs-btn');
        const taskFilter = document.getElementById('log-task-filter');
        let currentLogSize = 0;

        const updateLogs = async (isFullRefresh = false) => {
            // For incremental updates, check if user is at the bottom BEFORE adding new content.
            const shouldAutoScroll = isFullRefresh || (logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 5);
            const selectedTaskName = taskFilter ? taskFilter.value : '';

            if (isFullRefresh) {
                currentLogSize = 0;
                logContainer.textContent = '正在加载...';
            }

            const logData = await fetchLogs(currentLogSize, selectedTaskName);

            if (isFullRefresh) {
                // If the log is empty, show a message instead of a blank screen.
                logContainer.textContent = logData.new_content || '日志为空，等待内容...';
            } else if (logData.new_content) {
                // If it was showing the empty message, replace it.
                if (logContainer.textContent === '日志为空，等待内容...') {
                    logContainer.textContent = logData.new_content;
                } else {
                    logContainer.textContent += logData.new_content;
                }
            }
            currentLogSize = logData.new_pos;

            // Scroll to bottom if it was a full refresh or if the user was already at the bottom.
            if (shouldAutoScroll) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        };

        refreshBtn.addEventListener('click', () => updateLogs(true));

        clearBtn.addEventListener('click', async () => {
            if (confirm('你确定要清空所有运行日志吗？此操作不可恢复。')) {
                const result = await clearLogs();
                if (result) {
                    await updateLogs(true);
                    alert('日志已清空。');
                }
            }
        });

            // Function to populate the task filter with unique task names
            async function populateTaskFilter() {
                if (!taskFilter) return;
                
                // Fetch all tasks from the server
                const tasks = await fetchTasks();
                
                if (tasks && tasks.length > 0) {
                    // Get unique task names
                    const uniqueTaskNames = [...new Set(tasks.map(task => task.task_name))].sort();
                    
                    // Save the current selected value
                    const currentValue = taskFilter.value;
                    
                    // Clear existing options except the first one ("所有任务")
                    taskFilter.innerHTML = '<option value="">所有任务</option>';
                    
                    // Add new options
                    uniqueTaskNames.forEach(taskName => {
                        const option = document.createElement('option');
                        option.value = taskName;
                        option.textContent = taskName;
                        
                        // Restore the current selection
                        if (option.value === currentValue) {
                            option.selected = true;
                        }
                        
                        taskFilter.appendChild(option);
                    });
                }
            }
            
            // Add task filter change event listener
            if (taskFilter) {
                taskFilter.addEventListener('change', () => updateLogs(true));
            }
            
            // Populate the task filter when initializing the logs view
            await populateTaskFilter();
            
            // Also populate the task filter when clicking the refresh button
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

        // Enable auto-refresh by default
        autoRefreshCheckbox.checked = true;
        autoRefreshHandler();
        await updateLogs(true);
    }

    async function fetchAndRenderResults() {
        const selector = document.getElementById('result-file-selector');
        const checkbox = document.getElementById('recommended-only-checkbox');
        const sortBySelector = document.getElementById('sort-by-selector');
        const sortOrderSelector = document.getElementById('sort-order-selector');
        const taskNameFilter = document.getElementById('task-name-filter');
        const keywordFilter = document.getElementById('keyword-filter');
        const aiCriteriaFilter = document.getElementById('ai-criteria-filter');
        const manualKeywordFilter = document.getElementById('manual-keyword-filter');
        const container = document.getElementById('results-grid-container');

        if (!selector || !checkbox || !container || !sortBySelector || !sortOrderSelector || !taskNameFilter || !keywordFilter || !aiCriteriaFilter || !manualKeywordFilter) return;

        const selectedFile = selector.value;
        const recommendedOnly = checkbox.checked; // Checkbox is now an input type="checkbox"
        const taskName = taskNameFilter.value;
        const keyword = keywordFilter.value;
        const manualKeyword = manualKeywordFilter.value;
        const aiCriteria = aiCriteriaFilter.value;
        const sortBy = sortBySelector.value;
        const sortOrder = sortOrderSelector.value;

        if (!selectedFile) {
            container.innerHTML = '<p>请先选择一个结果文件。</p>';
            return;
        }

        localStorage.setItem('lastSelectedResultFile', selectedFile);

        container.innerHTML = '<p>正在加载结果...</p>';
        // 使用所有筛选条件获取结果，但如果是查看所有结果或切换结果文件，则获取所有结果以更新筛选选项
        const dataForFilters = await fetchResultContent(selectedFile, false, 'all', 'all', 'all', 'crawl_time', 'desc');
        const dataForDisplay = await fetchResultContent(selectedFile, recommendedOnly, taskName, keyword, aiCriteria, sortBy, sortOrder, manualKeyword);
        
        // 总是更新筛选控件的选项，无论当前筛选条件是什么
        if (dataForFilters && dataForFilters.items) {
            // 获取所有唯一的任务名称、关键词和AI标准
            const taskNames = [...new Set(dataForFilters.items.map(item => item['任务名称'] || 'unknown'))].sort();
            const keywords = [...new Set(dataForFilters.items.map(item => item['搜索关键字'] || 'unknown'))].sort();
            const aiCriterias = [...new Set(dataForFilters.items.map(item => item['AI标准'] || 'N/A'))].sort();
            
            // 更新任务名称筛选
            taskNameFilter.innerHTML = '<option value="all">所有任务</option>' + taskNames.map(name => `<option value="${name}">${name}</option>`).join('');
            // 恢复当前选择
            taskNameFilter.value = taskName;
            
            // 更新关键词筛选
            keywordFilter.innerHTML = '<option value="all">所有关键词</option>' + keywords.map(keyword => `<option value="${keyword}">${keyword}</option>`).join('');
            // 恢复当前选择
            keywordFilter.value = keyword;
            
            // 更新AI标准筛选
            aiCriteriaFilter.innerHTML = '<option value="all">所有AI标准</option>' + aiCriterias.map(criteria => `<option value="${criteria}">${criteria}</option>`).join('');
            // 恢复当前选择
            aiCriteriaFilter.value = aiCriteria;
        }
        
        container.innerHTML = renderResultsGrid(dataForDisplay);
    }

    async function initializeResultsView() {
        const selector = document.getElementById('result-file-selector');
        const checkbox = document.getElementById('recommended-only-checkbox');
        const refreshBtn = document.getElementById('refresh-results-btn');
        const deleteBtn = document.getElementById('delete-results-btn');
        const sortBySelector = document.getElementById('sort-by-selector');
        const sortOrderSelector = document.getElementById('sort-order-selector');

        const fileData = await fetchResultFiles();
        if (fileData && fileData.files && fileData.files.length > 0) {
            const lastSelectedFile = localStorage.getItem('lastSelectedResultFile');
            
            // Determine the file to select. Default to "所有结果" if nothing is stored.
            let fileToSelect = 'all';
            // If there's a last selected file and it's not "all", use it
            if (lastSelectedFile && lastSelectedFile !== 'all' && fileData.files.includes(lastSelectedFile)) {
                fileToSelect = lastSelectedFile;
            }

            // Add "所有结果" option
            const options = ['<option value="all" ' + (fileToSelect === 'all' ? 'selected' : '') + '>所有结果</option>'].concat(
                fileData.files.map(f =>
                    `<option value="${f}" ${f === fileToSelect ? 'selected' : ''}>${f}</option>`
                )
            );
            selector.innerHTML = options.join('');

            // The selector's value is now correctly set by the 'selected' attribute.
            // We can proceed with adding listeners and the initial fetch.

            // Add event listeners for all filters
            selector.addEventListener('change', fetchAndRenderResults);
            
            // Initialize the "仅看AI推荐" button state
            checkbox.setAttribute('data-checked', 'false');
            
            // Handle checkbox change event directly since it's now an input type="checkbox"
            checkbox.addEventListener('change', () => {
                fetchAndRenderResults();
            });
            
            const taskNameFilter = document.getElementById('task-name-filter');
            const keywordFilter = document.getElementById('keyword-filter');
            const aiCriteriaFilter = document.getElementById('ai-criteria-filter');
            const manualKeywordFilter = document.getElementById('manual-keyword-filter');
            if (taskNameFilter) taskNameFilter.addEventListener('change', fetchAndRenderResults);
            if (keywordFilter) keywordFilter.addEventListener('change', fetchAndRenderResults);
            if (aiCriteriaFilter) aiCriteriaFilter.addEventListener('change', fetchAndRenderResults);
            if (manualKeywordFilter) manualKeywordFilter.addEventListener('input', fetchAndRenderResults);
            
            // Add existing event listeners
            sortBySelector.addEventListener('change', fetchAndRenderResults);
            sortOrderSelector.addEventListener('change', fetchAndRenderResults);
            refreshBtn.addEventListener('click', fetchAndRenderResults);

            // Enable delete button when a file is selected
            const updateDeleteButtonState = () => {
                deleteBtn.disabled = !selector.value;
            };
            selector.addEventListener('change', updateDeleteButtonState);
            // 初始化时也更新一次删除按钮状态
            updateDeleteButtonState();

            // Delete button functionality
            deleteBtn.addEventListener('click', async () => {
                const selectedFile = selector.value;
                if (!selectedFile) {
                    alert('请先选择一个结果文件。');
                    return;
                }

                if (confirm(`你确定要删除结果文件 "${selectedFile}" 吗？此操作不可恢复。`)) {
                    const result = await deleteResultFile(selectedFile);
                    if (result) {
                        alert(result.message);
                        // Refresh the file list
                        await initializeResultsView();
                    }
                }
            });

            // Initial load
            await fetchAndRenderResults();
        } else {
            selector.innerHTML = '<option value="">没有可用的结果文件</option>';
            document.getElementById('results-grid-container').innerHTML = '<p>没有找到任何结果文件。请先运行监控任务。</p>';
        }
    }

    async function initializeNotificationsView() {
        // Render Notification Settings
        const notificationContainer = document.getElementById('notification-settings-container');
        const notificationSettings = await fetchNotificationSettings();
        if (notificationSettings !== null) {
            notificationContainer.innerHTML = renderNotificationSettings(notificationSettings);
        } else {
            notificationContainer.innerHTML = '<p>加载通知配置失败。请检查服务器是否正常运行。</p>';
        }

        // Add event listener for notification settings form
        const notificationForm = document.getElementById('notification-settings-form');
        if (notificationForm) {
            notificationForm.addEventListener('submit', async (e) => {
                e.preventDefault();

                // Collect form data
                const formData = new FormData(notificationForm);
                const settings = {};

                // Handle regular inputs
                for (let [key, value] of formData.entries()) {
                    if (key === 'PCURL_TO_MOBILE') {
                        settings[key] = value === 'on';
                    } else {
                        settings[key] = value || '';
                    }
                }

                // Handle unchecked checkboxes (they don't appear in FormData)
                const pcurlCheckbox = document.getElementById('pcurl-to-mobile');
                if (pcurlCheckbox && !pcurlCheckbox.checked) {
                    settings.PCURL_TO_MOBILE = false;
                }

                // Save settings
                const saveBtn = notificationForm.querySelector('button[type="submit"]');
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';

                const result = await updateNotificationSettings(settings);
                if (result) {
                    alert(result.message || "通知设置已保存！");
                }

                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            });

            // Add event listener for test notification buttons
            const testButtons = notificationForm.querySelectorAll('.test-notification-btn');
            testButtons.forEach(button => {
                button.addEventListener('click', async () => {
                    // Collect current form data first
                    const formData = new FormData(notificationForm);
                    const settings = {};

                    // Handle regular inputs
                    for (let [key, value] of formData.entries()) {
                        if (key === 'PCURL_TO_MOBILE') {
                            settings[key] = value === 'on';
                        } else {
                            settings[key] = value || '';
                        }
                    }

                    // Handle unchecked checkboxes
                    const pcurlCheckbox = document.getElementById('pcurl-to-mobile');
                    if (pcurlCheckbox && !pcurlCheckbox.checked) {
                        settings.PCURL_TO_MOBILE = false;
                    }

                    // Save the settings first
                    const saveResult = await updateNotificationSettings(settings);
                    if (!saveResult) {
                        alert('保存设置失败，请先检查设置是否正确。');
                        return;
                    }

                    // Send test notification
                    const channel = button.dataset.channel;
                    const originalText = button.textContent;
                    button.disabled = true;
                    button.textContent = '测试中...';

                    try {
                        const response = await fetch('/api/notifications/test', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({channel: channel}),
                        });

                        if (response.ok) {
                            const result = await response.json();
                            alert(result.message || '测试通知发送成功！');
                        } else {
                            const errorData = await response.json();
                            alert('测试通知发送失败: ' + (errorData.detail || '未知错误'));
                        }
                    } catch (error) {
                        alert('测试通知发送失败: ' + error.message);
                    } finally {
                        button.disabled = false;
                        button.textContent = originalText;
                    }
                });
            });
        }
    }

    async function initializeSettingsView() {
    // Render all sections as separate cards with the same level
    const settingsSection = document.querySelector('#settings-section');
    
        // 1. Render System Status first to avoid the stuck issue
    const statusContainer = document.getElementById('system-status-container');
    const status = await fetchSystemStatus();
    statusContainer.innerHTML = renderSystemStatus(status);
    
    // 2. Create Generic Settings Card
    const genericContainer = document.createElement('div');
    genericContainer.className = 'settings-card';
    genericContainer.innerHTML = `
        <h3>通用配置</h3>
        <div id="generic-settings-container">
            <p>正在加载通用配置...</p>
        </div>
    `;
    settingsSection.appendChild(genericContainer);
    
    // Fetch generic settings with error handling and timeout
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 seconds timeout

        const genericSettingsResponse = await fetch('/api/settings/generic', {
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!genericSettingsResponse.ok) {
            throw new Error(`HTTP error! status: ${genericSettingsResponse.status}`);
        }
        
        const genericSettings = await genericSettingsResponse.json();
        const genericSettingsContainer = document.getElementById('generic-settings-container');
        
                genericSettingsContainer.innerHTML = `
            <form id="generic-settings-form">
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="login-is-edge" name="LOGIN_IS_EDGE" ${genericSettings.LOGIN_IS_EDGE ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">使用Edge浏览器</div>
                            <p class="form-hint" style="margin: 2px 0;">默认使用Chrome浏览器</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="run-headless" name="RUN_HEADLESS" ${genericSettings.RUN_HEADLESS ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">爬虫以无头模式运行</div>
                            <p class="form-hint" style="margin: 2px 0;">本地运行时遇到验证码可设为否，Docker部署必须设为是</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="ai-debug-mode" name="AI_DEBUG_MODE" ${genericSettings.AI_DEBUG_MODE ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">AI调试模式</div>
                            <p class="form-hint" style="margin: 2px 0;">开启后将打印更多AI分析相关日志</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="enable-thinking" name="ENABLE_THINKING" ${genericSettings.ENABLE_THINKING ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">启用enable_thinking参数</div>
                            <p class="form-hint" style="margin: 2px 0;">某些AI模型需要此参数，有些则不支持</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="enable-response-format" name="ENABLE_RESPONSE_FORMAT" ${genericSettings.ENABLE_RESPONSE_FORMAT ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">启用response_format参数</div>
                            <p class="form-hint" style="margin: 2px 0;">豆包模型不支持json_object响应格式，需要设为否</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="send-url-format-image" name="SEND_URL_FORMAT_IMAGE" ${genericSettings.SEND_URL_FORMAT_IMAGE ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">发送URL格式图片</div>
                            <p class="form-hint" style="margin: 2px 0;">跳过图片下载，将直接发送商品图片URL给AI分析，无需转码，节省token消耗。未勾选时使用base64编码格式。</p>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="server-port">服务自定义端口</label>
                    <input type="number" id="server-port" name="SERVER_PORT" value="${genericSettings.SERVER_PORT || 8000}" min="1" max="65535">
                    <p class="form-hint">重启服务后生效</p>
                </div>
                
                <div class="form-group">
                    <label for="web-username">Web服务用户名</label>
                    <input type="text" id="web-username" name="WEB_USERNAME" value="${genericSettings.WEB_USERNAME || 'admin'}">
                    <p class="form-hint">用于登录Web管理界面</p>
                </div>
                
                <div class="form-group">
                    <label for="web-password">Web服务密码</label>
                    <input type="password" id="web-password" name="WEB_PASSWORD" value="${genericSettings.WEB_PASSWORD || 'admin123'}">
                    <p class="form-hint">用于登录Web管理界面</p>
                </div>
                
                <button type="submit" class="control-button primary-btn">保存通用配置</button>
            </form>
        `;
    } catch (error) {
        console.error("无法加载通用配置:", error);
        const genericSettingsContainer = document.getElementById('generic-settings-container');
        genericSettingsContainer.innerHTML = '<p>加载通用配置失败。请检查服务器是否正常运行。</p>';
    }
    
    // Add event listener for generic settings form
    const genericForm = document.getElementById('generic-settings-form');
    if (genericForm) {
        genericForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Collect form data
            const formData = new FormData(genericForm);
            const settings = {};
            
            // Handle checkboxes
            settings.LOGIN_IS_EDGE = formData.get('LOGIN_IS_EDGE') === 'on';
            settings.RUN_HEADLESS = formData.get('RUN_HEADLESS') === 'on';
            settings.AI_DEBUG_MODE = formData.get('AI_DEBUG_MODE') === 'on';
            settings.ENABLE_THINKING = formData.get('ENABLE_THINKING') === 'on';
            settings.ENABLE_RESPONSE_FORMAT = formData.get('ENABLE_RESPONSE_FORMAT') === 'on';
            settings.SEND_URL_FORMAT_IMAGE = formData.get('SEND_URL_FORMAT_IMAGE') === 'on';
            
            // Handle other inputs
            settings.SERVER_PORT = parseInt(formData.get('SERVER_PORT'));
            settings.WEB_USERNAME = formData.get('WEB_USERNAME');
            settings.WEB_PASSWORD = formData.get('WEB_PASSWORD');
            
            // Save settings
            const saveBtn = genericForm.querySelector('button[type="submit"]');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
            
            try {
                const response = await fetch('/api/settings/generic', {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings),
                });
                
                if (response.ok) {
                    alert('通用配置已保存！');
                } else {
                    const errorData = await response.json();
                    alert('保存失败: ' + (errorData.detail || '未知错误'));
                }
            } catch (error) {
                alert('保存失败: ' + error.message);
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        });
    }

        // 3. Render AI Settings
        const aiContainer = document.createElement('div');
        aiContainer.className = 'settings-card';
        aiContainer.innerHTML = `
            <h3>AI模型配置</h3>
            <div id="ai-settings-container">
                <p>正在加载AI配置...</p>
            </div>
        `;

        // Insert AI settings card before Prompt Management
        const promptCard = document.querySelector('.settings-card h3').closest('.settings-card');
        promptCard.parentNode.insertBefore(aiContainer, promptCard);

        const aiSettingsContainer = document.getElementById('ai-settings-container');
        const aiSettings = await fetchAISettings();
        if (aiSettings !== null) {
            aiSettingsContainer.innerHTML = renderAISettings(aiSettings);
        } else {
            aiSettingsContainer.innerHTML = '<p>加载AI配置失败。请检查服务器是否正常运行。</p>';
        }

        // 4. Setup Prompt Editor
        const promptSelector = document.getElementById('prompt-selector');
        const promptEditor = document.getElementById('prompt-editor');
        const savePromptBtn = document.getElementById('save-prompt-btn');
        
        // Add new prompt button
        const promptListContainer = document.querySelector('.prompt-list-container');
        const newPromptBtn = document.createElement('button');
        newPromptBtn.textContent = '新建模板';
        newPromptBtn.className = 'control-button primary-btn';
        newPromptBtn.style.marginLeft = '10px';
        promptListContainer.appendChild(newPromptBtn);

        // Add delete prompt button
        const deletePromptBtn = document.createElement('button');
        deletePromptBtn.textContent = '删除模板';
        deletePromptBtn.className = 'control-button danger-btn';
        deletePromptBtn.style.marginLeft = '10px';
        deletePromptBtn.style.backgroundColor = 'red';
        deletePromptBtn.style.color = 'white';
        deletePromptBtn.style.borderColor = 'red';
        deletePromptBtn.disabled = true; // 初始禁用，选择文件后启用
        promptListContainer.appendChild(deletePromptBtn);

        const prompts = await fetchPrompts();
        if (prompts && prompts.length > 0) {
            promptSelector.innerHTML = '<option value="">-- 请选择 --</option>' + prompts.map(p => `<option value="${p}">${p}</option>`).join('');
        } else if (prompts && prompts.length === 0) {
            promptSelector.innerHTML = '<option value="">没有找到Prompt文件</option>';
        } else {
            // prompts is null or undefined, which means fetch failed
            promptSelector.innerHTML = '<option value="">加载Prompt文件列表失败</option>';
        }

        promptSelector.addEventListener('change', async () => {
            const selectedFile = promptSelector.value;
            if (selectedFile) {
                promptEditor.value = "正在加载...";
                promptEditor.disabled = true;
                savePromptBtn.disabled = true;
                deletePromptBtn.disabled = true;
                const data = await fetchPromptContent(selectedFile);
                if (data) {
                    promptEditor.value = data.content;
                    promptEditor.disabled = false;
                    savePromptBtn.disabled = false;
                    deletePromptBtn.disabled = false; // 选择文件后启用删除按钮
                } else {
                    promptEditor.value = `加载文件 ${selectedFile} 失败。`;
                }
            } else {
                promptEditor.value = "请先从上方选择一个 Prompt 文件进行编辑...";
                promptEditor.disabled = true;
                savePromptBtn.disabled = true;
                deletePromptBtn.disabled = true; // 未选择文件时禁用删除按钮
            }
        });

        savePromptBtn.addEventListener('click', async () => {
            const selectedFile = promptSelector.value;
            const content = promptEditor.value;
            if (!selectedFile) {
                alert("请先选择一个要保存的Prompt文件。");
                return;
            }

            savePromptBtn.disabled = true;
            savePromptBtn.textContent = '保存中...';

            const result = await updatePrompt(selectedFile, content);
            if (result) {
                alert(result.message || "保存成功！");
            }
            // No need to show alert on failure, as updatePrompt already does.

            savePromptBtn.disabled = false;
            savePromptBtn.textContent = '保存更改';
        });
        
        // Delete prompt functionality
        deletePromptBtn.addEventListener('click', async () => {
            const selectedFile = promptSelector.value;
            if (!selectedFile) {
                alert("请先选择一个要删除的Prompt文件。");
                return;
            }
            
            if (!confirm(`你确定要删除Prompt文件 "${selectedFile}" 吗？此操作不可恢复。`)) {
                return;
            }
            
            deletePromptBtn.disabled = true;
            deletePromptBtn.textContent = '删除中...';
            
            try {
                const response = await fetch(`/api/prompts/${selectedFile}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || '删除失败');
                }
                
                const result = await response.json();
                alert(result.message || '删除成功！');
                
                // Refresh the prompt list
                const newPrompts = await fetchPrompts();
                promptSelector.innerHTML = '<option value="">-- 请选择 --</option>' + newPrompts.map(p => `<option value="${p}">${p}</option>`).join('');
                
                // Reset editor
                promptEditor.value = "请先从上方选择一个 Prompt 文件进行编辑...";
                promptEditor.disabled = true;
                savePromptBtn.disabled = true;
                deletePromptBtn.disabled = true;
                
            } catch (error) {
                console.error('删除Prompt失败:', error);
                alert('删除失败: ' + error.message);
            } finally {
                deletePromptBtn.disabled = false;
                deletePromptBtn.textContent = '删除模板';
            }
        });
        
        // New prompt functionality with modal instead of prompt()
        newPromptBtn.addEventListener('click', () => {
            // Create the modal HTML
            const modalHTML = `
                <div id="new-prompt-modal" class="modal-overlay visible">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>新建 Prompt 模板</h2>
                            <button id="close-new-prompt-modal" class="close-button">&times;</button>
                        </div>
                        <div class="modal-body">
                            <form id="new-prompt-form">
                                <div class="form-group">
                                    <label for="new-prompt-name">模板名称:</label>
                                    <input type="text" id="new-prompt-name" placeholder="请输入模板名称" required>
                                    <p class="form-hint">不需要添加.txt后缀</p>
                                </div>
                                <div class="form-group">
                                    <label for="new-prompt-content">模板内容:</label>
                                    <textarea id="new-prompt-content" rows="10" placeholder="请输入 Prompt 模板内容" required></textarea>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button id="cancel-new-prompt-btn" class="control-button">取消</button>
                            <button id="save-new-prompt-btn" class="control-button primary-btn">保存</button>
                        </div>
                    </div>
                </div>
            `;
            
            // Add modal to body
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            // Get modal elements
            const modal = document.getElementById('new-prompt-modal');
            const closeBtn = document.getElementById('close-new-prompt-modal');
            const cancelBtn = document.getElementById('cancel-new-prompt-btn');
            const saveBtn = document.getElementById('save-new-prompt-btn');
            const form = document.getElementById('new-prompt-form');
            
            // Close modal
            const closeModal = () => {
                modal.remove();
            };
            
            closeBtn.addEventListener('click', closeModal);
            cancelBtn.addEventListener('click', closeModal);
            
            // Click outside to close
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });
            
            // Save new prompt
            saveBtn.addEventListener('click', () => {
                if (!form.checkValidity()) {
                    form.reportValidity();
                    return;
                }
                
                const newFileName = document.getElementById('new-prompt-name').value.trim();
                const content = document.getElementById('new-prompt-content').value;
                
                // Validate file name
                if (newFileName.includes('/') || newFileName.includes('..')) {
                    alert('无效的文件名');
                    return;
                }
                
                // Call the API to create new prompt
                fetch('/api/prompts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        filename: newFileName,
                        content: content
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message || '新建模板成功！');
                    closeModal();
                    // Refresh the prompt list
                    return fetchPrompts();
                })
                .then(newPrompts => {
                    if (newPrompts) {
                        // Update the selector with new list
                        promptSelector.innerHTML = '<option value="">-- 请选择 --</option>' + newPrompts.map(p => `<option value="${p}">${p}</option>`).join('');
                    }
                })
                .catch(error => {
                    console.error('创建新模板失败:', error);
                    alert('创建新模板失败，请稍后重试。');
                });
            });
        });

        // 6. Add event listener for AI settings form
        const aiForm = document.getElementById('ai-settings-form');
        if (aiForm) {
            aiForm.addEventListener('submit', async (e) => {
                e.preventDefault();

                // Collect form data
                const formData = new FormData(aiForm);
                const settings = {};

                // Handle regular inputs
                for (let [key, value] of formData.entries()) {
                    // Convert kebab-case to UPPERCASE_WITH_UNDERSCORES
                    const convertedKey = key.toUpperCase().replace(/-/g, '_');
                    settings[convertedKey] = value || '';
                }

                // Save settings
                const saveBtn = aiForm.querySelector('button[type="submit"]');
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';

                const result = await updateAISettings(settings);
                if (result) {
                    alert(result.message || "AI设置已保存！");
                    
                    // 刷新系统状态检查
                    const status = await fetchSystemStatus();
                    const statusContainer = document.getElementById('system-status-container');
                    if (statusContainer) {
                        statusContainer.innerHTML = renderSystemStatus(status);
                    }
                }

                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            });

            // Add event listener for AI settings test button (browser)
            const testBtn = document.getElementById('test-ai-settings-btn');
            if (testBtn) {
                testBtn.addEventListener('click', async () => {
                    // Collect form data
                    const formData = new FormData(aiForm);
                    const settings = {};

                    // Handle regular inputs
                    for (let [key, value] of formData.entries()) {
                        settings[key] = value || '';
                    }

                    // Test settings
                    const originalText = testBtn.textContent;
                    testBtn.disabled = true;
                    testBtn.textContent = '测试中...';

                    const result = await testAISettings(settings);
                    if (result) {
                        if (result.success) {
                            alert(result.message || "AI模型连接测试成功！");
                        } else {
                            alert("浏览器测试失败: " + result.message);
                        }
                    }

                    testBtn.disabled = false;
                    testBtn.textContent = originalText;
                });
            }

            // Add event listener for AI settings test button (backend)
            const testBackendBtn = document.getElementById('test-ai-settings-backend-btn');
            if (testBackendBtn) {
                testBackendBtn.addEventListener('click', async () => {
                    // 先保存AI设置，然后再测试
                    const formData = new FormData(aiForm);
                    const settings = {};

                    // 收集表单数据
                    for (let [key, value] of formData.entries()) {
                        // 将kebab-case转换为UPPERCASE_WITH_UNDERSCORES
                        const convertedKey = key.toUpperCase().replace(/-/g, '_');
                        settings[convertedKey] = value || '';
                    }

                    const originalText = testBackendBtn.textContent;
                    testBackendBtn.disabled = true;
                    testBackendBtn.textContent = '保存并测试中...';

                    try {
                        // 保存AI设置
                        const saveResult = await updateAISettings(settings);
                        
                        if (saveResult) {
                            // 保存成功后执行后端测试
                            const response = await fetch('/api/settings/ai/test/backend', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                            });

                            if (!response.ok) {
                                throw new Error('后端测试请求失败');
                            }

                            const result = await response.json();
                            if (result.success) {
                                alert(result.message || "后端AI模型连接测试成功！");
                            } else {
                                alert("后端容器测试失败: " + result.message);
                            }
                        }
                    } catch (error) {
                        alert("后端容器测试错误: " + error.message);
                    } finally {
                        testBackendBtn.disabled = false;
                        testBackendBtn.textContent = originalText;
                        
                        // 刷新系统状态检查
                        const status = await fetchSystemStatus();
                        const statusContainer = document.getElementById('system-status-container');
                        if (statusContainer) {
                            statusContainer.innerHTML = renderSystemStatus(status);
                        }
                    }
                });
            }
        }
    }

    // Handle navigation clicks
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const hash = this.getAttribute('href');
            if (window.location.hash !== hash) {
                window.location.hash = hash;
            }
        });
    });

    // Handle hash changes (e.g., back/forward buttons, direct URL)
    window.addEventListener('hashchange', () => {
        navigateTo(window.location.hash);
    });

    // --- Event Delegation for dynamic content ---
        mainContent.addEventListener('click', async (event) => {
        const target = event.target;
        const button = target.closest('button'); // Find the closest button element
        if (!button) return;

        if (button.matches('.delete-card-btn')) {
            const card = button.closest('.result-card');
            // Note: We removed the JSON.parse from card.dataset.item to avoid the error
            if (confirm('你确定要删除此商品吗？')) {
                // Here you would implement the API call to delete the item if needed
                card.remove();
            }
            return;
        }

        const row = button.closest('tr');
        const taskId = row ? row.dataset.taskId : null;

        if (button.matches('.view-json-btn')) {
            const card = button.closest('.result-card');
            const itemData = JSON.parse(card.dataset.item);
            const jsonContent = document.getElementById('json-viewer-content');
            jsonContent.textContent = JSON.stringify(itemData, null, 2);

            const modal = document.getElementById('json-viewer-modal');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('visible'), 10);
        } else if (button.matches('.run-task-btn')) {
            const taskId = button.dataset.taskId;
            button.disabled = true;
            button.textContent = '启动中...';
            await startSingleTask(taskId);
            // The auto-refresh will update the UI. For immediate feedback:
            const tasks = await fetchTasks();
            document.getElementById('tasks-table-container').innerHTML = renderTasksTable(tasks);
        } else if (button.matches('.stop-task-btn')) {
            const taskId = button.dataset.taskId;
            button.disabled = true;
            button.textContent = '停止中...';
            await stopSingleTask(taskId);
            // The auto-refresh will update the UI. For immediate feedback:
            const tasks = await fetchTasks();
            document.getElementById('tasks-table-container').innerHTML = renderTasksTable(tasks);
        } else if (button.matches('.edit-btn')) {
            const taskData = JSON.parse(row.dataset.task);
            const isRunning = taskData.is_running === true;
            const statusBadge = isRunning
                ? `<span class="status-badge status-running">运行中</span>`
                : `<span class="status-badge status-stopped">已停止</span>`;

            row.classList.add('editing');
            row.innerHTML = `
                <td>
                    <label class="switch">
                        <input type="checkbox" ${taskData.enabled ? 'checked' : ''} data-field="enabled">
                        <span class="slider round"></span>
                    </label>
                </td>
                <td><input type="text" value="${taskData.task_name}" data-field="task_name"></td>
                <td>${statusBadge}</td>
                <td><input type="text" value="${taskData.keyword}" data-field="keyword"></td>
                <td>
                    <input type="text" value="${taskData.min_price || ''}" placeholder="不限" data-field="min_price" style="width: 60px;"> -
                    <input type="text" value="${taskData.max_price || ''}" placeholder="不限" data-field="max_price" style="width: 60px;">
                </td>
                <td>
                    <label>
                        <input type="checkbox" ${taskData.personal_only ? 'checked' : ''} data-field="personal_only"> 个人闲置
                    </label>
                </td>
                <td><input type="number" value="${taskData.max_pages || 3}" data-field="max_pages" style="width: 60px;" min="1"></td>
                <td>${(taskData.ai_prompt_criteria_file || 'N/A').replace('prompts/', '')}</td>
                <td><input type="text" value="${taskData.cron || ''}" placeholder="* * * * *" data-field="cron"></td>
                <td>
                    <button class="action-btn save-btn">保存</button>
                    <button class="action-btn cancel-btn">取消</button>
                </td>
            `;

        } else if (button.matches('.delete-btn')) {
            const taskName = row.querySelector('td:nth-child(2)').textContent;
            if (confirm(`你确定要删除任务 "${taskName}" 吗?`)) {
                const result = await deleteTask(taskId);
            if (result) {
                    row.remove();
                }
            }
        } else if (button.matches('.copy-btn')) {
            // Copy task functionality - optimized to not run AI again and handle duplicate names
            const task = JSON.parse(row.dataset.task);
            
            // Create new task data with existing criteria - will be renamed by backend
            const newTaskData = {
                task_name: task.task_name, // Name will be made unique by backend
                enabled: task.enabled,
                keyword: task.keyword,
                description: task.description,
                min_price: task.min_price,
                max_price: task.max_price,
                personal_only: task.personal_only,
                max_pages: task.max_pages,
                cron: task.cron,
                ai_prompt_base_file: task.ai_prompt_base_file,
                ai_prompt_criteria_file: task.ai_prompt_criteria_file, // Original criteria file path
                is_running: false
            };
            
            // Use direct task creation instead of AI generation
            try {
                const response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(newTaskData),
                });
                
                if (response.ok) {
                    // Refresh task list immediately for better UX
                    const container = document.getElementById('tasks-table-container');
                    const tasks = await fetchTasks();
                    container.innerHTML = renderTasksTable(tasks);
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || '复制任务失败');
                }
            } catch (error) {
                console.error('无法复制任务:', error);
                alert(`错误: ${error.message}`);
            }
        } else if (button.matches('#add-task-btn')) {
            const modal = document.getElementById('add-task-modal');
            modal.style.display = 'flex';
            // Use a short timeout to allow the display property to apply before adding the transition class
            setTimeout(() => modal.classList.add('visible'), 10);
        } else if (button.matches('.save-btn')) {
            const taskNameInput = row.querySelector('input[data-field="task_name"]');
            const keywordInput = row.querySelector('input[data-field="keyword"]');
            if (!taskNameInput.value.trim() || !keywordInput.value.trim()) {
                alert('任务名称和关键词不能为空。');
                return;
            }

            const inputs = row.querySelectorAll('input[data-field]');
            const updatedData = {};
            inputs.forEach(input => {
                const field = input.dataset.field;
                if (input.type === 'checkbox') {
                    updatedData[field] = input.checked;
                } else {
                    const value = input.value.trim();
                    if (field === 'max_pages') {
                        // 确保 max_pages 作为数字发送，如果为空则默认为3
                        updatedData[field] = value ? parseInt(value, 10) : 3;
                    } else {
                        updatedData[field] = value === '' ? null : value;
                    }
                }
            });

            const result = await updateTask(taskId, updatedData);
            if (result && result.task) {
                const container = document.getElementById('tasks-table-container');
                const tasks = await fetchTasks();
                container.innerHTML = renderTasksTable(tasks);
            }
        } else if (button.matches('.cancel-btn')) {
            const container = document.getElementById('tasks-table-container');
            const tasks = await fetchTasks();
            container.innerHTML = renderTasksTable(tasks);
            } else if (button.matches('.refresh-criteria')) {
            const task = JSON.parse(row.dataset.task);
            const modal = document.getElementById('refresh-criteria-modal');
            const textarea = document.getElementById('refresh-criteria-description');
            const refreshBtn = document.getElementById('refresh-criteria-btn');
            const btnText = refreshBtn.querySelector('.btn-text');
            const spinner = refreshBtn.querySelector('.spinner');
            const loadingText = refreshBtn.querySelector('.loading-text');
            
            // 恢复按钮默认状态
            btnText.style.display = 'inline-block';
            spinner.style.display = 'none';
            loadingText.style.display = 'none';
            refreshBtn.disabled = false;
            
            // 检查任务是否正在生成AI标准
            if (task.generating_ai_criteria) {
                // 如果正在生成，显示加载状态
                btnText.style.display = 'none';
                spinner.style.display = 'inline-block';
                loadingText.style.display = 'inline-block';
                refreshBtn.disabled = true;
            }
            
            textarea.value = task['description'] || '';
            modal.dataset.taskId = taskId;
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('visible'), 10);
            
            // Load reference files for refresh modal
            try {
                const response = await fetch('/api/prompts');
                const referenceFiles = await response.json();
                const selector = document.getElementById('refresh-reference-file-selector');
                
                // Clear existing options
                selector.innerHTML = '';
                
                // Add options
                if (referenceFiles.length === 0) {
                    selector.innerHTML = '<option value="">没有可用的参考文件</option>';
                    return;
                }
                
                // Add each file as an option
                referenceFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = 'prompts/' + file; // Add full path
                    option.textContent = file;
                    // Set base_prompt.txt as default if present
                    if (file === 'base_prompt.txt') {
                        option.selected = true;
                    }
                    selector.appendChild(option);
                });
                
                // Add event listener to preview button
                const previewBtn = document.getElementById('refresh-preview-reference-file-btn');
                previewBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const selectedFile = document.getElementById('refresh-reference-file-selector').value;
                    if (!selectedFile) {
                        alert('请先选择一个参考文件模板');
                        return;
                    }
                    // Function to load reference file preview for refresh modal
                    async function loadRefreshReferenceFilePreview(filePath) {
                        if (!filePath) {
                            return;
                        }
                        
                        try {
                            const previewContainer = document.getElementById('refresh-reference-preview-container');
                            const previewContent = document.getElementById('refresh-reference-file-preview');
                            
                            previewContent.textContent = '正在加载预览...';
                            previewContainer.style.display = 'block';
                            
                            const fileName = filePath.replace('prompts/', '');
                            const response = await fetch(`/api/prompts/${fileName}`);
                            const data = await response.json();
                            
                            previewContent.textContent = data.content;
                        } catch (error) {
                            console.error('无法加载参考文件内容:', error);
                            document.getElementById('refresh-reference-file-preview').textContent = '预览加载失败，请稍后重试...';
                        }
                    }
                    loadRefreshReferenceFilePreview(selectedFile);
                });
                
            } catch (error) {
                console.error('无法加载参考文件列表:', error);
                const selector = document.getElementById('refresh-reference-file-selector');
                selector.innerHTML = '<option value="">加载参考文件失败</option>';
            }
        } 
            // Handle criteria button click
        else if (button.matches('.criteria-btn')) {
            const criteriaFile = button.dataset.criteriaFile;
            const fileName = criteriaFile.replace(/^(prompts|requirement)\//, '');
            
            // Load the criteria file content
            const modal = document.getElementById('criteria-editor-modal');
            const filenameInput = document.getElementById('criteria-filename');
            const editorTextarea = document.getElementById('criteria-editor');
            
            filenameInput.value = fileName;
            
            // Fetch and display the file content
            // Determine if it's a criteria file based on full path from backend
            const isCriteriaFile = criteriaFile.startsWith('criteria/');
            const isRequirementFile = criteriaFile.startsWith('requirement/');
            const cleanFileName = criteriaFile.replace('criteria/', '').replace('prompts/', '').replace('requirement/', '');
            
            // Function to fetch content from the correct endpoint
            async function fetchContent() {
                try {
                    let data;
                    if (isCriteriaFile || isRequirementFile) {
                        // Fetch from criteria endpoint which now handles both criteria and requirement files
                        const response = await fetch(`/api/criteria/${encodeURIComponent(cleanFileName)}`);
                        data = await response.json();
                    } else {
                        // Fetch from prompts endpoint
                        data = await fetchPromptContent(cleanFileName);
                    }
                    if (data) {
                        editorTextarea.value = data.content;
                    } else {
                        editorTextarea.value = '加载文件失败，请稍后重试...';
                    }
                } catch (error) {
                    console.error('Failed to load file:', error);
                    editorTextarea.value = '加载文件失败，请稍后重试...';
                }
            }
            
            fetchContent();
            
            modal.style.display = 'flex';
            modal.dataset.filename = criteriaFile; // 保存完整的文件路径
            setTimeout(() => modal.classList.add('visible'), 10);
        } else if (button.matches('.send-notification-btn')) {
            const card = button.closest('.result-card');
            const notificationData = JSON.parse(card.dataset.notification);
            
            // Change button text to indicate loading
            button.disabled = true;
            button.textContent = '发送中...';
            
            // Send the notification
            sendNotification(notificationData).then(result => {
                if (result) {
                    if (result.channels) {
                        const successChannels = Object.entries(result.channels)
                            .filter(([channel, status]) => status)
                            .map(([channel, _]) => channel)
                            .join('、');
                        
                        if (successChannels) {
                            alert(`通知已发送成功到以下渠道: ${successChannels}`);
                        } else {
                            alert('没有可用的通知渠道配置！');
                        }
                    } else {
                        alert('通知已发送！');
                    }
                }
                // Restore button state
                button.disabled = false;
                button.textContent = '发送通知';
            }).catch(error => {
                // Restore button state even if there's an error
                button.disabled = false;
                button.textContent = '发送通知';
            });
        }
    });

    mainContent.addEventListener('change', async (event) => {
        const target = event.target;
        // Check if the changed element is a toggle switch in the main table (not in an editing row)
        if (target.matches('.tasks-table input[type="checkbox"]') && !target.closest('tr.editing')) {
            const row = target.closest('tr');
            const taskId = row.dataset.taskId;
            const isEnabled = target.checked;

            if (taskId) {
                await updateTask(taskId, {enabled: isEnabled});
                // 立即刷新任务列表以更新运行状态
                const container = document.getElementById('tasks-table-container');
                const tasks = await fetchTasks();
                container.innerHTML = renderTasksTable(tasks);
            }
        }
    });

    // --- Modal Logic ---
    const modal = document.getElementById('add-task-modal');
    if (modal) {
        const closeModalBtn = document.getElementById('close-modal-btn');
        const cancelBtn = document.getElementById('cancel-add-task-btn');
        const saveBtn = document.getElementById('save-new-task-btn');
        const form = document.getElementById('add-task-form');

        const closeModal = () => {
            modal.classList.remove('visible');
            setTimeout(() => {
                modal.style.display = 'none';
                form.reset(); // Reset form on close
            }, 300);
        };

        closeModalBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);

        let canClose = false;
        // Load reference files when modal opens
        modal.addEventListener('transitionend', () => {
            if (modal.style.display === 'flex' && modal.classList.contains('visible')) {
                loadReferenceFiles();
            }
        });
        
        modal.addEventListener('mousedown', event => {
            canClose = event.target === modal;
        });
        modal.addEventListener('mouseup', (event) => {
            // Close if clicked on the overlay background
            if (canClose && event.target === modal) {
                closeModal();
            }
        });
        
        // Function to load reference files
        async function loadReferenceFiles() {
            try {
                const response = await fetch('/api/prompts');
                const referenceFiles = await response.json();
                const selector = document.getElementById('reference-file-selector');
                
                // Clear existing options
                selector.innerHTML = '';
                
                // Add options
                if (referenceFiles.length === 0) {
                    selector.innerHTML = '<option value="">没有可用的参考文件</option>';
                    return;
                }
                
                // Add each file as an option
                referenceFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = 'prompts/' + file; // Add full path
                    option.textContent = file;
                    // Set base_prompt.txt as default if present
                    if (file === 'base_prompt.txt') {
                        option.selected = true;
                    }
                    selector.appendChild(option);
                });
                
                // Add event listener to preview button
                const previewBtn = document.getElementById('preview-reference-file-btn');
                previewBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const selectedFile = selector.value;
                    if (!selectedFile) {
                        alert('请先选择一个参考文件模板');
                        return;
                    }
                    loadReferenceFilePreview(selectedFile);
                });
                
            } catch (error) {
                console.error('无法加载参考文件列表:', error);
                const selector = document.getElementById('reference-file-selector');
                selector.innerHTML = '<option value="">加载参考文件失败</option>';
            }
        }
        
        // Function to load reference file preview
        async function loadReferenceFilePreview(filePath) {
            if (!filePath) {
                return;
            }
            
            try {
                const previewContainer = document.getElementById('reference-preview-container');
                const previewContent = document.getElementById('reference-file-preview');
                
                previewContent.textContent = '正在加载预览...';
                previewContainer.style.display = 'block';
                
                const fileName = filePath.replace('prompts/', '');
                const response = await fetch(`/api/prompts/${fileName}`);
                const data = await response.json();
                
                previewContent.textContent = data.content;
            } catch (error) {
                console.error('无法加载参考文件内容:', error);
                document.getElementById('reference-file-preview').textContent = '预览加载失败，请稍后重试...';
            }
        }

        saveBtn.addEventListener('click', async () => {
            if (form.checkValidity() === false) {
                form.reportValidity();
                return;
            }

            const formData = new FormData(form);
            const referenceSelector = document.getElementById('reference-file-selector');
            const data = {
                task_name: formData.get('task_name'),
                keyword: formData.get('keyword'),
                description: formData.get('description'),
                min_price: formData.get('min_price') || null,
                max_price: formData.get('max_price') || null,
                personal_only: formData.get('personal_only') === 'on',
                max_pages: parseInt(formData.get('max_pages'), 10) || 3,
                cron: formData.get('cron') || null,
                reference_file: referenceSelector.value,
            };

            // Show loading state
            const btnText = saveBtn.querySelector('.btn-text');
            const spinner = saveBtn.querySelector('.spinner');
            btnText.style.display = 'none';
            spinner.style.display = 'inline-block';
            saveBtn.disabled = true;

            const result = await createTaskWithAI(data);

            // Hide loading state
            btnText.style.display = 'inline-block';
            spinner.style.display = 'none';
            saveBtn.disabled = false;

            if (result && result.task) {
                closeModal();
                // Refresh task list
                const container = document.getElementById('tasks-table-container');
                if (container) {
                    const tasks = await fetchTasks();
                    container.innerHTML = renderTasksTable(tasks);
                }
            }
        });
    }

    // --- refresh criteria Modal Logic ---
    const refreshCriteriaModal = document.getElementById('refresh-criteria-modal');
    if (refreshCriteriaModal) {
        const form = document.getElementById('refresh-criteria-form');
        const closeModalBtn = document.getElementById('close-refresh-criteria-btn');
        const cancelBtn = document.getElementById('cancel-refresh-criteria-btn');
        const refreshBtn = document.getElementById('refresh-criteria-btn');

        const closeModal = () => {
            refreshCriteriaModal.classList.remove('visible');
            setTimeout(() => {
                refreshCriteriaModal.style.display = 'none';
                form.reset(); // Reset form on close
            }, 300);
        };

        closeModalBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);

        let canClose = false;
        refreshCriteriaModal.addEventListener('mousedown', event => {
            canClose = event.target === refreshCriteriaModal;
        });
        refreshCriteriaModal.addEventListener('mouseup', (event) => {
            // Close if clicked on the overlay background
            if (canClose && event.target === refreshCriteriaModal) {
                closeModal();
            }
        });

        // Add event listener to load reference files when refresh modal opens
        refreshCriteriaModal.addEventListener('transitionend', () => {
            if (refreshCriteriaModal.style.display === 'flex' && refreshCriteriaModal.classList.contains('visible')) {
                // Reference files are already loaded when the button is clicked
            }
        });

            refreshBtn.addEventListener('click', async () => {
            // 首先检查AI配置是否完整
            try {
                const aiSettingsResponse = await fetch('/api/settings/ai');
                const aiSettings = await aiSettingsResponse.json();
                
                if (!aiSettings.OPENAI_BASE_URL || !aiSettings.OPENAI_MODEL_NAME) {
                    alert('请先配置ai模型api接口');
                    return;
                }
            } catch (error) {
                console.error('检查AI配置失败:', error);
                alert('检查AI配置失败，请稍后重试');
                return;
            }
            
            if (form.checkValidity() === false) {
                form.reportValidity();
                return;
            }
            const btnText = refreshBtn.querySelector('.btn-text');
            const spinner = refreshBtn.querySelector('.spinner');
            const loadingText = refreshBtn.querySelector('.loading-text');

            // Show loading state
            btnText.style.display = 'none';
            spinner.style.display = 'inline-block';
            loadingText.style.display = 'inline-block';
            refreshBtn.disabled = true;

            const taskId = refreshCriteriaModal.dataset.taskId;
            const formData = new FormData(form);
            const refreshReferenceSelector = document.getElementById('refresh-reference-file-selector');
            
            // Send both description and reference file to updateTask, and set generating_ai_criteria to true
            const updateData = {
                description: formData.get('description'),
                reference_file: refreshReferenceSelector.value,
                generating_ai_criteria: true
            };
            
            try {
                const result = await updateTask(taskId, updateData);
                
            // 立即更新当前任务行的状态为"生成中"
            const taskRow = document.querySelector(`tr[data-task-id="${taskId}"]`);
            if (taskRow) {
                // 更新状态徽章
                const statusBadge = taskRow.querySelector('.status-badge');
                if (statusBadge) {
                    statusBadge.className = 'status-badge status-generating';
                    statusBadge.textContent = '生成中';
                    statusBadge.style.backgroundColor = 'orange';
                }
                
                // 禁用所有操作按钮（运行、编辑、复制、删除）
                const actionButtons = taskRow.querySelectorAll('.action-btn');
                actionButtons.forEach(btn => {
                    btn.disabled = true;
                    btn.style.backgroundColor = '#ccc'; // 灰色
                    btn.style.cursor = 'not-allowed';
                });
                
                // 禁用AI标准的生成和编辑按钮
                const criteriaButtons = taskRow.querySelectorAll('.refresh-criteria, .criteria-btn');
                criteriaButtons.forEach(btn => {
                    btn.disabled = true;
                    btn.style.backgroundColor = '#ccc'; // 灰色
                    btn.style.cursor = 'not-allowed';
                });
                
                // 禁用任务开关
                const toggleSwitch = taskRow.querySelector('.switch input[type="checkbox"]');
                if (toggleSwitch) {
                    toggleSwitch.disabled = true;
                }
            }
                
                // 不立即关闭模态框，保持打开状态直到生成完成
                
            } catch (error) {
                console.error('更新任务失败:', error);
                alert('更新任务失败: ' + error.message);
                
                // 恢复按钮状态
                btnText.style.display = 'inline-block';
                spinner.style.display = 'none';
                loadingText.style.display = 'none';
                refreshBtn.disabled = false;
            }
        })
    }


    // Initial load
    refreshLoginStatusWidget();
    
    // Add manual login button to the top header status widget
    const loginStatusWidget = document.querySelector('.login-status-widget');
    if (loginStatusWidget) {
        // Create the button
        const manualLoginBtn = document.createElement('button');
        manualLoginBtn.id = 'manual-login-btn-header';
        manualLoginBtn.className = 'control-button primary-btn';
        manualLoginBtn.style.backgroundColor = '#dc3545';
        manualLoginBtn.style.border = '1px solid #dc3545';
        manualLoginBtn.style.color = 'white';
        manualLoginBtn.style.padding = '8px 12px';
        manualLoginBtn.style.marginRight = '15px';
        manualLoginBtn.textContent = '点击自动获取cookie登录';
        
        // Add click event to show modal instead of confirm dialog
        manualLoginBtn.addEventListener('click', () => {
            // Show the custom modal
            const modal = document.getElementById('manual-login-confirm-modal');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('visible'), 10);
            
            // Get modal elements
            const confirmBtn = document.getElementById('confirm-manual-login-confirm-btn');
            const cancelBtn = document.getElementById('cancel-manual-login-confirm-btn');
            const closeBtn = document.getElementById('close-manual-login-confirm-modal');
            
            // Function to close the modal
            const closeModal = () => {
                modal.classList.remove('visible');
                setTimeout(() => {
                    modal.style.display = 'none';
                }, 300); // Match the modal transition duration
            };
            
                // Function to handle the confirmation action
                const handleConfirmation = async () => {
                    try {
                        const response = await fetch('/api/manual-login', {
                            method: 'POST'
                        });
                        
                        if (!response.ok) {
                            const errorData = await response.json();
                            alert('启动失败: ' + (errorData.detail || '未知错误'));
                        } else {
                            // 开始轮询检查登录状态
                            const pollInterval = 2000; // 每 2 秒检查一次
                            const pollTimeout = 300000; // 300 秒后超时
                            let pollAttempts = 0;
                            const maxAttempts = pollTimeout / pollInterval;
                            
                            // 开始轮询检查登录状态
                            const intervalId = setInterval(async () => {
                                pollAttempts++;
                                
                                try {
                                    const status = await fetchSystemStatus();
                                    if (status && status.login_state_file && status.login_state_file.exists) {
                                        // 登录状态已更新，刷新登录状态 widget
                                        await refreshLoginStatusWidget();
                                        // 停止轮询
                                        clearInterval(intervalId);
                                        return;
                                    }
                                } catch (error) {
                                    console.error('轮询检查登录状态时出错:', error);
                                }
                                
                                // 检查是否超时
                                if (pollAttempts >= maxAttempts) {
                                    console.log('轮询检查登录状态超时');
                                    clearInterval(intervalId);
                                    return;
                                }
                            }, pollInterval);
                        }
                        // No alert for success - directly close the modal
                    } catch (error) {
                        alert('启动失败: ' + error.message);
                    } finally {
                        closeModal();
                    }
                };
            
            // Add event listeners with once: true to avoid memory leaks
            confirmBtn.addEventListener('click', handleConfirmation, { once: true });
            cancelBtn.addEventListener('click', closeModal, { once: true });
            closeBtn.addEventListener('click', closeModal, { once: true });
            
                // Add click outside to close functionality
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) closeModal();
                }, { once: true });
        });
        
        // Insert the button before the status text
        const statusText = loginStatusWidget.querySelector('.status-text');
        if (statusText) {
            loginStatusWidget.insertBefore(manualLoginBtn, statusText);
        }
    }
    
    navigateTo(window.location.hash || '#tasks');

    // --- Global Event Listener for header/modals ---
    document.body.addEventListener('click', async (event) => {
        const target = event.target;
        const widgetUpdateBtn = target.closest('#update-login-state-btn-widget');
        const widgetDeleteBtn = target.closest('#delete-login-state-btn-widget');
        const copyCodeBtn = target.closest('#copy-login-script-btn');

        if (copyCodeBtn) {
            event.preventDefault();
            const codeToCopy = document.getElementById('login-script-code').textContent.trim();

            // 在安全上下文中使用现代剪贴板API，否则使用备用方法
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(codeToCopy).then(() => {
                    copyCodeBtn.textContent = '已复制!';
                    setTimeout(() => {
                        copyCodeBtn.textContent = '复制脚本';
                    }, 2000);
                }).catch(err => {
                    console.error('无法使用剪贴板API复制文本: ', err);
                    alert('复制失败，请手动复制。');
                });
            } else {
                // 针对非安全上下文 (如HTTP) 或旧版浏览器的备用方案
                const textArea = document.createElement("textarea");
                textArea.value = codeToCopy;
                // 使文本区域不可见
                textArea.style.position = "fixed";
                textArea.style.top = "-9999px";
                textArea.style.left = "-9999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {
                    document.execCommand('copy');
                    copyCodeBtn.textContent = '已复制!';
                    setTimeout(() => {
                        copyCodeBtn.textContent = '复制脚本';
                    }, 2000);
                } catch (err) {
                    console.error('备用方案: 无法复制文本', err);
                    alert('复制失败，请手动复制。');
                }
                document.body.removeChild(textArea);
            }
        } else if (widgetUpdateBtn) {
            event.preventDefault();
            const modal = document.getElementById('login-state-modal');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('visible'), 10);
        } else if (widgetDeleteBtn) {
            event.preventDefault();
            if (confirm('你确定要删除登录凭证 (xianyu_state.json) 吗？删除后需要重新设置才能运行任务。')) {
                const result = await deleteLoginState();
                if (result) {
                    alert(result.message);
                    await refreshLoginStatusWidget(); // Refresh the widget UI
                    // Also refresh settings view if it's currently active
                    if (window.location.hash === '#settings' || window.location.hash === '') {
                        const statusContainer = document.getElementById('system-status-container');
                        if (statusContainer) {
                            const status = await fetchSystemStatus();
                            statusContainer.innerHTML = renderSystemStatus(status);
                        }
                    }
                }
            }
        }
    });

    // --- JSON Viewer Modal Logic ---
    const jsonViewerModal = document.getElementById('json-viewer-modal');
    if (jsonViewerModal) {
        const closeBtn = document.getElementById('close-json-viewer-btn');

        const closeModal = () => {
            jsonViewerModal.classList.remove('visible');
            setTimeout(() => {
                jsonViewerModal.style.display = 'none';
            }, 300);
        };

        closeBtn.addEventListener('click', closeModal);
        jsonViewerModal.addEventListener('click', (event) => {
            if (event.target === jsonViewerModal) {
                closeModal();
            }
        });
    }

    // --- Criteria Editor Modal Logic ---
    const criteriaEditorModal = document.getElementById('criteria-editor-modal');
    if (criteriaEditorModal) {
        const closeBtn = document.getElementById('close-criteria-editor-btn');
        const cancelBtn = document.getElementById('cancel-criteria-editor-btn');
        const saveBtn = document.getElementById('save-criteria-editor-btn');
        const backBtn = document.getElementById('back-from-editor-btn');
        const editorTextarea = document.getElementById('criteria-editor');
        
        const closeModal = () => {
            criteriaEditorModal.classList.remove('visible');
            setTimeout(() => {
                criteriaEditorModal.style.display = 'none';
                // Clear content on close
                document.getElementById('criteria-filename').value = '';
                editorTextarea.value = '';
            }, 300);
        };

        // Close modal event handlers
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        criteriaEditorModal.addEventListener('click', (event) => {
            if (event.target === criteriaEditorModal) {
                closeModal();
            }
        });

        // Back button event handler (navigates back to task management)
        backBtn.addEventListener('click', () => {
            closeModal();
            // Ensure we're on the tasks page
            if (window.location.hash !== '#tasks') {
                window.location.hash = '#tasks';
            }
        });

            // Save button event handler
            saveBtn.addEventListener('click', async () => {
                const fullFileName = criteriaEditorModal.dataset.filename;
                const content = editorTextarea.value;

                if (!fullFileName || !content) {
                    alert('请确保文件名和内容都已填写。');
                    return;
                }
                
                try {
                    let apiPath;
                    // 根据文件名判断是哪种类型的文件并选择正确的API路径
                    if (fullFileName.includes('requirement/')) {
                        // requirement文件使用/api/criteria端点
                        apiPath = `/api/criteria/${encodeURIComponent(fullFileName.replace('requirement/', ''))}`;
                    } else if (fullFileName.includes('criteria/')) {
                        // criteria文件使用/api/criteria端点
                        apiPath = `/api/criteria/${encodeURIComponent(fullFileName.replace('criteria/', ''))}`;
                    } else if (fullFileName.includes('prompts/')) {
                        // prompt文件使用/api/prompts端点
                        apiPath = `/api/prompts/${encodeURIComponent(fullFileName.replace('prompts/', ''))}`;
                    } else {
                        // 普通文件名直接使用/api/criteria端点
                        apiPath = `/api/criteria/${encodeURIComponent(fullFileName)}`;
                    }
                    
                    const response = await fetch(apiPath, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({content: content}),
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        alert('文件保存成功！');
                        closeModal();
                    } else {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || '保存失败');
                    }
                } catch (error) {
                    console.error('Failed to save file:', error);
                    alert('文件保存失败: ' + error.message);
                }
            });
    }

    // --- Login State Modal Logic ---
    const loginStateModal = document.getElementById('login-state-modal');
    if (loginStateModal) {
        const closeBtn = document.getElementById('close-login-state-modal-btn');
        const cancelBtn = document.getElementById('cancel-login-state-btn');
        const saveBtn = document.getElementById('save-login-state-btn');
        const form = document.getElementById('login-state-form');
        const contentTextarea = document.getElementById('login-state-content');

        const closeModal = () => {
            loginStateModal.classList.remove('visible');
            setTimeout(() => {
                loginStateModal.style.display = 'none';
                form.reset();
            }, 300);
        };

        async function updateLoginState(content) {
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
            try {
                const response = await fetch('/api/login-state', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({content: content}),
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || '更新登录状态失败');
                }
                alert('登录状态更新成功！');
                closeModal();
                await refreshLoginStatusWidget(); // Refresh the widget UI
                // Also refresh settings view if it's currently active
                if (window.location.hash === '#settings') {
                    await initializeSettingsView();
                }
            } catch (error) {
                console.error('更新登录状态时出错:', error);
                alert(`更新失败: ${error.message}`);
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = '保存';
            }
        }

        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        loginStateModal.addEventListener('click', (event) => {
            if (event.target === loginStateModal) {
                closeModal();
            }
        });

        saveBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const content = contentTextarea.value.trim();
            if (!content) {
                alert('请粘贴从浏览器获取的JSON内容。');
                return;
            }
            await updateLoginState(content);
        });

    }
});

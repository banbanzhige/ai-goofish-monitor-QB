document.addEventListener('DOMContentLoaded', function () {
    // 下拉菜单交互逻辑
    document.addEventListener('click', function(event) {
        const dropdownBtn = event.target.closest('.dropdown-btn');
        
        // 点击下拉按钮
        if (dropdownBtn) {
            event.stopPropagation();
            
            const dropdownContainer = dropdownBtn.closest('.dropdown-container');
            const dropdownMenu = dropdownContainer.querySelector('.dropdown-menu');
            
            // 切换当前下拉菜单的显示/隐藏
            dropdownMenu.classList.toggle('show');
            
            // 关闭其他所有下拉菜单
            document.querySelectorAll('.dropdown-container').forEach(container => {
                if (container !== dropdownContainer) {
                    const menu = container.querySelector('.dropdown-menu');
                    menu.classList.remove('show');
                }
            });
        } else {
            // 点击外部区域，关闭所有下拉菜单
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });

    // 为下拉菜单项添加点击事件，点击后关闭菜单
    document.addEventListener('click', function(event) {
        const dropdownItem = event.target.closest('.dropdown-item');
        
        if (dropdownItem) {
            const dropdownMenu = dropdownItem.closest('.dropdown-menu');
            dropdownMenu.classList.remove('show');
        }
    });

    const mainContent = document.getElementById('main-content');
    const navLinks = document.querySelectorAll('.nav-link');
    let logRefreshInterval = null;
    let taskRefreshInterval = null;

    // Mobile Menu Logic
    const mobileMenuBtn = document.getElementById('mobile-menu-toggle');
    const sidebar = document.querySelector('aside');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

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

        // Close sidebar when clicking a nav link on mobile
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('active');
                    sidebarOverlay.classList.remove('active');
                }
            });
        });
    }

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
                            <option value="crawl_time">按浏览时间</option>
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
                            <select id="log-display-limit">
                                <option value="100" selected>100条</option>
                                <option value="200">200条</option>
                                <option value="500">500条</option>
                                <option value="1000">1000条</option>
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
            </section>`,
        scheduled: () => `
            <section id="scheduled-section" class="content-section">
                <div class="section-header">
                    <h2>定时任务</h2>
                    <button id="refresh-scheduled-btn" class="control-button" style="background-color: #52c41a; border-color: #52c41a; color: white;">🔄 刷新</button>
                </div>
                <div id="scheduled-table-container">
                    <p>正在加载定时任务...</p>
                </div>
            </section>`,
        accounts: () => `
            <section id="accounts-section" class="content-section">
                <div class="section-header">
                    <h2>闲鱼账号管理</h2>
                    <div class="header-buttons" style="justify-content: flex-end;">
                        <button id="import-from-login-btn" class="control-button" style="background-color: #52c41a; border-color: #52c41a; color: white;">🚀 自动获取账号</button>
                        <button id="add-account-btn" class="control-button primary-btn">✏️ 手动添加账号</button>
                    </div>
                </div>
                <div id="accounts-table-container">
                    <p>正在加载账号列表...</p>
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

    async function testAISettings(settings) {
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
            alert(`错误: ${error.message}`);
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
            // Handle various error formats
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

    async function deleteLoginState() {
        try {
            const response = await fetch('/api/login-state', { method: 'DELETE' });
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
            return await response.json();
        } catch (error) {
            console.error(error);
            return [];
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

    // --- 渲染函数 ---
    function renderLoginStatusWidget(status) {
        const container = document.getElementById('login-status-widget-container');
        if (!container) return;

        const loginState = status.login_state_file;
        const hasCookie = loginState && loginState.exists;

        // 固定按钮样式，无论登录状态如何都显示相同的按钮
        const content = `
            <div class="login-status-widget">
                <div class="login-dropdown-container" style="position: relative; display: inline-block;">
                    <button class="login-status-btn control-button primary-btn" 
                        style="background-color: #1890ff; border: 1px solid #1890ff; color: white; padding: 8px 16px;">
                        👤 账号
                    </button>
                    <div class="login-dropdown-menu" style="display: none; position: absolute; right: 0; top: 100%; min-width: 150px; background: white; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000; margin-top: 5px; overflow: hidden;">
                        <a href="#accounts" class="login-menu-item" style="display: block; padding: 12px 15px; color: #333; text-decoration: none; font-size: 14px;">
                            ➕ 添加闲鱼账号
                        </a>
                        <a href="/logout" class="login-menu-item" style="display: block; padding: 12px 15px; color: #333; text-decoration: none; font-size: 14px;">
                            🚪 退出登录
                        </a>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = content;

        // 下拉菜单交互
        const dropdownBtn = container.querySelector('.login-status-btn');
        const dropdownMenu = container.querySelector('.login-dropdown-menu');

        if (dropdownBtn && dropdownMenu) {
            dropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isVisible = dropdownMenu.style.display === 'block';
                dropdownMenu.style.display = isVisible ? 'none' : 'block';
            });

            // 点击外部关闭
            document.addEventListener('click', () => {
                dropdownMenu.style.display = 'none';
            });

            // 菜单项hover效果
            dropdownMenu.querySelectorAll('.login-menu-item').forEach(item => {
                item.addEventListener('mouseenter', () => {
                    if (!item.classList.contains('delete-item')) {
                        item.style.backgroundColor = '#f5f5f5';
                    } else {
                        item.style.backgroundColor = '#fff2f0';
                    }
                });
                item.addEventListener('mouseleave', () => {
                    item.style.backgroundColor = 'transparent';
                });
            });
        }

        // 自动获取/更新Cookie按钮事件
        const autoGetBtn = container.querySelector('#auto-get-cookie-btn') || container.querySelector('#auto-update-cookie-btn');
        if (autoGetBtn) {
            autoGetBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                dropdownMenu.style.display = 'none';

                // 显示自动登录确认模态框
                const confirmModal = document.getElementById('manual-login-confirm-modal');
                if (!confirmModal) return;

                confirmModal.style.display = 'flex';
                setTimeout(() => confirmModal.classList.add('visible'), 10);

                const confirmBtn = document.getElementById('confirm-manual-login-confirm-btn');
                const cancelBtn = document.getElementById('cancel-manual-login-confirm-btn');
                const closeBtn = document.getElementById('close-manual-login-confirm-modal');

                const closeModal = () => {
                    confirmModal.classList.remove('visible');
                    setTimeout(() => { confirmModal.style.display = 'none'; }, 300);
                };

                const handleConfirmation = async () => {
                    try {
                        const response = await fetch('/api/manual-login', { method: 'POST' });
                        if (!response.ok) {
                            const errorData = await response.json();
                            alert('启动失败: ' + (errorData.detail || '未知错误'));
                        } else {
                            // 轮询检查登录状态
                            const pollInterval = 2000;
                            const pollTimeout = 300000;
                            let pollAttempts = 0;
                            const maxAttempts = pollTimeout / pollInterval;

                            const intervalId = setInterval(async () => {
                                pollAttempts++;
                                try {
                                    const status = await fetchSystemStatus();
                                    if (status && status.login_state_file && status.login_state_file.exists) {
                                        await refreshLoginStatusWidget();
                                        clearInterval(intervalId);
                                        return;
                                    }
                                } catch (error) {
                                    console.error('轮询检查登录状态时出错:', error);
                                }
                                if (pollAttempts >= maxAttempts) {
                                    console.log('轮询检查登录状态超时');
                                    clearInterval(intervalId);
                                }
                            }, pollInterval);
                        }
                    } catch (error) {
                        alert('启动失败: ' + error.message);
                    } finally {
                        closeModal();
                    }
                };

                confirmBtn.addEventListener('click', handleConfirmation, { once: true });
                cancelBtn.addEventListener('click', closeModal, { once: true });
                closeBtn.addEventListener('click', closeModal, { once: true });
                confirmModal.addEventListener('click', (e) => {
                    if (e.target === confirmModal) closeModal();
                }, { once: true });
            });
        }

        // 手动输入Cookie按钮事件
        const manualInputBtn = container.querySelector('#manual-input-cookie-btn') || container.querySelector('#manual-update-cookie-btn');
        if (manualInputBtn) {
            manualInputBtn.addEventListener('click', (e) => {
                e.preventDefault();
                dropdownMenu.style.display = 'none';
                // 跳转到系统设置页面（或显示Cookie输入模态框）
                const settingsLink = document.querySelector('.nav-link[data-section="settings"]');
                if (settingsLink) settingsLink.click();
            });
        }

        // 删除Cookie按钮事件
        const deleteCookieBtn = container.querySelector('#delete-cookie-btn');
        if (deleteCookieBtn) {
            deleteCookieBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                dropdownMenu.style.display = 'none';

                if (confirm('确定要删除当前Cookie吗？删除后需要重新登录获取。')) {
                    try {
                        const response = await fetch('/api/login-state', { method: 'DELETE' });
                        if (response.ok) {
                            await refreshLoginStatusWidget();
                        } else {
                            alert('删除失败');
                        }
                    } catch (error) {
                        alert('删除失败: ' + error.message);
                    }
                }
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
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="notify-after-task-complete" name="NOTIFY_AFTER_TASK_COMPLETE" ${settings.NOTIFY_AFTER_TASK_COMPLETE ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">任务完成后发送通知</div>
                                <p class="form-hint" style="margin: 2px 0;">当监控任务完成时发送通知提醒</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>企业微信应用通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="wx-app-enabled" name="WX_APP_ENABLED" ${settings.WX_APP_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用企业微信应用通知</div>
                            </div>
                        </div>
                    </div>
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
                        <div style="position: relative;">
                            <input type="password" id="wx-secret" name="WX_SECRET" value="${settings.WX_SECRET || ''}" placeholder="例如: your_app_secret">
                        <button type="button" id="toggle-wx-secret-visibility" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 14px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                        </div>
                        <p class="form-hint">企业微信管理后台获取</p>
                    </div>
                    
                    <div class="form-group">
                        <label for="wx-to-user">通知用户 (可选)</label>
                        <input type="text" id="wx-to-user" name="WX_TO_USER" value="${settings.WX_TO_USER || ''}" placeholder="例如: UserID1|UserID2 或 @all">
                        <p class="form-hint">接收通知的用户ID列表，用|分隔，或@all通知所有用户</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="wx_app" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="wx_app" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>企业微信机器人通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="wx-bot-enabled" name="WX_BOT_ENABLED" ${settings.WX_BOT_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用企业微信机器人通知</div>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="wx-bot-url">Webhook URL</label>
                        <input type="text" id="wx-bot-url" name="WX_BOT_URL" value="${settings.WX_BOT_URL || ''}" placeholder="例如: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key">
                        <p class="form-hint">企业微信机器人的 Webhook 地址</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="wx_bot" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="wx_bot" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>钉钉机器人通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="dingtalk-enabled" name="DINGTALK_ENABLED" ${settings.DINGTALK_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用钉钉机器人通知</div>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="dingtalk-webhook">Webhook 地址</label>
                        <input type="text" id="dingtalk-webhook" name="DINGTALK_WEBHOOK" value="${settings.DINGTALK_WEBHOOK || ''}" placeholder="例如: https://oapi.dingtalk.com/robot/send?access_token=xxx">
                        <p class="form-hint">钉钉机器人的 Webhook 地址，从钉钉群机器人设置获取</p>
                    </div>
                    <div class="form-group">
                        <label for="dingtalk-secret">加签密钥 (可选)</label>
                        <div style="position: relative;">
                            <input type="password" id="dingtalk-secret" name="DINGTALK_SECRET" value="${settings.DINGTALK_SECRET || ''}" placeholder="例如: SECxxxxxxx">
                        <button type="button" id="toggle-dingtalk-secret-visibility" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 14px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                        </div>
                        <p class="form-hint">钉钉机器人的加签密钥，如果启用了安全设置中的"加签"功能则必填</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="dingtalk" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="dingtalk" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Telegram 机器人通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="telegram-enabled" name="TELEGRAM_ENABLED" ${settings.TELEGRAM_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用 Telegram 机器人通知</div>
                            </div>
                        </div>
                    </div>
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
                        <button type="button" class="test-notification-btn" data-channel="telegram" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="telegram" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Ntfy 通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="ntfy-enabled" name="NTFY_ENABLED" ${settings.NTFY_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用 Ntfy 通知</div>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="ntfy-topic-url">Topic URL</label>
                        <input type="text" id="ntfy-topic-url" name="NTFY_TOPIC_URL" value="${settings.NTFY_TOPIC_URL || ''}" placeholder="例如: https://ntfy.sh/your_topic">
                        <p class="form-hint">用于发送通知到 ntfy.sh 服务</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="ntfy" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="ntfy" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Gotify 通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="gotify-enabled" name="GOTIFY_ENABLED" ${settings.GOTIFY_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用 Gotify 通知</div>
                            </div>
                        </div>
                    </div>
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
                        <button type="button" class="test-notification-btn" data-channel="gotify" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="gotify" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>Bark 通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="bark-enabled" name="BARK_ENABLED" ${settings.BARK_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用 Bark 通知</div>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="bark-url">推送地址</label>
                        <input type="text" id="bark-url" name="BARK_URL" value="${settings.BARK_URL || ''}" placeholder="例如: https://api.day.app/your_key">
                        <p class="form-hint">Bark 推送地址</p>
                    </div>
                    <div class="form-group">
                        <button type="button" class="test-notification-btn" data-channel="bark" style="background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-right: 10px;">测试通知</button>
                        <button type="button" class="test-task-completion-btn" data-channel="bark" style="background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">测试任务完成通知</button>
                    </div>
                </div>
                
                <div class="notification-channel-card">
                    <h4>通用 Webhook 通知</h4>
                    <div class="form-group">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <label class="switch">
                                <input type="checkbox" id="webhook-enabled" name="WEBHOOK_ENABLED" ${settings.WEBHOOK_ENABLED ? 'checked' : ''}>
                                <span class="slider round"></span>
                            </label>
                            <div style="flex: 1;">
                                <div style="font-weight: 500;">启用通用 Webhook 通知</div>
                            </div>
                        </div>
                    </div>
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
                    <div style="position: relative;">
                        <input type="password" id="openai-api-key" name="OPENAI_API_KEY" value="${settings.OPENAI_API_KEY || ''}" placeholder="例如: sk-..." required>
                        <button type="button" id="toggle-openai-api-key-visibility" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 14px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                    </div>
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

            // 为登录状态小部件添加点击事件，用于切换"已获取cookie"和"已登录"按钮的下拉菜单
            const loginStatusWidget = document.querySelector('.login-status-widget');
            if (loginStatusWidget) {
                // 只选择前两个带有下拉菜单的控制按钮
                const buttons = loginStatusWidget.querySelectorAll('.control-button');
                // 只处理前两个应该有下拉菜单的按钮
                for (let i = 0; i < Math.min(buttons.length, 2); i++) {
                    const btn = buttons[i];
                    let dropdownMenu = btn.nextElementSibling;

                    // 检查是否找到了下拉菜单
                    if (dropdownMenu && dropdownMenu.classList.contains('dropdown-menu')) {
                        btn.addEventListener('click', (e) => {
                            e.preventDefault();
                            // 切换此下拉菜单
                            dropdownMenu.style.display = dropdownMenu.style.display === 'block' ? 'none' : 'block';

                            // 关闭小部件中的其他下拉菜单
                            loginStatusWidget.querySelectorAll('.dropdown-menu').forEach((menu) => {
                                if (menu !== dropdownMenu) {
                                    menu.style.display = 'none';
                                }
                            });
                        });

                        // 防止事件冒泡以避免意外行为
                        btn.addEventListener('click', (e) => e.stopPropagation());
                    }
                }

                // 点击外部关闭所有下拉菜单
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

        // 检查是否配置了至少一个通知渠道
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
            const crawlTime = item.公开信息浏览时间 ? new Date(item.公开信息浏览时间).toLocaleString('sv-SE').slice(0, 16) : '未知';
            const publishTime = info.发布时间 || '未知';

            // 转义HTML以防止XSS攻击
            const escapeHtml = (unsafe) => {
                if (typeof unsafe !== 'string') return unsafe;
                const div = document.createElement('div');
                div.textContent = unsafe;
                return div.innerHTML;
            };

            // 从商品链接中提取商品ID
            const extractItemId = (url) => {
                if (!url) return '';
                try {
                    // 匹配URL中的id参数
                    const match = url.match(/id=(\d+)/);
                    return match ? match[1] : '';
                } catch (error) {
                    console.error('无法从URL中提取商品ID:', error);
                    return '';
                }
            };

            // 在文本中高亮显示关键词
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
                爬取时间: item.公开信息浏览时间,
                搜索关键字: item.搜索关键字,
                任务名称: item.任务名称,
                AI标准: item.AI标准
            };

            // 从商品链接中提取商品ID
            const itemId = extractItemId(info.商品链接);
            return `
            <div class="result-card" data-notification='${escapeHtml(JSON.stringify(notificationData))}' data-item-id='${escapeHtml(itemId)}'>
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
                    <p>浏览于: ${escapeHtml(crawlTime)}</p>
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
                    <th>绑定账号</th>
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
                // 检查条件文件是否存在
                const criteriaFile = task.ai_prompt_criteria_file || 'N/A';
                const criteriaBtnText = criteriaFile
                    .replace(/^criteria\/(.*?)_criteria\.txt$/i, '$1') // 替换完整路径
                    .replace(/^criteria\//i, '') // 替换前缀
                    .replace(/_criteria\.txt$/i, '') // 替换后缀
                    .replace(/^prompts\/(.*?)_criteria\.txt$/i, '$1') // 处理旧路径
                    .replace(/_criteria$/i, '') // 处理不带.txt的情况
                    .replace(/^requirement\/(.*?)_requirement\.txt$/i, '$1_requirement'); // 处理"requirement/名称_requirement.txt"路径，只显示"名称_requirement"
                const hasAIStandard = !(criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement'));
                const hasCron = task.cron && task.cron.trim() !== '';
                const isEnabled = task.enabled === true;

                if (hasAIStandard && hasCron && isEnabled) {
                    statusBadge = `<span class="status-badge status-scheduled" style="background-color: #ffc107; color: #000;">定时中</span>`;
                } else if (criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement')) {
                    statusBadge = `<span class="status-badge status-waiting" style="background-color: #007bff;">待生成标准</span>`;
                } else {
                    statusBadge = `<span class="status-badge status-stopped">已停止</span>`;
                }
            }

            // 格式化条件文件名，只显示中间文本，不带前缀/后缀
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

            // 确定按钮是否应该禁用
            const buttonDisabledAttr = isRunning || isGeneratingAI ? 'disabled' : '';
            const buttonDisabledTitle = isGeneratingAI ? 'title="等待AI标准生成"' : (isRunning ? 'title="任务运行中"' : '');
            const buttonDisabledStyle = isRunning || isGeneratingAI ? 'style="background-color: #ccc; cursor: not-allowed;"' : '';

            // 检查是否禁止编辑
            const isEditDisabled = isRunning || isGeneratingAI;

            return `
            <tr data-task-id="${task.id}" data-task='${JSON.stringify(task)}'>
                <td style="text-align: center;">
                    <label class="switch">
                        <input type="checkbox" ${task.enabled ? 'checked' : ''} ${isEditDisabled ? 'disabled' : ''}>
                        <span class="slider round"></span>
                    </label>
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="task_name" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display">${task.task_name}</span>
                        <input type="text" class="editable-input" value="${task.task_name}" style="display:none;">
                    </div>
                </td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="keyword" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display tag">${task.keyword}</span>
                        <input type="text" class="editable-input" value="${task.keyword}" style="display:none;">
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="account-cell" data-task-id="${task.id}" data-bound-account="${task.bound_account || ''}" data-display-name="" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="account-display ${task.bound_account ? 'has-account' : 'no-account'}" style="${task.bound_account ? 'background-color:' + getAccountColorByName(task.bound_account) + ';color:#fff;' : ''}">
                            ${task.bound_account ? '加载中...' : '未绑定'}
                        </span>
                        <div class="editable-account-select">
                            <select class="account-select" style="display:none;">
                                <option value="">未绑定</option>
                            </select>
                        </div>
                    </div>
                    ${task.auto_switch_on_risk ? '<span class="auto-switch-icon" title="风控自动切换">🔄</span>' : ''}
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="price_range" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display">${task.min_price || '不限'} - ${task.max_price || '不限'}</span>
                        <div class="editable-price-inputs" style="display:none;">
                            <input type="number" class="editable-input price-min" value="${task.min_price || ''}" placeholder="最低价" style="width:60px;">
                            <span>-</span>
                            <input type="number" class="editable-input price-max" value="${task.max_price || ''}" placeholder="最高价" style="width:60px;">
                        </div>
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell editable-toggle" data-task-id="${task.id}" data-field="personal_only" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display ${task.personal_only ? 'tag personal' : ''}">${task.personal_only ? '个人闲置' : '不限'}</span>
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="max_pages" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display">${task.max_pages || 3}</span>
                        <input type="number" class="editable-input" value="${task.max_pages || 3}" min="1" style="display:none; width:50px;">
                    </div>
                </td>
                <td style="text-align: left !important;">
                    <div class="criteria" style="display: inline-block; text-align: left;">
${criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement') ? `
                            <div class="red-dot-container">
                                <button class="refresh-criteria success-btn" title="新生成AI标准" data-task-id="${task.id}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>待生成</button>
                                <span class="red-dot"></span>
                            </div>
                            <button class="criteria-btn danger-btn" title="编辑AI标准" data-task-id="${task.id}" data-criteria-file="${criteriaFile}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>
                                ${criteriaBtnText}
                            </button>
                        ` : `
                            <button class="refresh-criteria danger-btn" title="新生成AI标准" data-task-id="${task.id}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>重生成</button>
                            ${criteriaFile !== 'N/A' ? `
                                <button class="criteria-btn success-btn" title="编辑AI标准" data-task-id="${task.id}" data-criteria-file="${criteriaFile}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>
                                    ${criteriaBtnText}
                                </button>
                            ` : 'N/A'}
                        `}
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="cron" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display">${task.cron || '未设置'}</span>
                        <input type="text" class="editable-input" value="${task.cron || ''}" placeholder="分 时 日 月 周" style="display:none; width:100px;">
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="action-buttons">
                        ${actionButton}
                        <div class="dropdown-container">
                            <button class="dropdown-btn" ${buttonDisabledAttr} ${buttonDisabledTitle} ${buttonDisabledStyle}>操作 ▾</button>
                            <div class="dropdown-menu">
                                <button class="dropdown-item edit-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>✏️ 编辑</button>
                                <button class="dropdown-item copy-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>📋 复制</button>
                                <button class="dropdown-item delete-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>🗑️ 删除</button>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>`
        }).join('');

        return `<table class="tasks-table">${tableHeader}<tbody>${tableBody}</tbody></table>`;
    }

    // 填充任务表格中的账号选择器（新版：点击显示下拉框）
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
                    alert('更新账号绑定失败，请重试');
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
                    container.innerHTML = renderTasksTable(tasks);
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

        // Track text selection state globally
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

        // Click on editable display to show input
        document.addEventListener('click', async (event) => {
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

            // Handle toggle fields (personal_only) - click toggles immediately
            if (cell.classList.contains('editable-toggle')) {
                const row = cell.closest('tr');
                const taskData = JSON.parse(row.dataset.task);
                const newValue = !taskData.personal_only;

                try {
                    const result = await updateTask(taskId, { personal_only: newValue });
                    if (result) {
                        // Update display
                        display.textContent = newValue ? '个人闲置' : '不限';
                        display.className = 'editable-display ' + (newValue ? 'tag personal' : '');
                        // Update row data
                        taskData.personal_only = newValue;
                        row.dataset.task = JSON.stringify(taskData);
                        // 刷新任务列表并重新开启定时刷新
                        await refreshTasksAndRestartInterval();
                    }
                } catch (error) {
                    console.error('更新筛选条件失败:', error);
                    alert('更新失败，请重试');
                    // 即使失败也重新开启定时刷新
                    await refreshTasksAndRestartInterval();
                }
                return;
            }

            // Handle price_range field
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

            // Handle regular text/number inputs
            const input = cell.querySelector('.editable-input');
            if (input) {
                display.style.display = 'none';
                input.style.display = 'inline-block';
                // 自动调整输入框宽度
                autoResizeInput(input);
                input.focus();
                input.select();
                // 添加输入事件监听，实时调整宽度
                input.addEventListener('input', function() {
                    autoResizeInput(input);
                });
            }
        });

        // 刷新任务列表并重新开启定时刷新的函数
        async function refreshTasksAndRestartInterval() {
            const container = document.getElementById('tasks-table-container');
            const tasks = await fetchTasks();
            container.innerHTML = renderTasksTable(tasks);
            // 重新开启定时刷新
            if (!taskRefreshInterval) {
                taskRefreshInterval = setInterval(async () => {
                    const tasks = await fetchTasks();
                    if (container && !container.querySelector('tr.editing') && !document.querySelector('.editable-input:focus')) {
                        container.innerHTML = renderTasksTable(tasks);
                    }
                }, 5000);
            }
        }

        // Handle blur for regular inputs - save and switch back
        document.addEventListener('blur', async (event) => {
            const input = event.target;
            if (!input.classList.contains('editable-input')) return;

            // If selecting text, refocus instead of saving
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

            // Handle price_range inputs
            if (field === 'price_range') {
                const priceInputs = cell.querySelector('.editable-price-inputs');
                // Check if focus is still within price inputs
                setTimeout(async () => {
                    const activeElement = document.activeElement;
                    if (priceInputs.contains(activeElement)) return; // Still editing price

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
                        alert('更新失败，请重试');
                        // 即使失败也重新开启定时刷新
                        await refreshTasksAndRestartInterval();
                    }

                    priceInputs.style.display = 'none';
                    display.style.display = 'inline-block';
                }, 100);
                return;
            }

            // Handle other fields
            const newValue = input.value.trim();
            let updateData = {};

            if (field === 'task_name') {
                if (!newValue) {
                    alert('任务名称不能为空');
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
                    alert('关键词不能为空');
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
                    // Update display based on field
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
                alert('更新失败，请重试');
                // 即使失败也重新开启定时刷新
                await refreshTasksAndRestartInterval();
            }

            input.style.display = 'none';
            display.style.display = 'inline-block';
        }, true);

        // Enter key to save
        document.addEventListener('keypress', (event) => {
            if (event.key !== 'Enter') return;
            const input = event.target;
            if (!input.classList.contains('editable-input')) return;

            isSelectingText = false;
            input.blur();
        });

        // Escape key to cancel
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
    }


    function renderScheduledJobsTable(data) {
        if (!data || !data.jobs || data.jobs.length === 0) {
            return '<p>当前没有调度中的定时任务。请在"任务管理"中启用带有 Cron 表达式的任务。</p>';
        }

        const tableHeader = `
            <thead>
                <tr>
                    <th>执行顺序</th>
                    <th>任务名称</th>
                    <th>Cron 定时</th>
                    <th>下一次执行时间</th>
                    <th>操作</th>
                </tr>
            </thead>`;

        const tableBody = data.jobs.map(job => {
            const nextRunTime = job.next_run_time
                ? new Date(job.next_run_time).toLocaleString('zh-CN', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit'
                })
                : '未知';

            return `
            <tr data-job-id="${job.job_id}" data-task-id="${job.task_id}">
                <td style="text-align: center; font-weight: bold; color: #1890ff;">${job.execution_order || '-'}</td>
                <td style="text-align: center;">${job.task_name}</td>
                <td style="text-align: center;">
                    <input type="text" class="cron-input" value="${job.cron || ''}" 
                           placeholder="分 时 日 月 周" style="width: 120px; text-align: center;">
                </td>
                <td style="text-align: center;">${nextRunTime}</td>
                <td style="text-align: center;">
                    <button class="action-btn skip-job-btn" data-job-id="${job.job_id}" style="background-color: #faad14; color: white; border: 1px solid #faad14; border-radius: 4px; padding: 4px 12px; margin-right: 5px;">跳过本次</button>
                    <button class="action-btn run-now-btn" data-job-id="${job.job_id}" style="background-color: #52c41a; color: white; border: 1px solid #52c41a; border-radius: 4px; padding: 4px 12px; margin-right: 5px;">立刻执行</button>
                    <button class="action-btn cancel-job-btn" data-task-id="${job.task_id}" style="background-color: #ff4d4f; color: white; border: 1px solid #ff4d4f; border-radius: 4px; padding: 4px 12px;">取消任务</button>
                </td>
            </tr>`;
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

        // 更新导航链接的激活状态
        navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('href') === `#${sectionId}`);
        });

        // 更新主要内容
        if (templates[sectionId]) {
            mainContent.innerHTML = templates[sectionId]();
            // 使新内容可见
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
                    // 如果处于编辑模式，避免重新渲染以避免丢失用户输入
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
            } else if (sectionId === 'scheduled') {
                await initializeScheduledView();
            } else if (sectionId === 'accounts') {
                await initializeAccountsView();
            }

        } else {
            mainContent.innerHTML = '<section class="content-section active"><h2>页面未找到</h2></section>';
        }
    }

    async function initializeScheduledView() {
        const container = document.getElementById('scheduled-table-container');
        const refreshBtn = document.getElementById('refresh-scheduled-btn');

        const refreshScheduledJobs = async () => {
            const data = await fetchScheduledJobs();
            if (container) {
                container.innerHTML = renderScheduledJobsTable(data);
                attachScheduledEventListeners();
            }
        };

        const attachScheduledEventListeners = () => {
            // Cron 输入框失去焦点时保存
            container.querySelectorAll('.cron-input').forEach(input => {
                let isSelectingText = false;
                let originalValue = input.value;

                // Track when text selection starts
                input.addEventListener('mousedown', () => {
                    isSelectingText = true;
                    originalValue = input.value;
                });

                // Track when text selection ends (on document to catch edge cases)
                const handleMouseUp = () => {
                    // Delay reset to allow blur to check the flag first
                    setTimeout(() => {
                        isSelectingText = false;
                    }, 50);
                };
                document.addEventListener('mouseup', handleMouseUp);

                input.addEventListener('blur', async (e) => {
                    // If user was selecting text and mouse went outside, refocus
                    if (isSelectingText) {
                        e.preventDefault();
                        // Refocus the input to restore editing state
                        setTimeout(() => {
                            input.focus();
                        }, 10);
                        return;
                    }

                    const row = e.target.closest('tr');
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
                        isSelectingText = false; // Allow blur to save
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
    async function initializeAccountsView() {
        const container = document.getElementById('accounts-table-container');
        const addBtn = document.getElementById('add-account-btn');

        const refreshAccounts = async () => {
            const accounts = await fetchAccounts();
            if (container) {
                container.innerHTML = renderAccountsTable(accounts);
                attachAccountEventListeners();
            }
        };

        const attachAccountEventListeners = () => {
            // 激活账号按钮
            container.querySelectorAll('.activate-account-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;
                    if (confirm(`确定要激活账号 "${name}" 吗？`)) {
                        const result = await activateAccount(name);
                        if (result) {
                            await refreshAccounts();
                        }
                    }
                });
            });

            // 编辑账号按钮
            container.querySelectorAll('.edit-account-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;
                    const account = await fetchAccountDetail(name);
                    if (account) {
                        openEditAccountModal(account);
                    }
                });
            });

            // 删除账号按钮
            container.querySelectorAll('.delete-account-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;
                    const displayName = btn.dataset.displayName;
                    if (confirm(`确定要删除账号 "${displayName}" 吗？此操作不可恢复！`)) {
                        const result = await deleteAccount(name);
                        if (result) {
                            await refreshAccounts();
                        }
                    }
                });
            });

            // 查看风控历史按钮
            container.querySelectorAll('.view-history-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;
                    const account = await fetchAccountDetail(name);
                    if (account) {
                        openAccountHistoryModal(account);
                    }
                });
            });

            // 测试Cookie按钮
            container.querySelectorAll('.test-account-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;
                    btn.disabled = true;
                    btn.textContent = '测试中...';

                    // 更新状态列为检测中
                    const statusCell = container.querySelector(`.cookie-status-cell[data-name="${name}"]`);
                    if (statusCell) {
                        statusCell.innerHTML = '<span class="status-badge" style="background:#faad14;">检测中</span>';
                    }

                    try {
                        const response = await fetch(`/api/accounts/${name}/test`, { method: 'POST' });
                        const result = await response.json();

                        // 更新状态列
                        if (statusCell) {
                            if (response.ok && result.valid) {
                                statusCell.innerHTML = '<span class="status-badge status-ok" style="background:#52c41a;">有效</span>';
                                alert(`✓ Cookie有效！账号 "${name}" 可正常使用`);
                            } else {
                                statusCell.innerHTML = '<span class="status-badge status-error" style="background:#ff4d4f;">已过期</span>';
                                alert(`✗ Cookie无效或已过期\n${result.message || '请更新Cookie'}`);
                            }
                        }
                    } catch (error) {
                        if (statusCell) {
                            statusCell.innerHTML = '<span class="status-badge" style="background:#999;">检测失败</span>';
                        }
                        alert(`测试失败: ${error.message}`);
                    } finally {
                        btn.disabled = false;
                        btn.textContent = '测试';
                    }
                });
            });

            // 复制账号按钮（创建副本，自动命名）
            container.querySelectorAll('.copy-account-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.name;

                    btn.disabled = true;
                    btn.textContent = '复制中...';
                    try {
                        const response = await fetch(`/api/accounts/${name}/duplicate`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({})  // 不传new_name，后端自动生成
                        });

                        if (response.ok) {
                            await refreshAccounts();
                        } else {
                            const result = await response.json();
                            alert(`复制失败: ${result.detail || '未知错误'}`);
                        }
                    } catch (error) {
                        alert(`复制失败: ${error.message}`);
                    } finally {
                        btn.disabled = false;
                        btn.textContent = '复制';
                    }
                });
            });
        };

        // 打开手动添加账号模态框（复用login-state-modal）
        if (addBtn) {
            console.log('Account add button found, binding click event');
            addBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Add account button clicked');

                const modal = document.getElementById('login-state-modal');
                const form = document.getElementById('login-state-form');
                const saveBtn = document.getElementById('save-login-state-btn');
                const cancelBtn = document.getElementById('cancel-login-state-btn');
                const closeBtn = document.getElementById('close-login-state-modal-btn');
                const accountNameInput = document.getElementById('account-name-input');
                const stateContentTextarea = document.getElementById('login-state-content');

                if (!modal) {
                    alert('无法找到添加账号模态框');
                    return;
                }

                // 清空表单
                if (form) form.reset();

                // 显示模态框
                modal.style.display = 'flex';
                setTimeout(() => modal.classList.add('visible'), 10);

                const closeModal = () => {
                    modal.classList.remove('visible');
                    setTimeout(() => { modal.style.display = 'none'; }, 300);
                };

                // 保存账号
                const handleSave = async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const accountName = accountNameInput?.value?.trim();
                    const stateContent = stateContentTextarea?.value?.trim();

                    if (!accountName) {
                        alert('请输入账号名称');
                        accountNameInput?.focus();
                        return;
                    }

                    if (!stateContent) {
                        alert('请粘贴Cookie JSON内容');
                        stateContentTextarea?.focus();
                        return;
                    }

                    // 验证JSON格式
                    try {
                        JSON.parse(stateContent);
                    } catch (e) {
                        alert('Cookie内容不是有效的JSON格式');
                        return;
                    }

                    try {
                        const response = await fetch('/api/accounts', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                name: accountName,
                                display_name: accountName,
                                state_content: stateContent
                            })
                        });

                        if (response.ok) {
                            closeModal();
                            await refreshAccounts();
                        } else {
                            const result = await response.json();
                            alert(`添加失败: ${result.detail || '未知错误'}`);
                        }
                    } catch (error) {
                        alert(`添加失败: ${error.message}`);
                    }
                };

                saveBtn?.addEventListener('click', handleSave);
                cancelBtn?.addEventListener('click', closeModal);
                closeBtn?.addEventListener('click', closeModal);
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) closeModal();
                });

                // 聚焦到账号名称输入框
                accountNameInput?.focus();
            });
        } else {
            console.error('Add account button not found');
        }

        // 自动获取账号按钮（原从当前登录导入）
        const importBtn = document.getElementById('import-from-login-btn');
        if (importBtn) {
            importBtn.addEventListener('click', async () => {
                // 显示自动登录确认模态框
                const confirmModal = document.getElementById('manual-login-confirm-modal');
                if (!confirmModal) {
                    alert('无法找到登录确认模态框');
                    return;
                }

                confirmModal.style.display = 'flex';
                setTimeout(() => confirmModal.classList.add('visible'), 10);

                const confirmBtn = document.getElementById('confirm-manual-login-confirm-btn');
                const cancelBtn = document.getElementById('cancel-manual-login-confirm-btn');
                const closeBtn = document.getElementById('close-manual-login-confirm-modal');

                const closeModal = () => {
                    confirmModal.classList.remove('visible');
                    setTimeout(() => { confirmModal.style.display = 'none'; }, 300);
                };

                const handleConfirmation = async () => {
                    try {
                        // 启动自动登录
                        const response = await fetch('/api/manual-login', { method: 'POST' });
                        if (!response.ok) {
                            const errorData = await response.json();
                            alert('启动失败: ' + (errorData.detail || '未知错误'));
                            closeModal();
                            return;
                        }

                        // 轮询检查登录状态（检查 state 目录下是否有新生成的账号文件）
                        const pollInterval = 2000;
                        const pollTimeout = 300000;
                        let pollAttempts = 0;
                        const maxAttempts = pollTimeout / pollInterval;
                        let initialAccountCount = 0;

                        // 获取初始账号数量
                        const initialAccounts = await fetchAccounts();
                        initialAccountCount = initialAccounts.length;

                        const intervalId = setInterval(async () => {
                            pollAttempts++;
                            try {
                                // 检查账号数量是否增加
                                const currentAccounts = await fetchAccounts();
                                if (currentAccounts.length > initialAccountCount) {
                                    clearInterval(intervalId);
                                    console.log('检测到新账号生成，刷新账号列表');
                                    await refreshAccounts();
                                    await refreshLoginStatusWidget();
                                    return;
                                }
                            } catch (error) {
                                console.error('轮询检查登录状态时出错:', error);
                            }
                            if (pollAttempts >= maxAttempts) {
                                console.log('轮询检查登录状态超时');
                                clearInterval(intervalId);
                            }
                        }, pollInterval);

                    } catch (error) {
                        alert('启动失败: ' + error.message);
                    } finally {
                        closeModal();
                    }
                };

                confirmBtn.addEventListener('click', handleConfirmation, { once: true });
                cancelBtn.addEventListener('click', closeModal, { once: true });
                closeBtn.addEventListener('click', closeModal, { once: true });
                confirmModal.addEventListener('click', (e) => {
                    if (e.target === confirmModal) closeModal();
                }, { once: true });
            });
        }

        await refreshAccounts();

        // 定时自动检测Cookie状态（每5分钟）
        const COOKIE_CHECK_INTERVAL = 5 * 60 * 1000; // 5分钟
        let cookieCheckTimer = null;

        const checkAllCookieStatus = async () => {
            console.log('正在自动检测所有账号Cookie状态...');
            const accounts = await fetchAccounts();
            if (!accounts || accounts.length === 0) return;

            for (const account of accounts) {
                try {
                    const response = await fetch(`/api/accounts/${account.name}/test`, { method: 'POST' });
                    const result = await response.json();

                    // 更新状态列显示
                    const statusCell = container?.querySelector(`.cookie-status-cell[data-name="${account.name}"]`);
                    if (statusCell) {
                        if (response.ok && result.valid) {
                            statusCell.innerHTML = '<span class="status-badge status-ok" style="background:#52c41a;">有效</span>';
                        } else {
                            statusCell.innerHTML = '<span class="status-badge status-error" style="background:#ff4d4f;">已过期</span>';
                        }
                    }
                } catch (error) {
                    console.error(`检测账号 ${account.name} Cookie状态失败:`, error);
                }
            }
            console.log('Cookie状态检测完成');
        };

        // 页面加载时立即检测一次
        checkAllCookieStatus();

        // 启动定时检测
        cookieCheckTimer = setInterval(checkAllCookieStatus, COOKIE_CHECK_INTERVAL);

        // 页面卸载时清除定时器
        window.addEventListener('beforeunload', () => {
            if (cookieCheckTimer) clearInterval(cookieCheckTimer);
        });

        // 设置模态框事件监听
        setupAccountModals(refreshAccounts);
    }

    // 账号颜色生成 - 基于账号名生成固定颜色
    const ACCOUNT_COLORS = [
        '#1890ff', '#52c41a', '#722ed1', '#eb2f96', '#fa8c16',
        '#13c2c2', '#2f54eb', '#a0d911', '#f5222d', '#faad14'
    ];

    function getAccountColor(accountName) {
        if (!accountName) return '#999';
        let hash = 0;
        for (let i = 0; i < accountName.length; i++) {
            hash = accountName.charCodeAt(i) + ((hash << 5) - hash);
        }
        return ACCOUNT_COLORS[Math.abs(hash) % ACCOUNT_COLORS.length];
    }

    // 别名函数，用于任务表格渲染
    function getAccountColorByName(accountName) {
        return getAccountColor(accountName);
    }

    function renderAccountColorTag(displayName, accountName) {
        const color = getAccountColor(accountName);
        return `<span class="account-color-tag" style="background-color: ${color};">${displayName}</span>`;
    }

    function renderAccountsTable(accounts) {
        if (!accounts || accounts.length === 0) {
            return `
                <div class="empty-state">
                    <p>暂无账号，请点击上方按钮添加新账号。</p>
                    <p class="form-hint">账号Cookie可通过浏览器扩展获取，或使用自动获取功能。</p>
                </div>`;
        }

        let html = `<table class="data-table accounts-table">
            <thead>
                <tr>
                    <th>账号名称</th>
                    <th>状态</th>
                    <th>最后使用</th>
                    <th>风控次数</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>`;

        accounts.forEach(account => {
            const lastUsed = account.last_used_at
                ? new Date(account.last_used_at).toLocaleString('zh-CN')
                : '未使用';
            const riskClass = account.risk_control_count > 0 ? 'risk-warning' : '';
            const colorTag = renderAccountColorTag(account.display_name, account.name);

            // 状态显示
            let statusHtml;
            if (account.cookie_status === 'valid') {
                statusHtml = '<span class="status-badge status-ok" style="background:#52c41a;">有效</span>';
            } else if (account.cookie_status === 'expired') {
                statusHtml = '<span class="status-badge status-error" style="background:#ff4d4f;">已过期</span>';
            } else if (account.cookie_status === 'checking') {
                statusHtml = '<span class="status-badge" style="background:#faad14;">检测中</span>';
            } else {
                statusHtml = '<span class="status-badge" style="background:#999;">未检测</span>';
            }

            html += `
                <tr data-account-name="${account.name}">
            <td class="account-name-cell" style="text-align: center; justify-content: center;">${colorTag}</td>
            <td class="cookie-status-cell" data-name="${account.name}" style="text-align: center;">${statusHtml}</td>
            <td style="text-align: center;">${lastUsed}</td>
            <td class="${riskClass}" style="text-align: center;">
                        ${account.risk_control_count > 0
                    ? `<span class="risk-count">${account.risk_control_count}</span>
                               <button class="control-button small-btn view-history-btn" data-name="${account.name}">查看</button>`
                    : '<span class="no-risk">0</span>'
                }
                    </td>
                    <td class="action-buttons">
                        <button class="control-button small-btn test-account-btn" data-name="${account.name}" title="测试Cookie是否有效">测试</button>
                        <div class="dropdown-container">
                            <button class="dropdown-btn small-btn">操作 ▾</button>
                            <div class="dropdown-menu">
                                <button class="dropdown-item copy-account-btn" data-name="${account.name}">📋 复制</button>
                                <button class="dropdown-item edit-account-btn" data-name="${account.name}">✏️ 编辑</button>
                                <button class="dropdown-item delete-account-btn" data-name="${account.name}" data-display-name="${account.display_name}">🗑️ 删除</button>
                            </div>
                        </div>
                    </td>
                </tr>`;
        });

        html += `</tbody></table>`;
        return html;
    }

    function openAddAccountModal() {
        console.log('openAddAccountModal called');
        const modal = document.getElementById('add-account-modal');
        const form = document.getElementById('add-account-form');
        console.log('Modal element:', modal);
        if (form) form.reset();
        if (modal) {
            modal.style.display = 'flex';
            modal.style.opacity = '1';
            modal.style.visibility = 'visible';
            console.log('Modal display set to flex with opacity and visibility');
        } else {
            console.error('Add account modal not found in DOM');
        }
    }

    function openEditAccountModal(account) {
        const modal = document.getElementById('edit-account-modal');
        document.getElementById('edit-account-name').value = account.name;
        document.getElementById('edit-account-display-name').value = account.display_name;
        document.getElementById('edit-account-state-content').value = '';
        if (modal) {
            modal.style.display = 'flex';
            modal.style.opacity = '1';
            modal.style.visibility = 'visible';
        }
    }

    function openAccountHistoryModal(account) {
        const modal = document.getElementById('account-history-modal');
        const content = document.getElementById('account-history-content');

        if (!account.risk_control_history || account.risk_control_history.length === 0) {
            content.innerHTML = '<p>暂无风控记录</p>';
        } else {
            let html = `<div class="history-list">`;
            account.risk_control_history.slice().reverse().forEach(record => {
                const time = new Date(record.timestamp).toLocaleString('zh-CN');
                html += `
                    <div class="history-item">
                        <div class="history-time">${time}</div>
                        <div class="history-reason">${record.reason}</div>
                        ${record.task_name ? `<div class="history-task">任务: ${record.task_name}</div>` : ''}
                    </div>`;
            });
            html += `</div>`;
            content.innerHTML = html;
        }

        if (modal) {
            modal.style.display = 'flex';
            modal.style.opacity = '1';
            modal.style.visibility = 'visible';
        }
    }

    function setupAccountModals(refreshCallback) {
        // 添加账号模态框
        const addModal = document.getElementById('add-account-modal');
        const closeAddBtn = document.getElementById('close-add-account-modal-btn');
        const cancelAddBtn = document.getElementById('cancel-add-account-btn');
        const saveNewBtn = document.getElementById('save-new-account-btn');

        const closeAddModal = () => { if (addModal) addModal.style.display = 'none'; };

        if (closeAddBtn) closeAddBtn.addEventListener('click', closeAddModal);
        if (cancelAddBtn) cancelAddBtn.addEventListener('click', closeAddModal);

        if (saveNewBtn) {
            saveNewBtn.addEventListener('click', async () => {
                const displayName = document.getElementById('account-display-name').value.trim();
                const stateContent = document.getElementById('account-state-content').value.trim();

                if (!displayName || !stateContent) {
                    alert('请填写所有必填字段');
                    return;
                }

                // 自动从显示名称生成账号标识名（去除特殊字符，添加时间戳确保唯一）
                const timestamp = Date.now().toString(36);
                const safeName = displayName.replace(/[^\w\u4e00-\u9fa5]/g, '_').substring(0, 20);
                const name = `${safeName}_${timestamp}`;

                saveNewBtn.disabled = true;
                const result = await createAccount({ name, display_name: displayName, state_content: stateContent });
                saveNewBtn.disabled = false;

                if (result) {
                    closeAddModal();
                    await refreshCallback();
                }
            });
        }

        // 编辑账号模态框
        const editModal = document.getElementById('edit-account-modal');
        const closeEditBtn = document.getElementById('close-edit-account-modal-btn');
        const cancelEditBtn = document.getElementById('cancel-edit-account-btn');
        const saveEditBtn = document.getElementById('save-edit-account-btn');

        const closeEditModal = () => { if (editModal) editModal.style.display = 'none'; };

        if (closeEditBtn) closeEditBtn.addEventListener('click', closeEditModal);
        if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeEditModal);

        if (saveEditBtn) {
            saveEditBtn.addEventListener('click', async () => {
                const name = document.getElementById('edit-account-name').value;
                const displayName = document.getElementById('edit-account-display-name').value.trim();
                const stateContent = document.getElementById('edit-account-state-content').value.trim();

                if (!displayName) {
                    alert('显示名称不能为空');
                    return;
                }

                const updateData = { display_name: displayName };
                if (stateContent) {
                    updateData.state_content = stateContent;
                }

                saveEditBtn.disabled = true;
                const result = await updateAccount(name, updateData);
                saveEditBtn.disabled = false;

                if (result) {
                    closeEditModal();
                    await refreshCallback();
                }
            });
        }

        // 风控历史模态框
        const historyModal = document.getElementById('account-history-modal');
        const closeHistoryBtn = document.getElementById('close-account-history-modal-btn');

        if (closeHistoryBtn) {
            closeHistoryBtn.addEventListener('click', () => {
                if (historyModal) historyModal.style.display = 'none';
            });
        }
    }

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

            // 更新AI标准筛选，优化显示内容，仅保留核心信息
            aiCriteriaFilter.innerHTML = '<option value="all">所有AI标准</option>' + aiCriterias.map(criteria => {
                // 移除前缀和后缀，仅保留核心信息
                const displayText = criteria
                    .replace(/^criteria\//i, '') // 移除前缀
                    .replace(/_criteria\.txt$/i, '') // 移除后缀
                    .replace(/^prompts\/(.*?)_criteria\.txt$/i, '$1'); // 处理旧路径

                return `<option value="${criteria}">${displayText}</option>`;
            }).join('');
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

            // 确定要选择的文件。如果没有存储任何内容，则默认选择 "所有结果"。
            let fileToSelect = 'all';
            // 如果有上次选择的文件且不是 "all"，则使用它
            if (lastSelectedFile && lastSelectedFile !== 'all' && fileData.files.includes(lastSelectedFile)) {
                fileToSelect = lastSelectedFile;
            }

            // Add "所有结果" option
            const options = ['<option value="all" ' + (fileToSelect === 'all' ? 'selected' : '') + '>所有结果</option>'].concat(
                fileData.files.map(f => {
                    // 优化显示内容，仅保留核心文件名
                    const displayText = f
                        .replace(/_full_data\.jsonl$/i, '') // 移除_full_data.jsonl后缀
                        .replace(/_full_data\.json$/i, '') // 移除_full_data.json后缀
                        .replace(/\.jsonl$/i, '') // 移除.jsonl后缀
                        .replace(/\.json$/i, ''); // 移除.json后缀
                    return `<option value="${f}" ${f === fileToSelect ? 'selected' : ''}>${displayText}</option>`;
                })
            );
            selector.innerHTML = options.join('');

            // 选择器的值现在已通过'selected'属性正确设置。
            // 我们可以继续添加监听器并执行初始请求。

            // 为所有筛选器添加事件监听器
            selector.addEventListener('change', fetchAndRenderResults);

            // Initialize the "仅看AI推荐" button state
            checkbox.setAttribute('data-checked', 'false');

            // 直接处理复选框更改事件，因为它现在是input type="checkbox"类型
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

            // 添加现有的事件监听器
            sortBySelector.addEventListener('change', fetchAndRenderResults);
            sortOrderSelector.addEventListener('change', fetchAndRenderResults);
            refreshBtn.addEventListener('click', fetchAndRenderResults);

            // 当选择文件时启用删除按钮
            const updateDeleteButtonState = () => {
                deleteBtn.disabled = !selector.value;
            };
            selector.addEventListener('change', updateDeleteButtonState);
            // 初始化时也更新一次删除按钮状态
            updateDeleteButtonState();

            // 删除按钮功能
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
            
            // Add event listener for show password buttons in notification settings
            const toggleWxSecretButton = document.getElementById('toggle-wx-secret-visibility');
            const wxSecretInput = document.getElementById('wx-secret');
            if (toggleWxSecretButton && wxSecretInput) {
                toggleWxSecretButton.addEventListener('click', () => {
                    if (wxSecretInput.type === 'password') {
                        wxSecretInput.type = 'text';
                        toggleWxSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        wxSecretInput.type = 'password';
                        toggleWxSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }

            const toggleDingtalkSecretButton = document.getElementById('toggle-dingtalk-secret-visibility');
            const dingtalkSecretInput = document.getElementById('dingtalk-secret');
            if (toggleDingtalkSecretButton && dingtalkSecretInput) {
                toggleDingtalkSecretButton.addEventListener('click', () => {
                    if (dingtalkSecretInput.type === 'password') {
                        dingtalkSecretInput.type = 'text';
                        toggleDingtalkSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        dingtalkSecretInput.type = 'password';
                        toggleDingtalkSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }
        } else {
            notificationContainer.innerHTML = '<p>加载通知配置失败。请检查服务器是否正常运行。</p>';
        }

        // Function to save notification settings
        async function saveNotificationSettingsNow() {
            const notificationForm = document.getElementById('notification-settings-form');
            if (!notificationForm) return;

            // Collect form data
            const formData = new FormData(notificationForm);
            const settings = {};

            // Handle regular inputs
            for (let [key, value] of formData.entries()) {
                if (key.startsWith('PCURL_TO_MOBILE') || key.startsWith('NOTIFY_AFTER_TASK_COMPLETE') ||
                    key.endsWith('_ENABLED')) {
                    settings[key] = value === 'on';
                } else {
                    settings[key] = value || '';
                }
            }

            // Handle notify after task complete checkbox if it's not in FormData
            const notifyAfterTaskCompleteCheckbox = document.getElementById('notify-after-task-complete');
            if (notifyAfterTaskCompleteCheckbox) {
                settings.NOTIFY_AFTER_TASK_COMPLETE = notifyAfterTaskCompleteCheckbox.checked;
            }

            // Save settings without showing alert
            await updateNotificationSettings(settings);
        }

        // Add event listener for notification settings form
        const notificationForm = document.getElementById('notification-settings-form');
        if (notificationForm) {
            // Save on form submit
            notificationForm.addEventListener('submit', async (e) => {
                e.preventDefault();

                // Collect form data for manual save button
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

                // Handle notify after task complete checkbox
                const notifyAfterTaskCompleteCheckbox = document.getElementById('notify-after-task-complete');
                settings.NOTIFY_AFTER_TASK_COMPLETE = notifyAfterTaskCompleteCheckbox.checked;

                // Save with user feedback
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

            // Save whenever any toggle switch changes
            notificationForm.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.addEventListener('change', saveNotificationSettingsNow);
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
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ channel: channel }),
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

            // Add event listener for test task completion notification buttons
            const testTaskCompletionButtons = notificationForm.querySelectorAll('.test-task-completion-btn');
            testTaskCompletionButtons.forEach(button => {
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

                    // Send test task completion notification
                    const channel = button.dataset.channel;
                    const originalText = button.textContent;
                    button.disabled = true;
                    button.textContent = '测试中...';

                    try {
                        const response = await fetch('/api/notifications/test-task-completion', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ channel: channel }),
                        });

                        if (response.ok) {
                            const result = await response.json();
                            alert(result.message || '测试任务完成通知发送成功！');
                        } else {
                            const errorData = await response.json();
                            alert('测试任务完成通知发送失败: ' + (errorData.detail || '未知错误'));
                        }
                    } catch (error) {
                        alert('测试任务完成通知发送失败: ' + error.message);
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
                    <div style="position: relative;">
                        <input type="password" id="web-password" name="WEB_PASSWORD" value="${genericSettings.WEB_PASSWORD || 'admin123'}">
                        <button type="button" id="toggle-web-password-visibility" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 14px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                    </div>
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

        // Function to save generic settings
        async function saveGenericSettingsNow() {
            const genericForm = document.getElementById('generic-settings-form');
            if (!genericForm) return;

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

            // Handle other inputs that are relevant
            settings.SERVER_PORT = parseInt(formData.get('SERVER_PORT'));
            settings.WEB_USERNAME = formData.get('WEB_USERNAME');
            settings.WEB_PASSWORD = formData.get('WEB_PASSWORD');

            // Save settings
            try {
                await fetch('/api/settings/generic', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings),
                });
            } catch (error) {
                console.error('自动保存失败:', error);
            }
        }

        // Add event listener for generic settings form
        const genericForm = document.getElementById('generic-settings-form');
        if (genericForm) {
            // Save on form submit
            genericForm.addEventListener('submit', async (e) => {
                e.preventDefault();

                // Collect form data for manual save button
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

                // Save with user feedback
                const saveBtn = genericForm.querySelector('button[type="submit"]');
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';

                try {
                    const response = await fetch('/api/settings/generic', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
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

            // Save whenever any toggle switch changes
            genericForm.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.addEventListener('change', saveGenericSettingsNow);
            });

            // Add event listener for show password buttons
            const toggleWebPasswordButton = document.getElementById('toggle-web-password-visibility');
            const webPasswordInput = document.getElementById('web-password');
            if (toggleWebPasswordButton && webPasswordInput) {
                toggleWebPasswordButton.addEventListener('click', () => {
                    if (webPasswordInput.type === 'password') {
                        webPasswordInput.type = 'text';
                        toggleWebPasswordButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        webPasswordInput.type = 'password';
                        toggleWebPasswordButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }

            const toggleWxSecretButton = document.getElementById('toggle-wx-secret-visibility');
            const wxSecretInput = document.getElementById('wx-secret');
            if (toggleWxSecretButton && wxSecretInput) {
                toggleWxSecretButton.addEventListener('click', () => {
                    if (wxSecretInput.type === 'password') {
                        wxSecretInput.type = 'text';
                        toggleWxSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        wxSecretInput.type = 'password';
                        toggleWxSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }

            const toggleDingtalkSecretButton = document.getElementById('toggle-dingtalk-secret-visibility');
            const dingtalkSecretInput = document.getElementById('dingtalk-secret');
            if (toggleDingtalkSecretButton && dingtalkSecretInput) {
                toggleDingtalkSecretButton.addEventListener('click', () => {
                    if (dingtalkSecretInput.type === 'password') {
                        dingtalkSecretInput.type = 'text';
                        toggleDingtalkSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        dingtalkSecretInput.type = 'password';
                        toggleDingtalkSecretButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }

            const toggleOpenaiApiKeyButton = document.getElementById('toggle-openai-api-key-visibility');
            const openaiApiKeyInput = document.getElementById('openai-api-key');
            if (toggleOpenaiApiKeyButton && openaiApiKeyInput) {
                toggleOpenaiApiKeyButton.addEventListener('click', () => {
                    if (openaiApiKeyInput.type === 'password') {
                        openaiApiKeyInput.type = 'text';
                        toggleOpenaiApiKeyButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        openaiApiKeyInput.type = 'password';
                        toggleOpenaiApiKeyButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }
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
            
            // Add event listener for show password button in AI settings
            const toggleOpenaiApiKeyButton = document.getElementById('toggle-openai-api-key-visibility');
            const openaiApiKeyInput = document.getElementById('openai-api-key');
            if (toggleOpenaiApiKeyButton && openaiApiKeyInput) {
                toggleOpenaiApiKeyButton.addEventListener('click', () => {
                    if (openaiApiKeyInput.type === 'password') {
                        openaiApiKeyInput.type = 'text';
                        toggleOpenaiApiKeyButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                <line x1="1" y1="1" x2="23" y2="23"></line>
                            </svg>
                        `;
                    } else {
                        openaiApiKeyInput.type = 'password';
                        toggleOpenaiApiKeyButton.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        `;
                    }
                });
            }
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
        link.addEventListener('click', function (e) {
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
            // 获取商品ID唯一标识
            const itemId = card.dataset.itemId;

            if (confirm('你确定要删除此商品吗？')) {
                // 实现API调用删除商品
                const selector = document.getElementById('result-file-selector');
                const selectedFile = selector.value;

                if (selectedFile) {
                    // 创建包含唯一标识的商品数据
                    const itemData = {
                        商品信息: {
                            商品链接: `id=${itemId}` // 使用商品ID构造一个简约的查找条件
                        }
                    };

                    // 调用API删除商品，传递唯一标识符
                    fetch(`/api/results/delete`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            filename: selectedFile,
                            item: itemData
                        })
                    })
                        .then(response => {
                            if (response.ok) {
                                // 删除成功，从DOM中移除卡片
                                card.remove();
                            } else {
                                throw new Error('删除失败');
                            }
                        })
                        .catch(error => {
                            console.error('删除商品时出错:', error);
                            alert('删除失败，请重试');
                        });
                } else {
                    // 没有找到文件或索引，直接从DOM删除但不通知API
                    card.remove();
                }
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
            openEditTaskModal(taskData, taskId);
        } else if (button.matches('.delete-btn')) {
            const taskName = row.querySelector('td:nth-child(2)').innerText.trim();
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
                await updateTask(taskId, { enabled: isEnabled });
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
                loadAccountSelector(); // 加载账号选择器
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

        // Function to load account selector options
        async function loadAccountSelector() {
            try {
                const selector = document.getElementById('bound-account');
                if (!selector) return;

                const accounts = await fetchAccounts();

                // Clear existing options except the first default option
                selector.innerHTML = '<option value="">不限（使用默认登录状态）</option>';

                if (accounts && accounts.length > 0) {
                    accounts.forEach(account => {
                        const option = document.createElement('option');
                        option.value = account.name;
                        option.textContent = account.display_name;
                        selector.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('无法加载账号列表:', error);
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
            const boundAccountSelector = document.getElementById('bound-account');
            const autoSwitchCheckbox = document.getElementById('auto-switch-on-risk');
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
                bound_account: boundAccountSelector ? boundAccountSelector.value : null,
                auto_switch_on_risk: autoSwitchCheckbox ? autoSwitchCheckbox.checked : false,
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

        // Track mousedown origin to prevent modal close when text selection ends on overlay
        let mouseDownOnOverlay = false;
        criteriaEditorModal.addEventListener('mousedown', (event) => {
            mouseDownOnOverlay = (event.target === criteriaEditorModal);
        });
        criteriaEditorModal.addEventListener('click', (event) => {
            if (event.target === criteriaEditorModal && mouseDownOnOverlay) {
                closeModal();
            }
            mouseDownOnOverlay = false;
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content }),
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
        const accountNameInput = document.getElementById('account-name-input');

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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content }),
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
            e.stopPropagation();
            
            // 判断当前模态框的用途：如果账号名称输入框可见且有值，则是添加账号，否则是更新登录状态
            const accountName = accountNameInput?.value?.trim();
            const stateContent = contentTextarea?.value?.trim();
            
            // 检查账号名称输入框是否可见（通过CSS display属性判断）
            const isAccountNameVisible = accountNameInput && accountNameInput.offsetParent !== null;
            
            if (isAccountNameVisible) {
                // 作为添加账号使用，不执行此处的逻辑，因为已经在 initializeAccountsView 中处理
                return;
            }
            
            // 作为更新登录状态使用
            if (!stateContent) {
                alert('请粘贴从浏览器获取的JSON内容。');
                return;
            }
            
            await updateLoginState(stateContent);
        });

    }

    // --- 编辑任务模态框逻辑 ---
    const editTaskModal = document.getElementById('edit-task-modal');
    if (editTaskModal) {
        const closeBtn = document.getElementById('close-edit-task-modal-btn');
        const cancelBtn = document.getElementById('cancel-edit-task-btn');
        const saveBtn = document.getElementById('save-edit-task-btn');
        const form = document.getElementById('edit-task-form');

        const closeEditTaskModal = () => {
            editTaskModal.classList.remove('visible');
            setTimeout(() => {
                editTaskModal.style.display = 'none';
                form.reset();
            }, 300);
        };

        closeBtn.addEventListener('click', closeEditTaskModal);
        cancelBtn.addEventListener('click', closeEditTaskModal);

        // Track mousedown origin to prevent modal close when text selection ends on overlay
        let mouseDownOnOverlay = false;
        editTaskModal.addEventListener('mousedown', (event) => {
            mouseDownOnOverlay = (event.target === editTaskModal);
        });
        editTaskModal.addEventListener('click', (event) => {
            // Only close if both mousedown AND click happened on the overlay
            if (event.target === editTaskModal && mouseDownOnOverlay) {
                closeEditTaskModal();
            }
            mouseDownOnOverlay = false;
        });

        // 加载账号选择器
        async function loadEditAccountSelector(selectedAccount = '') {
            try {
                const selector = document.getElementById('edit-bound-account');
                if (!selector) return;

                const accounts = await fetchAccounts();

                selector.innerHTML = '<option value="">不限（使用默认登录状态）</option>';

                if (accounts && accounts.length > 0) {
                    accounts.forEach(account => {
                        const option = document.createElement('option');
                        option.value = account.name;
                        option.textContent = account.display_name;
                        if (account.name === selectedAccount) {
                            option.selected = true;
                        }
                        selector.appendChild(option);
                    });
                }

                // 更新颜色
                updateEditAccountColor(selectedAccount);

                // 添加change事件监听
                selector.onchange = function () {
                    updateEditAccountColor(this.value);
                };
            } catch (error) {
                console.error('无法加载账号列表:', error);
            }
        }

        // 更新账号选择器边框颜色 - 复用现有的getAccountColorByName函数
        function updateEditAccountColor(accountName) {
            const selector = document.getElementById('edit-bound-account');
            if (!selector) return;

            if (accountName) {
                selector.style.borderColor = getAccountColorByName(accountName);
            } else {
                selector.style.borderColor = '#ccc';
            }
        }

        // 保存编辑
        saveBtn.addEventListener('click', async () => {
            const taskId = document.getElementById('edit-task-id').value;
            const btnText = saveBtn.querySelector('.btn-text');
            const spinner = saveBtn.querySelector('.spinner');

            const data = {
                enabled: document.getElementById('edit-task-enabled').checked,
                task_name: document.getElementById('edit-task-name').value,
                keyword: document.getElementById('edit-keyword').value,
                min_price: document.getElementById('edit-min-price').value || null,
                max_price: document.getElementById('edit-max-price').value || null,
                max_pages: parseInt(document.getElementById('edit-max-pages').value, 10) || 3,
                bound_account: document.getElementById('edit-bound-account').value || null,
                auto_switch_on_risk: document.getElementById('edit-auto-switch-on-risk').checked,
                cron: document.getElementById('edit-task-cron').value || null,
                personal_only: document.getElementById('edit-personal-only').checked,
            };

            // 保存更改不发送description字段，避免触发AI生成
            // AI生成由"新生成并保存/重新生成并保存"按钮单独处理

            // 只有当选择了参考文件时才添加到数据中（不触发生成）
            const referenceFile = document.getElementById('edit-reference-file-selector').value;
            if (referenceFile) {
                data.ai_prompt_criteria_file = referenceFile;
            }

            saveBtn.disabled = true;
            if (btnText) btnText.textContent = '保存中...';
            if (spinner) spinner.style.display = 'inline-block';

            try {
                const result = await updateTask(taskId, data);
                if (result) {
                    closeEditTaskModal();
                    // 刷新任务列表
                    const tasks = await fetchTasks();
                    document.getElementById('tasks-table-container').innerHTML = renderTasksTable(tasks);
                }
            } catch (error) {
                console.error('保存任务失败:', error);
                alert(`保存失败: ${error.message}`);
            } finally {
                saveBtn.disabled = false;
                if (btnText) btnText.textContent = '保存更改';
                if (spinner) spinner.style.display = 'none';
            }
        });

        // 全局函数：打开编辑任务模态框
        window.openEditTaskModal = async function (taskData, taskId) {
            // 填充表单
            document.getElementById('edit-task-id').value = taskId;
            document.getElementById('edit-task-enabled').checked = taskData.enabled || false;
            document.getElementById('edit-task-name').value = taskData.task_name || '';
            document.getElementById('edit-keyword').value = taskData.keyword || '';
            document.getElementById('edit-min-price').value = taskData.min_price || '';
            document.getElementById('edit-max-price').value = taskData.max_price || '';
            document.getElementById('edit-max-pages').value = taskData.max_pages || 3;
            document.getElementById('edit-auto-switch-on-risk').checked = taskData.auto_switch_on_risk || false;
            document.getElementById('edit-task-cron').value = taskData.cron || '';
            document.getElementById('edit-personal-only').checked = taskData.personal_only || false;

            // 加载账号选择器并选中当前绑定的账号
            await loadEditAccountSelector(taskData.bound_account || '');

            // 加载参考文件选择器
            await loadEditReferenceFileSelector(taskData.ai_prompt_criteria_file || '');

            // 加载当前AI标准信息
            await loadEditCriteriaInfo(taskData);

            // 显示模态框
            editTaskModal.style.display = 'flex';
            editTaskModal.style.opacity = '1';
            editTaskModal.style.visibility = 'visible';
            setTimeout(() => editTaskModal.classList.add('visible'), 10);
        };

        // 加载编辑模态框参考文件选择器
        async function loadEditReferenceFileSelector(currentFile = '') {
            const selector = document.getElementById('edit-reference-file-selector');
            if (!selector) return;

            try {
                // 获取参考文件列表 - API返回数组格式
                const response = await fetch('/api/prompts');
                if (!response.ok) throw new Error('无法获取参考文件列表');
                const files = await response.json(); // API直接返回数组

                selector.innerHTML = '<option value="">保持现有模板</option>';

                if (Array.isArray(files) && files.length > 0) {
                    files.forEach(file => {
                        const option = document.createElement('option');
                        option.value = file;
                        option.textContent = file;
                        selector.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('加载参考文件列表失败:', error);
                selector.innerHTML = '<option value="">加载失败</option>';
            }
        }

        // 加载当前AI标准信息
        async function loadEditCriteriaInfo(taskData) {
            const statusText = document.getElementById('edit-criteria-status-text');
            const descTextarea = document.getElementById('edit-task-description');
            const criteriaTextarea = document.getElementById('edit-criteria-content');
            const regenerateBtn = document.getElementById('edit-regenerate-criteria-btn');

            const criteriaFile = taskData.ai_prompt_criteria_file || '';

            if (criteriaFile) {
                const isRequirement = criteriaFile.includes('requirement');
                if (isRequirement) {
                    statusText.textContent = '待生成';
                    statusText.style.backgroundColor = '#007bff';
                    // 待生成时按钮文案和颜色（绿色）
                    if (regenerateBtn) {
                        regenerateBtn.textContent = '新生成并保存';
                        regenerateBtn.style.backgroundColor = '#52c41a';
                        regenerateBtn.style.borderColor = '#52c41a';
                    }
                } else {
                    statusText.textContent = '已生成';
                    statusText.style.backgroundColor = '#52c41a';
                    // 已生成时按钮文案和颜色（橙色）
                    if (regenerateBtn) {
                        regenerateBtn.textContent = '重新生成并保存';
                        regenerateBtn.style.backgroundColor = '#fa8c16';
                        regenerateBtn.style.borderColor = '#fa8c16';
                    }
                }
            } else {
                statusText.textContent = '未设置';
                statusText.style.backgroundColor = '#999';
                if (regenerateBtn) {
                    regenerateBtn.textContent = '新生成并保存';
                    regenerateBtn.style.backgroundColor = '#52c41a';
                    regenerateBtn.style.borderColor = '#52c41a';
                }
            }

            // 加载当前需求描述
            descTextarea.value = taskData.description || '';

            // 尝试加载criteria内容
            // criteria文件路径类似 "criteria/xxx_criteria.txt"，需要提取文件名
            if (criteriaFile && !criteriaFile.includes('requirement')) {
                try {
                    // 提取文件名部分（去掉目录前缀）
                    const filename = criteriaFile.includes('/')
                        ? criteriaFile.split('/').pop()
                        : criteriaFile;

                    // 使用 /api/criteria/{filename} 获取criteria内容
                    const response = await fetch(`/api/criteria/${encodeURIComponent(filename)}`);
                    if (response.ok) {
                        const data = await response.json();
                        criteriaTextarea.value = data.content || '(暂无内容)';
                    } else {
                        criteriaTextarea.value = '(无法加载)';
                    }
                } catch (error) {
                    console.error('加载criteria失败:', error);
                    criteriaTextarea.value = '(加载失败)';
                }
            } else {
                criteriaTextarea.value = '(尚未生成AI标准)';
            }
        }

        // Tab切换事件
        document.querySelectorAll('.edit-criteria-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;

                // 更新Tab按钮样式
                document.querySelectorAll('.edit-criteria-tab').forEach(t => {
                    t.classList.remove('active');
                    t.style.borderBottom = 'none';
                    t.style.color = '#666';
                });
                tab.classList.add('active');
                tab.style.borderBottom = '2px solid #1890ff';
                tab.style.color = '#1890ff';

                // 切换内容显示
                document.querySelectorAll('.edit-criteria-tab-content').forEach(content => {
                    content.style.display = 'none';
                });
                document.getElementById(`edit-tab-${targetTab}`).style.display = 'block';
            });
        });

        // 预览参考文件按钮事件
        const editPreviewBtn = document.getElementById('edit-preview-reference-btn');
        if (editPreviewBtn) {
            editPreviewBtn.addEventListener('click', async () => {
                const selector = document.getElementById('edit-reference-file-selector');
                const previewContainer = document.getElementById('edit-reference-preview-container');
                const previewPre = document.getElementById('edit-reference-file-preview');

                const selectedFile = selector.value;
                if (!selectedFile || selectedFile === '保持现有模板') { // Check for default option
                    alert('请先选择一个参考文件');
                    return;
                }

                try {
                    const response = await fetch(`/api/prompts/${encodeURIComponent(selectedFile)}`);
                    if (!response.ok) throw new Error('无法获取文件内容');
                    const data = await response.json();

                    previewPre.textContent = data.content || '(空文件)';
                    previewContainer.style.display = 'block';
                } catch (error) {
                    console.error('预览失败:', error);
                    previewPre.textContent = '加载失败: ' + error.message;
                    previewContainer.style.display = 'block';
                }
            });
        }

        // 重新生成AI标准按钮事件
        const editRegenerateBtn = document.getElementById('edit-regenerate-criteria-btn');
        if (editRegenerateBtn) {
            editRegenerateBtn.addEventListener('click', async () => {
                const taskId = document.getElementById('edit-task-id').value;
                if (!taskId) {
                    alert('无法获取任务ID');
                    return;
                }

                const descriptionTextarea = document.getElementById('edit-task-description');
                const description = descriptionTextarea.value.trim();

                if (!description) {
                    alert('请先填写需求描述');
                    return;
                }

                const originalBtnText = editRegenerateBtn.textContent;
                editRegenerateBtn.disabled = true;
                editRegenerateBtn.textContent = '生成中...';

                try {
                    // 使用updateTask API，携带description字段触发AI生成
                    const result = await updateTask(taskId, { description: description });

                    if (result) {
                        alert('AI标准生成已启动，请稍后刷新查看结果');

                        // 关闭模态框并刷新任务列表
                        closeEditTaskModal();
                        const tasks = await fetchTasks();
                        document.getElementById('tasks-table-container').innerHTML = renderTasksTable(tasks);
                    } else {
                        throw new Error('更新请求失败');
                    }
                } catch (error) {
                    console.error('生成失败:', error);
                    alert('生成失败: ' + error.message);
                } finally {
                    editRegenerateBtn.disabled = false;
                    editRegenerateBtn.textContent = originalBtnText;
                }
            });
        }
    }

    // 初始化任务表格账号单元格点击事件
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

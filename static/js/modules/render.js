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
                        Notification.error('启动失败: ' + (errorData.detail || '未知错误'));
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
                    Notification.error('启动失败: ' + error.message);
                } finally {
                    closeModal();
                }
            };

            if (!confirmBtn.dataset.bound) {
                confirmBtn.dataset.bound = '1';
                confirmBtn.addEventListener('click', handleConfirmation);
            }
            if (!cancelBtn.dataset.bound) {
                cancelBtn.dataset.bound = '1';
                cancelBtn.addEventListener('click', closeModal);
            }
            if (!closeBtn.dataset.bound) {
                closeBtn.dataset.bound = '1';
                closeBtn.addEventListener('click', closeModal);
            }
            if (!confirmModal.dataset.overlayBound) {
                confirmModal.dataset.overlayBound = '1';
                confirmModal.addEventListener('click', (e) => {
                    if (e.target === confirmModal) closeModal();
                });
            }
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

            const result = await Notification.confirmDelete('确定要删除当前 Cookie 吗？', '确认删除');
            if (result.isConfirmed) {
                try {
                    const response = await fetch('/api/login-state', { method: 'DELETE' });
                    if (response.ok) {
                        await refreshLoginStatusWidget();
                    } else {
                        Notification.error('删除失败');
                    }
                } catch (error) {
                    Notification.error('删除失败: ' + error.message);
                }
            }
        });
    }
}

function renderNotificationSettings(settings) {
    if (!settings) return '<p>无法加载通知设置。</p>';

    return `
            <form id="notification-settings-form">
                <div class="notification-tabs" role="tablist" aria-label="通知配置渠道"></div>
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

function setupNotificationTabs() {
    const section = document.getElementById('notifications-section');
    if (!section) return;

    const tabContainer = section.querySelector('.notification-tabs');
    const cards = Array.from(section.querySelectorAll('.notification-channel-card'));
    if (!tabContainer || cards.length === 0) return;

    tabContainer.innerHTML = '';
    const tabButtons = [];

    cards.forEach((card, index) => {
        const title = card.querySelector('h4')?.textContent?.trim() || `Tab ${index + 1}`;
        const tabId = `notification-tab-${index + 1}`;

        card.dataset.tab = tabId;
        card.classList.add('notification-tab-panel');
        card.setAttribute('role', 'tabpanel');
        card.id = tabId;

        const tabButton = document.createElement('button');
        tabButton.type = 'button';
        tabButton.className = 'notification-tab';
        tabButton.dataset.tab = tabId;
        tabButton.setAttribute('role', 'tab');
        tabButton.setAttribute('aria-controls', tabId);
        tabButton.textContent = title;

        tabContainer.appendChild(tabButton);
        tabButtons.push(tabButton);
    });

    const activateTab = (tabId) => {
        tabButtons.forEach((button) => {
            const isActive = button.dataset.tab === tabId;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
            button.tabIndex = isActive ? 0 : -1;
        });

        cards.forEach((card) => {
            const isActive = card.dataset.tab === tabId;
            card.classList.toggle('active', isActive);
            card.hidden = !isActive;
        });
    };

    if (tabButtons[0]?.dataset.tab) {
        activateTab(tabButtons[0].dataset.tab);
    }

    tabContainer.addEventListener('click', (event) => {
        const target = event.target.closest('.notification-tab');
        if (!target) return;
        activateTab(target.dataset.tab);
    });
}


function setupSettingsTabs() {
    const section = document.getElementById('settings-section');
    if (!section) return;

    const tabContainer = section.querySelector('.settings-tabs');
    const tabButtons = Array.from(section.querySelectorAll('.settings-tab'));
    const panels = Array.from(section.querySelectorAll('.settings-tab-panel'));
    if (!tabContainer || tabButtons.length === 0 || panels.length === 0) return;

    const activateTab = (tabId) => {
        tabButtons.forEach((button) => {
            const isActive = button.dataset.tab === tabId;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
            button.tabIndex = isActive ? 0 : -1;
        });

        panels.forEach((panel) => {
            const isActive = panel.dataset.tab === tabId;
            panel.classList.toggle('active', isActive);
            panel.hidden = !isActive;
        });
    };

    const defaultTab = tabButtons.find((button) => button.classList.contains('active')) || tabButtons[0];
    if (defaultTab?.dataset.tab) {
        activateTab(defaultTab.dataset.tab);
    }

    tabContainer.addEventListener('click', (event) => {
        const target = event.target.closest('.settings-tab');
        if (!target) return;
        activateTab(target.dataset.tab);
    });
}

function setupModelTabs() {
    const section = document.getElementById('model-management-section');
    if (!section) return;

    const tabContainer = section.querySelector('.settings-tabs');
    const tabButtons = Array.from(section.querySelectorAll('.settings-tab'));
    const panels = Array.from(section.querySelectorAll('.settings-tab-panel'));
    if (!tabContainer || tabButtons.length === 0 || panels.length === 0) return;

    const activateTab = (tabId) => {
        tabButtons.forEach((button) => {
            const isActive = button.dataset.tab === tabId;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
            button.tabIndex = isActive ? 0 : -1;
        });

        panels.forEach((panel) => {
            const isActive = panel.dataset.tab === tabId;
            panel.classList.toggle('active', isActive);
            panel.hidden = !isActive;
        });

        if (tabId === 'settings-tab-bayes' && typeof window.ensureBayesManagerInitialized === 'function') {
            window.ensureBayesManagerInitialized();
        }
    };

    const defaultTab = tabButtons.find((button) => button.classList.contains('active')) || tabButtons[0];
    if (defaultTab?.dataset.tab) {
        activateTab(defaultTab.dataset.tab);
    }

    tabContainer.addEventListener('click', (event) => {
        const target = event.target.closest('.settings-tab');
        if (!target) return;
        activateTab(target.dataset.tab);
    });
}


function renderAISettings(settings) {
    if (!settings) return '<p>无法加载AI设置。</p>';

    return `
            <form id="ai-settings-form">
                <div class="form-group">
                    <label for="openai-api-key">API Key<span class="required-pill">必填</span></label>
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
                    <label for="openai-base-url">API Base URL<span class="required-pill">必填</span></label>
                    <input type="text" id="openai-base-url" name="OPENAI_BASE_URL" value="${settings.OPENAI_BASE_URL || ''}" placeholder="例如: https://api.openai.com/v1/" required>
                    <p class="form-hint">AI模型的API接口地址，必须兼容OpenAI格式</p>
                </div>

                <div class="form-group">
                    <label for="openai-model-name">模型名称<span class="required-pill">必填</span></label>
                    <input type="text" id="openai-model-name" name="OPENAI_MODEL_NAME" value="${settings.OPENAI_MODEL_NAME || ''}" placeholder="例如: gemini-2.5-pro" required>
                    <p class="form-hint">你要使用的具体模型名称，必须支持图片分析</p>
                </div>

                <div class="form-group">
                    <label for="ai-max-tokens-param-name">tokens字段名<span class="required-pill">必填</span></label>
                    <input type="text" id="ai-max-tokens-param-name" name="AI_MAX_TOKENS_PARAM_NAME" value="${settings.AI_MAX_TOKENS_PARAM_NAME ?? ''}" placeholder="例如: max_tokens 或 max_completion_tokens">
                    <p class="form-hint">不同模型字段名不同（豆包常用 max_completion_tokens），留空将回退为OpenAI格式默认字段 max_tokens</p>
                </div>

                <div class="form-group">
                    <label for="ai-max-tokens-limit">输出tokens上限<span class="required-pill">必填</span></label>
                    <input type="number" id="ai-max-tokens-limit" name="AI_MAX_TOKENS_LIMIT" value="${settings.AI_MAX_TOKENS_LIMIT ?? ''}" min="1" max="200000" placeholder="例如: 20000">
                    <p class="form-hint">用于限制模型输出长度，若默认输出上限过小会导致ai标准截断影响输出效果或报错，建议根据模型实际能力填写推荐不少于10000</p>
                </div>

                <div class="form-group">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <label class="switch">
                            <input type="checkbox" id="enable-thinking" name="ENABLE_THINKING" ${settings.ENABLE_THINKING ? 'checked' : ''}>
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
                            <input type="checkbox" id="enable-response-format" name="ENABLE_RESPONSE_FORMAT" ${settings.ENABLE_RESPONSE_FORMAT ? 'checked' : ''}>
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
                            <input type="checkbox" id="ai-vision-enabled" name="AI_VISION_ENABLED" ${settings.AI_VISION_ENABLED ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">开启AI多模态输入</div>
                            <p class="form-hint" style="margin: 2px 0;">开启后将商品图片以image_url方式传入模型进行视觉评估</p>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <button type="button" id="test-ai-settings-btn" class="control-button">测试连接</button>
                    <button type="submit" class="control-button primary-btn">保存AI设置</button>
                </div>
            </form>
        `;
}

function renderProxySettings(settings) {
    if (!settings) return '<p>无法加载代理设置。</p>';

    const renderProxyToggle = (id, name, title, hint, checked) => `
            <div class="form-group">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label class="switch">
                        <input type="checkbox" id="${id}" name="${name}" ${checked ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                    <div style="flex: 1;">
                        <div style="font-weight: 500;">${title}</div>
                        <p class="form-hint" style="margin: 2px 0;">${hint}</p>
                    </div>
                </div>
            </div>
        `;

    return `
            <form id="proxy-settings-form">
                <div class="form-group">
                    <label for="proxy-url">代理地址</label>
                    <input type="text" id="proxy-url" name="PROXY_URL" value="${settings.PROXY_URL || ''}" placeholder="例如: http://127.0.0.1:7890">
                    <p class="form-hint">HTTP/S代理地址，支持 http 和 socks5 格式。不开启各模块开关时不会生效。</p>
                </div>

                ${renderProxyToggle('proxy-ai-enabled', 'PROXY_AI_ENABLED', 'AI模型走代理', '仅影响AI接口请求', settings.PROXY_AI_ENABLED)}
                ${renderProxyToggle('proxy-ntfy-enabled', 'PROXY_NTFY_ENABLED', 'ntfy走代理', '仅影响ntfy通知请求', settings.PROXY_NTFY_ENABLED)}
                ${renderProxyToggle('proxy-gotify-enabled', 'PROXY_GOTIFY_ENABLED', 'Gotify走代理', '仅影响Gotify通知请求', settings.PROXY_GOTIFY_ENABLED)}
                ${renderProxyToggle('proxy-bark-enabled', 'PROXY_BARK_ENABLED', 'Bark走代理', '仅影响Bark通知请求', settings.PROXY_BARK_ENABLED)}
                ${renderProxyToggle('proxy-wx-bot-enabled', 'PROXY_WX_BOT_ENABLED', '企业微信机器人走代理', '仅影响企业微信机器人通知请求', settings.PROXY_WX_BOT_ENABLED)}
                ${renderProxyToggle('proxy-wx-app-enabled', 'PROXY_WX_APP_ENABLED', '企业微信应用走代理', '仅影响企业微信应用API请求', settings.PROXY_WX_APP_ENABLED)}
                ${renderProxyToggle('proxy-telegram-enabled', 'PROXY_TELEGRAM_ENABLED', 'Telegram走代理', '仅影响Telegram通知请求', settings.PROXY_TELEGRAM_ENABLED)}
                ${renderProxyToggle('proxy-webhook-enabled', 'PROXY_WEBHOOK_ENABLED', 'Webhook走代理', '仅影响Webhook通知请求', settings.PROXY_WEBHOOK_ENABLED)}
                ${renderProxyToggle('proxy-dingtalk-enabled', 'PROXY_DINGTALK_ENABLED', '钉钉走代理', '仅影响钉钉机器人通知请求', settings.PROXY_DINGTALK_ENABLED)}

                <button type="submit" class="control-button primary-btn">保存代理设置</button>
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
        env.webhook_url_set ||
        env.dingtalk_webhook_set;

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
    const selectedIds = new Set(
        Array.from(document.querySelectorAll('.result-select-checkbox:checked'))
            .map(checkbox => checkbox.dataset.itemId)
            .filter(Boolean)
    );
    const tasksByName = (data.tasks || []).reduce((acc, task) => {
        if (task && task.task_name) acc[task.task_name] = task;
        return acc;
    }, {});
    const cards = data.items.map(item => {
        const info = item.商品信息 || {};
        const seller = item.卖家信息 || {};
        const ai = item.ai_analysis || {};
        const taskMeta = tasksByName[item.任务名称] || {};
        const personalOnly = item.personal_only ?? taskMeta.personal_only ?? false;
        const inspectionService = item.inspection_service ?? taskMeta.inspection_service ?? false;
        const accountAssurance = item.account_assurance ?? taskMeta.account_assurance ?? false;
        const freeShipping = item.free_shipping ?? taskMeta.free_shipping ?? false;
        const superShop = item.super_shop ?? taskMeta.super_shop ?? false;
        const brandNew = item.brand_new ?? taskMeta.brand_new ?? false;
        const strictSelected = item.strict_selected ?? taskMeta.strict_selected ?? false;
        const resale = item.resale ?? taskMeta.resale ?? false;
        const publishOption = item.new_publish_option ?? taskMeta.new_publish_option ?? '';
        const regionValue = item.region ?? taskMeta.region ?? '';

        // 新结构优先使用recommendation_level与confidence_score展示推荐结论
        const recommendedLevels = new Set(['STRONG_BUY', 'CAUTIOUS_BUY', 'CONDITIONAL_BUY']);
        const levelTextMap = {
            STRONG_BUY: '强烈推荐',
            CAUTIOUS_BUY: '谨慎推荐',
            CONDITIONAL_BUY: '有条件推荐',
            NOT_RECOMMENDED: '不推荐',
        };
        const recommendationLevel = typeof ai.recommendation_level === 'string' ? ai.recommendation_level : '';
        const levelIsRecommended = recommendationLevel ? recommendedLevels.has(recommendationLevel) : null;
        const isRecommended = levelIsRecommended !== null ? levelIsRecommended : ai.is_recommended === true;
        const recommendationClass = isRecommended ? 'recommended' : 'not-recommended';
        const confidenceScore = typeof ai.confidence_score === 'number' ? ai.confidence_score : null;
        const confidenceText = confidenceScore !== null ? confidenceScore.toFixed(2) : '';
        const levelText = recommendationLevel ? (levelTextMap[recommendationLevel] || recommendationLevel) : '';
        const recommendationText = levelText
            ? (confidenceText ? `${levelText} (${confidenceText})` : levelText)
            : (ai.is_recommended === true ? '推荐' : (ai.is_recommended === false ? '不推荐' : '待定'));

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

        const normalizeText = (value) => (typeof value === 'string' ? value.trim() : '');
        const describeCategoryScore = (score) => {
            if (typeof score !== 'number') return '';
            if (score >= 0.9) return '单一品类';
            if (score >= 0.7) return '2-3类';
            if (score > 0) return '多品类';
            return '';
        };

        const buildSellerProfileHtml = () => {
            const sellerType = ai?.criteria_analysis?.seller_type || {};
            const persona = normalizeText(sellerType.persona);
            const comment = normalizeText(sellerType.comment);
            const lines = [];

            if (persona || comment) {
                lines.push(`卖家类型: ${persona || '未知'}${comment ? `（${comment}）` : ''}`);
            }

            const register = normalizeText(seller['卖家注册时长']);
            const positiveRate = normalizeText(seller['作为卖家的好评率']);
            const sellerCreditLevel = normalizeText(seller['卖家信用等级'] || seller['卖家芝麻信用']);
            const onSale = normalizeText(seller['在售/已售商品数']);

            if (register) lines.push(`注册时长: ${register}`);
            if (positiveRate) lines.push(`卖家好评率: ${positiveRate}`);
            if (sellerCreditLevel) lines.push(`信用等级: ${sellerCreditLevel}`);
            if (onSale) lines.push(`在售/已售: ${onSale}`);

            const categoryScore = item?.ml_precalc?.bayes?.features?.category_score;
            const categoryText = describeCategoryScore(categoryScore);
            if (categoryText) lines.push(`品类集中度: ${categoryText}`);

            const displayLines = lines.filter(Boolean).slice(0, 5);
            if (!displayLines.length) return '';

            const list = displayLines.map(line => `<li>${escapeHtml(line)}</li>`).join('');
            return `<div class="seller-profile" style="margin-top:6px; font-size:12px; color:#666;">
                            <div style="font-weight:600; margin-bottom:4px;">卖家画像</div>
                            <ul style="margin:0; padding-left:16px; line-height:1.4; word-break: break-word; overflow-wrap: anywhere;">${list}</ul>
                        </div>`;
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
                recommendation_level: ai.recommendation_level,
                confidence_score: ai.confidence_score,
                recommendation_score_v2: ai.recommendation_score_v2,
                is_recommended: ai.is_recommended,
                reason: ai.reason,
                risk_tags: ai.risk_tags,
                action_required: ai.action_required
            },
            爬取时间: item.公开信息浏览时间,
            搜索关键字: item.搜索关键字,
            任务名称: item.任务名称,
            AI标准: item.AI标准
        };

        // 从商品链接中提取商品ID
        const itemId = extractItemId(info.商品链接);
        const checkedAttr = selectedIds.has(itemId) ? 'checked' : '';
        return `
            <div class="result-card" data-notification='${escapeHtml(JSON.stringify(notificationData))}' data-item-id='${escapeHtml(itemId)}'>
            <label class="result-select-box" title="选择此商品">
                <input type="checkbox" class="result-select-checkbox" data-item-id="${escapeHtml(itemId)}" ${checkedAttr}>
                <span></span>
            </label>
            <button class="delete-card-btn" title="删除此商品"></button>
                <div class="card-image">
                    <a href="${escapeHtml(info.商品链接) || '#'}" target="_blank"><img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(info.商品标题) || '商品图片'}" loading="lazy" onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuWbvueJhzwvdGV4dD48L3N2Zz4=';"></a>
                </div>
                <div class="card-content">
                <h3 class="card-title"><a href="${escapeHtml(info.商品链接) || '#'}" target="_blank" title="${escapeHtml(info.商品标题) || ''}">${highlightKeyword(escapeHtml(info.商品标题), manualKeyword) || '无标题'}</a></h3>
                    <p class="card-price">${highlightKeyword(escapeHtml(info.当前售价), manualKeyword) || '价格未知'}</p>
                    ${(() => {
                const filterTags = [];
                if (personalOnly) filterTags.push('个人闲置');
                if (inspectionService) filterTags.push('验货宝');
                if (accountAssurance) filterTags.push('验号担保');
                if (freeShipping) filterTags.push('包邮');
                if (superShop) filterTags.push('超赞鱼小铺');
                if (brandNew) filterTags.push('全新');
                if (strictSelected) filterTags.push('严选');
                if (resale) filterTags.push('转卖');
                if (publishOption) filterTags.push(publishOption);
                if (regionValue) filterTags.push(regionValue);
                if (!filterTags.length) return '';
                const tagsHtml = filterTags.map(tag => `<span class="result-filter-tag">${escapeHtml(tag)}</span>`).join('');
                return `<div class="result-filter-tags">${tagsHtml}</div>`;
            })()}
                    <div class="card-ai-summary ${recommendationClass}">
                        ${(() => {
                // 新版推荐度系统 (v2) - 优先使用
                const recScoreV2 = ai.recommendation_score_v2;
                if (recScoreV2 && typeof recScoreV2.recommendation_score === 'number') {
                    const finalScore = recScoreV2.recommendation_score;
                    const bayesianScore = recScoreV2.bayesian?.score ? (recScoreV2.bayesian.score * 100).toFixed(1) : 'N/A';
                    const visualScore = recScoreV2.visual_ai?.score ? (recScoreV2.visual_ai.score * 100).toFixed(1) : 'N/A';
                    const aiScore = recScoreV2.fusion?.ai_score ? recScoreV2.fusion.ai_score.toFixed(1) : 'N/A';

                    // 根据分数确定徽章样式
                    let scoreBadgeClass = 'score-badge-low';
                    if (finalScore >= 80) scoreBadgeClass = 'score-badge-high';
                    else if (finalScore >= 60) scoreBadgeClass = 'score-badge-medium';

                    const detailTooltip = `点击查看详细评分分解`;

                    // 准备详细数据用于模态框
                    const detailData = JSON.stringify({
                        finalScore: finalScore.toFixed(1),
                        bayesian: bayesianScore,
                        visual: visualScore,
                        ai: aiScore,
                        fusion: recScoreV2.fusion,
                        bayesianDetails: recScoreV2.bayesian,
                        visualDetails: recScoreV2.visual_ai
                    });

                    return `
                                    <strong>
                                        AI建议: ${escapeHtml(levelText || (isRecommended ? '推荐' : '不推荐'))} | 
                                        推荐度: <span class="recommendation-score ${scoreBadgeClass} clickable-score" 
                                                     title="${detailTooltip}" 
                                                     data-score-detail='${escapeHtml(detailData)}'
                                                     onclick="window.showScoreDetailModal(this)">${finalScore.toFixed(1)}分</span>
                                    </strong>
                                `;
                }

                // 降级到旧版置信度显示
                return `<strong>AI建议: ${escapeHtml(recommendationText)}</strong>`;
            })()}
                        <p title="${escapeHtml(ai.reason) || ''}">原因: ${highlightKeyword(escapeHtml(ai.reason), manualKeyword) || '无分析'}</p>
                        ${buildSellerProfileHtml()}
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

function isMobileLayout() {
    return window.matchMedia("(max-width: 768px)").matches
        || window.matchMedia("(max-width: 1366px) and (hover: none) and (pointer: coarse)").matches;
}

function renderTasksTable(tasks) {
    if (!tasks || tasks.length === 0) {
        return '<p>没有找到任何任务。请点击右上角“创建新任务”来添加一个。</p>';
    }

    const isMobile = isMobileLayout();

    const tableHeader = `
            <thead>
                <tr>
                    <th></th>
                    <th>启用</th>
                    <th>任务名称</th>
                    <th>运行状态</th>
                    <th>关键词</th>
                    <th>绑定账号</th>
                    <th>价格范围</th>
                    <th>高级筛选</th>
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

        const filterTagsList = [];
        if (task.personal_only) {
            filterTagsList.push({ text: '个人闲置', active: true });
        }
        if (task.inspection_service) {
            filterTagsList.push({ text: '验货宝', active: true });
        }
        if (task.account_assurance) {
            filterTagsList.push({ text: '验号担保', active: true });
        }
        if (task.free_shipping) {
            filterTagsList.push({ text: '包邮', active: true });
        }
        if (task.super_shop) {
            filterTagsList.push({ text: '超赞鱼小铺', active: true });
        }
        if (task.brand_new) {
            filterTagsList.push({ text: '全新', active: true });
        }
        if (task.strict_selected) {
            filterTagsList.push({ text: '严选', active: true });
        }
        if (task.resale) {
            filterTagsList.push({ text: '转卖', active: true });
        }
        if (task.new_publish_option) {
            filterTagsList.push({ text: task.new_publish_option, active: true });
        }
        if (task.region) {
            filterTagsList.push({ text: task.region, active: true, title: task.region });
        }
        if (!filterTagsList.length) {
            filterTagsList.push({ text: '不限', active: false });
        }

        const filterTags = filterTagsList.map(tag => {
            const titleAttr = tag.title ? `title="${tag.title}"` : '';
            const isActive = tag.active || tag.text === '不限';
            const activeClass = isActive ? 'is-active' : '';
            return `<span class="filter-tag ${activeClass}" ${titleAttr}>${tag.text}</span>`;
        }).join('');

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



        if (isMobile) {
            return `
                <div class="task-card" data-task-id="${task.id}" data-task='${JSON.stringify(task)}'>
                    <div class="task-card-header">
                        <div class="task-title">${task.task_name}</div>
                        <div class="task-status">${statusBadge}</div>
                        <label class="switch">
                            <input type="checkbox" class="task-enabled-toggle" ${task.enabled ? 'checked' : ''} ${isEditDisabled ? 'disabled' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                    <div class="task-card-body">
                        <div class="task-row"><span>关键词</span><span>${task.keyword}</span></div>
                        <div class="task-row"><span>价格</span><span>${task.min_price || '不限'} - ${task.max_price || '不限'}</span></div>
                        <div class="task-row">
                            <span>账号</span>
                            <span class="task-account-info">
                                <span class="account-display ${task.bound_account ? 'has-account' : 'no-account'}" data-field="bound_account" style="${task.bound_account ? 'background-color:' + getAccountColorByName(task.bound_account) + ';color:#fff;' : ''}">${task.bound_account || '未绑定'}</span>
                                ${task.auto_switch_on_risk ? '<span class="auto-switch-tag" title="风控自动切换">自动切换</span>' : ''}
                            </span>
                        </div>
                        <div class="task-row">
                            <span>高级筛选</span>
                            <span class="filter-tags">${filterTags}</span>
                        </div>
                        <div class="task-card-filter-panel" style="display:none;">
                            <div class="editable-advanced-panel" style="display:flex;">
                            <div class="filter-section">
                                <span class="filter-label">筛选条件</span>
                                <div class="tag-toggle-group filter-tag-toggle-group">
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-personal-only" ${task.personal_only ? 'checked' : ''}>
                                        <span>个人闲置</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-free-shipping" ${task.free_shipping ? 'checked' : ''}>
                                        <span>包邮</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-inspection-service" ${task.inspection_service ? 'checked' : ''}>
                                        <span>验货宝</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-account-assurance" ${task.account_assurance ? 'checked' : ''}>
                                        <span>验号担保</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-super-shop" ${task.super_shop ? 'checked' : ''}>
                                        <span>超赞鱼小铺</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-brand-new" ${task.brand_new ? 'checked' : ''}>
                                        <span>全新</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-strict-selected" ${task.strict_selected ? 'checked' : ''}>
                                        <span>严选</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-resale" ${task.resale ? 'checked' : ''}>
                                        <span>转卖</span>
                                    </label>
                                </div>
                            </div>
                            <div class="filter-row">
                                <div class="filter-field inline-field">
                                    <span class="filter-label">新发布时间</span>
                                    <select class="filter-publish-option">
                                        <option value="">最新</option>
                                        <option value="1天内" ${task.new_publish_option === '1天内' ? 'selected' : ''}>1天内</option>
                                        <option value="3天内" ${task.new_publish_option === '3天内' ? 'selected' : ''}>3天内</option>
                                        <option value="7天内" ${task.new_publish_option === '7天内' ? 'selected' : ''}>7天内</option>
                                        <option value="14天内" ${task.new_publish_option === '14天内' ? 'selected' : ''}>14天内</option>
                                    </select>
                                </div>
                                <div class="filter-field region-field inline-field">
                                    <span class="filter-label">区域</span>
                                    <div class="region-select-row compact">
                                        <select class="filter-region-province">
                                            <option value="">省/自治区/直辖市</option>
                                        </select>
                                        <select class="filter-region-city">
                                            <option value="">市/地区</option>
                                        </select>
                                        <select class="filter-region-district">
                                            <option value="">区/县</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="filter-actions">
                                    <button class="filter-save-btn">保存</button>
                                    <button class="filter-cancel-btn">取消</button>
                                </div>
                            </div>
                        </div>
                        <div class="task-row"><span>最大页数</span><span>${task.max_pages || 3}</span></div>
                        <div class="task-row"><span>定时</span><span>${task.cron || '未设置'}</span></div>
                    </div>
                    <div class="task-card-actions">
                        ${actionButton}
                        <div class="dropdown-container">
                            <button class="dropdown-btn" ${buttonDisabledAttr} ${buttonDisabledTitle} ${buttonDisabledStyle}>操作</button>
                            <div class="dropdown-menu">
                                <button class="dropdown-item edit-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>编辑</button>
                                <button class="dropdown-item copy-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>复制</button>
                                <button class="dropdown-item delete-btn" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>删除</button>
                            </div>
                        </div>
                    </div>
                </div>`;
        }
        return `
            <tr data-task-id="${task.id}" data-task='${JSON.stringify(task)}'>
                <td style="text-align: center;" class="drag-handle-cell">
                    <span class="drag-handle" draggable="true" title="Drag">::</span>
                </td>
                <td style="text-align: center;">
                    <label class="switch">
                        <input type="checkbox" class="task-enabled-toggle" ${task.enabled ? 'checked' : ''} ${isEditDisabled ? 'disabled' : ''}>
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
                            ${task.bound_account || '未绑定'}
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
                    <div class="editable-cell editable-advanced-filter" data-task-id="${task.id}" data-field="advanced_filters" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display filter-tags">${filterTags}</span>
                        <div class="editable-advanced-panel" style="display:none;">
                            <div class="filter-section">
                                <span class="filter-label">筛选条件</span>
                                <div class="tag-toggle-group filter-tag-toggle-group">
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-personal-only" ${task.personal_only ? 'checked' : ''}>
                                        <span>个人闲置</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-free-shipping" ${task.free_shipping ? 'checked' : ''}>
                                        <span>包邮</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-inspection-service" ${task.inspection_service ? 'checked' : ''}>
                                        <span>验货宝</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-account-assurance" ${task.account_assurance ? 'checked' : ''}>
                                        <span>验号担保</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-super-shop" ${task.super_shop ? 'checked' : ''}>
                                        <span>超赞鱼小铺</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-brand-new" ${task.brand_new ? 'checked' : ''}>
                                        <span>全新</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-strict-selected" ${task.strict_selected ? 'checked' : ''}>
                                        <span>严选</span>
                                    </label>
                                    <label class="tag-toggle">
                                        <input type="checkbox" class="filter-resale" ${task.resale ? 'checked' : ''}>
                                        <span>转卖</span>
                                    </label>
                                </div>
                            </div>
                            <div class="filter-row">
                                <div class="filter-field inline-field">
                                    <span class="filter-label">新发布时间</span>
                                    <select class="filter-publish-option">
                                        <option value="">最新</option>
                                        <option value="1天内" ${task.new_publish_option === '1天内' ? 'selected' : ''}>1天内</option>
                                        <option value="3天内" ${task.new_publish_option === '3天内' ? 'selected' : ''}>3天内</option>
                                        <option value="7天内" ${task.new_publish_option === '7天内' ? 'selected' : ''}>7天内</option>
                                        <option value="14天内" ${task.new_publish_option === '14天内' ? 'selected' : ''}>14天内</option>
                                    </select>
                                </div>
                                <div class="filter-field region-field inline-field">
                                    <span class="filter-label">区域</span>
                                    <div class="region-select-row compact">
                                        <select class="filter-region-province">
                                            <option value="">省/自治区/直辖市</option>
                                        </select>
                                        <select class="filter-region-city">
                                            <option value="">市/地区</option>
                                        </select>
                                        <select class="filter-region-district">
                                            <option value="">区/县</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="filter-actions">
                                <button class="filter-save-btn">保存</button>
                                <button class="filter-cancel-btn">取消</button>
                            </div>
                        </div>
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="editable-cell" data-task-id="${task.id}" data-field="max_pages" ${isEditDisabled ? 'style="pointer-events: none; opacity: 0.7;"' : ''}>
                        <span class="editable-display">${task.max_pages || 3}</span>
                        <input type="number" class="editable-input" value="${task.max_pages || 3}" min="1" style="display:none; width:50px;">
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="criteria">
${isGeneratingAI ? `
                            <button class="refresh-criteria danger-btn" title="正在生成AI标准" data-task-id="${task.id}" disabled style="background-color: #ccc; cursor: not-allowed;">生成中...</button>
                        ` : criteriaBtnText.toLowerCase().endsWith('requirement') || criteriaBtnText.toLowerCase().endsWith('_requirement') ? `
                            <div class="red-dot-container">
                                <button class="refresh-criteria success-btn" title="新生成AI标准" data-task-id="${task.id}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>待生成</button>
                                <span class="red-dot"></span>
                            </div>
                        ` : `
                            ${criteriaFile !== 'N/A' ? `
                                <button class="criteria-btn success-btn" title="编辑AI标准" data-task-id="${task.id}" data-criteria-file="${criteriaFile}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>
                                    ${criteriaBtnText}
                                </button>
                            ` : `
                                <button class="refresh-criteria success-btn" title="新生成AI标准" data-task-id="${task.id}" ${isEditDisabled ? 'disabled style="background-color: #ccc; cursor: not-allowed;"' : ''}>待生成</button>
                            `}
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

    if (isMobile) {
        return `<div class="task-cards">${tableBody}</div>`;
    }
    return `<table class="tasks-table">${tableHeader}<tbody>${tableBody}</tbody></table>`;
}


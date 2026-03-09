﻿// 设置视图
async function initializeSettingsView() {

    const settingsSection = document.querySelector('#settings-section');

    setupSettingsTabs();


    const statusContainer = document.getElementById('system-status-container');
    const status = await fetchSystemStatus();
    statusContainer.innerHTML = renderSystemStatus(status);
    let cachedGenericSettings = null;


    const genericContainer = document.createElement('div');
    genericContainer.className = 'settings-card';
    genericContainer.innerHTML = `
    <h3>通用配置</h3>
    <div id="generic-settings-container">
        <p>正在加载通用配置...</p>
    </div>
`;
    const genericPanel = document.getElementById('generic-settings-panel') || settingsSection;
    genericPanel.appendChild(genericContainer);


    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const genericSettingsResponse = await fetch('/api/settings/generic', {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!genericSettingsResponse.ok) {
            throw new Error(`HTTP error! status: ${genericSettingsResponse.status}`);
        }

        const genericSettings = await genericSettingsResponse.json();
        cachedGenericSettings = genericSettings;
        const genericSettingsContainer = document.getElementById('generic-settings-container');

        genericSettingsContainer.innerHTML = `
        <form id="generic-settings-form">
            <p class="form-hint" style="margin: 0 0 12px 0;">
                说明：通用配置属于全局部署参数，修改后对所有用户生效；仅管理员（admin/super_admin）可保存。
            </p>
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
                    <input type="password" id="web-password" name="WEB_PASSWORD" value="" placeholder="${genericSettings.WEB_PASSWORD_SET ? '已设置，留空不修改' : '请输入新的登录密码'}">
                    <button type="button" id="toggle-web-password-visibility" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 14px;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </button>
                </div>
                <p class="form-hint">${genericSettings.WEB_PASSWORD_SET ? '用于登录Web管理界面（已设置，留空不修改）' : '用于登录Web管理界面'}</p>
            </div>

            <button type="submit" class="control-button primary-btn">保存通用配置</button>
        </form>
    `;
    } catch (error) {
        console.error("无法加载通用配置:", error);
        const genericSettingsContainer = document.getElementById('generic-settings-container');
        genericSettingsContainer.innerHTML = '<p>加载通用配置失败。请检查服务器是否正常运行。</p>';
    }


    async function saveGenericSettingsNow() {
        const genericForm = document.getElementById('generic-settings-form');
        if (!genericForm) return;


        const formData = new FormData(genericForm);
        const settings = {};


        settings.LOGIN_IS_EDGE = formData.get('LOGIN_IS_EDGE') === 'on';
        settings.RUN_HEADLESS = formData.get('RUN_HEADLESS') === 'on';
        settings.AI_DEBUG_MODE = formData.get('AI_DEBUG_MODE') === 'on';

        settings.SERVER_PORT = parseInt(formData.get('SERVER_PORT'));
        settings.WEB_USERNAME = formData.get('WEB_USERNAME');
        settings.WEB_PASSWORD = formData.get('WEB_PASSWORD');


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


    const genericForm = document.getElementById('generic-settings-form');
    if (genericForm) {

        genericForm.addEventListener('submit', async (e) => {
            e.preventDefault();


            const formData = new FormData(genericForm);
            const settings = {};


            settings.LOGIN_IS_EDGE = formData.get('LOGIN_IS_EDGE') === 'on';
            settings.RUN_HEADLESS = formData.get('RUN_HEADLESS') === 'on';
            settings.AI_DEBUG_MODE = formData.get('AI_DEBUG_MODE') === 'on';

            settings.SERVER_PORT = parseInt(formData.get('SERVER_PORT'));
            settings.WEB_USERNAME = formData.get('WEB_USERNAME');
            settings.WEB_PASSWORD = formData.get('WEB_PASSWORD');


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
                    Notification.success('通用配置已保存！');
                } else {
                    const errorData = await response.json();
                    Notification.error('保存失败: ' + (errorData.detail || '未知错误'));
                }
            } catch (error) {
                Notification.error('保存失败: ' + error.message);
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        });


        genericForm.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', saveGenericSettingsNow);
        });


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


    const aiContainer = document.createElement('div');
    aiContainer.className = 'settings-card';
    aiContainer.innerHTML = `
        <h3>AI模型配置</h3>
        <div id="ai-settings-container">
            <p>正在加载AI配置...</p>
        </div>
    `;

    const aiPanel = document.getElementById('ai-settings-panel') || settingsSection;
    aiPanel.appendChild(aiContainer);

    const aiSettingsContainer = document.getElementById('ai-settings-container');
    const aiSettings = await fetchAISettings();
    if (aiSettings !== null) {
        let genericSettingsForAI = cachedGenericSettings;
        if (!genericSettingsForAI) {
            try {
                const response = await fetch('/api/settings/generic');
                if (response.ok) {
                    genericSettingsForAI = await response.json();
                }
            } catch (error) {
                console.error('无法获取通用配置:', error);
            }
        }
        const mergedAISettings = {
            ...aiSettings,
            ENABLE_THINKING: genericSettingsForAI?.ENABLE_THINKING,
            ENABLE_RESPONSE_FORMAT: genericSettingsForAI?.ENABLE_RESPONSE_FORMAT,
            AI_VISION_ENABLED: genericSettingsForAI?.AI_VISION_ENABLED,
        };
        aiSettingsContainer.innerHTML = renderAISettings(mergedAISettings);


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

    // 4. Render Proxy Settings（代理设置独立Tab，避免影响全局请求）
    const proxyContainer = document.createElement('div');
    proxyContainer.className = 'settings-card';
    proxyContainer.innerHTML = `
        <h3>代理设置</h3>
        <div id="proxy-settings-container">
            <p>正在加载代理设置...</p>
        </div>
    `;

    const proxyPanel = document.getElementById('proxy-settings-panel') || settingsSection;
    proxyPanel.appendChild(proxyContainer);

    const proxySettingsContainer = document.getElementById('proxy-settings-container');
    const proxySettings = await fetchProxySettings();
    if (proxySettings !== null) {
        proxySettingsContainer.innerHTML = renderProxySettings(proxySettings);
    } else {
        proxySettingsContainer.innerHTML = '<p>加载代理设置失败。请检查服务器是否正常运行。</p>';
    }

    async function saveProxySettingsNow() {
        const proxyForm = document.getElementById('proxy-settings-form');
        if (!proxyForm) return null;

        const formData = new FormData(proxyForm);
        const settings = {
            PROXY_URL: formData.get('PROXY_URL') || '',
            PROXY_AI_ENABLED: formData.get('PROXY_AI_ENABLED') === 'on',
            PROXY_NTFY_ENABLED: formData.get('PROXY_NTFY_ENABLED') === 'on',
            PROXY_GOTIFY_ENABLED: formData.get('PROXY_GOTIFY_ENABLED') === 'on',
            PROXY_BARK_ENABLED: formData.get('PROXY_BARK_ENABLED') === 'on',
            PROXY_WX_BOT_ENABLED: formData.get('PROXY_WX_BOT_ENABLED') === 'on',
            PROXY_WX_APP_ENABLED: formData.get('PROXY_WX_APP_ENABLED') === 'on',
            PROXY_TELEGRAM_ENABLED: formData.get('PROXY_TELEGRAM_ENABLED') === 'on',
            PROXY_WEBHOOK_ENABLED: formData.get('PROXY_WEBHOOK_ENABLED') === 'on',
            PROXY_DINGTALK_ENABLED: formData.get('PROXY_DINGTALK_ENABLED') === 'on',
        };

        return await updateProxySettings(settings);
    }

    const proxyForm = document.getElementById('proxy-settings-form');
    if (proxyForm) {
        proxyForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const saveBtn = proxyForm.querySelector('button[type="submit"]');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';

            const result = await saveProxySettingsNow();
            if (result) {
                Notification.success(result.message || '代理设置已保存！');
            }

            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        });

        // 代理开关变化时自动静默保存，降低遗漏风险
        proxyForm.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
            checkbox.addEventListener('change', async () => {
                await saveProxySettingsNow();
            });
        });
    }


    const legacyDatabasePanel = document.getElementById('database-settings-panel');
    if (legacyDatabasePanel) {
        await initializeDatabaseWarehousePanel(legacyDatabasePanel);
    }


    await initializeModelManagementPanels();

    const aiForm = document.getElementById('ai-settings-form');
    const applyAiSettingsToForm = (aiSettings) => {
        if (!aiForm || !aiSettings || typeof aiSettings !== 'object') return;
        const setValue = (selector, value) => {
            const element = aiForm.querySelector(selector);
            if (element) {
                element.value = value ?? '';
            }
        };
        setValue('#openai-base-url', aiSettings.OPENAI_BASE_URL || '');
        setValue('#openai-model-name', aiSettings.OPENAI_MODEL_NAME || '');
        setValue('#ai-max-tokens-param-name', aiSettings.AI_MAX_TOKENS_PARAM_NAME || '');
        setValue('#ai-max-tokens-limit', aiSettings.AI_MAX_TOKENS_LIMIT ?? '');

        const apiKeyInput = aiForm.querySelector('#openai-api-key');
        if (apiKeyInput) {
            apiKeyInput.value = '';
            if (aiSettings.OPENAI_API_KEY_SET) {
                apiKeyInput.placeholder = '已迁移或已设置，留空不修改';
            }
        }
    };
    const applyProxySettingsToForm = (proxySettings) => {
        if (!proxyForm || !proxySettings || typeof proxySettings !== 'object') return;
        const proxyUrlInput = proxyForm.querySelector('#proxy-url');
        if (proxyUrlInput) {
            proxyUrlInput.value = proxySettings.PROXY_URL || '';
        }
        const proxyKeys = [
            'PROXY_AI_ENABLED',
            'PROXY_NTFY_ENABLED',
            'PROXY_GOTIFY_ENABLED',
            'PROXY_BARK_ENABLED',
            'PROXY_WX_BOT_ENABLED',
            'PROXY_WX_APP_ENABLED',
            'PROXY_TELEGRAM_ENABLED',
            'PROXY_WEBHOOK_ENABLED',
            'PROXY_DINGTALK_ENABLED',
        ];
        proxyKeys.forEach((key) => {
            const checkbox = proxyForm.querySelector(`input[name="${key}"]`);
            if (checkbox) {
                checkbox.checked = Boolean(proxySettings[key]);
            }
        });
    };
    const aiGenericToggleKeys = new Set([
        'ENABLE_THINKING',
        'ENABLE_RESPONSE_FORMAT',
        'AI_VISION_ENABLED'
    ]);

    const buildAiGenericToggleSettings = (formData) => ({
        ENABLE_THINKING: formData.get('ENABLE_THINKING') === 'on',
        ENABLE_RESPONSE_FORMAT: formData.get('ENABLE_RESPONSE_FORMAT') === 'on',
        AI_VISION_ENABLED: formData.get('AI_VISION_ENABLED') === 'on',
    });

    const updateAiGenericToggleSettings = async (settings) => {
        try {
            const response = await fetch('/api/settings/generic', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '更新AI通用开关失败');
            }
            return await response.json();
        } catch (error) {
            console.error('无法更新AI通用开关:', error);
            Notification.error(`错误: ${error.message}`);
            return null;
        }
    };

    const refreshSystemStatusPanel = async () => {
        const status = await fetchSystemStatus();
        const statusContainer = document.getElementById('system-status-container');
        if (statusContainer) {
            statusContainer.innerHTML = renderSystemStatus(status);
        }
    };

    const buildAiHealthSummaryLines = (health) => {
        if (!health || typeof health !== 'object') {
            return ['AI可用性检测失败：未获取到有效结果。'];
        }

        const lines = [];
        const overallLabel = health.overall_label || '未知';
        const overallMessage = health.overall_message || '';
        const sourceLabel = health.source_label || '未知来源';
        const checkedAt = health.checked_at || '未检测';
        const webTest = health.web_test || {};
        const backendTest = health.backend_test || {};
        const vision = health.vision_capability || {};

        const formatProbe = (title, probe) => {
            const probeLevel = probe.level || 'unknown';
            const probeLevelMap = {
                ok: '成功',
                warning: '警告',
                error: '失败',
                unknown: '未检测',
            };
            const probeLabel = probeLevelMap[probeLevel] || '未知';
            const latency = probe.latency_ms ? `（${probe.latency_ms}ms）` : '';
            return `${title}：${probeLabel} - ${probe.message || '未检测'}${latency}`;
        };

        const visionLabelMap = {
            supported: '支持',
            unsupported: '不支持',
            unknown: '未知',
        };
        const visionLabel = visionLabelMap[vision.status] || '未知';

        lines.push(`AI API 可用性：${overallLabel}${overallMessage ? ` - ${overallMessage}` : ''}`);
        lines.push(`配置来源：${sourceLabel}`);
        lines.push(formatProbe('Web连通性', webTest));
        lines.push(formatProbe('后端连通性', backendTest));
        lines.push(`图像输入能力：${visionLabel}${vision.message ? ` - ${vision.message}` : ''}`);
        lines.push(`检测时间：${checkedAt}`);
        return lines;
    };

    if (aiForm) {
        aiForm.addEventListener('submit', async (e) => {
            e.preventDefault();


            const formData = new FormData(aiForm);
            const settings = {};
            const genericToggleSettings = buildAiGenericToggleSettings(formData);


            for (let [key, value] of formData.entries()) {

                const convertedKey = key.toUpperCase().replace(/-/g, '_');
                if (aiGenericToggleKeys.has(convertedKey)) {
                    continue;
                }
                settings[convertedKey] = value || '';
            }

            // tokens上限仅在填写时做数值校验，避免NaN写入配置
            const tokensLimitInput = (formData.get('AI_MAX_TOKENS_LIMIT') || '').toString().trim();
            if (tokensLimitInput !== '') {
                const tokensLimitRaw = parseInt(tokensLimitInput, 10);
                settings.AI_MAX_TOKENS_LIMIT = Number.isFinite(tokensLimitRaw) && tokensLimitRaw > 0 ? tokensLimitRaw : '';
            }


            const saveBtn = aiForm.querySelector('button[type="submit"]');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';

            const result = await updateAISettings(settings);
            if (result) {
                Notification.success(result.message || "AI设置已保存！");
                await updateAiGenericToggleSettings(genericToggleSettings);
                await checkAIHealth(
                    { check_vision: genericToggleSettings.AI_VISION_ENABLED === true },
                    { silent: true }
                );

                // 刷新系统状态检查
                await refreshSystemStatusPanel();
            }

            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        });


        const testBtn = document.getElementById('test-ai-settings-btn');
        if (testBtn) {
            testBtn.addEventListener('click', async () => {
                const formData = new FormData(aiForm);
                const settings = {};
                const genericToggleSettings = buildAiGenericToggleSettings(formData);

                for (let [key, value] of formData.entries()) {
                    if (aiGenericToggleKeys.has(key)) {
                        continue;
                    }
                    settings[key] = value || '';
                }

                // 测试时仅在填写时传递tokens上限，避免空值被强制兜底
                const tokensLimitInput = (formData.get('AI_MAX_TOKENS_LIMIT') || '').toString().trim();
                if (tokensLimitInput !== '') {
                    const tokensLimitRaw = parseInt(tokensLimitInput, 10);
                    settings.AI_MAX_TOKENS_LIMIT = Number.isFinite(tokensLimitRaw) && tokensLimitRaw > 0 ? tokensLimitRaw : '';
                }
                if (proxyForm) {
                    const proxyFormData = new FormData(proxyForm);
                    settings.PROXY_URL = proxyFormData.get('PROXY_URL') || '';
                    settings.PROXY_AI_ENABLED = proxyFormData.get('PROXY_AI_ENABLED') === 'on';
                }

                const originalText = testBtn.textContent;
                testBtn.disabled = true;
                testBtn.textContent = '测试中...';
                const results = [];

                try {
                    const saveResult = await updateAISettings(settings);
                    if (!saveResult) {
                        results.push('保存AI设置失败，无法继续执行可用性检测。');
                    } else {
                        const toggleSaveResult = await updateAiGenericToggleSettings(genericToggleSettings);
                        if (!toggleSaveResult) {
                            results.push('AI通用开关保存失败，检测结果可能不准确。');
                        }

                        if (proxyForm) {
                            const proxySaveResult = await saveProxySettingsNow();
                            if (!proxySaveResult) {
                                results.push('代理配置保存失败，检测结果可能不准确。');
                            }
                        }

                        const health = await checkAIHealth(
                            {
                                check_vision: genericToggleSettings.AI_VISION_ENABLED === true,
                                run_web: true,
                                run_backend: true,
                            },
                            { silent: true }
                        );
                        if (health) {
                            results.push(...buildAiHealthSummaryLines(health));
                        } else {
                            results.push('AI可用性检测失败：接口无响应。');
                        }
                    }
                } catch (error) {
                    results.push(`检测过程发生错误：${error.message}`);
                } finally {
                    testBtn.disabled = false;
                    testBtn.textContent = originalText;
                    await refreshSystemStatusPanel();
                }

                Notification.infoMultiline(results.join('\n'));
            });
        }

    }
}

async function initializeModelManagementView() {
    setupModelTabs();
    await initializeModelManagementPanels();

    // 检查当前是否激活了Bayes标签，如果是则主动初始化
    const bayesPanel = document.getElementById('settings-tab-bayes');
    if (bayesPanel && !bayesPanel.hidden && typeof window.ensureBayesManagerInitialized === 'function') {
        await window.ensureBayesManagerInitialized();
    }
}

async function initializeModelManagementPanels() {
    const promptSelector = document.getElementById('prompt-selector');
    const promptEditor = document.getElementById('prompt-editor');
    const savePromptBtn = document.getElementById('save-prompt-btn');


    const promptListContainer = document.querySelector('.prompt-list-container');
    if (promptSelector && promptEditor && savePromptBtn && promptListContainer) {
        const newPromptBtn = document.createElement('button');
        newPromptBtn.textContent = '新建模板';
        newPromptBtn.className = 'control-button primary-btn';
        newPromptBtn.style.marginLeft = '10px';
        promptListContainer.appendChild(newPromptBtn);


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
                Notification.warning("请先选择一个要保存的Prompt文件。");
                return;
            }

            savePromptBtn.disabled = true;
            savePromptBtn.textContent = '保存中...';

            const result = await updatePrompt(selectedFile, content);
            if (result) {
                Notification.success(result.message || "保存成功！");
            }


            savePromptBtn.disabled = false;
            savePromptBtn.textContent = '保存更改';
        });


        deletePromptBtn.addEventListener('click', async () => {
            const selectedFile = promptSelector.value;
            if (!selectedFile) {
                Notification.warning("请先选择一个要删除的Prompt文件。");
                return;
            }

            const result = await Notification.confirmDelete(`你确定要删除Prompt文件 "${selectedFile}" 吗？此操作不可恢复。`); if (!result.isConfirmed) {
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
                Notification.success(result.message || '删除成功！');


                const newPrompts = await fetchPrompts();
                promptSelector.innerHTML = '<option value="">-- 请选择 --</option>' + newPrompts.map(p => `<option value="${p}">${p}</option>`).join('');


                promptEditor.value = "请先从上方选择一个 Prompt 文件进行编辑...";
                promptEditor.disabled = true;
                savePromptBtn.disabled = true;
                deletePromptBtn.disabled = true;

            } catch (error) {
                console.error('删除Prompt失败:', error);
                Notification.error('删除失败: ' + error.message);
            } finally {
                deletePromptBtn.disabled = false;
                deletePromptBtn.textContent = '删除模板';
            }
        });


        newPromptBtn.addEventListener('click', () => {

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


            document.body.insertAdjacentHTML('beforeend', modalHTML);


            const modal = document.getElementById('new-prompt-modal');
            const closeBtn = document.getElementById('close-new-prompt-modal');
            const cancelBtn = document.getElementById('cancel-new-prompt-btn');
            const saveBtn = document.getElementById('save-new-prompt-btn');
            const form = document.getElementById('new-prompt-form');


            const closeModal = () => {
                modal.remove();
            };

            closeBtn.addEventListener('click', closeModal);
            cancelBtn.addEventListener('click', closeModal);


            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });


            saveBtn.addEventListener('click', () => {
                if (!form.checkValidity()) {
                    form.reportValidity();
                    return;
                }

                const newFileName = document.getElementById('new-prompt-name').value.trim();
                const content = document.getElementById('new-prompt-content').value;


                if (/[\\\\/:]/.test(newFileName) || newFileName.includes('..')) {
                    Notification.warning('无效的文件名');
                    return;
                }


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
                        Notification.success(data.message || '新建模板成功！');
                        closeModal();

                        return fetchPrompts();
                    })
                    .then(newPrompts => {
                        if (newPrompts) {

                            promptSelector.innerHTML = '<option value="">-- 请选择 --</option>' + newPrompts.map(p => `<option value="${p}">${p}</option>`).join('');
                        }
                    })
                    .catch(error => {
                        console.error('创建新模板失败:', error);
                        Notification.error('创建新模板失败，请稍后重试。');
                    });
            });
        });

    }

    const bayesSelector = document.getElementById('bayes-selector');
    const bayesEditor = document.getElementById('bayes-editor');
    const saveBayesBtn = document.getElementById('save-bayes-btn');
    const bayesListContainer = document.querySelector('.bayes-list-container');

    if (bayesSelector && bayesEditor && saveBayesBtn && bayesListContainer) {
        const newBayesBtn = document.createElement('button');
        newBayesBtn.textContent = '新建模板';
        newBayesBtn.className = 'control-button primary-btn';
        newBayesBtn.style.marginLeft = '10px';
        bayesListContainer.appendChild(newBayesBtn);

        const deleteBayesBtn = document.createElement('button');
        deleteBayesBtn.textContent = '删除模板';
        deleteBayesBtn.className = 'control-button danger-btn';
        deleteBayesBtn.style.marginLeft = '10px';
        deleteBayesBtn.style.backgroundColor = 'red';
        deleteBayesBtn.style.color = 'white';
        deleteBayesBtn.style.borderColor = 'red';
        deleteBayesBtn.disabled = true;
        bayesListContainer.appendChild(deleteBayesBtn);

        const bayesGuideContent = document.getElementById('bayes-guide-content');
        const loadBayesGuide = async () => {
            if (!bayesGuideContent) return;
            bayesGuideContent.textContent = '正在加载指引...';
            const guideData = await fetchBayesGuide();
            if (guideData && guideData.content) {
                bayesGuideContent.textContent = guideData.content;
            } else {
                bayesGuideContent.textContent = '加载指引失败，请检查 prompts/guide/bayes_guide.md';
            }
        };

        const refreshBayesList = async () => {
            const profiles = await fetchBayesProfiles();
            if (profiles && profiles.length > 0) {
                bayesSelector.innerHTML = '<option value="">-- 请选择 --</option>' + profiles.map(p => `<option value="${p}">${p}</option>`).join('');
            } else if (profiles && profiles.length === 0) {
                bayesSelector.innerHTML = '<option value="">没有找到Bayes文件</option>';
            } else {
                bayesSelector.innerHTML = '<option value="">加载Bayes文件列表失败</option>';
            }
        };

        await refreshBayesList();

        await loadBayesGuide();

        bayesSelector.addEventListener('change', async () => {
            const selectedFile = bayesSelector.value;
            if (selectedFile) {
                bayesEditor.value = "正在加载...";
                bayesEditor.disabled = true;
                saveBayesBtn.disabled = true;
                deleteBayesBtn.disabled = true;
                const data = await fetchBayesContent(selectedFile);
                if (data) {
                    bayesEditor.value = data.content;
                    bayesEditor.disabled = false;
                    saveBayesBtn.disabled = false;
                    deleteBayesBtn.disabled = false;
                } else {
                    bayesEditor.value = `加载文件 ${selectedFile} 失败。`;
                }
            } else {
                bayesEditor.value = "请先从上方选择一个 Bayes 文件进行编辑...";
                bayesEditor.disabled = true;
                saveBayesBtn.disabled = true;
                deleteBayesBtn.disabled = true;
            }
        });

        saveBayesBtn.addEventListener('click', async () => {
            const selectedFile = bayesSelector.value;
            const content = bayesEditor.value;
            if (!selectedFile) {
                Notification.warning("请先选择一个要保存的Bayes文件。");
                return;
            }
            saveBayesBtn.disabled = true;
            saveBayesBtn.textContent = '保存中...';
            const result = await updateBayes(selectedFile, content);
            if (result) {
                Notification.success(`Bayes 文件 ${selectedFile} 更新成功！`);
            }
            saveBayesBtn.disabled = false;
            saveBayesBtn.textContent = '保存更改';
        });

        deleteBayesBtn.addEventListener('click', async () => {
            const selectedFile = bayesSelector.value;
            if (!selectedFile) {
                Notification.warning("请先选择一个要删除的Bayes文件。");
                return;
            }
            const result = await Notification.confirmDelete(`你确定要删除Bayes文件 "${selectedFile}" 吗？此操作不可恢复。`); if (!result.isConfirmed) {
                return;
            }
            deleteBayesBtn.disabled = true;
            deleteBayesBtn.textContent = '删除中...';
            try {
                const response = await deleteBayesProfile(selectedFile);
                if (response) {
                    Notification.success(`Bayes 文件 ${selectedFile} 删除成功！`);
                }
                await refreshBayesList();

                await loadBayesGuide();
                bayesEditor.value = "请先从上方选择一个 Bayes 文件进行编辑...";
                bayesEditor.disabled = true;
                saveBayesBtn.disabled = true;
                deleteBayesBtn.disabled = true;
            } catch (error) {
                console.error('删除Bayes失败:', error);
                Notification.error('删除失败，请稍后重试。');
            } finally {
                deleteBayesBtn.disabled = false;
                deleteBayesBtn.textContent = '删除模板';
            }
        });

        newBayesBtn.addEventListener('click', () => {
            const modalHTML = `
        <div id="new-bayes-modal" class="modal-overlay visible">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>新建 Bayes 模板</h2>
                    <button id="close-new-bayes-modal" class="close-button">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="new-bayes-form">
                        <div class="form-group">
                            <label for="new-bayes-name">模板名称:</label>
                            <input type="text" id="new-bayes-name" placeholder="请输入模板名称" required>
                            <p class="form-hint">不需要添加.json后缀</p>
                        </div>
                        <div class="form-group">
                            <label for="new-bayes-content">模板内容:</label>
                            <textarea id="new-bayes-content" rows="10" placeholder="请输入 Bayes 模板内容" required></textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button id="cancel-new-bayes-btn" class="control-button">取消</button>
                    <button id="save-new-bayes-btn" class="control-button primary-btn">保存</button>
                </div>
            </div>
        </div>
        `;
            document.body.insertAdjacentHTML('beforeend', modalHTML);

            const modal = document.getElementById('new-bayes-modal');
            const closeBtn = document.getElementById('close-new-bayes-modal');
            const cancelBtn = document.getElementById('cancel-new-bayes-btn');
            const saveBtn = document.getElementById('save-new-bayes-btn');
            const form = document.getElementById('new-bayes-form');

            const closeModal = () => {
                if (modal) modal.remove();
            };
            closeBtn.addEventListener('click', closeModal);
            cancelBtn.addEventListener('click', closeModal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });

            saveBtn.addEventListener('click', async () => {
                if (!form.checkValidity()) {
                    form.reportValidity();
                    return;
                }
                const newFileName = document.getElementById('new-bayes-name').value.trim();
                const content = document.getElementById('new-bayes-content').value;
                if (!newFileName) {
                    Notification.warning('请输入模板名称。');
                    return;
                }
                if (/[\\\\/:]/.test(newFileName) || newFileName.includes('..')) {
                    Notification.warning('无效的文件名');
                    return;
                }
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
                const result = await createBayesProfile(newFileName, content);
                if (result) {
                    Notification.success(`Bayes 文件 ${newFileName} 创建成功！`);
                    await refreshBayesList();

                    await loadBayesGuide();
                    bayesSelector.value = newFileName.endsWith('.json') ? newFileName : `${newFileName}.json`;
                    bayesEditor.value = content;
                    bayesEditor.disabled = false;
                    saveBayesBtn.disabled = false;
                    deleteBayesBtn.disabled = false;
                    closeModal();
                }
                saveBtn.disabled = false;
                saveBtn.textContent = '保存';
            });
        });
    }


}


// ============== 数据库设置渲染与事件 ==============

async function initializeDatabaseWarehousePanel(mountNode) {
    if (!mountNode) return;
    mountNode.innerHTML = `
        <div class="settings-card">
            <h3>PostgreSQL 数据仓库配置</h3>
            <div id="database-settings-container">
                <p>正在加载数据库配置...</p>
            </div>
        </div>
    `;

    const databaseSettingsContainer = mountNode.querySelector('#database-settings-container');
    if (!databaseSettingsContainer) return;

    try {
        const dbResponse = await fetch('/api/settings/database');
        if (dbResponse.ok) {
            const dbSettings = await dbResponse.json();
            databaseSettingsContainer.innerHTML = renderDatabaseSettings(dbSettings);
            initializeDatabaseSettingsEvents();
        } else {
            databaseSettingsContainer.innerHTML = '<p>加载数据库配置失败。</p>';
        }
    } catch (error) {
        console.error('无法加载数据库配置:', error);
        databaseSettingsContainer.innerHTML = '<p>加载数据库配置失败。请检查服务器是否正常运行。</p>';
    }
}
window.initializeDatabaseWarehousePanel = initializeDatabaseWarehousePanel;

function renderDatabaseSettings(settings) {
    const configuredBackend = (settings.CONFIGURED_BACKEND || settings.STORAGE_BACKEND || 'local').toLowerCase();
    const runtimeBackend = (settings.RUNTIME_BACKEND || configuredBackend).toLowerCase();
    const isPostgres = configuredBackend === 'postgres';
    const isPostgresRunning = runtimeBackend === 'postgres';
    const configuredModeLabel = settings.CONFIGURED_BACKEND_LABEL || (configuredBackend === 'postgres' ? 'PostgreSQL（多用户）' : '本地文件（单用户）');
    const runtimeModeLabel = settings.RUNTIME_BACKEND_LABEL || (runtimeBackend === 'postgres' ? 'PostgreSQL（多用户）' : '本地文件（单用户）');
    const modeConsistent = settings.BACKEND_CONSISTENT !== false && configuredBackend === runtimeBackend;

    const dbStatus = settings.DB_STATUS || {};
    const dbStatusLabel = dbStatus.label || settings.DB_STATUS_LABEL || '未连接';
    const dbStatusMessage = dbStatus.message || settings.DB_STATUS_MESSAGE || '';
    const dbStatusVersion = dbStatus.version || settings.DB_STATUS_VERSION || '';
    const dbStatusLevel = dbStatus.level || settings.DB_STATUS_LEVEL || 'info';
    const isConnected = dbStatusLevel === 'ok';

    const encryptionWarning = settings.ENCRYPTION_KEY_DEFAULT ?
        '<p class="form-hint" style="color: #ff4d4f;">⚠️ 正在使用默认加密密钥，生产环境请务必修改！</p>' : '';
    const encryptionKeyHint = settings.ENCRYPTION_MASTER_KEY_SET
        ? '<p class="form-hint">主密钥已设置，留空将保持不变。</p>'
        : '';
    const passwordHint = settings.DB_PASSWORD_SET
        ? '<p class="form-hint">密码已设置，留空将保持不变。</p>'
        : '';

    // 状态指示器颜色
    const statusColor = isConnected ? '#52c41a' : (dbStatusLevel === 'error' ? '#ff4d4f' : '#d9d9d9');
    const statusBgColor = isConnected ? 'rgba(82, 196, 26, 0.1)' : (dbStatusLevel === 'error' ? 'rgba(255, 77, 79, 0.1)' : 'rgba(0, 0, 0, 0.02)');

    return `
        <form id="database-settings-form">
            <!-- 主控开关区域 -->
            <div class="db-master-switch-card" style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 20px 24px;
                margin-bottom: 24px;
                color: white;
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            ">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <div style="
                        width: 48px;
                        height: 48px;
                        background: rgba(255,255,255,0.2);
                        border-radius: 12px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 24px;
                    ">🗄️</div>
                    <div>
                        <div style="font-size: 18px; font-weight: 600; margin-bottom: 4px;">PostgreSQL 数据仓库</div>
                        <div style="font-size: 13px; opacity: 0.9;">
                            ${isPostgres ? '已启用 - 多用户模式' : '未启用 - 当前使用本地文件存储'}
                        </div>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 13px; opacity: 0.9;">${isPostgres ? '已开启' : '已关闭'}</span>
                    <label class="switch db-warehouse-switch" style="margin: 0;">
                        <input type="checkbox" id="db-warehouse-toggle" ${isPostgres ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                </div>
            </div>

            <!-- 状态信息卡片 -->
            <div class="db-status-grid" style="
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            ">
                <!-- 运行模式 -->
                <div class="db-status-item" style="
                    background: var(--bg-secondary, #f5f5f5);
                    border-radius: 10px;
                    padding: 16px;
                    border: 1px solid var(--border-color, #e8e8e8);
                ">
                    <div style="font-size: 12px; color: var(--text-secondary, #888); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">运行模式</div>
                    <div style="font-size: 16px; font-weight: 600; color: var(--text-primary, #333);">${runtimeModeLabel}</div>
                </div>
                <!-- 配置模式 -->
                <div class="db-status-item" style="
                    background: var(--bg-secondary, #f5f5f5);
                    border-radius: 10px;
                    padding: 16px;
                    border: 1px solid var(--border-color, #e8e8e8);
                ">
                    <div style="font-size: 12px; color: var(--text-secondary, #888); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">配置模式</div>
                    <div style="font-size: 16px; font-weight: 600; color: var(--text-primary, #333);">${configuredModeLabel}</div>
                </div>
                <!-- 连接状态 -->
                <div class="db-status-item" style="
                    background: ${statusBgColor};
                    border-radius: 10px;
                    padding: 16px;
                    border: 1px solid ${statusColor};
                ">
                    <div style="font-size: 12px; color: var(--text-secondary, #888); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">连接状态</div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="
                            width: 10px;
                            height: 10px;
                            border-radius: 50%;
                            background: ${statusColor};
                            display: inline-block;
                            ${isConnected ? 'animation: pulse 2s infinite;' : ''}
                        "></span>
                        <span style="font-size: 16px; font-weight: 600; color: ${statusColor};">${dbStatusLabel}</span>
                    </div>
                    ${dbStatusVersion ? `<div style="font-size: 11px; color: var(--text-secondary, #888); margin-top: 6px;">${dbStatusVersion}</div>` : ''}
                </div>
                <!-- 模式一致性 -->
                <div class="db-status-item" style="
                    background: ${modeConsistent ? 'rgba(82, 196, 26, 0.1)' : 'rgba(250, 173, 20, 0.1)'};
                    border-radius: 10px;
                    padding: 16px;
                    border: 1px solid ${modeConsistent ? '#52c41a' : '#faad14'};
                ">
                    <div style="font-size: 12px; color: var(--text-secondary, #888); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">模式一致性</div>
                    <div style="font-size: 16px; font-weight: 600; color: ${modeConsistent ? '#52c41a' : '#faad14'};">
                        ${modeConsistent ? '✓ 一致' : '⚠ 不一致'}
                    </div>
                    ${!modeConsistent ? '<div style="font-size: 11px; color: #faad14; margin-top: 6px;">需重启服务生效</div>' : ''}
                </div>
            </div>

            <!-- 连接配置区域 -->
            <div class="db-config-section" style="
                background: white;
                border-radius: 12px;
                padding: 24px;
                border: 1px solid var(--border-color, #e8e8e8);
                margin-bottom: 20px;
            ">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
                    <span style="font-size: 18px;">⚙️</span>
                    <h4 style="margin: 0; font-size: 16px; font-weight: 600;">连接配置</h4>
                </div>

                <div style="display: grid; grid-template-columns: 3fr 1fr; gap: 16px;">
                    <div class="form-group" style="margin-bottom: 0;">
                        <label for="db-host" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">主机地址</label>
                        <input type="text" id="db-host" name="DB_HOST" value="${settings.DB_HOST || ''}" placeholder="192.168.1.100 或 localhost" style="width: 100%;">
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <label for="db-port" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">端口</label>
                        <input type="text" id="db-port" name="DB_PORT" value="${settings.DB_PORT || '5432'}" placeholder="5432" style="width: 100%;">
                    </div>
                </div>

                <div class="form-group" style="margin-top: 16px; margin-bottom: 0;">
                    <label for="db-name" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">数据库名</label>
                    <input type="text" id="db-name" name="DB_NAME" value="${settings.DB_NAME || ''}" placeholder="goofish_monitor" style="width: 100%;">
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px;">
                    <div class="form-group" style="margin-bottom: 0;">
                        <label for="db-user" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">用户名</label>
                        <input type="text" id="db-user" name="DB_USER" value="${settings.DB_USER || ''}" placeholder="postgres" style="width: 100%;">
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <label for="db-password" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">密码</label>
                        <div style="position: relative;">
                            <input type="password" id="db-password" name="DB_PASSWORD" value="" placeholder="数据库密码" style="width: 100%; padding-right: 40px;">
                            <button type="button" id="toggle-db-password" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 4px; color: #888;">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                            </button>
                        </div>
                        ${passwordHint}
                    </div>
                </div>

                <div class="form-group" style="margin-top: 16px; margin-bottom: 0;">
                    <label for="encryption-key" style="font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block;">加密主密钥</label>
                    <div style="position: relative;">
                        <input type="password" id="encryption-key" name="ENCRYPTION_MASTER_KEY" value="" placeholder="用于加密敏感数据（如账号密码）" style="width: 100%; padding-right: 40px;">
                        <button type="button" id="toggle-encryption-key" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 4px; color: #888;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                    </div>
                    ${encryptionKeyHint}
                    ${encryptionWarning}
                </div>

                <div style="display: flex; gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border-color, #e8e8e8);">
                    <button type="button" id="test-db-connection-btn" class="control-button" style="
                        background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
                        border: none;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 8px;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        transition: transform 0.2s, box-shadow 0.2s;
                    ">
                        <span>🔗</span> 测试连接
                    </button>
                    <button type="submit" class="control-button primary-btn" style="
                        padding: 10px 20px;
                        border-radius: 8px;
                        font-weight: 500;
                    ">💾 保存配置</button>
                </div>

                <div id="db-connection-status" style="margin-top: 12px;"></div>
            </div>

            <!-- 数据迁移区域 -->
            <div class="db-migration-section" style="
                background: white;
                border-radius: 12px;
                padding: 24px;
                border: 1px solid var(--border-color, #e8e8e8);
            ">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                    <span style="font-size: 18px;">📦</span>
                    <h4 style="margin: 0; font-size: 16px; font-weight: 600;">数据迁移</h4>
                </div>
                <p class="form-hint" style="margin: 0 0 16px; color: var(--text-secondary, #666); font-size: 13px; font-style: normal;">
                    将本地文件数据复制到 PostgreSQL 数据库。本地数据将保留作为备份。
                </p>

                <div id="migration-scope-panel" style="
                    margin-bottom: 16px;
                    background: #fafafa;
                    border: 1px solid #f0f0f0;
                    border-radius: 8px;
                    padding: 12px;
                    font-size: 13px;
                    color: var(--text-secondary, #666);
                ">
                    正在加载迁移范围说明...
                </div>
                
                <div style="display: flex; gap: 12px;">
                    <button type="button" id="dry-run-migration-btn" class="control-button" style="
                        background: #f5f5f5;
                        border: 1px solid #d9d9d9;
                        color: #555;
                        padding: 10px 16px;
                        border-radius: 8px;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        gap: 6px;
                    ">
                        <span>🧪</span> 测试迁移
                    </button>
                    <button type="button" id="run-migration-btn" class="control-button" style="
                        background: linear-gradient(135deg, #52c41a 0%, #389e0d 100%);
                        border: none;
                        color: white;
                        padding: 10px 16px;
                        border-radius: 8px;
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        gap: 6px;
                    ">
                        <span>🚀</span> 执行迁移
                    </button>
                </div>
                <div style="
                    margin-top: 14px;
                    padding-top: 14px;
                    border-top: 1px dashed var(--border-color, #e8e8e8);
                ">
                    <p class="form-hint" style="margin: 0; font-style: normal;">
                        执行“正式迁移”时会自动将全局 .env 中的 AI 模型与代理参数迁移到当前登录用户私有配置。
                    </p>
                </div>

                <div id="migration-result" style="margin-top: 12px;"></div>
            </div>
        </form>

        <style>
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .db-warehouse-switch .slider {
                background-color: rgba(255,255,255,0.3) !important;
            }
            .db-warehouse-switch input:checked + .slider {
                background-color: rgba(255,255,255,0.5) !important;
            }
            .db-warehouse-switch .slider:before {
                background-color: white !important;
            }
            #test-db-connection-btn:hover, #run-migration-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
        </style>
    `;
}

function initializeDatabaseSettingsEvents() {
    const form = document.getElementById('database-settings-form');
    if (!form) return;

    // 数据仓库主控开关
    const dbWarehouseToggle = document.getElementById('db-warehouse-toggle');
    if (dbWarehouseToggle) {
        dbWarehouseToggle.addEventListener('change', async (e) => {
            const isEnabling = e.target.checked;

            if (isEnabling) {
                // 开启PostgreSQL模式
                const dbHost = document.getElementById('db-host')?.value?.trim();
                const dbName = document.getElementById('db-name')?.value?.trim();
                const dbUser = document.getElementById('db-user')?.value?.trim();

                if (!dbHost || !dbName || !dbUser) {
                    Notification.warning('请先填写完整的数据库连接信息（主机、数据库名、用户名）并保存配置。');
                    e.target.checked = false;
                    return;
                }

                const confirmResult = await Notification.confirm(
                    '开启后系统将使用 PostgreSQL 存储数据。请确保已完成数据迁移，否则数据可能丢失。',
                    '确定开启 PostgreSQL 模式？',
                    {
                        icon: 'warning',
                        confirmButtonText: '确定开启',
                        confirmButtonColor: '#722ed1'
                    }
                );

                if (!confirmResult.isConfirmed) {
                    e.target.checked = false;
                    return;
                }

                Notification.loading('正在验证数据库并切换模式...', '开启中');

                try {
                    const response = await fetch('/api/settings/database/enable', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const result = await response.json();
                    Notification.close();

                    if (response.ok && result.success) {
                        await Notification.successDialog(
                            '系统将刷新进入登录页面。请使用您的账号登录。',
                            'PostgreSQL 模式已开启'
                        );
                        window.location.href = '/login';
                    } else {
                        Notification.error(result.detail || result.message || '开启失败，请检查数据库是否已正确迁移。');
                        e.target.checked = false;
                    }
                } catch (error) {
                    Notification.close();
                    Notification.error(`请求失败: ${error.message}`);
                    e.target.checked = false;
                }
            } else {
                // 关闭PostgreSQL模式，切换回本地存储
                const confirmResult = await Notification.confirm(
                    '关闭后系统将切换回本地文件存储模式。PostgreSQL中的数据不会丢失，但也不会同步到本地文件。',
                    '确定关闭 PostgreSQL 模式？',
                    {
                        icon: 'warning',
                        confirmButtonText: '确定关闭',
                        confirmButtonColor: '#ff4d4f'
                    }
                );

                if (!confirmResult.isConfirmed) {
                    e.target.checked = true;
                    return;
                }

                Notification.loading('正在切换到本地存储模式...', '切换中');

                try {
                    const response = await fetch('/api/settings/database/disable', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const result = await response.json();
                    Notification.close();

                    if (response.ok && result.success) {
                        await Notification.successDialog(
                            '系统将刷新进入登录页面。',
                            '已切换到本地存储模式'
                        );
                        window.location.href = '/login';
                    } else {
                        Notification.error(result.detail || result.message || '关闭失败。');
                        e.target.checked = true;
                    }
                } catch (error) {
                    Notification.close();
                    Notification.error(`请求失败: ${error.message}`);
                    e.target.checked = true;
                }
            }
        });
    }

    const dbHostInput = document.getElementById('db-host');
    const dbPortInput = document.getElementById('db-port');
    const normalizeDbHostInput = () => {
        if (!dbHostInput) return;
        const raw = (dbHostInput.value || '').trim();
        if (!raw) return;

        let host = raw;
        let port = '';

        // 主机地址兼容 http(s):// 与 host:port
        if (raw.includes('://')) {
            try {
                const parsed = new URL(raw);
                if (parsed.hostname) {
                    host = parsed.hostname;
                    port = parsed.port || '';
                } else {
                    host = raw.split('://')[1] || raw;
                }
            } catch (error) {
                host = raw.split('://')[1] || raw;
            }
        }

        host = host.split('/')[0];

        if (host.includes(':') && host.indexOf(':') === host.lastIndexOf(':') && !host.startsWith('[')) {
            const [hostPart, portPart] = host.split(':');
            if (/^\d+$/.test(portPart)) {
                host = hostPart;
                port = portPart;
            }
        }

        dbHostInput.value = host;
        if (port && dbPortInput) {
            dbPortInput.value = port;
        }
    };

    if (dbHostInput) {
        dbHostInput.addEventListener('blur', normalizeDbHostInput);
        dbHostInput.addEventListener('change', normalizeDbHostInput);
        dbHostInput.addEventListener('paste', () => setTimeout(normalizeDbHostInput, 0));
    }

    // 密码显示/隐藏切换
    const toggleDbPassword = document.getElementById('toggle-db-password');
    const dbPasswordInput = document.getElementById('db-password');
    if (toggleDbPassword && dbPasswordInput) {
        toggleDbPassword.addEventListener('click', () => {
            dbPasswordInput.type = dbPasswordInput.type === 'password' ? 'text' : 'password';
        });
    }

    const toggleEncryptionKey = document.getElementById('toggle-encryption-key');
    const encryptionKeyInput = document.getElementById('encryption-key');
    if (toggleEncryptionKey && encryptionKeyInput) {
        toggleEncryptionKey.addEventListener('click', () => {
            encryptionKeyInput.type = encryptionKeyInput.type === 'password' ? 'text' : 'password';
        });
    }

    // 测试连接
    const testBtn = document.getElementById('test-db-connection-btn');
    const statusDiv = document.getElementById('db-connection-status');
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            const formData = new FormData(form);
            const settings = {
                DB_HOST: formData.get('DB_HOST'),
                DB_PORT: formData.get('DB_PORT'),
                DB_NAME: formData.get('DB_NAME'),
                DB_USER: formData.get('DB_USER')
            };
            const passwordValue = formData.get('DB_PASSWORD');
            if (passwordValue) {
                settings.DB_PASSWORD = passwordValue;
            }

            testBtn.disabled = true;
            testBtn.textContent = '测试中...';
            statusDiv.innerHTML = '<p style="color: var(--text-secondary);">正在测试连接...</p>';

            try {
                const response = await fetch('/api/settings/database/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                const result = await response.json();
                if (result.success) {
                    const versionHtml = result.version ? `<div style="color: var(--text-secondary); margin-top: 4px;">${result.version}</div>` : '';
                    statusDiv.innerHTML = `<div style="color: #52c41a;">✅ ${result.message}</div>${versionHtml}`;
                } else {
                    statusDiv.innerHTML = `<div style="color: #ff4d4f;">❌ ${result.message}</div>`;
                }
            } catch (error) {
                statusDiv.innerHTML = `<p style="color: #ff4d4f;">❌ 测试失败: ${error.message}</p>`;
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = '测试连接';
            }
        });
    }

    // 保存配置
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const passwordValue = formData.get('DB_PASSWORD');

        const settings = {
            DB_HOST: formData.get('DB_HOST'),
            DB_PORT: formData.get('DB_PORT'),
            DB_NAME: formData.get('DB_NAME'),
            DB_USER: formData.get('DB_USER'),
            ENCRYPTION_MASTER_KEY: formData.get('ENCRYPTION_MASTER_KEY')
        };

        if (!String(settings.DB_HOST || '').trim() || !String(settings.DB_NAME || '').trim()) {
            Notification.warning('请先填写主机地址和数据库名，再保存配置。');
            return;
        }

        // 只有当密码被修改（不是占位符）时才发送密码
        if (passwordValue) {
            settings.DB_PASSWORD = passwordValue;
        }

        const saveBtn = form.querySelector('button[type="submit"]');
        const originalText = saveBtn.textContent;
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';

        try {
            const response = await fetch('/api/settings/database', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const result = await response.json();
            if (response.ok) {
                Notification.success(result.message || '数据库配置已保存！');
            } else {
                Notification.error('保存失败: ' + (result.detail || '未知错误'));
            }
        } catch (error) {
            Notification.error('保存失败: ' + error.message);
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        }
    });

    // 数据迁移
    const dryRunBtn = document.getElementById('dry-run-migration-btn');
    const runMigrationBtn = document.getElementById('run-migration-btn');
    const migrationResultDiv = document.getElementById('migration-result');
    const migrationScopePanel = document.getElementById('migration-scope-panel');

    const migrationLabelMap = {
        tasks: '任务配置',
        results: '监控结果',
        bayes_profiles: '贝叶斯模型',
        bayes_samples: '贝叶斯样本',
        ai_criteria: 'AI标准',
        platform_accounts: '平台账号'
    };

    const escapeHtml = (value) => String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');

    const renderMigrationScope = (scope) => {
        if (!migrationScopePanel) return;
        const policyNotice = (scope?.policy_notice || '').toString().trim();
        const willMigrate = Array.isArray(scope?.will_migrate) ? scope.will_migrate : [];
        const sharedBaseAssets = Array.isArray(scope?.shared_base_assets) ? scope.shared_base_assets : [];
        const willNotMigrate = Array.isArray(scope?.will_not_migrate) ? scope.will_not_migrate : [];

        if (!policyNotice && !willMigrate.length && !sharedBaseAssets.length && !willNotMigrate.length) {
            migrationScopePanel.innerHTML = '<span style="color:#ff4d4f;">未获取到迁移范围说明。</span>';
            return;
        }

        const policyHtml = policyNotice
            ? `<div style="padding: 8px 10px; border-radius: 6px; background: #fffbe6; border: 1px solid #ffe58f; color: #8c6d1f;">${escapeHtml(policyNotice)}</div>`
            : '';

        const willMigrateHtml = willMigrate.map((item) => (
            `<li style="margin: 4px 0;">
                <strong>${escapeHtml(item.label || item.key)}</strong>
                <span style="color: var(--text-secondary, #666);">：${escapeHtml(item.description || '')}</span>
            </li>`
        )).join('');

        const sharedBaseAssetsHtml = sharedBaseAssets.map((item) => (
            `<li style="margin: 4px 0;">
                <strong>${escapeHtml(item.label || item.key)}</strong>
                <span style="color: var(--text-secondary, #666);">：${escapeHtml(item.description || '')}</span>
            </li>`
        )).join('');

        const willNotMigrateHtml = willNotMigrate.map((item) => (
            `<li style="margin: 4px 0;">
                <strong>${escapeHtml(item.label || item.key)}</strong>
                <span style="color: var(--text-secondary, #666);">：${escapeHtml(item.reason || '')}</span>
            </li>`
        )).join('');

        migrationScopePanel.innerHTML = `
            <div style="display: grid; gap: 10px;">
                ${policyHtml}
                <div>
                    <div style="font-weight: 600; color: #52c41a; margin-bottom: 6px;">会迁移</div>
                    <ul style="margin: 0; padding-left: 20px;">${willMigrateHtml}</ul>
                </div>
                <div>
                    <div style="font-weight: 600; color: #1677ff; margin-bottom: 6px;">系统级基础资源</div>
                    <ul style="margin: 0; padding-left: 20px;">${sharedBaseAssetsHtml}</ul>
                </div>
                <div>
                    <div style="font-weight: 600; color: #fa8c16; margin-bottom: 6px;">不会迁移</div>
                    <ul style="margin: 0; padding-left: 20px;">${willNotMigrateHtml}</ul>
                </div>
            </div>
        `;
    };

    const loadMigrationScope = async () => {
        if (!migrationScopePanel) return;
        migrationScopePanel.innerHTML = '正在加载迁移范围说明...';
        try {
            const response = await fetch('/api/settings/database/migration-scope');
            const result = await response.json();
            if (response.ok && result.success) {
                renderMigrationScope(result.scope || {});
            } else {
                migrationScopePanel.innerHTML = `<span style="color:#ff4d4f;">迁移范围加载失败：${escapeHtml(result.detail || result.message || '未知错误')}</span>`;
            }
        } catch (error) {
            migrationScopePanel.innerHTML = `<span style="color:#ff4d4f;">迁移范围加载失败：${escapeHtml(error.message)}</span>`;
        }
    };

    const runMigration = async (dryRun) => {
        const btn = dryRun ? dryRunBtn : runMigrationBtn;
        const originalText = btn.textContent;
        btn.disabled = true;
        dryRunBtn.disabled = true;
        runMigrationBtn.disabled = true;
        btn.textContent = '迁移中...';
        migrationResultDiv.innerHTML = '<p style="color: var(--text-secondary);">正在执行迁移，请稍候...</p>';

        try {
            const response = await fetch('/api/settings/database/migrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dry_run: dryRun, auto_enable_mode: !dryRun })
            });
            const result = await response.json();

            if (response.ok && result.success) {
                const stats = result.stats || {};
                const modeText = dryRun ? '测试迁移' : '正式迁移';
                const aiProxyMigration = result.ai_proxy_migration && typeof result.ai_proxy_migration === 'object'
                    ? result.ai_proxy_migration
                    : null;
                let html = `<div style="background: var(--bg-secondary); padding: 12px; border-radius: 8px; margin-top: 8px;">
                    <p style="color: #52c41a; margin-bottom: 8px;"><strong>✅ ${modeText}完成</strong></p>`;

                renderMigrationScope(result.scope || {});

                for (const [category, counts] of Object.entries(stats)) {
                    const migrated = counts.migrated || 0;
                    const errors = counts.errors || 0;
                    const statusIcon = errors > 0 ? '⚠️' : '✅';
                    const categoryLabel = migrationLabelMap[category] || category;
                    html += `<p style="margin: 4px 0;">${statusIcon} ${categoryLabel}: ${migrated} 条迁移${dryRun ? '(模拟)' : '成功'}${errors > 0 ? `, ${errors} 条错误` : ''}</p>`;
                }
                if (!dryRun && result.mode_switch_message) {
                    const switchColor = result.mode_switched ? '#52c41a' : '#faad14';
                    html += `<p style="margin: 8px 0 0; color: ${switchColor};">${result.mode_switch_message}</p>`;
                }
                if (!dryRun && aiProxyMigration && aiProxyMigration.enabled) {
                    const aiProxySuccess = Boolean(aiProxyMigration.success);
                    const aiProxyColor = aiProxySuccess ? '#52c41a' : '#faad14';
                    const aiProxyIcon = aiProxySuccess ? '✅' : '⚠️';
                    const aiProxyMessage = escapeHtml(aiProxyMigration.message || (aiProxySuccess ? 'AI/代理配置迁移成功。' : 'AI/代理配置迁移未完成。'));
                    html += `<p style="margin: 8px 0 0; color: ${aiProxyColor};">${aiProxyIcon} ${aiProxyMessage}</p>`;
                }
                html += '</div>';
                migrationResultDiv.innerHTML = html;
                Notification.success(result.message || `${modeText}完成！`);
            } else {
                migrationResultDiv.innerHTML = `<p style="color: #ff4d4f;">❌ 迁移失败: ${result.detail || result.message || '未知错误'}</p>`;
                Notification.error(result.detail || result.message || '迁移失败，请检查日志后重试');
            }
        } catch (error) {
            migrationResultDiv.innerHTML = `<p style="color: #ff4d4f;">❌ 迁移失败: ${error.message}</p>`;
            Notification.error(`迁移失败: ${error.message}`);
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
            dryRunBtn.disabled = false;
            runMigrationBtn.disabled = false;
        }
    };

    if (dryRunBtn) {
        dryRunBtn.addEventListener('click', () => runMigration(true));
    }

    if (runMigrationBtn) {
        runMigrationBtn.addEventListener('click', async () => {
            const confirmResult = await Notification.confirm('确定要执行正式迁移吗？建议先执行测试迁移确认无误后再正式迁移。');
            if (confirmResult.isConfirmed) {
                await runMigration(false);
            }
        });
    }

    loadMigrationScope();
}

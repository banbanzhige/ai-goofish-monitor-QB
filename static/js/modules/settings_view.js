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


    await initializeModelManagementPanels();

    const aiForm = document.getElementById('ai-settings-form');
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

                const originalText = testBtn.textContent;
                testBtn.disabled = true;
                testBtn.textContent = '测试中...';
                const results = [];
                let browserOk = false;
                let backendOk = false;

                const browserResult = await testAISettings(settings, { silent: true });
                if (browserResult && browserResult.success) {
                    browserOk = true;
                    results.push(`浏览器测试成功：${browserResult.message || '连接正常'}`);
                } else if (browserResult) {
                    results.push(`浏览器测试失败：${browserResult.message || '未知错误'}`);
                } else {
                    results.push('浏览器测试失败：无响应');
                }

                try {
                    const saveResult = await updateAISettings(settings);
                    if (!saveResult) {
                        results.push('后端容器测试失败：保存AI设置失败');
                    } else {
                        const toggleSaveResult = await updateAiGenericToggleSettings(genericToggleSettings);
                        if (!toggleSaveResult) {
                            results.push('后端容器测试失败：AI通用开关保存失败');
                        }
                        const response = await fetch('/api/settings/ai/test/backend', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                        });

                        if (!response.ok) {
                            throw new Error('后端测试请求失败');
                        }

                        const backendResult = await response.json();
                        if (backendResult.success) {
                            backendOk = true;
                            results.push(`后端容器测试成功：${backendResult.message || '连接正常'}`);
                        } else {
                            results.push(`后端容器测试失败：${backendResult.message || '未知错误'}`);
                        }
                    }
                } catch (error) {
                    results.push(`后端容器测试错误：${error.message}`);
                } finally {
                    testBtn.disabled = false;
                    testBtn.textContent = originalText;

                    // 刷新系统状态检查
                    const status = await fetchSystemStatus();
                    const statusContainer = document.getElementById('system-status-container');
                    if (statusContainer) {
                        statusContainer.innerHTML = renderSystemStatus(status);
                    }
                }

                const successLines = [
                    '浏览器测试成功：AI模型连接测试成功！',
                    '后端容器测试成功：后端AI模型连接测试成功！',
                    '容器网络正常！系统已经准备好运行！'
                ];
                const message = (browserOk && backendOk)
                    ? successLines.join('\n')
                    : results.join('\n');
                Notification.infoMultiline(message);
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


                if (newFileName.includes('/') || newFileName.includes('..')) {
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
                if (newFileName.includes('/') || newFileName.includes('..')) {
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

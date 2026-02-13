﻿// 通知视图（本地模式使用 .env，服务器模式使用用户私有配置）

const NOTIFICATION_CHANNEL_META = {
    wx_app: {
        label: '企业微信应用通知',
        fields: [
            { key: 'corp_id', label: '企业 ID', type: 'text', placeholder: '例如: wwxxxxxxxxx' },
            { key: 'agent_id', label: '应用 ID', type: 'text', placeholder: '例如: 1000001' },
            { key: 'secret', label: '应用密钥', type: 'password', placeholder: '例如: your_app_secret' },
            { key: 'to_user', label: '通知用户（可选）', type: 'text', placeholder: '例如: UserID1|UserID2 或 @all' }
        ]
    },
    wx_bot: {
        label: '企业微信机器人通知',
        fields: [
            { key: 'url', label: 'Webhook URL', type: 'text', placeholder: '例如: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...' }
        ]
    },
    dingtalk: {
        label: '钉钉机器人通知',
        fields: [
            { key: 'webhook', label: 'Webhook 地址', type: 'text', placeholder: '例如: https://oapi.dingtalk.com/robot/send?access_token=...' },
            { key: 'secret', label: '加签密钥（可选）', type: 'password', placeholder: '例如: SECxxxxxxx' }
        ]
    },
    telegram: {
        label: 'Telegram 机器人通知',
        fields: [
            { key: 'bot_token', label: 'Bot Token', type: 'password', placeholder: '例如: 123456:ABC...' },
            { key: 'chat_id', label: 'Chat ID', type: 'text', placeholder: '例如: 123456789' }
        ]
    },
    ntfy: {
        label: 'Ntfy 通知',
        fields: [
            { key: 'topic_url', label: 'Topic URL', type: 'text', placeholder: '例如: https://ntfy.sh/your_topic' }
        ]
    },
    gotify: {
        label: 'Gotify 通知',
        fields: [
            { key: 'url', label: '服务地址', type: 'text', placeholder: '例如: https://push.example.de' },
            { key: 'token', label: '应用 Token', type: 'password', placeholder: '例如: your_gotify_token' }
        ]
    },
    bark: {
        label: 'Bark 通知',
        fields: [
            { key: 'url', label: '推送地址', type: 'text', placeholder: '例如: https://api.day.app/your_key' }
        ]
    },
    webhook: {
        label: '通用 Webhook 通知',
        fields: [
            { key: 'url', label: 'URL 地址', type: 'text', placeholder: '例如: https://your-webhook-url.com/endpoint' },
            { key: 'method', label: '请求方法', type: 'select', options: ['POST', 'GET'], defaultValue: 'POST' },
            { key: 'headers', label: '请求头（JSON）', type: 'textarea', placeholder: '{"Authorization":"Bearer token"}' },
            { key: 'content_type', label: '内容类型', type: 'select', options: ['JSON', 'FORM'], defaultValue: 'JSON' },
            { key: 'query_parameters', label: '查询参数（可选）', type: 'textarea', placeholder: '{"title":"${title}"}' },
            { key: 'body', label: '请求体（可选）', type: 'textarea', placeholder: '{"content":"${content}"}' }
        ]
    }
};

const NOTIFICATION_CHANNEL_ORDER = ['wx_app', 'wx_bot', 'dingtalk', 'telegram', 'ntfy', 'gotify', 'bark', 'webhook'];
let notificationDraftCounter = 0;

function escapeNotificationHtml(value) {
    if (value === null || value === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(value);
    return div.innerHTML;
}

function getNotificationChannelLabel(channelType) {
    const key = String(channelType || '').trim();
    return NOTIFICATION_CHANNEL_META[key]?.label || key || '未知渠道';
}

function normalizeNotificationConfigItem(item) {
    const channelTypeRaw = String(item?.channel_type || '').trim();
    const channelType = NOTIFICATION_CHANNEL_META[channelTypeRaw] ? channelTypeRaw : 'ntfy';
    const rawConfig = item?.config && typeof item.config === 'object' ? item.config : {};
    const config = { ...rawConfig };

    return {
        id: item?.id ? String(item.id) : '',
        tempId: item?.tempId || `draft-${Date.now()}-${notificationDraftCounter++}`,
        channel_type: channelType,
        name: String(item?.name || '').trim(),
        is_enabled: item?.is_enabled !== false,
        notify_on_recommend: item?.notify_on_recommend !== false,
        notify_on_complete: item?.notify_on_complete !== false,
        config,
    };
}

function createEmptyNotificationConfig(channelType = 'ntfy', defaultBoundTask = '') {
    const normalizedChannel = NOTIFICATION_CHANNEL_META[channelType] ? channelType : 'ntfy';
    const boundTask = String(defaultBoundTask || '').trim();
    const defaultName = `${getNotificationChannelLabel(normalizedChannel)}账号${boundTask ? `-${boundTask}` : ''}`;
    const config = {};
    if (boundTask) {
        config.bound_task = boundTask;
    }
    return normalizeNotificationConfigItem({
        name: defaultName,
        channel_type: normalizedChannel,
        is_enabled: true,
        notify_on_recommend: true,
        notify_on_complete: true,
        config,
    });
}

function getNotificationFieldValue(rawValue, field) {
    if (rawValue === null || rawValue === undefined || rawValue === '') {
        return field.defaultValue || '';
    }
    if (typeof rawValue === 'object') {
        try {
            return JSON.stringify(rawValue, null, 2);
        } catch (_) {
            return '';
        }
    }
    return String(rawValue);
}

function renderNotificationChannelField(field, configValue) {
    const fieldValue = getNotificationFieldValue(configValue, field);
    const safeValue = escapeNotificationHtml(fieldValue);
    const safeLabel = escapeNotificationHtml(field.label);
    const safePlaceholder = escapeNotificationHtml(field.placeholder || '');

    if (field.type === 'select') {
        const options = (field.options || []).map(option => {
            const optionValue = String(option);
            const selected = optionValue === fieldValue ? 'selected' : '';
            return `<option value="${escapeNotificationHtml(optionValue)}" ${selected}>${escapeNotificationHtml(optionValue)}</option>`;
        }).join('');
        return `
            <div class="form-group">
                <label>${safeLabel}</label>
                <select class="notify-channel-field" data-field-key="${escapeNotificationHtml(field.key)}">
                    ${options}
                </select>
            </div>
        `;
    }

    if (field.type === 'textarea') {
        return `
            <div class="form-group">
                <label>${safeLabel}</label>
                <textarea class="notify-channel-field" data-field-key="${escapeNotificationHtml(field.key)}" rows="3" placeholder="${safePlaceholder}">${safeValue}</textarea>
            </div>
        `;
    }

    const inputType = field.type === 'password' ? 'password' : 'text';
    return `
        <div class="form-group">
            <label>${safeLabel}</label>
            <input type="${inputType}" class="notify-channel-field" data-field-key="${escapeNotificationHtml(field.key)}" value="${safeValue}" placeholder="${safePlaceholder}">
        </div>
    `;
}

function renderNotificationChannelFields(channelType, config) {
    const meta = NOTIFICATION_CHANNEL_META[channelType] || NOTIFICATION_CHANNEL_META.ntfy;
    const configObj = config && typeof config === 'object' ? config : {};
    return meta.fields.map(field => renderNotificationChannelField(field, configObj[field.key])).join('');
}

function renderNotificationTaskOptions(taskItems, selectedTask = '') {
    const normalizedSelectedTask = String(selectedTask || '').trim();
    const hasSelectedTask = (Array.isArray(taskItems) ? taskItems : []).some(item => {
        const taskName = String(item?.task_name || '').trim();
        return taskName && taskName === normalizedSelectedTask;
    });
    const options = (Array.isArray(taskItems) ? taskItems : [])
        .map(item => {
            const taskName = String(item?.task_name || '').trim();
            const keyword = String(item?.keyword || '').trim();
            if (!taskName) return '';
            const optionLabel = keyword ? `${taskName}（关键词：${keyword}）` : taskName;
            const selected = taskName === normalizedSelectedTask ? 'selected' : '';
            return `<option value="${escapeNotificationHtml(taskName)}" ${selected}>${escapeNotificationHtml(optionLabel)}</option>`;
        })
        .filter(Boolean)
        .join('');
    const defaultSelected = normalizedSelectedTask ? '' : 'selected';
    const fallbackSelectedOption = (!hasSelectedTask && normalizedSelectedTask)
        ? `<option value="${escapeNotificationHtml(normalizedSelectedTask)}" selected>${escapeNotificationHtml(normalizedSelectedTask)}（历史绑定任务）</option>`
        : '';
    return `
        <option value="" ${defaultSelected}>不绑定任务（默认配置）</option>
        ${fallbackSelectedOption}
        ${options}
    `;
}

function renderNotificationConfigCard(item, channelType, taskItems = [], defaultBoundTask = '') {
    const configItem = normalizeNotificationConfigItem(item);
    const normalizedChannel = NOTIFICATION_CHANNEL_META[channelType] ? channelType : configItem.channel_type;
    const idAttr = configItem.id ? `data-config-id="${escapeNotificationHtml(configItem.id)}"` : '';
    const channelLabel = getNotificationChannelLabel(normalizedChannel);
    const boundTask = String(
        configItem.config.bound_task
        || configItem.config.bound_task_name
        || configItem.config.task_name
        || defaultBoundTask
        || ''
    ).trim();
    const isCollapsible = Boolean(configItem.id);
    const collapsedClass = isCollapsible ? ' is-collapsed' : '';
    const collapseButtonText = isCollapsible ? '展开' : '收起';
    const boundTaskText = boundTask || '未绑定任务（全局默认）';

    return `
        <div class="notification-config-item${collapsedClass}" ${idAttr} data-temp-id="${escapeNotificationHtml(configItem.tempId)}" data-channel-type="${escapeNotificationHtml(normalizedChannel)}" data-bound-task="${escapeNotificationHtml(boundTask)}">
            <div class="notification-config-header">
                <div class="notification-config-header-main">
                    <h4>${escapeNotificationHtml(configItem.name || '未命名通知配置')}</h4>
                    <span class="notification-channel-badge">${escapeNotificationHtml(channelLabel)}</span>
                    <span class="notification-bound-task-badge">绑定任务：${escapeNotificationHtml(boundTaskText)}</span>
                </div>
                <div class="notification-config-header-actions">
                    <div class="notify-header-switch">
                        <label class="switch">
                            <input type="checkbox" class="notify-enabled" ${configItem.is_enabled ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                        <span>启用该通知配置</span>
                    </div>
                    <button type="button" class="control-button small-btn notify-collapse-btn">${collapseButtonText}</button>
                </div>
            </div>
            <div class="notification-config-body">
            <div class="form-group">
                <label>配置名称</label>
                <input type="text" class="notify-config-name" value="${escapeNotificationHtml(configItem.name)}" placeholder="例如：我的企业微信账号">
            </div>
            <div class="form-group">
                <label>绑定任务（可选）</label>
                <select class="notify-bound-task-select">
                    ${renderNotificationTaskOptions(taskItems, boundTask)}
                </select>
                <p class="form-hint">绑定后仅该任务优先命中；不绑定时作为该渠道默认配置。</p>
            </div>
            <div class="form-group notification-event-switch-row">
                <div style="display:flex; align-items:center; gap:8px;">
                    <label class="switch">
                        <input type="checkbox" class="notify-on-recommend" ${configItem.notify_on_recommend ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                    <div style="flex:1;">商品推荐通知</div>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <label class="switch">
                        <input type="checkbox" class="notify-on-complete" ${configItem.notify_on_complete ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                    <div style="flex:1;">任务完成通知</div>
                </div>
            </div>
            <div class="notification-channel-fields">
                ${renderNotificationChannelFields(normalizedChannel, configItem.config)}
            </div>
            <div class="notification-config-actions">
                <button type="button" class="control-button primary-btn notify-save-config-btn">保存配置</button>
                <button type="button" class="control-button notify-test-config-btn" data-test-type="product">测试商品通知</button>
                <button type="button" class="control-button notify-test-config-btn" data-test-type="completion">测试任务完成通知</button>
                <button type="button" class="control-button danger-btn notify-delete-config-btn">删除配置</button>
            </div>
            </div>
        </div>
    `;
}

function renderChannelEmptyState(channelType) {
    return `<div class="notification-empty-state" data-empty-channel="${escapeNotificationHtml(channelType)}">当前渠道暂无通知账号，点击“新增账号”创建。</div>`;
}

function renderServerNotificationSettings(configs, taskItems) {
    const list = Array.isArray(configs) ? configs : [];
    const groupedConfigs = {};
    NOTIFICATION_CHANNEL_ORDER.forEach(channel => {
        groupedConfigs[channel] = [];
    });

    list.forEach(item => {
        const channelType = String(item?.channel_type || '').trim();
        if (!NOTIFICATION_CHANNEL_META[channelType]) return;
        groupedConfigs[channelType].push(item);
    });

    Object.keys(groupedConfigs).forEach(channel => {
        groupedConfigs[channel].sort((left, right) => {
            return String(left?.name || '').localeCompare(String(right?.name || ''), 'zh-Hans-CN');
        });
    });

    return `
        <div id="notification-server-root">
        <div class="notification-tabs" role="tablist" aria-label="通知配置渠道"></div>

        <div class="notification-channel-card">
            <h4>通用配置</h4>
            <div class="notification-server-tip">
                服务器模式下通知配置为当前登录用户私有数据，不再读取全局 .env。你可以在同一渠道配置多个通知账号，并通过“绑定任务”做通知隔离。
            </div>
            <p class="form-hint">新建配置默认不绑定任务，可按需选择任务实现隔离。</p>
            <div class="notification-server-toolbar">
                <button type="button" class="control-button" id="refresh-notification-config-btn">刷新配置</button>
            </div>
        </div>

        ${NOTIFICATION_CHANNEL_ORDER.map(channel => `
            <div class="notification-channel-card" data-channel-panel="${escapeNotificationHtml(channel)}">
                <h4>${escapeNotificationHtml(getNotificationChannelLabel(channel))}</h4>
                <div class="notification-channel-toolbar">
                    <button type="button" class="control-button primary-btn add-channel-config-btn" data-channel="${escapeNotificationHtml(channel)}">新增账号</button>
                    <span class="form-hint">在当前渠道添加多个通知账号，支持按绑定任务自动隔离通知。</span>
                </div>
                <div class="notification-channel-config-list" data-channel="${escapeNotificationHtml(channel)}">
                    ${groupedConfigs[channel].length
                ? groupedConfigs[channel].map(item => renderNotificationConfigCard(item, channel, taskItems, '')).join('')
                : renderChannelEmptyState(channel)}
                </div>
            </div>
        `).join('')}
        </div>
    `;
}

function parseNotificationCardPayload(card) {
    const configId = String(card.getAttribute('data-config-id') || '').trim();
    const channelType = String(card.getAttribute('data-channel-type') || '').trim();
    const configName = String(card.querySelector('.notify-config-name')?.value || '').trim();
    const boundTask = String(card.querySelector('.notify-bound-task-select')?.value || card.getAttribute('data-bound-task') || '').trim();
    const isEnabled = Boolean(card.querySelector('.notify-enabled')?.checked);
    const notifyOnRecommend = Boolean(card.querySelector('.notify-on-recommend')?.checked);
    const notifyOnComplete = Boolean(card.querySelector('.notify-on-complete')?.checked);

    if (!channelType || !NOTIFICATION_CHANNEL_META[channelType]) {
        throw new Error('请选择有效的通知渠道');
    }
    if (!configName) {
        throw new Error('配置名称不能为空');
    }

    const config = {};
    card.querySelectorAll('.notify-channel-field').forEach(field => {
        const key = String(field.getAttribute('data-field-key') || '').trim();
        if (!key) return;
        const rawValue = String(field.value || '').trim();
        if (!rawValue) return;
        if (key === 'headers') {
            try {
                const parsed = JSON.parse(rawValue);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                    config[key] = parsed;
                } else {
                    throw new Error('请求头必须是 JSON 对象');
                }
            } catch (error) {
                throw new Error(`请求头格式错误：${error.message}`);
            }
            return;
        }
        config[key] = rawValue;
    });

    if (boundTask) {
        config.bound_task = boundTask;
    }

    return {
        configId,
        payload: {
            channel_type: channelType,
            name: configName,
            config,
            is_enabled: isEnabled,
            notify_on_recommend: notifyOnRecommend,
            notify_on_complete: notifyOnComplete,
        },
    };
}

function getNotificationCardInfo(card) {
    const channelType = String(card.getAttribute('data-channel-type') || '').trim();
    const configId = String(card.getAttribute('data-config-id') || '').trim();
    const boundTask = String(card.getAttribute('data-bound-task') || '').trim();
    return { channelType, configId, boundTask };
}

function getNotificationErrorMessage(error, fallback = '操作失败') {
    if (error && typeof error === 'object' && typeof error.message === 'string' && error.message.trim()) {
        return error.message;
    }
    if (typeof error === 'string' && error.trim()) {
        return error;
    }
    return fallback;
}

function setNotificationCardCollapsed(card, collapsed) {
    if (!card) return;
    const shouldCollapse = Boolean(collapsed);
    card.classList.toggle('is-collapsed', shouldCollapse);
    const collapseButton = card.querySelector('.notify-collapse-btn');
    if (collapseButton) {
        collapseButton.textContent = shouldCollapse ? '展开' : '收起';
    }
}

async function fetchNotificationUserProfile() {
    try {
        const response = await fetch('/api/users/me');
        if (!response.ok) return null;
        return await response.json();
    } catch (_) {
        return null;
    }
}

async function fetchNotificationTaskContext() {
    try {
        const response = await fetch('/api/tasks');
        if (!response.ok) return { taskItems: [] };
        const tasks = await response.json();
        if (!Array.isArray(tasks)) return { taskItems: [] };

        const dedup = new Map();
        tasks.forEach(task => {
            const taskName = String(task?.task_name || task?.name || '').trim();
            if (!taskName || dedup.has(taskName)) return;
            dedup.set(taskName, {
                task_name: taskName,
                keyword: String(task?.keyword || '').trim(),
            });
        });
        return { taskItems: Array.from(dedup.values()) };
    } catch (_) {
        return { taskItems: [] };
    }
}

async function sendNotificationConfigTest(card, testType) {
    const { channelType, configId, boundTask } = getNotificationCardInfo(card);
    if (!channelType) {
        Notification.warning('请先选择通知渠道');
        return;
    }

    const endpointMap = {
        completion: '/api/notifications/test-task-completion',
        product: '/api/notifications/test-product',
    };
    const endpoint = endpointMap[testType] || endpointMap.product;

    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            channel: channelType,
            config_id: configId || null,
            bound_task: boundTask || null,
        }),
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.detail || '测试通知失败');
    }
    if (result.success === false) {
        throw new Error(result.message || '测试通知失败');
    }
    return result;
}

function getCurrentNotificationTabKey(serverRoot) {
    const visibleCard = Array.from(serverRoot.querySelectorAll('.notification-channel-card'))
        .find(card => !card.hidden);
    if (!visibleCard) {
        return '';
    }
    return String(visibleCard.getAttribute('data-channel-panel') || '__general__');
}

function activateNotificationTabByKey(serverRoot, targetKey) {
    const key = String(targetKey || '').trim();
    if (!key) return;

    const cards = Array.from(serverRoot.querySelectorAll('.notification-channel-card'));
    const tabs = Array.from(serverRoot.querySelectorAll('.notification-tab'));
    if (!cards.length || !tabs.length) return;

    const targetIndex = cards.findIndex(card => {
        const cardKey = String(card.getAttribute('data-channel-panel') || '__general__');
        return cardKey === key;
    });
    if (targetIndex < 0 || !tabs[targetIndex]) return;
    tabs[targetIndex].click();
}

async function ensureConfigPersistedForTesting(card) {
    const { configId, payload } = parseNotificationCardPayload(card);
    if (configId) {
        await updateMyNotificationConfig(configId, payload);
        return configId;
    }
    const created = await createMyNotificationConfig(payload);
    const savedConfig = created?.config || {};
    const newConfigId = String(savedConfig.id || '').trim();
    if (!newConfigId) {
        throw new Error(created?.message || '测试前自动保存失败');
    }
    card.setAttribute('data-config-id', newConfigId);
    setNotificationCardCollapsed(card, false);
    return newConfigId;
}

async function renderServerNotificationView(notificationContainer, options = {}) {
    const activeTabKey = String(options.activeTabKey || '').trim();
    const [configsResp, taskContext] = await Promise.all([
        fetchMyNotificationConfigs(),
        fetchNotificationTaskContext(),
    ]);
    const configs = Array.isArray(configsResp?.configs) ? configsResp.configs : [];
    const taskItems = taskContext.taskItems || [];

    notificationContainer.innerHTML = renderServerNotificationSettings(
        configs,
        taskItems
    );
    setupNotificationTabs();

    const serverRoot = notificationContainer.querySelector('#notification-server-root');
    if (!serverRoot) return;

    const refreshButton = serverRoot.querySelector('#refresh-notification-config-btn');
    const addButtons = serverRoot.querySelectorAll('.add-channel-config-btn');
    activateNotificationTabByKey(serverRoot, activeTabKey);

    addButtons.forEach(button => {
        button.addEventListener('click', () => {
            const channelType = String(button.getAttribute('data-channel') || '').trim();
            if (!NOTIFICATION_CHANNEL_META[channelType]) return;
            const listContainer = serverRoot.querySelector(`.notification-channel-config-list[data-channel="${channelType}"]`);
            if (!listContainer) return;
            const emptyState = listContainer.querySelector(`.notification-empty-state[data-empty-channel="${channelType}"]`);
            if (emptyState) {
                emptyState.remove();
            }
            const newCard = renderNotificationConfigCard(
                createEmptyNotificationConfig(channelType, ''),
                channelType,
                taskItems,
                ''
            );
            listContainer.insertAdjacentHTML('beforeend', newCard);
        });
    });

    if (refreshButton) {
        refreshButton.addEventListener('click', async () => {
            const currentTabKey = getCurrentNotificationTabKey(serverRoot);
            await renderServerNotificationView(notificationContainer, { activeTabKey: currentTabKey });
        });
    }

    serverRoot.addEventListener('input', (event) => {
        const nameInput = event.target.closest('.notify-config-name');
        if (!nameInput) return;
        const card = nameInput.closest('.notification-config-item');
        const title = card?.querySelector('.notification-config-header h4');
        if (title) {
            const nextTitle = String(nameInput.value || '').trim();
            title.textContent = nextTitle || '未命名通知配置';
        }
    });
    serverRoot.addEventListener('change', (event) => {
        const taskSelect = event.target.closest('.notify-bound-task-select');
        if (!taskSelect) return;
        const card = taskSelect.closest('.notification-config-item');
        if (!card) return;
        const boundTask = String(taskSelect.value || '').trim();
        card.setAttribute('data-bound-task', boundTask);
        const badge = card.querySelector('.notification-bound-task-badge');
        if (badge) {
            const boundTaskText = boundTask || '未绑定任务（全局默认）';
            badge.textContent = `绑定任务：${boundTaskText}`;
        }
    });

    serverRoot.addEventListener('click', async (event) => {
        const collapseButton = event.target.closest('.notify-collapse-btn');
        if (collapseButton) {
            const card = event.target.closest('.notification-config-item');
            if (!card) return;
            const collapsed = !card.classList.contains('is-collapsed');
            setNotificationCardCollapsed(card, collapsed);
            return;
        }

        const saveButton = event.target.closest('.notify-save-config-btn');
        const deleteButton = event.target.closest('.notify-delete-config-btn');
        const testButton = event.target.closest('.notify-test-config-btn');
        if (!saveButton && !deleteButton && !testButton) return;

        const card = event.target.closest('.notification-config-item');
        if (!card) return;

        if (saveButton) {
            try {
                const { configId, payload } = parseNotificationCardPayload(card);
                saveButton.disabled = true;
                const originalText = saveButton.textContent;
                saveButton.textContent = '保存中...';
                const currentTabKey = getCurrentNotificationTabKey(serverRoot);

                let savedResult = null;
                if (configId) {
                    savedResult = await updateMyNotificationConfig(configId, payload);
                } else {
                    savedResult = await createMyNotificationConfig(payload);
                }

                const savedConfig = savedResult?.config || {};
                const savedId = String(savedConfig.id || configId || '').trim();
                if (savedId) {
                    card.setAttribute('data-config-id', savedId);
                }

                Notification.success('通知配置保存成功');
                setNotificationCardCollapsed(card, true);
                activateNotificationTabByKey(serverRoot, currentTabKey);
            } catch (error) {
                Notification.error(getNotificationErrorMessage(error, '保存通知配置失败'));
            } finally {
                saveButton.disabled = false;
                saveButton.textContent = '保存配置';
            }
            return;
        }

        if (deleteButton) {
            const configId = String(card.getAttribute('data-config-id') || '').trim();
            const channelType = String(card.getAttribute('data-channel-type') || '').trim();
            const listContainer = card.closest('.notification-channel-config-list');
            if (!configId) {
                card.remove();
                if (listContainer && !listContainer.querySelector('.notification-config-item')) {
                    listContainer.innerHTML = renderChannelEmptyState(channelType);
                }
                return;
            }

            const confirmResult = await Notification.confirmDelete('确定删除该通知配置吗？');
            if (!confirmResult.isConfirmed) return;

            try {
                await deleteMyNotificationConfig(configId);
                Notification.success('通知配置已删除');
                card.remove();
                if (listContainer && !listContainer.querySelector('.notification-config-item')) {
                    listContainer.innerHTML = renderChannelEmptyState(channelType);
                }
            } catch (error) {
                Notification.error(getNotificationErrorMessage(error, '删除通知配置失败'));
            }
            return;
        }

        if (testButton) {
            const testType = String(testButton.getAttribute('data-test-type') || 'product').trim();
            const originText = testButton.textContent;
            try {
                testButton.disabled = true;
                testButton.textContent = '测试中...';
                await ensureConfigPersistedForTesting(card);
                const result = await sendNotificationConfigTest(card, testType);
                Notification.success(result?.message || '测试通知发送成功');
            } catch (error) {
                Notification.error(getNotificationErrorMessage(error, '测试通知发送失败'));
            } finally {
                testButton.disabled = false;
                testButton.textContent = originText;
            }
        }
    });
}

async function initializeLocalNotificationsView(notificationContainer) {
    const notificationSettings = await fetchNotificationSettings();
    if (notificationSettings === null) {
        notificationContainer.innerHTML = '<p>加载通知配置失败。请检查服务器是否正常运行。</p>';
        return;
    }

    notificationContainer.innerHTML = renderNotificationSettings(notificationSettings);
    setupNotificationTabs();

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

    async function saveNotificationSettingsNow() {
        const notificationForm = document.getElementById('notification-settings-form');
        if (!notificationForm) return;
        const settings = buildNotificationSettingsPayload(notificationForm);
        await updateNotificationSettings(settings);
    }

    function buildNotificationSettingsPayload(notificationForm) {
        const formData = new FormData(notificationForm);
        const settings = {};

        for (let [key, value] of formData.entries()) {
            if (key === 'PCURL_TO_MOBILE' || key === 'NOTIFY_AFTER_TASK_COMPLETE' || key.endsWith('_ENABLED')) {
                settings[key] = value === 'on';
            } else {
                settings[key] = value || '';
            }
        }

        notificationForm.querySelectorAll('input[type="checkbox"][name]').forEach((checkbox) => {
            const key = checkbox.name;
            if (key === 'PCURL_TO_MOBILE' || key === 'NOTIFY_AFTER_TASK_COMPLETE' || key.endsWith('_ENABLED')) {
                settings[key] = checkbox.checked;
            }
        });

        return settings;
    }

    const notificationForm = document.getElementById('notification-settings-form');
    if (!notificationForm) return;

    notificationForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const settings = buildNotificationSettingsPayload(notificationForm);
        const saveBtn = notificationForm.querySelector('button[type="submit"]');
        const originalText = saveBtn.textContent;
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';

        const result = await updateNotificationSettings(settings);
        if (result) {
            Notification.success(result.message || '通知设置已保存！');
        }

        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
    });

    notificationForm.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', saveNotificationSettingsNow);
    });

    const testButtons = notificationForm.querySelectorAll('.test-notification-btn');
    testButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const settings = buildNotificationSettingsPayload(notificationForm);
            const saveResult = await updateNotificationSettings(settings);
            if (!saveResult) {
                Notification.error('保存设置失败，请先检查设置是否正确。');
                return;
            }

            const channel = button.dataset.channel;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = '测试中...';

            try {
                const response = await fetch('/api/notifications/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ channel }),
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok || result.success === false) {
                    throw new Error(result.detail || result.message || '未知错误');
                }
                Notification.success(result.message || '测试通知发送成功！');
            } catch (error) {
                Notification.error(`测试通知发送失败: ${error.message}`);
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        });
    });

    const testTaskCompletionButtons = notificationForm.querySelectorAll('.test-task-completion-btn');
    testTaskCompletionButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const settings = buildNotificationSettingsPayload(notificationForm);
            const saveResult = await updateNotificationSettings(settings);
            if (!saveResult) {
                Notification.error('保存设置失败，请先检查设置是否正确。');
                return;
            }

            const channel = button.dataset.channel;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = '测试中...';

            try {
                const response = await fetch('/api/notifications/test-task-completion', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ channel }),
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok || result.success === false) {
                    throw new Error(result.detail || result.message || '未知错误');
                }
                Notification.success(result.message || '测试任务完成通知发送成功！');
            } catch (error) {
                Notification.error(`测试任务完成通知发送失败: ${error.message}`);
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        });
    });
}

async function initializeNotificationsView() {
    const notificationContainer = document.getElementById('notification-settings-container');
    if (!notificationContainer) return;

    const profile = await fetchNotificationUserProfile();
    const isMultiUserMode = Boolean(profile?.is_multi_user_mode);

    try {
        if (isMultiUserMode) {
            await renderServerNotificationView(notificationContainer);
        } else {
            await initializeLocalNotificationsView(notificationContainer);
        }
    } catch (error) {
        notificationContainer.innerHTML = '<p>加载通知配置失败。请检查服务器是否正常运行。</p>';
        Notification.error(error.message || '加载通知配置失败');
    }
}

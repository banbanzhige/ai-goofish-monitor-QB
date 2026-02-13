// 用户数据视图模块 - v1.0.1
// 提供卡片式用户列表、Tab切换（所有用户/我的资料）、头像上传、密码修改等功能

var usersViewInitialized = false;
var currentUserProfile = null;
var currentUserId = '';
var currentPagePermissions = null;
var userCardDataMap = {};
var currentEditingUser = null;
var currentGroupList = [];
var currentAssetsSnapshot = null;

const GROUP_PERMISSION_CATEGORIES = ['tasks', 'results', 'accounts', 'notify', 'ai', 'admin'];
const GROUP_PERMISSION_LABELS = {
    tasks: '任务',
    results: '结果',
    accounts: '账号',
    notify: '通知',
    ai: 'AI',
    admin: '管理'
};

const GROUP_CODE_LABELS = {
    super_admin_group: '超级管理员组',
    admin_group: '系统管理员组',
    operator_group: '操作员组',
    viewer_group: '查看者组'
};

const PAGE_LABELS = {
    tasks: '任务管理',
    accounts: '账号管理',
    scheduled: '定时任务',
    results: '结果查看',
    logs: '运行日志',
    notifications: '通知配置',
    'model-management': '模型管理',
    settings: '系统设置',
    'user-data': '用户数据'
};

function getDisplayLabel(code, labelMap) {
    const normalizedCode = String(code || '').trim();
    if (!normalizedCode) return '';
    const lowerCode = normalizedCode.toLowerCase();
    return labelMap[normalizedCode] || labelMap[lowerCode] || '';
}

function syncLoginStatusWidgetAvatar(avatarUrl) {
    if (!avatarUrl) return;
    if (typeof refreshLoginStatusWidget === 'function') {
        refreshLoginStatusWidget();
    }
}

function renderLabelWithCode(code, labelMap) {
    const normalizedCode = String(code || '').trim();
    if (!normalizedCode) {
        return '-';
    }
    const label = getDisplayLabel(normalizedCode, labelMap);
    if (!label) {
        return `<code>${escapeHtml(normalizedCode)}</code>`;
    }
    return `
        <span>${escapeHtml(label)}</span>
        <div class="rbac-subtext"><code>${escapeHtml(normalizedCode)}</code></div>
    `;
}

function getGroupTagClassByCode(groupCode) {
    const code = String(groupCode || '').toLowerCase();
    if (code === 'super_admin_group') return 'group-tag-super-admin';
    if (code === 'admin_group') return 'role-admin';
    if (code === 'operator_group') return 'role-operator';
    if (code === 'viewer_group') return 'role-viewer';
    return 'group-tag-custom';
}

function renderGroupNameBadge(group) {
    if (!group) return '';
    const label = String(group.name || '').trim() || getDisplayLabel(group.code, GROUP_CODE_LABELS) || String(group.code || '').trim() || '未命名组';
    const tagClass = getGroupTagClassByCode(group.code || '');
    return `<span class="role-badge ${tagClass}">${escapeHtml(label)}</span>`;
}

function renderGroupBadges(groupList) {
    const groups = Array.isArray(groupList) ? groupList : [];
    if (!groups.length) return '无';
    const badges = groups.map(group => renderGroupNameBadge(group)).filter(Boolean).join('');
    return `<div class="rbac-role-badges">${badges}</div>`;
}

function getPagePermissionCategory(pageName) {
    const map = {
        tasks: 'tasks',
        scheduled: 'tasks',
        results: 'results',
        logs: 'results',
        accounts: 'accounts',
        notifications: 'notify',
        'model-management': 'ai',
        settings: 'admin',
        'user-data': null
    };
    return Object.prototype.hasOwnProperty.call(map, pageName) ? map[pageName] : '__UNMAPPED__';
}

function isGroupAllowedForPage(group, pageName) {
    const requiredCategory = getPagePermissionCategory(pageName);
    if (requiredCategory === '__UNMAPPED__') return false;
    if (requiredCategory === null) return true;
    const permissionMap = normalizeGroupPermissions(group);
    return Boolean(permissionMap[requiredCategory]);
}

function renderGroupIdentifierBadge(group) {
    const code = String(group?.code || '').trim();
    if (!code) return '-';
    const label = getDisplayLabel(code, GROUP_CODE_LABELS) || code;
    const tagClass = getGroupTagClassByCode(code);
    return `
        <div class="rbac-inline-meta">
            <span class="role-badge ${tagClass}">${escapeHtml(label)}</span>
            <code>${escapeHtml(code)}</code>
        </div>
    `;
}

// ============== API 鍑芥暟 ==============

async function fetchUsers(skip = 0, limit = 50) {
    try {
        const response = await fetch(`/api/users?skip=${skip}&limit=${limit}`);
        if (!response.ok) {
            if (response.status === 403) {
                return { error: 'forbidden', message: '无权访问用户管理' };
            }
            throw new Error('获取用户列表失败');
        }
        return await response.json();
    } catch (error) {
        console.error('获取用户列表错误:', error);
        return { error: true, message: error.message };
    }
}

async function fetchMyProfile() {
    try {
        const response = await fetch('/api/users/me');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取用户信息错误:', error);
        return null;
    }
}

async function fetchPagePermissions() {
    try {
        const response = await fetch('/api/users/page-permissions');
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('获取页面权限错误:', error);
        return null;
    }
}

async function fetchMyAssets() {
    try {
        const response = await fetch('/api/users/me/assets');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || '获取用户资产失败');
        }
        return data;
    } catch (error) {
        console.error('获取用户资产错误:', error);
        throw error;
    }
}

async function fetchGroups() {
    try {
        const response = await fetch('/api/groups');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || '获取用户组失败');
        }
        return data.groups || [];
    } catch (error) {
        console.error('获取用户组错误:', error);
        throw error;
    }
}

async function createGroup(payload) {
    const response = await fetch('/api/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '创建用户组失败');
    }
    return data;
}

async function updateGroup(groupId, payload) {
    const response = await fetch(`/api/groups/${groupId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '更新用户组失败');
    }
    return data;
}

async function deleteGroup(groupId) {
    const response = await fetch(`/api/groups/${groupId}`, {
        method: 'DELETE'
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '删除用户组失败');
    }
    return data;
}

async function updateGroupPermissions(groupId, categories) {
    const response = await fetch(`/api/groups/${groupId}/permissions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categories })
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '更新用户组权限失败');
    }
    return data;
}

async function setUserGroups(userId, groupIds) {
    const response = await fetch(`/api/users/${userId}/groups`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_ids: groupIds || [] })
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '设置用户组失败');
    }
    return data;
}

async function fetchMyAvatar() {
    try {
        const response = await fetch('/api/users/me/avatar');
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('获取头像错误:', error);
        return null;
    }
}

async function uploadAvatar(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/users/me/avatar', {
        method: 'POST',
        body: formData
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '涓婁紶澶村儚澶辫触');
    }
    return data;
}

async function updateMyProfile(profileData) {
    const response = await fetch('/api/users/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileData)
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '更新资料失败');
    }
    return data;
}

async function changeMyPassword(passwordData) {
    const response = await fetch('/api/users/me/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passwordData)
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '修改密码失败');
    }
    return data;
}

async function resetUserPassword(userId, passwordData) {
    const response = await fetch(`/api/users/${userId}/password`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passwordData)
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || '重置用户密码失败');
    }
    return data;
}

async function createUser(userData) {
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || '创建用户失败');
        }
        return data;
    } catch (error) {
        console.error('创建用户错误:', error);
        throw error;
    }
}

async function updateUser(userId, userData) {
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || '更新用户失败');
        }
        return data;
    } catch (error) {
        console.error('更新用户错误:', error);
        throw error;
    }
}

async function deleteUserApi(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || '删除用户失败');
        }
        return data;
    } catch (error) {
        console.error('删除用户错误:', error);
        throw error;
    }
}

// ============== 宸ュ叿鍑芥暟 ==============

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getAvatarColor(username) {
    const colors = [
        '#722ed1', '#1890ff', '#52c41a', '#fa8c16',
        '#eb2f96', '#13c2c2', '#2f54eb', '#fa541c'
    ];
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
}

function getRoleInfo(role) {
    const roleMap = {
        'super_admin': { text: '超级管理员', class: 'role-super-admin', color: 'linear-gradient(135deg, #722ed1, #eb2f96)' },
        'admin': { text: '系统管理员', class: 'role-admin', color: '#722ed1' },
        'operator': { text: '操作员', class: 'role-operator', color: '#1890ff' },
        'viewer': { text: '查看员', class: 'role-viewer', color: '#8c8c8c' }
    };
    return roleMap[role] || { text: role, class: 'role-viewer', color: '#8c8c8c' };
}

function normalizeUserGroups(groups) {
    if (!Array.isArray(groups)) return [];
    return groups
        .filter(group => group && (group.id || group.code || group.name))
        .map(group => ({
            id: group.id ? String(group.id) : '',
            code: group.code ? String(group.code) : '',
            name: group.name ? String(group.name) : ''
        }));
}

function getGroupPriority(group) {
    const code = String(group?.code || '').toLowerCase();
    const levelMap = {
        super_admin_group: 4,
        admin_group: 3,
        operator_group: 2,
        viewer_group: 1
    };
    return levelMap[code] || 0;
}

function getPrimaryGroup(user) {
    const groups = normalizeUserGroups(user?.groups);
    if (!groups.length) return null;
    const sorted = [...groups].sort((left, right) => getGroupPriority(right) - getGroupPriority(left));
    return sorted[0];
}

function getGroupBadgeInfo(user) {
    const primaryGroup = getPrimaryGroup(user);
    if (!primaryGroup) {
        return getRoleInfo(normalizeUserRole(user?.role));
    }

    const groupCode = String(primaryGroup.code || '').toLowerCase();
    const systemGroupMap = {
        super_admin_group: { text: primaryGroup.name || '超级管理员组', class: 'group-tag-super-admin', color: '#ff4d4f' },
        admin_group: { text: primaryGroup.name || '系统管理员组', class: 'role-admin', color: '#722ed1' },
        operator_group: { text: primaryGroup.name || '操作员组', class: 'role-operator', color: '#1890ff' },
        viewer_group: { text: primaryGroup.name || '查看者组', class: 'role-viewer', color: '#8c8c8c' }
    };
    return systemGroupMap[groupCode] || {
        text: primaryGroup.name || primaryGroup.code || '用户组',
        class: 'role-operator',
        color: '#1890ff'
    };
}

function hasAdminPrivilege(profile) {
    if (!profile || !profile.is_multi_user_mode) return false;
    if (Array.isArray(profile.categories) && profile.categories.includes('admin')) {
        return true;
    }
    return Number(profile.management_level || 0) >= 3;
}

function hasSuperAdminPrivilege(profile) {
    if (!profile || !profile.is_multi_user_mode) return false;
    return Number(profile.management_level || 0) >= 4;
}

function getUserId(user) {
    return String(user?.id || user?.user_id || '');
}

function normalizeUserRole(role) {
    if (role === 'super-admin') {
        return 'super_admin';
    }
    return role || 'viewer';
}

function isSameUserId(left, right) {
    return String(left || '') === String(right || '');
}

// ============== 鍗＄墖娓叉煋 ==============

function renderUserCard(user, options = {}) {
    const canManage = Boolean(options.canManage);
    const activeUserId = String(options.activeUserId || '');
    const userId = getUserId(user);
    const groupInfo = getGroupBadgeInfo(user);
    const primaryGroup = getPrimaryGroup(user);
    const statusClass = user.is_active ? 'status-active' : 'status-inactive';
    const statusText = user.is_active ? '激活' : '禁用';
    const lastLogin = user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '从未登录';
    const initial = (user.username || 'U')[0].toUpperCase();
    const avatarColor = getAvatarColor(user.username || 'U');
    const avatarUrl = user.avatar_url || null;

    const avatarHtml = avatarUrl
        ? `<img src="${avatarUrl}" alt="${escapeHtml(user.username)}" class="mp-avatar-img">`
        : `<div class="mp-avatar-placeholder" style="background: ${avatarColor}">${initial}</div>`;
    const isCurrentUser = Boolean(user.is_current_user);
    const isSelected = isSameUserId(activeUserId, userId);

    // 操作按钮区
    let actionButtons = '';
    if (canManage && userId && !isCurrentUser) {
        actionButtons = `
            <div class="mp-card-actions">
                <button class="mp-action-btn edit-user-btn" data-user-id="${userId}" title="缂栬緫">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                    </svg>
                </button>
                <button class="mp-action-btn delete-user-btn" data-user-id="${userId}" title="删除">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        `;
    }

    return `
        <div class="mp-user-card ${isCurrentUser ? 'is-self-card' : ''} ${isSelected ? 'is-selected' : ''}" data-user-id="${userId}" data-group-code="${escapeHtml(primaryGroup?.code || '')}">
            <div class="mp-card-top">
                <div class="mp-avatar-wrapper">
                    ${isCurrentUser ? `<div class="mp-crown-icon">👑</div>` : ''}
                    ${avatarHtml}
                </div>
                <div class="mp-card-header">
                    <div class="mp-username-row">
                        <span class="mp-username">${escapeHtml(user.username)}</span>
                        ${actionButtons}
                    </div>
                    <div class="mp-badges-row">
                        <span class="mp-role-badge ${groupInfo.class}">${groupInfo.text}</span>
                        <span class="mp-status-badge ${statusClass}">${statusText}</span>
                    </div>
                </div>
            </div>
            <div class="mp-card-body">
                <div class="mp-info-row">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                        <polyline points="22,6 12,13 2,6"></polyline>
                    </svg>
                    <span class="mp-email">${escapeHtml(user.email || '未设置邮箱')}</span>
                </div>
                <div class="mp-info-row mp-login-row">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    <span class="mp-last-login">${lastLogin}</span>
                </div>
            </div>
            ${canManage && userId && !isCurrentUser ? `
            <div class="mp-card-footer">
                <button class="mp-toggle-btn toggle-user-btn ${user.is_active ? 'is-active' : ''}" data-user-id="${userId}" data-active="${user.is_active}">
                    ${user.is_active ? '禁用账号' : '启用账号'}
                </button>
            </div>
            ` : ''}
        </div>
    `;
}

function renderUsersCards(container, users, options = {}) {
    if (!container) return;
    const canManage = Boolean(options.canManage);
    const currentUserIdValue = String(options.currentUserId || '');
    const activeUserId = String(options.activeUserId || '');
    const currentProfile = options.currentProfile || null;

    if (!users || users.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无用户数据</p>';
        userCardDataMap = {};
        return;
    }

    // 为事件处理缓存用户数据，避免通过 DOM 文本反推角色造成数据误判
    userCardDataMap = {};
    const normalizedUsers = users.map(user => {
        const normalized = {
            ...user,
            id: getUserId(user),
            role: normalizeUserRole(user.role),
            groups: normalizeUserGroups(user.groups)
        };
        normalized.is_current_user = isSameUserId(normalized.id, currentUserIdValue);
        if (normalized.is_current_user && currentProfile?.avatar_url && !normalized.avatar_url) {
            normalized.avatar_url = currentProfile.avatar_url;
        }
        userCardDataMap[normalized.id] = normalized;
        return normalized;
    });

    // 当前用户排在第一位
    normalizedUsers.sort((a, b) => {
        if (a.is_current_user && !b.is_current_user) return -1;
        if (!a.is_current_user && b.is_current_user) return 1;
        return 0;
    });

    const cards = normalizedUsers
        .map(user => renderUserCard(user, { canManage, activeUserId }))
        .join('');
    container.innerHTML = `<div class="user-cards-grid">${cards}</div>`;
}

// ============== 我的资料渲染 ==============

function renderMyProfile(container, profile) {
    if (!container || !profile) return;

    const groupInfo = getGroupBadgeInfo(profile);
    const initial = (profile.username || 'U')[0].toUpperCase();
    const avatarColor = getAvatarColor(profile.username || 'U');
    const avatarUrl = profile.avatar_url || null;
    const isMultiUser = profile.is_multi_user_mode;

    container.innerHTML = `
        <div class="my-profile-container">
            <div class="profile-section">
                <h3>个人头像</h3>
                <div class="avatar-upload-area">
                    <div class="avatar-preview" id="avatar-preview">
                        ${avatarUrl
            ? `<img src="${avatarUrl}" alt="我的头像" class="user-avatar-img large">`
            : `<div class="user-avatar large" style="background: ${avatarColor}">${initial}</div>`
        }
                        <div class="avatar-upload-overlay" id="avatar-upload-trigger">
                            <span>📷 更换头像</span>
                        </div>
                    </div>
                    <input type="file" id="avatar-file-input" accept="image/jpeg,image/png,image/gif,image/webp" style="display: none;">
                    <p class="avatar-hint">支持 JPG/PNG/GIF/WEBP，最大 2MB</p>
                </div>
            </div>
            
            <div class="profile-section">
                <h3>基本信息</h3>
                <div class="profile-info-grid">
                    <div class="profile-info-item">
                        <label>用户名</label>
                        <div class="profile-info-value">${escapeHtml(profile.username)}</div>
                    </div>
                    <div class="profile-info-item">
                        <label>用户组</label>
                        <div class="profile-info-value">
                            <span class="role-badge ${groupInfo.class}" style="background: ${groupInfo.color}">${groupInfo.text}</span>
                        </div>
                    </div>
                    <div class="profile-info-item">
                        <label>邮箱</label>
                        <div class="profile-info-value editable" id="profile-email-display">
                            ${escapeHtml(profile.email || '未设置')}
                            ${isMultiUser ? '<button class="edit-inline-btn" id="edit-email-btn">✏️</button>' : ''}
                        </div>
                        <div class="profile-info-edit" id="profile-email-edit" style="display: none;">
                            <input type="email" id="new-email-input" value="${escapeHtml(profile.email || '')}" placeholder="请输入邮箱">
                            <button class="control-button small-btn success-btn" id="save-email-btn">保存</button>
                            <button class="control-button small-btn" id="cancel-email-btn">取消</button>
                        </div>
                    </div>
                </div>
            </div>
            
            ${isMultiUser ? `
            <div class="profile-section">
                <h3>修改密码</h3>
                <div class="password-change-form">
                    <div class="form-group">
                        <label>当前密码</label>
                        <input type="password" id="old-password-input" placeholder="请输入当前密码">
                    </div>
                    <div class="form-group">
                        <label>新密码</label>
                        <input type="password" id="new-password-input" placeholder="请输入新密码（至少6位）">
                    </div>
                    <div class="form-group">
                        <label>确认新密码</label>
                        <input type="password" id="confirm-password-input" placeholder="请再次输入新密码">
                    </div>
                    <button class="control-button primary-btn" id="change-password-btn">修改密码</button>
                </div>
            </div>
            ` : `
            <div class="profile-section">
                <h3>修改密码</h3>
                <p class="hint-text">本地模式请直接修改 .env 文件中的 WEB_PASSWORD 配置项</p>
            </div>
            `}
        </div>
    `;

    // 绑定事件
    attachProfileEventListeners(container, profile);
}

function attachProfileEventListeners(container, profile) {
    // 头像上传触发
    const uploadTrigger = container.querySelector('#avatar-upload-trigger');
    const fileInput = container.querySelector('#avatar-file-input');

    if (uploadTrigger && fileInput) {
        uploadTrigger.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // 检查文件大小
            if (file.size > 2 * 1024 * 1024) {
                Notification.error('图片大小不能超过 2MB');
                return;
            }

            try {
                const result = await uploadAvatar(file);
                Notification.success('头像上传成功');
                if (currentUserProfile && result.avatar_url) {
                    currentUserProfile.avatar_url = result.avatar_url;
                }
                // 更新头像显示
                const preview = container.querySelector('#avatar-preview');
                if (preview && result.avatar_url) {
                    preview.innerHTML = `
                        <img src="${result.avatar_url}" alt="我的头像" class="user-avatar-img large">
                        <div class="avatar-upload-overlay" id="avatar-upload-trigger">
                            <span>📷 更换头像</span>
                        </div>
                    `;
                    // 重新绑定点击事件
                    preview.querySelector('#avatar-upload-trigger').addEventListener('click', () => fileInput.click());
                }

                // 同步更新卡片区当前用户头像
                if (currentUserId && result.avatar_url) {
                    const userCard = document.querySelector(`.mp-user-card[data-user-id="${currentUserId}"]`);
                    if (userCard) {
                        const cardAvatar = userCard.querySelector('.mp-avatar-img');
                        if (cardAvatar) {
                            cardAvatar.src = result.avatar_url;
                        } else {
                            const avatarWrap = userCard.querySelector('.mp-avatar-wrapper');
                            if (avatarWrap) {
                                const crownHtml = avatarWrap.querySelector('.mp-crown-icon')?.outerHTML || '';
                                avatarWrap.innerHTML = `${crownHtml}<img src="${result.avatar_url}" alt="我的头像" class="mp-avatar-img">`;
                            }
                        }
                    }
                }
                syncLoginStatusWidgetAvatar(result.avatar_url);
            } catch (error) {
                Notification.error(error.message);
            }
        });
    }

    // 閭缂栬緫
    const editEmailBtn = container.querySelector('#edit-email-btn');
    const emailDisplay = container.querySelector('#profile-email-display');
    const emailEdit = container.querySelector('#profile-email-edit');
    const saveEmailBtn = container.querySelector('#save-email-btn');
    const cancelEmailBtn = container.querySelector('#cancel-email-btn');

    if (editEmailBtn) {
        editEmailBtn.addEventListener('click', () => {
            emailDisplay.style.display = 'none';
            emailEdit.style.display = 'flex';
        });
    }

    if (cancelEmailBtn) {
        cancelEmailBtn.addEventListener('click', () => {
            emailEdit.style.display = 'none';
            emailDisplay.style.display = 'flex';
        });
    }

    if (saveEmailBtn) {
        saveEmailBtn.addEventListener('click', async () => {
            const newEmail = container.querySelector('#new-email-input').value.trim();
            try {
                await updateMyProfile({ email: newEmail || null });
                Notification.success('邮箱更新成功');
                emailDisplay.innerHTML = `
                    ${escapeHtml(newEmail || '未设置')}
                    <button class="edit-inline-btn" id="edit-email-btn">✏️</button>
                `;
                emailEdit.style.display = 'none';
                emailDisplay.style.display = 'flex';
                // 重新绑定编辑按钮
                emailDisplay.querySelector('#edit-email-btn').addEventListener('click', () => {
                    emailDisplay.style.display = 'none';
                    emailEdit.style.display = 'flex';
                });
            } catch (error) {
                Notification.error(error.message);
            }
        });
    }

    // 修改密码
    const changePasswordBtn = container.querySelector('#change-password-btn');
    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', async () => {
            const oldPassword = container.querySelector('#old-password-input').value;
            const newPassword = container.querySelector('#new-password-input').value;
            const confirmPassword = container.querySelector('#confirm-password-input').value;

            if (!oldPassword || !newPassword) {
                Notification.warning('请填写当前密码和新密码');
                return;
            }

            if (newPassword.length < 6) {
                Notification.warning('新密码至少需要 6 位');
                return;
            }

            if (newPassword !== confirmPassword) {
                Notification.warning('两次输入的新密码不一致');
                return;
            }

            try {
                await changeMyPassword({ old_password: oldPassword, new_password: newPassword });
                Notification.success('密码修改成功');
                container.querySelector('#old-password-input').value = '';
                container.querySelector('#new-password-input').value = '';
                container.querySelector('#confirm-password-input').value = '';
            } catch (error) {
                Notification.error(error.message);
            }
        });
    }
}

// ============== 用户组管理渲染 ==============

function normalizeGroupPermissions(group) {
    const permissionMap = {};
    GROUP_PERMISSION_CATEGORIES.forEach(category => {
        permissionMap[category] = false;
    });
    (group.permissions || []).forEach(item => {
        if (item && item.category && Object.prototype.hasOwnProperty.call(permissionMap, item.category)) {
            permissionMap[item.category] = Boolean(item.enabled);
        }
    });
    return permissionMap;
}

function canEditSystemGroupPermissions() {
    return Number(currentUserProfile?.management_level || 0) >= 4;
}

function renderGroupPermissionChecks(group) {
    const permissionMap = normalizeGroupPermissions(group);
    const disableSystemEdit = Boolean(group?.is_system) && !canEditSystemGroupPermissions();
    return GROUP_PERMISSION_CATEGORIES.map(category => `
        <td>
            <label class="rbac-checkbox-wrap">
                <input type="checkbox"
                       data-kind="group-permission"
                       data-group-id="${group.id}"
                       data-category="${category}"
                       ${permissionMap[category] ? 'checked' : ''}
                       ${disableSystemEdit ? 'disabled' : ''}>
                <span></span>
            </label>
        </td>
    `).join('');
}

function buildGroupMatrixRows(groups) {
    return (groups || []).map(group => `
        <tr data-group-id="${group.id}">
            <td>${escapeHtml(group.name || '')}${group.is_system ? ' <span class="status-badge status-running">系统</span>' : ''}</td>
            <td>${renderGroupIdentifierBadge(group)}</td>
            <td>${Number(group.member_count || 0)}</td>
            ${renderGroupPermissionChecks(group)}
            <td>
                <div class="action-buttons">
                    <button type="button" class="control-button small-btn save-group-permissions-btn" data-group-id="${group.id}"
                        ${group.is_system && !canEditSystemGroupPermissions() ? 'disabled title="仅超级管理员可修改系统预置组权限"' : ''}>保存权限</button>
                    <button type="button" class="control-button small-btn ${group.is_system ? '' : 'danger-btn'} delete-group-btn" data-group-id="${group.id}" ${group.is_system ? 'disabled' : ''}>删除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function renderRbacReadonlySection(groups = []) {
    const pageNames = Object.keys(PAGE_LABELS);
    const pageRows = pageNames.map(pageName => {
        const allowedGroups = (groups || []).filter(group => isGroupAllowedForPage(group, pageName));
        return `
        <tr>
            <td>${escapeHtml(PAGE_LABELS[pageName] || pageName)}</td>
            <td><code>${escapeHtml(pageName)}</code></td>
            <td>${renderGroupBadges(allowedGroups)}</td>
        </tr>
    `;
    }).join('');

    return `
        <div class="rbac-section">
            <h4>高级视图（只读）</h4>
            <p class="rbac-hint">该视图仅用于审阅页面与用户组的生效关系，权限写入请使用上方用户组管理。</p>
            <div class="rbac-table-wrapper">
                <table class="rbac-table">
                    <thead>
                        <tr>
                            <th>页面名称</th>
                            <th>页面标识</th>
                            <th>允许用户组</th>
                        </tr>
                    </thead>
                    <tbody>${pageRows}</tbody>
                </table>
            </div>
        </div>
    `;
}
function refreshGroupManagementViews(container) {
    if (!container) return;

    const matrixBody = container.querySelector('#group-permission-matrix-body');
    if (matrixBody) {
        const rows = buildGroupMatrixRows(currentGroupList);
        matrixBody.innerHTML = rows || '<tr><td colspan="20">暂无用户组</td></tr>';
    }

    const readonlyContainer = container.querySelector('#rbac-readonly-container');
    if (readonlyContainer) {
        readonlyContainer.innerHTML = renderRbacReadonlySection(currentGroupList);
    }
}

async function refreshGroupManagementData(container) {
    const groups = await fetchGroups();
    currentGroupList = Array.isArray(groups) ? groups : [];
    refreshGroupManagementViews(container);
}

function renderGroupManagement(container, groups) {
    if (!container) return;
    const permissionHeaders = GROUP_PERMISSION_CATEGORIES
        .map(category => `<th>${escapeHtml(GROUP_PERMISSION_LABELS[category] || category)}</th>`)
        .join('');

    const rows = buildGroupMatrixRows(groups);

    container.innerHTML = `
        <div class="rbac-manager">
            <div class="rbac-header">
                <h3>用户组管理</h3>
            </div>
            <div class="rbac-section">
                <div class="rbac-create-shell">
                    <div class="rbac-create-toolbar">
                        <div class="rbac-create-title-wrap">
                            <h4>新建用户组</h4>
                            <p class="rbac-create-hint">点击“创建用户组”开始创建。</p>
                        </div>
                        <div class="rbac-create-buttons">
                            <button type="button" id="toggle-create-group-btn" class="control-button primary-btn">
                                <span id="toggle-create-group-btn-text">创建用户组</span>
                            </button>
                            <button type="button" id="reload-group-btn" class="control-button">重新加载</button>
                        </div>
                    </div>
                </div>
                <div id="create-group-form" class="rbac-create-form" style="display: none;">
                    <div class="profile-info-grid">
                        <div class="profile-info-item">
                            <label>组标识</label>
                            <input type="text" id="new-group-code" placeholder="例如：ops_group">
                        </div>
                        <div class="profile-info-item">
                            <label>组名称</label>
                            <input type="text" id="new-group-name" placeholder="例如：运营组">
                        </div>
                        <div class="profile-info-item">
                            <label>描述</label>
                            <input type="text" id="new-group-description" placeholder="可选">
                        </div>
                    </div>
                    <div class="rbac-create-form-actions">
                        <button type="button" id="create-group-btn" class="control-button primary-btn">确认创建</button>
                        <button type="button" id="cancel-create-group-btn" class="control-button">取消</button>
                    </div>
                </div>
            </div>
            <div class="rbac-section">
                <h4>组权限矩阵</h4>
                <div class="rbac-table-wrapper">
                    <table class="rbac-table">
                        <thead>
                            <tr>
                                <th>组名称</th>
                                <th>组标识</th>
                                <th>成员数</th>
                                ${permissionHeaders}
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="group-permission-matrix-body">${rows || '<tr><td colspan="20">暂无用户组</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
            <div id="rbac-readonly-container">${renderRbacReadonlySection(groups)}</div>
        </div>
    `;
}

async function loadGroupManagement(container) {
    if (!container) return;
    container.innerHTML = '<p>正在加载用户组配置...</p>';
    try {
        await refreshGroupManagementData(container);
        renderGroupManagement(container, currentGroupList);
        attachGroupManagementEventListeners(container);
    } catch (error) {
        container.innerHTML = `<p class="error-state">加载用户组管理失败: ${escapeHtml(error.message)}</p>`;
    }
}

function collectGroupPermissions(container, groupId) {
    const categories = {};
    GROUP_PERMISSION_CATEGORIES.forEach(category => {
        const input = container.querySelector(
            `input[data-kind="group-permission"][data-group-id="${groupId}"][data-category="${category}"]`
        );
        categories[category] = Boolean(input?.checked);
    });
    return categories;
}

function attachGroupManagementEventListeners(container) {
    const toggleCreateBtn = container.querySelector('#toggle-create-group-btn');
    const toggleCreateBtnText = container.querySelector('#toggle-create-group-btn-text');
    const createForm = container.querySelector('#create-group-form');
    const createBtn = container.querySelector('#create-group-btn');
    const cancelCreateBtn = container.querySelector('#cancel-create-group-btn');
    const reloadBtn = container.querySelector('#reload-group-btn');

    const setCreateFormVisible = (visible) => {
        if (!createForm) return;
        createForm.style.display = visible ? 'block' : 'none';
        if (toggleCreateBtn) {
            toggleCreateBtn.classList.toggle('is-active', visible);
            toggleCreateBtn.setAttribute('aria-expanded', visible ? 'true' : 'false');
        }
        if (toggleCreateBtnText) {
            toggleCreateBtnText.textContent = visible ? '收起表单' : '创建用户组';
        }
    };

    if (toggleCreateBtn && !toggleCreateBtn._listenerAttached) {
        toggleCreateBtn._listenerAttached = true;
        toggleCreateBtn.addEventListener('click', () => {
            const shouldShow = !createForm || createForm.style.display !== 'block';
            setCreateFormVisible(shouldShow);
            const codeInput = container.querySelector('#new-group-code');
            if (shouldShow && codeInput) codeInput.focus();
        });
    }

    if (cancelCreateBtn && !cancelCreateBtn._listenerAttached) {
        cancelCreateBtn._listenerAttached = true;
        cancelCreateBtn.addEventListener('click', () => {
            setCreateFormVisible(false);
        });
    }

    if (reloadBtn && !reloadBtn._listenerAttached) {
        reloadBtn._listenerAttached = true;
        reloadBtn.addEventListener('click', async () => {
            await refreshGroupManagementData(container);
            Notification.info('用户组配置已刷新');
        });
    }

    if (createBtn && !createBtn._listenerAttached) {
        createBtn._listenerAttached = true;
        createBtn.addEventListener('click', async () => {
            const code = (container.querySelector('#new-group-code')?.value || '').trim();
            const name = (container.querySelector('#new-group-name')?.value || '').trim();
            const description = (container.querySelector('#new-group-description')?.value || '').trim();
            if (!code || !name) {
                Notification.warning('请填写组标识和组名称');
                return;
            }
            const categories = {};
            GROUP_PERMISSION_CATEGORIES.forEach(category => {
                categories[category] = false;
            });
            try {
                const created = await createGroup({ code, name, description: description || null, permissions: categories });
                const createdGroup = created?.group;
                if (createdGroup) {
                    currentGroupList.push({
                        ...createdGroup,
                        member_count: Number(createdGroup.member_count || 0)
                    });
                } else {
                    await refreshGroupManagementData(container);
                }
                refreshGroupManagementViews(container);
                Notification.success('用户组创建成功');
                const codeInput = container.querySelector('#new-group-code');
                const nameInput = container.querySelector('#new-group-name');
                const descInput = container.querySelector('#new-group-description');
                if (codeInput) codeInput.value = '';
                if (nameInput) nameInput.value = '';
                if (descInput) descInput.value = '';
                setCreateFormVisible(false);
            } catch (error) {
                Notification.error(error.message || '创建用户组失败');
            }
        });
    }

    if (!container._groupActionDelegated) {
        container._groupActionDelegated = true;
        container.addEventListener('click', async (event) => {
            const saveBtn = event.target.closest('.save-group-permissions-btn');
            if (saveBtn) {
                const groupId = saveBtn.dataset.groupId;
                if (!groupId) return;
                const categories = collectGroupPermissions(container, groupId);
                try {
                    await updateGroupPermissions(groupId, categories);
                    const groupIndex = currentGroupList.findIndex(group => String(group.id) === String(groupId));
                    if (groupIndex >= 0) {
                        const permissions = GROUP_PERMISSION_CATEGORIES.map(category => ({
                            category,
                            enabled: Boolean(categories[category])
                        }));
                        currentGroupList[groupIndex] = {
                            ...currentGroupList[groupIndex],
                            permissions
                        };
                    }
                    refreshGroupManagementViews(container);
                    Notification.success('权限更新成功');
                } catch (error) {
                    Notification.error(error.message || '权限更新失败');
                }
                return;
            }

            const deleteBtn = event.target.closest('.delete-group-btn');
            if (!deleteBtn || deleteBtn.disabled) return;

            const groupId = deleteBtn.dataset.groupId;
            if (!groupId) return;
            const result = await Notification.confirmDelete('确定删除该用户组吗？');
            if (!result.isConfirmed) return;
            try {
                await deleteGroup(groupId);
                currentGroupList = currentGroupList.filter(group => String(group.id) !== String(groupId));
                refreshGroupManagementViews(container);
                Notification.success('用户组删除成功');
            } catch (error) {
                Notification.error(error.message || '用户组删除失败');
            }
        });
    }
}

function formatAssetTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return escapeHtml(String(value));
    }
    return date.toLocaleString('zh-CN');
}

function renderAssetMetricCard(label, value) {
    return `
        <div class="asset-metric-card">
            <div class="asset-metric-label">${escapeHtml(label)}</div>
            <div class="asset-metric-value">${Number(value || 0)}</div>
        </div>
    `;
}

function renderTaskAssetsRows(taskAssets) {
    if (!taskAssets || taskAssets.length === 0) {
        return '<tr><td colspan="5">暂无任务资产</td></tr>';
    }
    return taskAssets.map(item => `
        <tr>
            <td>${escapeHtml(item.task_name || '-')}</td>
            <td>${escapeHtml(item.keyword || '-')}</td>
            <td>${Number(item.result_count || 0)}</td>
            <td>${item.is_running ? '<span class="status-badge status-running">运行中</span>' : (item.enabled ? '<span class="status-badge status-stopped">已启用</span>' : '<span class="status-badge status-offline">已禁用</span>')}</td>
            <td>${formatAssetTime(item.latest_result_time)}</td>
        </tr>
    `).join('');
}

function renderSimpleAssetTags(items, emptyText) {
    if (!Array.isArray(items) || items.length === 0) {
        return `<span class="asset-empty-text">${escapeHtml(emptyText)}</span>`;
    }
    return items.map(item => {
        const name = item.name || item.display_name || item.id || '未命名';
        return `<span class="asset-tag">${escapeHtml(name)}</span>`;
    }).join('');
}

function renderUserAssets(container, assetsData) {
    if (!container) return;
    const summary = assetsData?.summary || {};
    const taskAssets = Array.isArray(assetsData?.task_assets) ? assetsData.task_assets : [];
    const accounts = Array.isArray(assetsData?.accounts) ? assetsData.accounts : [];
    const apiConfigs = Array.isArray(assetsData?.api_configs) ? assetsData.api_configs : [];
    const notificationConfigs = Array.isArray(assetsData?.notification_configs) ? assetsData.notification_configs : [];
    const generatedAt = formatAssetTime(assetsData?.generated_at);

    container.innerHTML = `
        <div class="asset-overview-panel">
            <div class="asset-metrics-grid">
                ${renderAssetMetricCard('任务总数', summary.tasks_total)}
                ${renderAssetMetricCard('结果总数', summary.results_total)}
                ${renderAssetMetricCard('账号总数', summary.accounts_total)}
                ${renderAssetMetricCard('API配置', summary.api_configs_total)}
                ${renderAssetMetricCard('通知配置', summary.notification_configs_total)}
                ${renderAssetMetricCard('AI标准', summary.ai_criteria_total)}
            </div>
            <p class="hint-text">统计时间：${generatedAt}</p>
        </div>
        <div class="asset-detail-grid">
            <div class="asset-detail-card">
                <h4>任务资产明细</h4>
                <div class="rbac-table-wrapper">
                    <table class="rbac-table asset-table">
                        <thead>
                            <tr>
                                <th>任务名称</th>
                                <th>关键词</th>
                                <th>结果数</th>
                                <th>状态</th>
                                <th>最新结果时间</th>
                            </tr>
                        </thead>
                        <tbody>${renderTaskAssetsRows(taskAssets)}</tbody>
                    </table>
                </div>
            </div>
            <div class="asset-detail-card">
                <h4>账号资产</h4>
                <div class="asset-tags-wrap">${renderSimpleAssetTags(accounts, '暂无账号资产')}</div>
                <h4>API 配置</h4>
                <div class="asset-tags-wrap">${renderSimpleAssetTags(apiConfigs, '暂无 API 配置')}</div>
                <h4>通知配置</h4>
                <div class="asset-tags-wrap">${renderSimpleAssetTags(notificationConfigs, '暂无通知配置')}</div>
            </div>
        </div>
    `;
}

async function loadUserAssets(container) {
    if (!container) return false;
    container.innerHTML = '<p>正在加载用户资产...</p>';
    try {
        const assetsData = await fetchMyAssets();
        currentAssetsSnapshot = assetsData;
        renderUserAssets(container, assetsData);
        return true;
    } catch (error) {
        const message = error.message || '加载用户资产失败';
        container.innerHTML = `<p class="error-state">加载用户资产失败: ${escapeHtml(message)}</p>`;
        Notification.error(message);
        return false;
    }
}

// ============== Tab 切换 ==============

function renderUserDataTabs(container, profile) {
    const canManageUsers = hasAdminPrivilege(profile);
    const canManageRoles = hasAdminPrivilege(profile);
    const canManageWarehouse = hasAdminPrivilege(profile);
    const defaultTab = 'users';

    return `
        <div class="settings-tabs user-data-tabs" id="user-data-tabs" role="tablist" aria-label="用户数据分组">
            <button type="button" class="settings-tab ${defaultTab === 'users' ? 'active' : ''}" data-tab="users" role="tab" aria-selected="${defaultTab === 'users' ? 'true' : 'false'}">用户卡片</button>
            <button type="button" class="settings-tab" data-tab="assets" role="tab" aria-selected="false">用户资产管理</button>
            ${canManageWarehouse ? '<button type="button" class="settings-tab" data-tab="warehouse" role="tab" aria-selected="false">数据仓库</button>' : ''}
            ${canManageRoles ? '<button type="button" class="settings-tab" data-tab="group-management" role="tab" aria-selected="false">用户组管理</button>' : ''}
        </div>
        <div class="tab-content" id="users-unified-tab" style="display: ${defaultTab === 'users' ? 'block' : 'none'};">
            <div class="section-header">
                <h3>用户卡片</h3>
                ${canManageUsers ? '<button id="add-user-btn" class="control-button primary-btn">+ 添加用户</button>' : ''}
            </div>
            <p class="hint-text">点击卡片可编辑个人资料；管理员点击其他用户卡片可直接编辑。</p>
            <div id="users-cards-container">
                <p>正在加载用户列表...</p>
            </div>
        </div>
        <div class="tab-content" id="user-assets-tab" style="display: none;">
            <div class="section-header">
                <h3>用户资产管理</h3>
                <button id="refresh-user-assets-btn" class="control-button">刷新资产</button>
            </div>
            <p class="hint-text">按当前登录用户统计任务、结果、账号与配置资产。</p>
            <div id="user-assets-container">
                <p>正在加载用户资产...</p>
            </div>
        </div>
        ${canManageWarehouse ? `
        <div class="tab-content" id="user-warehouse-tab" style="display: none;">
            <div class="section-header">
                <h3>数据仓库配置</h3>
                <button id="refresh-user-warehouse-btn" class="control-button">刷新配置</button>
            </div>
            <p class="hint-text">数据库模式、连接状态与迁移工具。</p>
            <div id="user-warehouse-container">
                <p>正在加载数据库配置...</p>
            </div>
        </div>
        ` : ''}
        ${canManageRoles ? `
        <div class="tab-content" id="group-management-tab" style="display: none;">
            <div id="group-management-container">
                <p>正在加载用户组管理...</p>
            </div>
        </div>
        ` : ''}
    `;
}

function attachTabEventListeners(container, refreshCallback, refreshAssetsCallback, refreshWarehouseCallback) {
    const tabBtns = container.querySelectorAll('#user-data-tabs .settings-tab');
    const usersUnifiedTab = container.querySelector('#users-unified-tab');
    const userAssetsTab = container.querySelector('#user-assets-tab');
    const userWarehouseTab = container.querySelector('#user-warehouse-tab');
    const groupManagementTab = container.querySelector('#group-management-tab');
    const groupManagementContainer = container.querySelector('#group-management-container');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            // 更新按钮样式
            tabBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');

            const tab = btn.dataset.tab;
            if (tab === 'users') {
                if (usersUnifiedTab) usersUnifiedTab.style.display = 'block';
                if (userAssetsTab) userAssetsTab.style.display = 'none';
                if (userWarehouseTab) userWarehouseTab.style.display = 'none';
                if (groupManagementTab) groupManagementTab.style.display = 'none';
                if (refreshCallback) await refreshCallback();
            } else if (tab === 'assets') {
                if (usersUnifiedTab) usersUnifiedTab.style.display = 'none';
                if (userAssetsTab) userAssetsTab.style.display = 'block';
                if (userWarehouseTab) userWarehouseTab.style.display = 'none';
                if (groupManagementTab) groupManagementTab.style.display = 'none';
                if (refreshAssetsCallback) await refreshAssetsCallback();
            } else if (tab === 'warehouse') {
                if (usersUnifiedTab) usersUnifiedTab.style.display = 'none';
                if (userAssetsTab) userAssetsTab.style.display = 'none';
                if (userWarehouseTab) userWarehouseTab.style.display = 'block';
                if (groupManagementTab) groupManagementTab.style.display = 'none';
                if (refreshWarehouseCallback) await refreshWarehouseCallback();
            } else if (tab === 'group-management') {
                if (usersUnifiedTab) usersUnifiedTab.style.display = 'none';
                if (userAssetsTab) userAssetsTab.style.display = 'none';
                if (userWarehouseTab) userWarehouseTab.style.display = 'none';
                if (groupManagementTab) groupManagementTab.style.display = 'block';
                await loadGroupManagement(groupManagementContainer);
            }
        });
    });
}

async function loadMyProfile(container, profileOverride = null) {
    if (!container) return;

    const profile = profileOverride || await fetchMyProfile();
    if (!profile) {
        container.innerHTML = '<p class="error-state">鍔犺浇涓汉璧勬枡澶辫触</p>';
        return;
    }

    // 获取头像信息
    const avatarInfo = await fetchMyAvatar();
    if (avatarInfo && avatarInfo.avatar_url) {
        profile.avatar_url = avatarInfo.avatar_url;
    }

    currentUserProfile = profile;
    renderMyProfile(container, profile);
}

function markSelectedUserCard(container, selectedUserId) {
    if (!container) return;
    const cards = container.querySelectorAll('.mp-user-card');
    cards.forEach(card => {
        card.classList.toggle('is-selected', isSameUserId(card.dataset.userId, selectedUserId));
    });
}

async function openUserCardDetail({
    clickedUserId,
    cardsContainer,
    canManageUsers
}) {
    if (!clickedUserId || !cardsContainer) return;
    const clickedUser = userCardDataMap[clickedUserId];
    if (!clickedUser) {
        Notification.error('未找到用户数据，请刷新后重试');
        return;
    }

    markSelectedUserCard(cardsContainer, clickedUserId);

    // 当前账号：弹出资料编辑模态框
    if (clickedUser.is_current_user) {
        showUserProfileModal({
            ...(currentUserProfile || {}),
            ...clickedUser,
            user_id: clickedUser.id,
            is_multi_user_mode: currentUserProfile?.is_multi_user_mode
        });
        return;
    }

    // 管理员可直接编辑其他用户
    if (canManageUsers) {
        showEditUserModal(clickedUser);
        return;
    }

    // 普通用户点击其他卡片时，仅允许查看当前登录账号资料
    Notification.info('该卡片仅支持查看当前登录账号的详细资料');
}

// ============== 模态框函数 ==============

function showUserProfileModal(profile) {
    const modal = document.getElementById('user-profile-modal');
    const modalBody = document.getElementById('user-profile-modal-body');
    const modalTitle = document.getElementById('user-profile-modal-title');

    if (!modal || !modalBody) return;

    modalTitle.textContent = '我的资料';
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('visible'), 10);

    renderMyProfile(modalBody, profile);
}

function hideUserProfileModal() {
    const modal = document.getElementById('user-profile-modal');
    if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => { modal.style.display = 'none'; }, 300);
    }
}

function showAddUserModal() {
    const modal = document.getElementById('add-user-modal');
    if (modal) {
        modal.style.display = 'flex';
        setTimeout(() => modal.classList.add('visible'), 10);
        const form = document.getElementById('add-user-form');
        if (form) form.reset();
        const groupSelect = document.getElementById('new-user-groups');
        if (groupSelect) {
            groupSelect.innerHTML = buildGroupSelectOptions([]);
        }
    }
}

function hideAddUserModal() {
    const modal = document.getElementById('add-user-modal');
    if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => { modal.style.display = 'none'; }, 300);
    }
}

function showEditUserModal(user) {
    const modal = document.getElementById('edit-user-modal');
    const modalBody = document.getElementById('edit-user-modal-body');
    const modalTitle = document.getElementById('edit-user-modal-title');

    if (!modal || !modalBody) return;

    // 存储当前编辑的用户数据
    currentEditingUser = user;

    modalTitle.textContent = `编辑用户 - ${user.username}`;
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('visible'), 10);

    // 渲染编辑用户界面，使用与「我的资料」相同的 UI 风格
    renderEditUserProfile(modalBody, user);
}

function buildGroupSelectOptions(selectedGroupIds) {
    const selectedSet = new Set((selectedGroupIds || []).map(id => String(id)));
    if (!currentGroupList || currentGroupList.length === 0) {
        return '<option value="">暂无可用用户组</option>';
    }
    return currentGroupList.map(group => `
        <option value="${group.id}" ${selectedSet.has(String(group.id)) ? 'selected' : ''}>
            ${escapeHtml(group.name || group.code || '未命名组')}
        </option>
    `).join('');
}

function renderEditUserProfile(container, user) {
    if (!container || !user) return;

    const groupInfo = getGroupBadgeInfo(user);
    const initial = (user.username || 'U')[0].toUpperCase();
    const avatarColor = getAvatarColor(user.username || 'U');
    const avatarUrl = user.avatar_url || null;

    const selectedGroupIds = (user.group_ids || []).map(id => String(id));
    const canResetOtherPassword = hasSuperAdminPrivilege(currentUserProfile) && !isSameUserId(currentUserId, user.id);

    container.innerHTML = `
        <div class="my-profile-container">
            <input type="hidden" id="edit-user-id" value="${user.id}">
            
            <div class="profile-section">
                <h3>用户头像</h3>
                <div class="avatar-upload-area">
                    <div class="avatar-preview">
                        ${avatarUrl
            ? `<img src="${avatarUrl}" alt="${escapeHtml(user.username)}" class="user-avatar-img large">`
            : `<div class="user-avatar large" style="background: ${avatarColor}">${initial}</div>`
        }
                    </div>
                    <p class="avatar-hint">管理员无法修改其他用户头像</p>
                </div>
            </div>
            
            <div class="profile-section">
                <h3>基本信息</h3>
                <div class="profile-info-grid">
                    <div class="profile-info-item">
                        <label>用户名</label>
                        <div class="profile-info-value">${escapeHtml(user.username)}</div>
                    </div>
                    <div class="profile-info-item">
                        <label>邮箱</label>
                        <div class="profile-info-value editable" id="edit-profile-email-display">
                            ${escapeHtml(user.email || '未设置')}
                            <button class="edit-inline-btn" id="toggle-email-edit-btn">✏️</button>
                        </div>
                        <div class="profile-info-edit" id="edit-profile-email-edit" style="display: none;">
                            <input type="email" id="edit-user-email" value="${escapeHtml(user.email || '')}" placeholder="请输入邮箱">
                        </div>
                    </div>
                    <div class="profile-info-item">
                        <label>当前用户组</label>
                        <div class="profile-info-value">
                            <span class="role-badge ${groupInfo.class}" style="background: ${groupInfo.color}">${groupInfo.text}</span>
                        </div>
                    </div>
                    <div class="profile-info-item">
                        <label>用户组（可多选）</label>
                        <div class="profile-info-value">
                            <select id="edit-user-groups" class="styled-select compact" multiple style="min-height: 108px;">
                                ${buildGroupSelectOptions(selectedGroupIds)}
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="profile-section">
                <h3>账号状态</h3>
                <div class="form-group switch-group">
                    <div class="switch-label-row">
                        <span class="switch-label-text">启用账号</span>
                        <label class="switch">
                            <input type="checkbox" id="edit-user-active" ${user.is_active ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                    <p class="form-hint">${user.is_active ? '账号当前已启用' : '账号当前已禁用'}</p>
                </div>
            </div>

            ${canResetOtherPassword ? `
            <div class="profile-section">
                <h3>密码重置</h3>
                <div class="password-change-form">
                    <div class="form-group">
                        <label>新密码</label>
                        <input type="password" id="reset-user-new-password" placeholder="请输入新密码（至少6位）">
                    </div>
                    <div class="form-group">
                        <label>确认新密码</label>
                        <input type="password" id="reset-user-confirm-password" placeholder="请再次输入新密码">
                    </div>
                    <button class="control-button danger-btn" id="reset-user-password-btn">重置该用户密码</button>
                    <p class="form-hint">重置后将使该用户所有会话失效，需要重新登录。</p>
                </div>
            </div>
            ` : ''}
        </div>
    `;

    // 绑定邮箱编辑切换事件
    attachEditUserEventListeners(container);
}

function attachEditUserEventListeners(container) {
    const toggleEmailBtn = container.querySelector('#toggle-email-edit-btn');
    const emailDisplay = container.querySelector('#edit-profile-email-display');
    const emailEdit = container.querySelector('#edit-profile-email-edit');

    if (toggleEmailBtn && emailDisplay && emailEdit) {
        toggleEmailBtn.addEventListener('click', () => {
            const isEditing = emailEdit.style.display !== 'none';
            emailEdit.style.display = isEditing ? 'none' : 'block';
            emailDisplay.style.display = isEditing ? 'flex' : 'none';
        });
    }

    const resetPasswordBtn = container.querySelector('#reset-user-password-btn');
    if (resetPasswordBtn && !resetPasswordBtn._listenerAttached) {
        resetPasswordBtn._listenerAttached = true;
        resetPasswordBtn.addEventListener('click', async () => {
            const userId = container.querySelector('#edit-user-id')?.value;
            const newPassword = container.querySelector('#reset-user-new-password')?.value || '';
            const confirmPassword = container.querySelector('#reset-user-confirm-password')?.value || '';

            if (!userId) {
                Notification.error('未找到目标用户，请刷新后重试');
                return;
            }
            if (!newPassword) {
                Notification.warning('请输入新密码');
                return;
            }
            if (newPassword.length < 6) {
                Notification.warning('新密码至少需要 6 位');
                return;
            }
            if (newPassword !== confirmPassword) {
                Notification.warning('两次输入的新密码不一致');
                return;
            }

            const confirmResult = await Notification.confirm('确认重置该用户密码吗？重置后该用户需要重新登录。');
            if (!confirmResult.isConfirmed) {
                return;
            }

            resetPasswordBtn.disabled = true;
            const originalText = resetPasswordBtn.textContent;
            resetPasswordBtn.textContent = '重置中...';
            try {
                const result = await resetUserPassword(userId, {
                    new_password: newPassword,
                    revoke_sessions: true
                });
                const revoked = Number(result.revoked_sessions || 0);
                Notification.success(`密码已重置，已清理 ${revoked} 个会话`);
                const newPasswordInput = container.querySelector('#reset-user-new-password');
                const confirmPasswordInput = container.querySelector('#reset-user-confirm-password');
                if (newPasswordInput) newPasswordInput.value = '';
                if (confirmPasswordInput) confirmPasswordInput.value = '';
            } catch (error) {
                Notification.error(error.message || '重置用户密码失败');
            } finally {
                resetPasswordBtn.disabled = false;
                resetPasswordBtn.textContent = originalText;
            }
        });
    }
}

function hideEditUserModal() {
    const modal = document.getElementById('edit-user-modal');
    if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => { modal.style.display = 'none'; }, 300);
    }
}

// ============== 浜嬩欢澶勭悊 ==============

function attachUserEventListeners(container, refreshCallback, canManage) {
    // 添加用户按钮
    const addBtn = container.querySelector('#add-user-btn');
    if (addBtn) {
        addBtn.addEventListener('click', () => showAddUserModal());
    }

    // 保存新用户
    const saveNewUserBtn = document.getElementById('save-new-user-btn');
    if (saveNewUserBtn && !saveNewUserBtn._listenerAttached) {
        saveNewUserBtn._listenerAttached = true;
        saveNewUserBtn.addEventListener('click', async () => {
            const username = document.getElementById('new-user-username').value.trim();
            const password = document.getElementById('new-user-password').value;
            const email = document.getElementById('new-user-email').value.trim();
            const groupSelect = document.getElementById('new-user-groups');
            const groupIds = groupSelect
                ? Array.from(groupSelect.selectedOptions).map(option => option.value).filter(Boolean)
                : [];

            if (!username || !password) {
                Notification.warning('用户名和密码不能为空');
                return;
            }
            if (!groupIds.length) {
                Notification.warning('请至少选择一个用户组');
                return;
            }

            try {
                await createUser({ username, password, email: email || null, group_ids: groupIds });
                Notification.success('用户创建成功');
                hideAddUserModal();
                if (refreshCallback) await refreshCallback();
            } catch (error) {
                Notification.error(error.message || '创建用户失败');
            }
        });
    }

    // 保存编辑
    const saveEditUserBtn = document.getElementById('save-edit-user-btn');
    if (saveEditUserBtn && !saveEditUserBtn._listenerAttached) {
        saveEditUserBtn._listenerAttached = true;
        saveEditUserBtn.addEventListener('click', async () => {
            const userId = document.getElementById('edit-user-id').value;
            const email = document.getElementById('edit-user-email').value.trim();
            const isActive = document.getElementById('edit-user-active').checked;
            const groupSelect = document.getElementById('edit-user-groups');
            const groupIds = groupSelect
                ? Array.from(groupSelect.selectedOptions).map(option => option.value).filter(Boolean)
                : [];
            if (!groupIds.length) {
                Notification.warning('请至少选择一个用户组');
                return;
            }

            try {
                await updateUser(userId, { email: email || null, is_active: isActive, group_ids: groupIds });
                Notification.success('用户信息已更新');
                hideEditUserModal();
                if (refreshCallback) await refreshCallback();
            } catch (error) {
                Notification.error(error.message || '更新用户失败');
            }
        });
    }

    // 关闭模态框按钮
    const closeButtons = document.querySelectorAll('.close-user-modal-btn, .cancel-user-btn');
    closeButtons.forEach(btn => {
        if (!btn._listenerAttached) {
            btn._listenerAttached = true;
            btn.addEventListener('click', () => {
                hideAddUserModal();
                hideEditUserModal();
            });
        }
    });

    // 关闭个人资料模态框按钮
    const profileCloseButtons = document.querySelectorAll('.close-user-profile-modal-btn');
    profileCloseButtons.forEach(btn => {
        if (!btn._listenerAttached) {
            btn._listenerAttached = true;
            btn.addEventListener('click', () => {
                hideUserProfileModal();
            });
        }
    });

    // 卡片内按钮事件委托
    const cardsContainer = container.querySelector('#users-cards-container');
    if (cardsContainer) {
        cardsContainer.addEventListener('click', async (e) => {
            const target = e.target;
            const card = target.closest('.mp-user-card');
            const userId = target.dataset?.userId || card?.dataset?.userId;

            if (!userId) return;

            // 缂栬緫鎸夐挳
            if (target.classList.contains('edit-user-btn')) {
                const user = userCardDataMap[userId];
                if (!user) {
                    Notification.error('未找到用户数据，请刷新后重试');
                    return;
                }
                showEditUserModal(user);
                return;
            }

            // 启用/禁用按钮
            if (target.classList.contains('toggle-user-btn')) {
                const isActive = target.dataset.active === 'true';
                const action = isActive ? '禁用' : '启用';
                const confirmResult = await Notification.confirm(`确定要${action}该用户吗？`);
                if (confirmResult.isConfirmed) {
                    try {
                        await updateUser(userId, { is_active: !isActive });
                        Notification.success(`用户已${action}`);
                        if (refreshCallback) await refreshCallback();
                    } catch (error) {
                        Notification.error(error.message || `${action}用户失败`);
                    }
                }
                return;
            }

            // 删除按钮
            if (target.classList.contains('delete-user-btn')) {
                const confirmResult = await Notification.confirmDelete('确定要删除该用户吗？此操作不可恢复。');
                if (confirmResult.isConfirmed) {
                    try {
                        await deleteUserApi(userId);
                        Notification.success('用户已删除');
                        if (refreshCallback) await refreshCallback();
                    } catch (error) {
                        Notification.error(error.message || '删除用户失败');
                    }
                }
                return;
            }

            // 点击整张卡片：打开详情/编辑模态框
            if (card) {
                await openUserCardDetail({
                    clickedUserId: userId,
                    cardsContainer,
                    canManageUsers: canManage
                });
            }
        });
    }
}

// ============== 初始化 ==============

async function initializeUsersView() {
    const container = document.getElementById('users-table-container') || document.getElementById('user-data-content');
    if (!container) return;

    // 拉取页面权限，确保前端行为与后端权限配置一致
    currentPagePermissions = await fetchPagePermissions();
    const canAccessUserData = !currentPagePermissions ||
        currentPagePermissions.accessible_pages?.['user-data'] !== false;
    if (!canAccessUserData) {
        container.innerHTML = '<p class="error-state">⚠️ 权限不足：当前账号无法访问用户数据页面</p>';
        return;
    }

    // 获取当前用户资料
    const profile = await fetchMyProfile();
    if (!profile) {
        container.innerHTML = '<p class="error-state">获取用户信息失败，请刷新页面</p>';
        return;
    }

    currentUserProfile = profile;
    currentUserId = getUserId(profile);
    if (profile.security_notice) {
        const noticeShownKey = `security_notice_shown_${profile.username || profile.user_id || 'current'}`;
        if (sessionStorage.getItem(noticeShownKey) !== '1') {
            Notification.warning(profile.security_notice);
            sessionStorage.setItem(noticeShownKey, '1');
        }
    }

    // 初始化当前用户头像，保证卡片和详情一致
    const myAvatarInfo = await fetchMyAvatar();
    if (myAvatarInfo && myAvatarInfo.avatar_url) {
        currentUserProfile.avatar_url = myAvatarInfo.avatar_url;
    }

    const canManageUsers = Boolean(
        hasAdminPrivilege(profile)
    );

    if (canManageUsers && profile.is_multi_user_mode) {
        try {
            currentGroupList = await fetchGroups();
        } catch (error) {
            currentGroupList = [];
            Notification.warning('用户组数据加载失败，用户组分配功能暂不可用');
        }
    } else {
        currentGroupList = [];
    }

    // 渲染 Tab 结构
    container.innerHTML = renderUserDataTabs(container, profile);

    const refreshUsers = async () => {
        const cardsContainer = container.querySelector('#users-cards-container');
        if (!cardsContainer) return;

        let users = [];
        if (canManageUsers) {
            const result = await fetchUsers();
            if (result.error === 'forbidden') {
                cardsContainer.innerHTML = '<p class="error-state">⚠️ 权限不足：仅管理员可访问用户列表</p>';
                return;
            }
            if (result.error) {
                cardsContainer.innerHTML = `<p class="error-state">鍔犺浇澶辫触: ${result.message}</p>`;
                return;
            }
            users = result.users || result || [];
        } else {
            users = [currentUserProfile];
        }

        renderUsersCards(cardsContainer, users, {
            canManage: canManageUsers,
            currentUserId,
            activeUserId: currentUserId,
            currentProfile: currentUserProfile
        });
    };

    const refreshAssets = async () => {
        const assetsContainer = container.querySelector('#user-assets-container');
        return await loadUserAssets(assetsContainer);
    };

    const refreshWarehouse = async () => {
        const warehouseContainer = container.querySelector('#user-warehouse-container');
        if (!warehouseContainer) return false;
        if (typeof window.initializeDatabaseWarehousePanel !== 'function') {
            warehouseContainer.innerHTML = '<p class="error-state">数据库面板加载失败：缺少初始化函数</p>';
            return false;
        }
        await window.initializeDatabaseWarehousePanel(warehouseContainer);
        return true;
    };

    // 绑定 Tab 切换事件
    attachTabEventListeners(container, refreshUsers, refreshAssets, refreshWarehouse);

    const refreshAssetsBtn = container.querySelector('#refresh-user-assets-btn');
    if (refreshAssetsBtn) {
        refreshAssetsBtn.addEventListener('click', async () => {
            const success = await refreshAssets();
            if (success) {
                Notification.toast('用户资产已刷新', 'success');
            }
        });
    }

    const refreshWarehouseBtn = container.querySelector('#refresh-user-warehouse-btn');
    if (refreshWarehouseBtn) {
        refreshWarehouseBtn.addEventListener('click', async () => {
            const success = await refreshWarehouse();
            if (success) {
                Notification.toast('数据仓库配置已刷新', 'success');
            }
        });
    }

    // 绑定用户管理事件
    attachUserEventListeners(container, refreshUsers, canManageUsers);

    // 初始加载
    await refreshUsers();

    // 检查是否需要自动打开个人资料弹窗（从下拉菜单“个人信息”跳转）
    const hash = window.location.hash;
    if (hash.includes('profile=me')) {
        // 延迟执行确保页面渲染完成
        setTimeout(() => {
            showUserProfileModal(currentUserProfile);
            // 清理 URL 参数
            history.replaceState(null, '', '#users');
        }, 100);
    }
}

// ============== 权限检查与菜单显示 ==============

async function checkUserRoleAndShowMenu() {
    const navUsersAdmin = document.getElementById('nav-users-admin');
    if (!navUsersAdmin) return;

    const pagePermissions = await fetchPagePermissions();
    const canAccessUserData = pagePermissions?.accessible_pages?.['user-data'];

    // 以服务端页面权限为准；请求失败时回退到用户已登录即可显示
    if (canAccessUserData === true) {
        navUsersAdmin.style.display = '';
        return;
    }
    if (canAccessUserData === false) {
        navUsersAdmin.style.display = 'none';
        return;
    }

    const profile = await fetchMyProfile();
    if (profile) {
        navUsersAdmin.style.display = '';
    } else {
        navUsersAdmin.style.display = 'none';
    }
}

// ============== 个人信息页面 ==============

async function initializeProfileView() {
    const container = document.getElementById('profile-content-container');
    if (!container) return;

    // 获取当前用户资料
    const profile = await fetchMyProfile();
    if (!profile) {
        container.innerHTML = '<p class="error-state">获取用户信息失败，请刷新页面</p>';
        return;
    }

    // 获取头像
    const myAvatarInfo = await fetchMyAvatar();
    if (myAvatarInfo && myAvatarInfo.avatar_url) {
        profile.avatar_url = myAvatarInfo.avatar_url;
    }

    // 渲染个人信息页面
    renderProfilePage(container, profile);
}

function renderProfilePage(container, profile) {
    const username = profile.username || '未设置';
    const email = profile.email || '';
    const groupInfo = getGroupBadgeInfo(profile);
    const avatarUrl = profile.avatar_url || null;

    // 生成头像
    const initial = (username || 'U')[0].toUpperCase();
    const avatarColors = ['#1890ff', '#52c41a', '#faad14', '#eb2f96', '#722ed1', '#13c2c2'];
    const colorIndex = username.charCodeAt(0) % avatarColors.length;
    const avatarColor = avatarColors[colorIndex];

    container.innerHTML = `
        <div class="profile-page-layout">
            <!-- 头像区域 -->
            <div class="profile-section profile-avatar-section">
                <h3>个人头像</h3>
                <div class="profile-avatar-wrapper">
                    <div class="profile-avatar-display" id="profile-avatar-display">
                        ${avatarUrl
            ? `<img src="${avatarUrl}" alt="${escapeHtml(username)}" class="profile-avatar-img">`
            : `<div class="profile-avatar-placeholder" style="background: ${avatarColor}">${initial}</div>`
        }
                    </div>
                    <div class="profile-avatar-actions">
                        <input type="file" id="profile-avatar-input" accept="image/jpeg,image/png,image/gif,image/webp" style="display: none;">
                        <button id="profile-change-avatar-btn" class="control-button primary-btn">更换头像</button>
                        <p class="profile-avatar-hint">支持 JPG/PNG/GIF/WEBP，最大 2MB</p>
                    </div>
                </div>
            </div>

            <!-- 基本信息区域 -->
            <div class="profile-section profile-info-section">
                <h3>基本信息</h3>
                <div class="profile-info-grid">
                    <div class="profile-info-item">
                        <label>用户名</label>
                        <div class="profile-info-value">${escapeHtml(username)}</div>
                    </div>
                    <div class="profile-info-item">
                        <label>用户组</label>
                        <div class="profile-info-value">
                            <span class="role-badge ${groupInfo.class}" style="background: ${groupInfo.color}">${groupInfo.text}</span>
                        </div>
                    </div>
                    <div class="profile-info-item profile-info-editable">
                        <label>邮箱</label>
                        <div class="profile-info-value-editable">
                            <span id="profile-email-display">${email || '未设置'}</span>
                            <button id="profile-edit-email-btn" class="profile-edit-btn" title="编辑邮箱">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                </svg>
                            </button>
                        </div>
                        <div id="profile-email-editor" class="profile-inline-editor" style="display: none;">
                            <input type="email" id="profile-email-input" class="profile-input" placeholder="请输入邮箱地址" value="${escapeHtml(email)}">
                            <div class="profile-editor-actions">
                                <button id="profile-save-email-btn" class="control-button primary-btn small">保存</button>
                                <button id="profile-cancel-email-btn" class="control-button outline-btn small">取消</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 修改密码区域 -->
            <div class="profile-section profile-password-section">
                <h3>修改密码</h3>
                <div class="profile-password-form">
                    <div class="profile-form-group">
                        <label for="profile-current-password">当前密码</label>
                        <input type="password" id="profile-current-password" class="profile-input" placeholder="请输入当前密码">
                    </div>
                    <div class="profile-form-group">
                        <label for="profile-new-password">新密码</label>
                        <input type="password" id="profile-new-password" class="profile-input" placeholder="请输入新密码（至少6位）">
                    </div>
                    <div class="profile-form-group">
                        <label for="profile-confirm-password">确认新密码</label>
                        <input type="password" id="profile-confirm-password" class="profile-input" placeholder="请再次输入新密码">
                    </div>
                    <button id="profile-change-password-btn" class="control-button primary-btn">修改密码</button>
                </div>
            </div>
        </div>
    `;

    // 绑定事件
    attachProfilePageEventListeners(container, profile);
}

function attachProfilePageEventListeners(container, profile) {
    // 头像上传
    const avatarInput = container.querySelector('#profile-avatar-input');
    const changeAvatarBtn = container.querySelector('#profile-change-avatar-btn');
    const avatarDisplay = container.querySelector('#profile-avatar-display');

    if (changeAvatarBtn && avatarInput) {
        changeAvatarBtn.addEventListener('click', () => avatarInput.click());

        avatarInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (file.size > 2 * 1024 * 1024) {
                Notification.error('头像文件不能超过 2MB');
                return;
            }

            const result = await uploadAvatar(file);
            if (result && result.avatar_url) {
                avatarDisplay.innerHTML = `<img src="${result.avatar_url}" alt="${escapeHtml(profile.username)}" class="profile-avatar-img">`;
                if (currentUserProfile) {
                    currentUserProfile.avatar_url = result.avatar_url;
                }
                syncLoginStatusWidgetAvatar(result.avatar_url);
                Notification.success('头像上传成功');
            }
        });
    }

    // 邮箱编辑
    const emailDisplay = container.querySelector('#profile-email-display');
    const editEmailBtn = container.querySelector('#profile-edit-email-btn');
    const emailEditor = container.querySelector('#profile-email-editor');
    const emailInput = container.querySelector('#profile-email-input');
    const saveEmailBtn = container.querySelector('#profile-save-email-btn');
    const cancelEmailBtn = container.querySelector('#profile-cancel-email-btn');

    if (editEmailBtn && emailEditor) {
        editEmailBtn.addEventListener('click', () => {
            emailEditor.style.display = 'block';
            emailDisplay.parentElement.querySelector('.profile-info-value-editable').style.display = 'none';
            emailInput.focus();
        });

        cancelEmailBtn.addEventListener('click', () => {
            emailEditor.style.display = 'none';
            emailDisplay.parentElement.querySelector('.profile-info-value-editable').style.display = 'flex';
            emailInput.value = profile.email || '';
        });

        saveEmailBtn.addEventListener('click', async () => {
            const newEmail = emailInput.value.trim();
            const result = await updateMyProfile({ email: newEmail });
            if (result) {
                profile.email = newEmail;
                emailDisplay.textContent = newEmail || '未设置';
                emailEditor.style.display = 'none';
                emailDisplay.parentElement.querySelector('.profile-info-value-editable').style.display = 'flex';
                Notification.success('邮箱更新成功');
            }
        });
    }

    // 密码修改
    const currentPasswordInput = container.querySelector('#profile-current-password');
    const newPasswordInput = container.querySelector('#profile-new-password');
    const confirmPasswordInput = container.querySelector('#profile-confirm-password');
    const changePasswordBtn = container.querySelector('#profile-change-password-btn');

    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', async () => {
            const currentPassword = currentPasswordInput.value;
            const newPassword = newPasswordInput.value;
            const confirmPassword = confirmPasswordInput.value;

            if (!currentPassword) {
                Notification.error('请输入当前密码');
                return;
            }
            if (!newPassword || newPassword.length < 6) {
                Notification.error('新密码至少需要 6 位');
                return;
            }
            if (newPassword !== confirmPassword) {
                Notification.error('两次输入的新密码不一致');
                return;
            }

            const result = await changeMyPassword({
                current_password: currentPassword,
                new_password: newPassword
            });

            if (result) {
                Notification.success('密码修改成功');
                currentPasswordInput.value = '';
                newPasswordInput.value = '';
                confirmPasswordInput.value = '';
            }
        });
    }
}


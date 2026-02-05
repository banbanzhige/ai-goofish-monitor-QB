﻿// 账号管理视图
async function initializeAccountsView() {
    const container = document.getElementById('accounts-table-container');
    const addBtn = document.getElementById('add-account-btn');
    const cleanupExpiredBtn = document.getElementById('cleanup-expired-accounts-btn');

    const refreshAccounts = async () => {
        const accounts = await fetchAccounts();
        if (container) {
            renderAccountsInto(container, accounts);
            attachAccountEventListeners();
        }
    };

    const attachAccountEventListeners = () => {
        // 激活账号按钮
        container.querySelectorAll('.activate-account-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const name = btn.dataset.name;
                const confirmResult = await Notification.confirm(`确定要激活账号 "${name}" 吗？`);
                if (confirmResult.isConfirmed) {
                    const activateResult = await activateAccount(name);
                    if (activateResult) {
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
                const confirmResult = await Notification.confirmDelete(`确定要删除账号 "${displayName}" 吗？此操作不可恢复！`);
                if (confirmResult.isConfirmed) {
                    const deleteResult = await deleteAccount(name);
                    if (deleteResult) {
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

                    if (response.ok && result.valid) {
                        if (statusCell) {
                            statusCell.innerHTML = '<span class="status-badge status-ok" style="background:#52c41a;">有效</span>';
                        }
                        Notification.success(`✓ ${result.message}`);
                    } else {
                        if (statusCell) {
                            statusCell.innerHTML = '<span class="status-badge status-error" style="background:#ff4d4f;">已过期</span>';
                        }

                        if (response.ok) {
                            const displayName = btn.dataset.displayName || name;
                            const rawMessage = result?.message || 'Cookie已失效';
                            const prefix = `账号 '${name}' `;
                            const reason = rawMessage.startsWith(prefix) ? rawMessage.slice(prefix.length) : rawMessage;
                            const confirmMessage = `账号 "${displayName}" 已失效。\n${reason}\n是否删除该账号？`;
                            const confirmResult = await Notification.confirm(confirmMessage);
                            if (confirmResult.isConfirmed) {
                                const deleteResult = await deleteAccount(name);
                                if (deleteResult) {
                                    await refreshAccounts();
                                }
                            }
                        } else {
                            const errorMessage = result?.detail || result?.message || '未知错误';
                            Notification.error(`测试账号 '${name}' 失败: ${errorMessage}`);
                        }
                    }
                } catch (error) {
                    if (statusCell) {
                        statusCell.innerHTML = '<span class="status-badge" style="background:#999;">检测失败</span>';
                    }
                    Notification.error(`测试账号 '${name}' 失败: ${error.message}`);
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
                        Notification.error(`复制失败: ${result.detail || '未知错误'}`);
                    }
                } catch (error) {
                    Notification.error(`复制失败: ${error.message}`);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '复制';
                }
            });
        });
    };

    if (cleanupExpiredBtn) {
        cleanupExpiredBtn.addEventListener('click', async () => {
            const confirmResult = await Notification.confirmDelete('将删除所有已失效账号，是否继续？');
            if (!confirmResult.isConfirmed) return;
            const originalText = cleanupExpiredBtn.textContent;
            cleanupExpiredBtn.disabled = true;
            cleanupExpiredBtn.textContent = '清理中...';

            try {
                const result = await cleanupExpiredAccounts();
                if (result) {
                    Notification.success(result.message || '批量清理完成');
                    await refreshAccounts();
                }
            } finally {
                cleanupExpiredBtn.disabled = false;
                cleanupExpiredBtn.textContent = originalText;
            }
        });
    }

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
                Notification.info('无法找到添加账号模态框');
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
                    Notification.warning('请输入账号名称');
                    accountNameInput?.focus();
                    return;
                }

                if (!stateContent) {
                    Notification.warning('请粘贴Cookie JSON内容');
                    stateContentTextarea?.focus();
                    return;
                }

                // 验证JSON格式
                try {
                    JSON.parse(stateContent);
                } catch (e) {
                    Notification.info('Cookie内容不是有效的JSON格式');
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
                        Notification.error(`添加失败`);
                    }
                } catch (error) {
                    Notification.error(`添加失败: ${error.message}`);
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
                Notification.info('无法找到登录确认模态框');
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
                        Notification.error('启动失败: ' + (errorData.detail || '未知错误'));
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

function renderAccountLabel(displayName, accountName, statusHtml) {
    return `
        <div class="account-label">
            ${renderAccountColorTag(displayName, accountName)}
            <span class="account-status-badge">${statusHtml}</span>
        </div>
    `;
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
                <th></th>
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
        const labelHtml = renderAccountLabel(account.display_name, account.name, '');
        const riskValueHtml = account.risk_control_count > 0
            ? `<span class="risk-pill risk-pill--warn">${account.risk_control_count}</span>`
            : '<span class="risk-pill risk-pill--ok">0</span>';
        const riskSummaryHtml = `<div class="risk-summary"><span class="risk-label">风控次数</span>${riskValueHtml}<span class="account-status-badge">${statusHtml}</span></div>`;

        html += `
            <tr data-account-name="${account.name}">
        <td style="text-align: center;" class="drag-handle-cell">
            <span class="drag-handle" draggable="true" title="Drag">::</span>
        </td>
        <td class="account-name-cell" data-label="\u8d26\u53f7" style="text-align: center; justify-content: center;">${labelHtml}</td>
        <td class="cookie-status-cell" data-name="${account.name}" data-label="状态" style="text-align: center;">${statusHtml}</td>
        <td class="last-used-cell" data-label="最后使用" style="text-align: center;">${lastUsed}</td>
        <td class="risk-control-cell ${riskClass}" data-label="风控次数" style="text-align: center;">
                    ${riskSummaryHtml}
                    ${account.risk_control_count > 0
                ? `<button class="control-button small-btn view-history-btn" data-name="${account.name}">查看</button>`
                : ''
            }
                </td>
                <td class="action-buttons" data-label="操作">
                    <button class="control-button small-btn test-account-btn" data-name="${account.name}" data-display-name="${account.display_name}" title="测试Cookie是否有效">测试</button>
                    <div class="dropdown-container">
                        <button class="dropdown-btn small-btn"><span class="dropdown-label">操作</span><span class="dropdown-arrow">▾</span></button>
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
                Notification.warning('请填写所有必填字段');
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
                Notification.warning('显示名称不能为空');
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


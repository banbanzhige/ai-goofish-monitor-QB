﻿﻿﻿// 通知视图
async function initializeNotificationsView() {

    const notificationContainer = document.getElementById('notification-settings-container');
    const notificationSettings = await fetchNotificationSettings();
    if (notificationSettings !== null) {
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
    } else {
        notificationContainer.innerHTML = '<p>加载通知配置失败。请检查服务器是否正常运行。</p>';
    }


    async function saveNotificationSettingsNow() {
        const notificationForm = document.getElementById('notification-settings-form');
        if (!notificationForm) return;


        const formData = new FormData(notificationForm);
        const settings = {};


        for (let [key, value] of formData.entries()) {
            if (key.startsWith('PCURL_TO_MOBILE') || key.startsWith('NOTIFY_AFTER_TASK_COMPLETE') ||
                key.endsWith('_ENABLED')) {
                settings[key] = value === 'on';
            } else {
                settings[key] = value || '';
            }
        }


        const notifyAfterTaskCompleteCheckbox = document.getElementById('notify-after-task-complete');
        if (notifyAfterTaskCompleteCheckbox) {
            settings.NOTIFY_AFTER_TASK_COMPLETE = notifyAfterTaskCompleteCheckbox.checked;
        }


        await updateNotificationSettings(settings);
    }


    const notificationForm = document.getElementById('notification-settings-form');
    if (notificationForm) {

        notificationForm.addEventListener('submit', async (e) => {
            e.preventDefault();


            const formData = new FormData(notificationForm);
            const settings = {};


            for (let [key, value] of formData.entries()) {
                if (key === 'PCURL_TO_MOBILE') {
                    settings[key] = value === 'on';
                } else {
                    settings[key] = value || '';
                }
            }


            const pcurlCheckbox = document.getElementById('pcurl-to-mobile');
            if (pcurlCheckbox && !pcurlCheckbox.checked) {
                settings.PCURL_TO_MOBILE = false;
            }


            const notifyAfterTaskCompleteCheckbox = document.getElementById('notify-after-task-complete');
            settings.NOTIFY_AFTER_TASK_COMPLETE = notifyAfterTaskCompleteCheckbox.checked;


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

                const formData = new FormData(notificationForm);
                const settings = {};


                for (let [key, value] of formData.entries()) {
                    if (key === 'PCURL_TO_MOBILE') {
                        settings[key] = value === 'on';
                    } else {
                        settings[key] = value || '';
                    }
                }


                const pcurlCheckbox = document.getElementById('pcurl-to-mobile');
                if (pcurlCheckbox && !pcurlCheckbox.checked) {
                    settings.PCURL_TO_MOBILE = false;
                }


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
                        body: JSON.stringify({ channel: channel }),
                    });

                    if (response.ok) {
                        const result = await response.json();
                        Notification.success(result.message || '测试通知发送成功！');
                    } else {
                        const errorData = await response.json();
                        Notification.error('测试通知发送失败: ' + (errorData.detail || '未知错误'));
                    }
                } catch (error) {
                    Notification.error('测试通知发送失败: ' + error.message);
                } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            });
        });


        const testTaskCompletionButtons = notificationForm.querySelectorAll('.test-task-completion-btn');
        testTaskCompletionButtons.forEach(button => {
            button.addEventListener('click', async () => {

                const formData = new FormData(notificationForm);
                const settings = {};


                for (let [key, value] of formData.entries()) {
                    if (key === 'PCURL_TO_MOBILE') {
                        settings[key] = value === 'on';
                    } else {
                        settings[key] = value || '';
                    }
                }


                const pcurlCheckbox = document.getElementById('pcurl-to-mobile');
                if (pcurlCheckbox && !pcurlCheckbox.checked) {
                    settings.PCURL_TO_MOBILE = false;
                }


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
                        body: JSON.stringify({ channel: channel }),
                    });

                    if (response.ok) {
                        const result = await response.json();
                        Notification.success(result.message || '测试任务完成通知发送成功！');
                    } else {
                        const errorData = await response.json();
                        Notification.error('测试任务完成通知发送失败: ' + (errorData.detail || '未知错误'));
                    }
                } catch (error) {
                    Notification.error('测试任务完成通知发送失败: ' + error.message);
                } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            });
        });
    }
}


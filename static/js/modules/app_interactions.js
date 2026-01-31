﻿﻿﻿﻿﻿// 全局交互事件委托
var appInteractionsInitialized = false;

function initAppInteractions(mainContent) {
    if (appInteractionsInitialized) return;
    appInteractionsInitialized = true;
    if (!mainContent) return;

    // --- 动态内容事件委托 ---
    mainContent.addEventListener('click', async (event) => {
        const target = event.target;
        const button = target.closest('button'); // 获取最近的按钮元素
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
                    deleteResultsBatch({
                        filename: selectedFile,
                        item_ids: [itemId]
                    }).then(async result => {
                        if (result) {
                            await fetchAndRenderResults({ force: true });
                        }
                    });
                } else {
                    card.remove();
                }
            }
            return;
        }


        const taskContainer = button.closest('tr, .task-card');
        const row = taskContainer && taskContainer.matches('tr') ? taskContainer : null;
        const taskId = taskContainer ? taskContainer.dataset.taskId : null;
        const taskData = taskContainer && taskContainer.dataset.task ? JSON.parse(taskContainer.dataset.task) : null;

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

            const tasks = await fetchTasks();
            renderTasksInto(document.getElementById('tasks-table-container'), tasks);
        } else if (button.matches('.stop-task-btn')) {
            const taskId = button.dataset.taskId;
            button.disabled = true;
            button.textContent = '停止中...';
            await stopSingleTask(taskId);

            const tasks = await fetchTasks();
            renderTasksInto(document.getElementById('tasks-table-container'), tasks);
        } else if (button.matches('.edit-btn')) {
            if (!taskData || !taskId) return;
            openEditTaskModal(taskData, taskId);
        } else if (button.matches('.delete-btn')) {
            const taskName = taskData?.task_name || (row ? row.querySelector('td:nth-child(2)')?.innerText.trim() : '');
            if (confirm(`你确定要删除任务 "${taskName}" 吗`)) {
                const result = await deleteTask(taskId);
                if (result && taskContainer) {
                    taskContainer.remove();
                }
            }
        } else if (button.matches('.copy-btn')) {


            const task = taskData || (row ? JSON.parse(row.dataset.task) : null);
            if (!task) return;


            const newTaskData = {
                task_name: task.task_name,
                enabled: task.enabled,
                keyword: task.keyword,
                description: task.description,
                min_price: task.min_price,
                max_price: task.max_price,
                personal_only: task.personal_only,
                max_pages: task.max_pages,
                cron: task.cron,
                ai_prompt_base_file: task.ai_prompt_base_file,
                ai_prompt_criteria_file: task.ai_prompt_criteria_file,
                bayes_profile: task.bayes_profile || 'bayes_v1',
                is_running: false
            };


            try {
                const response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(newTaskData),
                });

                if (response.ok) {

                    const container = document.getElementById('tasks-table-container');
                    const tasks = await fetchTasks();
                    renderTasksInto(container, tasks);
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
                renderTasksInto(container, tasks);
            }
        } else if (button.matches('.cancel-btn')) {
            const container = document.getElementById('tasks-table-container');
            const tasks = await fetchTasks();
            renderTasksInto(container, tasks);
        } else if (button.matches('.refresh-criteria')) {
            const task = JSON.parse(row.dataset.task);
            openAiCriteriaModal({
                mode: 'generate',
                task,
                taskId,
                criteriaFile: task.ai_prompt_criteria_file || 'N/A'
            });
        } else if (button.matches('.criteria-btn')) {
            const task = JSON.parse(row.dataset.task);
            openAiCriteriaModal({
                mode: 'edit',
                task,
                taskId,
                criteriaFile: button.dataset.criteriaFile
            });
        } else if (button.matches('.send-notification-btn')) {
            const card = button.closest('.result-card');
            const notificationData = JSON.parse(card.dataset.notification);


            button.disabled = true;
            button.textContent = '发送中...';


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

                button.disabled = false;
                button.textContent = '发送通知';
            }).catch(error => {

                button.disabled = false;
                button.textContent = '发送通知';
            });
        }
    });

    mainContent.addEventListener('change', async (event) => {
        const target = event.target;

        if (target.matches('.task-enabled-toggle') && !target.closest('tr.editing')) {
            const row = target.closest('tr, .task-card');
            const taskId = row.dataset.taskId;
            const isEnabled = target.checked;

            if (taskId) {
                await updateTask(taskId, { enabled: isEnabled });
                // 立即刷新任务列表以更新运行状态
                const container = document.getElementById('tasks-table-container');
                const tasks = await fetchTasks();
                renderTasksInto(container, tasks);
            }
        }
    });


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
                form.reset();
            }, 300);
        };

        closeModalBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);

        let canClose = false;
        const updateReferenceDefault = () => {
            const selector = document.getElementById('reference-file-selector');
            if (!selector) return;
            const current = selector.value;
            if (current && current !== 'prompts/base_prompt.txt') return;
            const preferred = selector.dataset.preferred;
            if (!preferred) return;
            const targetValue = preferred.startsWith('prompts/') ? preferred : `prompts/${preferred}`;
            const match = Array.from(selector.options).find(option => option.value === targetValue);
            if (match) {
                selector.value = targetValue;
            }
        };

        const saveReferenceDefault = () => {
            const selector = document.getElementById('reference-file-selector');
            if (!selector) return;
            if (selector.value) {
                selector.dataset.preferred = selector.value;
            }
        };

        modal.addEventListener('transitionend', () => {
            if (modal.style.display === 'flex' && modal.classList.contains('visible')) {
                loadReferenceFiles().then(updateReferenceDefault);
                loadAccountSelector(); // 加载账号选择器
            }
        });

        modal.addEventListener('mousedown', event => {
            canClose = event.target === modal;
        });
        modal.addEventListener('mouseup', (event) => {

            if (canClose && event.target === modal) {
                closeModal();
            }
        });


        async function loadReferenceFiles() {
            try {
                const response = await fetch('/api/prompts');
                const referenceFiles = await response.json();
                const selector = document.getElementById('reference-file-selector');


                selector.innerHTML = '';


                if (referenceFiles.length === 0) {
                    selector.innerHTML = '<option value="">没有可用的参考文件</option>';
                    return;
                }


                const preferred = selector.dataset.preferred
                    ? selector.dataset.preferred.replace(/^prompts[\\/]/i, '')
                    : '';
                let matchedPreferred = false;
                referenceFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = 'prompts/' + file;
                    option.textContent = file;

                    if (preferred && file === preferred) {
                        option.selected = true;
                        matchedPreferred = true;
                    } else if (!preferred && file === 'base_prompt.txt') {
                        option.selected = true;
                    }
                    selector.appendChild(option);
                });
                if (preferred && !matchedPreferred) {
                    const fallback = selector.querySelector('option[value="prompts/base_prompt.txt"]');
                    if (fallback) {
                        fallback.selected = true;
                    }
                }


                const previewBtn = document.getElementById('preview-reference-file-btn');
                previewBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const selectedFile = selector.value;
                    if (!selectedFile) {
                        alert('请先选择一个参考文件模板');
                        return;
                    }
                    saveReferenceDefault();
                    loadReferenceFilePreview(selectedFile);
                });

            } catch (error) {
                console.error('无法加载参考文件列表:', error);
                const selector = document.getElementById('reference-file-selector');
                selector.innerHTML = '<option value="">加载参考文件失败</option>';
            }
        }

        const referenceSelector = document.getElementById('reference-file-selector');
        if (referenceSelector && !referenceSelector.dataset.bound) {
            referenceSelector.dataset.bound = '1';
            referenceSelector.addEventListener('change', saveReferenceDefault);
            referenceSelector.addEventListener('blur', saveReferenceDefault);
        }


        async function loadAccountSelector() {
            try {
                const selector = document.getElementById('bound-account');
                if (!selector) return;

                const accounts = await fetchAccounts();


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

            if (!validateTaskFiltersForm('region-province', 'region-city', 'region-district', 'new-publish-option')) {
                return;
            }

            const formData = new FormData(form);
            const referenceSelector = document.getElementById('reference-file-selector');
            const boundAccountSelector = document.getElementById('bound-account');
            const autoSwitchCheckbox = document.getElementById('auto-switch-on-risk');
            const regionValue = buildRegionValue(
                document.getElementById('region-province')?.value || '',
                document.getElementById('region-city')?.value || '',
                document.getElementById('region-district')?.value || ''
            );

            const data = {
                task_name: formData.get('task_name'),
                keyword: formData.get('keyword'),
                description: formData.get('description'),
                min_price: formData.get('min_price') || null,
                max_price: formData.get('max_price') || null,
                personal_only: formData.get('personal_only') === 'on',
                free_shipping: formData.get('free_shipping') === 'on',
                inspection_service: formData.get('inspection_service') === 'on',
                account_assurance: formData.get('account_assurance') === 'on',
                super_shop: formData.get('super_shop') === 'on',
                brand_new: formData.get('brand_new') === 'on',
                strict_selected: formData.get('strict_selected') === 'on',
                resale: formData.get('resale') === 'on',
                new_publish_option: formData.get('new_publish_option') || null,
                region: regionValue || null,
                max_pages: parseInt(formData.get('max_pages'), 10) || 3,
                cron: formData.get('cron') || null,
                reference_file: referenceSelector.value,
                bound_account: boundAccountSelector ? boundAccountSelector.value : null,
                auto_switch_on_risk: autoSwitchCheckbox ? autoSwitchCheckbox.checked : false,
                bayes_profile: document.getElementById('bayes-profile')?.value || 'bayes_v1',
            };


            const btnText = saveBtn.querySelector('.btn-text');
            const spinner = saveBtn.querySelector('.spinner');
            btnText.style.display = 'none';
            spinner.style.display = 'inline-block';
            saveBtn.disabled = true;

            const result = await createTaskWithAI(data);


            btnText.style.display = 'inline-block';
            spinner.style.display = 'none';
            saveBtn.disabled = false;

            if (result && result.task) {
                closeModal();

                const container = document.getElementById('tasks-table-container');
                if (container) {
                    const tasks = await fetchTasks();
                    renderTasksInto(container, tasks);
                }
            }
        });

        setupRegionSelectors({
            provinceId: 'region-province',
            cityId: 'region-city',
            districtId: 'region-district',
            regionValue: ''
        }).catch(error => console.error('初始化区域选择器失败:', error));
    }


    const aiCriteriaModal = document.getElementById('ai-criteria-modal');
    if (aiCriteriaModal) {
        const form = document.getElementById('ai-criteria-form');
        const closeModalBtn = document.getElementById('close-ai-criteria-btn');
        const cancelBtn = document.getElementById('cancel-ai-criteria-btn');
        const generateBtn = document.getElementById('ai-criteria-generate-btn');
        const saveBtn = document.getElementById('ai-criteria-save-btn');
        const descriptionTextarea = document.getElementById('ai-criteria-description');
        const referenceSelector = document.getElementById('ai-criteria-reference-selector');
        const previewBtn = document.getElementById('ai-criteria-preview-btn');
        const previewContainer = document.getElementById('ai-criteria-preview-container');
        const previewContent = document.getElementById('ai-criteria-preview-content');
        const filenameInput = document.getElementById('ai-criteria-filename');
        const sourceInput = document.getElementById('ai-criteria-source');
        const editorTextarea = document.getElementById('ai-criteria-editor');
        const bayesSelector = document.getElementById('ai-criteria-bayes-profile');

        const closeModal = () => {
            aiCriteriaModal.classList.remove('visible');
            setTimeout(() => {
                aiCriteriaModal.style.display = 'none';
                form.reset();
                filenameInput.value = '';
                if (sourceInput) sourceInput.value = '';
                editorTextarea.value = '';
                previewContainer.style.display = 'none';
            }, 300);
        };

        closeModalBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);

        let canClose = false;
        aiCriteriaModal.addEventListener('mousedown', event => {
            canClose = event.target === aiCriteriaModal;
        });
        aiCriteriaModal.addEventListener('mouseup', (event) => {
            if (canClose && event.target === aiCriteriaModal) {
                closeModal();
            }
        });

        const setActiveTab = (tabName) => {
            const tabs = Array.from(document.querySelectorAll('.ai-criteria-tab'));
            tabs.forEach(tab => {
                const isActive = tab.dataset.tab === tabName;
                tab.classList.toggle('active', isActive);
                tab.style.borderBottom = isActive ? '2px solid #1890ff' : 'none';
                tab.style.color = isActive ? '#1890ff' : '#666';
            });
            document.querySelectorAll('.ai-criteria-tab-content').forEach(content => {
                content.style.display = 'none';
            });
            const content = document.getElementById(`ai-criteria-tab-${tabName}`);
            if (content) content.style.display = 'block';

            generateBtn.style.display = tabName === 'generate' ? 'inline-flex' : 'none';
            saveBtn.style.display = tabName === 'edit' ? 'inline-flex' : 'none';
        };

        document.querySelectorAll('.ai-criteria-tab').forEach(tab => {
            tab.addEventListener('click', () => {
            if (tab.dataset.tab === 'edit' && tab.disabled) {
                return;
            }
                setActiveTab(tab.dataset.tab);
                if (tab.dataset.tab === 'edit') {
                    loadEditContent(aiCriteriaModal.dataset.criteriaFile);
                }
            });
        });

        const loadReferenceFiles = async (preferredFileName = '') => {
            try {
                const response = await fetch('/api/prompts');
                const referenceFiles = await response.json();
                referenceSelector.innerHTML = '';
                if (referenceFiles.length === 0) {
                    referenceSelector.innerHTML = '<option value="">没有可用的参考文件</option>';
                    return;
                }
                const preferred = (preferredFileName || '').trim();
                let matchedPreferred = false;
                referenceFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = 'prompts/' + file;
                    option.textContent = file;
                    if (preferred && file === preferred) {
                        option.selected = true;
                        matchedPreferred = true;
                    } else if (!preferred && file === 'base_prompt.txt') {
                        option.selected = true;
                    }
                    referenceSelector.appendChild(option);
                });
                if (preferred && !matchedPreferred) {
                    const fallback = referenceSelector.querySelector('option[value="prompts/base_prompt.txt"]');
                    if (fallback) {
                        fallback.selected = true;
                    }
                }
            } catch (error) {
                console.error('无法加载参考文件列表:', error);
                referenceSelector.innerHTML = '<option value="">加载参考文件失败</option>';
            }
        };

        const normalizePromptFileName = (value) => {
            if (!value) return '';
            const cleaned = value.replace(/^prompts[\\/]/i, '').trim();
            return cleaned.split(/[\\/]/).pop() || cleaned;
        };

        const resolveBasePromptName = (task) => {
            const baseName = normalizePromptFileName(task?.ai_prompt_base_file || '');
            const criteriaName = normalizePromptFileName(task?.ai_prompt_criteria_file || '');
            if (criteriaName && /_prompt\.txt$/i.test(criteriaName) && (!baseName || baseName === 'base_prompt.txt')) {
                return criteriaName;
            }
            return baseName;
        };

        const loadBayesProfiles = async (preferredProfile = '') => {
            if (!bayesSelector) return;
            try {
                const profiles = await fetchBayesProfiles();
                bayesSelector.innerHTML = '';
                if (!profiles || !Array.isArray(profiles) || profiles.length === 0) {
                    bayesSelector.innerHTML = '<option value="">没有找到Bayes文件</option>';
                    return;
                }
                const preferred = (preferredProfile || '').trim();
                const preferredWithExt = preferred && preferred.endsWith('.json') ? preferred : (preferred ? `${preferred}.json` : '');
                let matchedPreferred = false;
                profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile;
                    option.textContent = profile;
                    if (preferred && (profile === preferred || profile === preferredWithExt)) {
                        option.selected = true;
                        matchedPreferred = true;
                    }
                    bayesSelector.appendChild(option);
                });
                if (preferred && !matchedPreferred) {
                    const fallback = bayesSelector.querySelector('option[value="bayes_v1.json"]')
                        || bayesSelector.querySelector('option[value="bayes_v1"]');
                    if (fallback) {
                        fallback.selected = true;
                    }
                }
                if (!preferred && !bayesSelector.querySelector('option[selected]')) {
                    const fallback = bayesSelector.querySelector('option[value="bayes_v1.json"]')
                        || bayesSelector.querySelector('option[value="bayes_v1"]');
                    if (fallback) {
                        fallback.selected = true;
                    }
                }
            } catch (error) {
                console.error('无法加载Bayes文件列表:', error);
                bayesSelector.innerHTML = '<option value="">加载Bayes文件失败</option>';
            }
        };

        previewBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const selectedFile = referenceSelector.value;
            if (!selectedFile) {
                alert('请先选择一个参考文件模板');
                return;
            }
            try {
                previewContent.textContent = '正在加载预览...';
                previewContainer.style.display = 'block';
                const fileName = selectedFile.replace('prompts/', '');
                const response = await fetch(`/api/prompts/${fileName}`);
                const data = await response.json();
                previewContent.textContent = data.content;
            } catch (error) {
                console.error('无法加载参考文件内容:', error);
                previewContent.textContent = '预览加载失败，请稍后重试...';
            }
        });

        const updateEditDisabledState = (task) => {
            const isGenerating = !!task?.generating_ai_criteria;
            const hasCriteria = aiCriteriaModal.dataset.hasCriteria === '1';
            const editTab = Array.from(document.querySelectorAll('.ai-criteria-tab'))
                .find(tab => tab.dataset.tab === 'edit');
            if (editTab) {
                editTab.disabled = isGenerating || !hasCriteria;
                editTab.style.opacity = (isGenerating || !hasCriteria) ? '0.5' : '';
                editTab.style.cursor = (isGenerating || !hasCriteria) ? 'not-allowed' : 'pointer';
            }
            editorTextarea.disabled = isGenerating || !hasCriteria;
            if (saveBtn.style.display !== 'none') {
                saveBtn.disabled = isGenerating || !hasCriteria;
            }
        };

        const updateGenerateButtonState = (task) => {
            const btnText = generateBtn.querySelector('.btn-text');
            const spinner = generateBtn.querySelector('.spinner');
            const loadingText = generateBtn.querySelector('.loading-text');

            btnText.style.display = 'inline-block';
            spinner.style.display = 'none';
            loadingText.style.display = 'none';
            generateBtn.disabled = false;

            if (task && task.generating_ai_criteria) {
                btnText.style.display = 'none';
                spinner.style.display = 'inline-block';
                loadingText.style.display = 'inline-block';
                generateBtn.disabled = true;
            }
        };

        const loadEditContent = async (criteriaFile) => {
            if (!criteriaFile || criteriaFile === 'N/A' || !criteriaFile.startsWith('criteria/')) {
                editorTextarea.value = '(尚未生成AI标准)';
                return;
            }
            try {
                const isCriteriaFile = criteriaFile.startsWith('criteria/');
                const isRequirementFile = criteriaFile.startsWith('requirement/');
                const cleanFileName = criteriaFile.replace('criteria/', '').replace('prompts/', '').replace('requirement/', '');
                let data;
                if (isCriteriaFile || isRequirementFile) {
                    const response = await fetch(`/api/criteria/${encodeURIComponent(cleanFileName)}`);
                    data = await response.json();
                } else {
                    data = await fetchPromptContent(cleanFileName);
                }
                editorTextarea.value = data?.content || '(暂无内容)';
            } catch (error) {
                console.error('Failed to load file:', error);
                editorTextarea.value = '加载文件失败，请稍后重试...';
            }
        };

        window.openAiCriteriaModal = async ({ mode, task, taskId, criteriaFile }) => {
            aiCriteriaModal.dataset.taskId = taskId;
            aiCriteriaModal.dataset.criteriaFile = criteriaFile || 'N/A';
            aiCriteriaModal.dataset.hasCriteria = criteriaFile && criteriaFile.startsWith('criteria/') ? '1' : '0';
            descriptionTextarea.value = task?.description || '';
            filenameInput.value = criteriaFile && criteriaFile !== 'N/A' && criteriaFile.startsWith('criteria/')
                ? criteriaFile.replace(/^(prompts|requirement|criteria)[\\/]/i, '')
                : '';
            const baseName = resolveBasePromptName(task);
            const preferReference = baseName || '';
            if (sourceInput) {
                // 展示本次标准生成所使用的参考模板来源，尽量清洗为文件名
                sourceInput.value = baseName || '(未知来源)';
            }
            editorTextarea.value = '';
            previewContainer.style.display = 'none';

            await loadReferenceFiles(preferReference);
            await loadBayesProfiles(task?.bayes_profile || '');
            updateGenerateButtonState(task || null);
            updateEditDisabledState(task || null);
            setActiveTab(mode === 'edit' ? 'edit' : 'generate');
            if (mode === 'edit') {
                await loadEditContent(criteriaFile);
            }
            const btnText = generateBtn.querySelector('.btn-text');
            if (btnText) {
                btnText.textContent = aiCriteriaModal.dataset.hasCriteria === '1' ? '重新生成' : '新生成';
            }

            aiCriteriaModal.style.display = 'flex';
            setTimeout(() => aiCriteriaModal.classList.add('visible'), 10);
        };

        generateBtn.addEventListener('click', async () => {
            try {
                const aiSettingsResponse = await fetch('/api/settings/ai');
                const aiSettings = await aiSettingsResponse.json();

                if (!aiSettings.OPENAI_BASE_URL || !aiSettings.OPENAI_MODEL_NAME) {
                    alert('请先到系统设置-AI模型配置-配置ai模型api接口');
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

            const btnText = generateBtn.querySelector('.btn-text');
            const spinner = generateBtn.querySelector('.spinner');
            const loadingText = generateBtn.querySelector('.loading-text');
            btnText.textContent = aiCriteriaModal.dataset.hasCriteria === '1' ? '重新生成' : '新生成';
            btnText.style.display = 'none';
            spinner.style.display = 'inline-block';
            loadingText.style.display = 'inline-block';
            generateBtn.disabled = true;

            const modalTaskId = aiCriteriaModal.dataset.taskId;
            const formData = new FormData(form);

            const updateData = {
                description: formData.get('description'),
                reference_file: referenceSelector.value,
                generating_ai_criteria: true
            };
            if (bayesSelector && bayesSelector.value) {
                updateData.bayes_profile = bayesSelector.value;
            }

            try {
                await updateTask(modalTaskId, updateData);

                const taskRow = document.querySelector(`tr[data-task-id="${modalTaskId}"]`);
                if (taskRow) {
                    updateEditDisabledState({ generating_ai_criteria: true });
                    const statusBadge = taskRow.querySelector('.status-badge');
                    if (statusBadge) {
                        statusBadge.className = 'status-badge status-generating';
                        statusBadge.textContent = '生成中';
                        statusBadge.style.backgroundColor = 'orange';
                    }

                    const actionButtons = taskRow.querySelectorAll('.action-btn');
                    actionButtons.forEach(btn => {
                        btn.disabled = true;
                        btn.style.backgroundColor = '#ccc';
                        btn.style.cursor = 'not-allowed';
                    });

                    const criteriaButtons = taskRow.querySelectorAll('.refresh-criteria, .criteria-btn');
                    criteriaButtons.forEach(btn => {
                        btn.disabled = true;
                        btn.style.backgroundColor = '#ccc';
                        btn.style.cursor = 'not-allowed';
                    });

                    const toggleSwitch = taskRow.querySelector('.switch input[type="checkbox"]');
                    if (toggleSwitch) {
                        toggleSwitch.disabled = true;
                    }
                }
            } catch (error) {
                console.error('更新任务失败:', error);
                alert('更新任务失败: ' + error.message);
                btnText.style.display = 'inline-block';
                spinner.style.display = 'none';
                loadingText.style.display = 'none';
                generateBtn.disabled = false;
            }
        });

        saveBtn.addEventListener('click', async () => {
            const fullFileName = aiCriteriaModal.dataset.criteriaFile;
            const content = editorTextarea.value;

            if (!fullFileName || fullFileName === 'N/A' || !content) {
                alert('请确保文件名和内容都已填写。');
                return;
            }

            try {
                let apiPath;
                if (fullFileName.includes('requirement/')) {
                    apiPath = `/api/criteria/${encodeURIComponent(fullFileName.replace('requirement/', ''))}`;
                } else if (fullFileName.includes('criteria/')) {
                    apiPath = `/api/criteria/${encodeURIComponent(fullFileName.replace('criteria/', ''))}`;
                } else if (fullFileName.includes('prompts/')) {
                    apiPath = `/api/prompts/${encodeURIComponent(fullFileName.replace('prompts/', ''))}`;
                } else {
                    apiPath = `/api/criteria/${encodeURIComponent(fullFileName)}`;
                }

                const response = await fetch(apiPath, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content }),
                });

                if (response.ok) {
                    await response.json();
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


    refreshLoginStatusWidget();


    const loginStatusWidget = document.querySelector('.login-status-widget');
    if (loginStatusWidget) {

        const manualLoginBtn = document.createElement('button');
        manualLoginBtn.id = 'manual-login-btn-header';
        manualLoginBtn.className = 'control-button primary-btn';
        manualLoginBtn.style.backgroundColor = '#dc3545';
        manualLoginBtn.style.border = '1px solid #dc3545';
        manualLoginBtn.style.color = 'white';
        manualLoginBtn.style.padding = '8px 12px';
        manualLoginBtn.style.marginRight = '15px';
        manualLoginBtn.textContent = '点击自动获取cookie登录';


        manualLoginBtn.addEventListener('click', () => {

            const modal = document.getElementById('manual-login-confirm-modal');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('visible'), 10);


            const confirmBtn = document.getElementById('confirm-manual-login-confirm-btn');
            const cancelBtn = document.getElementById('cancel-manual-login-confirm-btn');
            const closeBtn = document.getElementById('close-manual-login-confirm-modal');


            const closeModal = () => {
                modal.classList.remove('visible');
                setTimeout(() => {
                    modal.style.display = 'none';
                }, 300);
            };


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

                } catch (error) {
                    alert('启动失败: ' + error.message);
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

            if (!modal.dataset.overlayBound) {
                modal.dataset.overlayBound = '1';
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) closeModal();
                });
            }
        });


        const statusText = loginStatusWidget.querySelector('.status-text');
        if (statusText) {
            loginStatusWidget.insertBefore(manualLoginBtn, statusText);
        }
    }



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
        }
    });


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

        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        loginStateModal.addEventListener('click', (event) => {
            if (event.target === loginStateModal) {
                closeModal();
            }
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


        let mouseDownOnOverlay = false;
        editTaskModal.addEventListener('mousedown', (event) => {
            mouseDownOnOverlay = (event.target === editTaskModal);
        });
        editTaskModal.addEventListener('click', (event) => {

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

            if (!validateTaskFiltersForm('edit-region-province', 'edit-region-city', 'edit-region-district', 'edit-new-publish-option')) {
                return;
            }

            const editRegionValue = buildRegionValue(
                document.getElementById('edit-region-province')?.value || '',
                document.getElementById('edit-region-city')?.value || '',
                document.getElementById('edit-region-district')?.value || ''
            );

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
                free_shipping: document.getElementById('edit-free-shipping').checked,
                inspection_service: document.getElementById('edit-inspection-service').checked,
                account_assurance: document.getElementById('edit-account-assurance').checked,
                super_shop: document.getElementById('edit-super-shop').checked,
                brand_new: document.getElementById('edit-brand-new').checked,
                strict_selected: document.getElementById('edit-strict-selected').checked,
                resale: document.getElementById('edit-resale').checked,
                new_publish_option: document.getElementById('edit-new-publish-option').value || null,
                region: editRegionValue || null,
                bayes_profile: document.getElementById('edit-bayes-profile')?.value || 'bayes_v1',
            };

            // 保存更改不发送description字段，避免触发AI生成
            // AI生成由"新生成并保存/重新生成并保存"按钮单独处理

            // 只有当选择了参考文件时才添加到数据中（不触发生成）
            const referenceFile = document.getElementById('edit-reference-file-selector').value;
            if (referenceFile) {
                data.ai_prompt_base_file = referenceFile.startsWith('prompts/')
                    ? referenceFile
                    : `prompts/${referenceFile}`;
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
                    renderTasksInto(document.getElementById('tasks-table-container'), tasks);
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
            document.getElementById('edit-free-shipping').checked = taskData.free_shipping || false;
            document.getElementById('edit-inspection-service').checked = taskData.inspection_service || false;
            document.getElementById('edit-account-assurance').checked = taskData.account_assurance || false;
            document.getElementById('edit-super-shop').checked = taskData.super_shop || false;
            document.getElementById('edit-brand-new').checked = taskData.brand_new || false;
            document.getElementById('edit-strict-selected').checked = taskData.strict_selected || false;
            document.getElementById('edit-resale').checked = taskData.resale || false;
            document.getElementById('edit-new-publish-option').value = taskData.new_publish_option || '';
            const editBayesProfile = document.getElementById('edit-bayes-profile');
            if (editBayesProfile) {
                editBayesProfile.value = taskData.bayes_profile || 'bayes_v1';
            }
            await setupRegionSelectors({
                provinceId: 'edit-region-province',
                cityId: 'edit-region-city',
                districtId: 'edit-region-district',
                regionValue: taskData.region || ''
            });

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
                if (!selectedFile || selectedFile === '保持现有模板') {
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
                        renderTasksInto(document.getElementById('tasks-table-container'), tasks);
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
}

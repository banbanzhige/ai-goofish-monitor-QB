// 结果视图
var resultViewPage = 1;
var resultViewPreference = null;
var resultViewTasks = [];
var pendingResultFilters = null;
var resultPreferenceTimer = null;
var editingResultRule = null;

async function loadResultBlacklistRules() {
    const list = document.getElementById('blacklist-rules-list');
    if (!list) return;
    try {
        const data = await resultManagementRequest('blacklist-rules?limit=50');
        list.replaceChildren();
        for (const rule of data.items || []) {
            const row = document.createElement('div');
            row.className = 'filter-group';
            const label = document.createElement('span');
            label.textContent = `${rule.enabled ? '启用' : '停用'} · ${rule.scope === 'global' ? '本人所有任务' : (rule.task_name_snapshot || '当前任务')} · ${rule.kind} · ${rule.pattern}`;
            row.appendChild(label);
            for (const [text, action] of [['编辑', 'edit'], [rule.enabled ? '停用' : '启用', 'toggle'], ['删除', 'delete']]) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'control-button';
                button.textContent = text;
                button.addEventListener('click', async () => {
                    if (action === 'edit') {
                        editingResultRule = rule;
                        document.getElementById('blacklist-kind').value = rule.kind;
                        document.getElementById('blacklist-pattern').value = rule.pattern;
                        document.getElementById('blacklist-global').checked = rule.scope === 'global';
                        document.getElementById('add-blacklist-btn').textContent = '保存修改';
                        return;
                    }
                    try {
                        if (action === 'delete') {
                            const confirmed = await Notification.confirm('确定删除这条黑名单规则吗？');
                            if (!confirmed.isConfirmed) return;
                            await resultManagementRequest(`blacklist-rules/${encodeURIComponent(rule.id)}?expected_revision=${rule.revision}`, { method: 'DELETE' });
                        } else {
                            await resultManagementRequest(`blacklist-rules/${encodeURIComponent(rule.id)}`, {
                                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ expected_revision: rule.revision, enabled: !rule.enabled })
                            });
                        }
                        await loadResultBlacklistRules();
                        await fetchAndRenderResults({ force: true });
                    } catch (error) {
                        console.error('修改黑名单规则失败:', error);
                        Notification.error(error.message);
                    }
                });
                row.appendChild(button);
            }
            list.appendChild(row);
        }
        if (!(data.items || []).length) list.textContent = '还没有黑名单规则。';
    } catch (error) {
        console.error('读取黑名单规则失败:', error);
        list.textContent = `无法读取规则：${error.message}`;
    }
}

function resultRulePayload() {
    const selectedFile = document.getElementById('result-file-selector')?.value;
    const global = document.getElementById('blacklist-global')?.checked;
    if (!global && !resultTaskRef(selectedFile)) {
        throw new Error('请先选择一个具体任务，或明确勾选“本人所有任务”。');
    }
    return {
        scope: global ? 'global' : 'task', task_ref: global ? null : resultTaskRef(selectedFile),
        kind: document.getElementById('blacklist-kind').value,
        pattern: document.getElementById('blacklist-pattern').value.trim(),
        filename: selectedFile
    };
}

function resultTaskRef(filename) {
    if (filename === 'all') return null;
    const task = resultViewTasks.find(item => `${String(item.task_name || '').replace(/ /g, '_').replace(/\//g, '_')}_full_data.jsonl` === filename);
    return task?.stable_task_id || null;
}

async function saveResultViewPreference() {
    if (!resultViewPreference) return;
    const selector = document.getElementById('result-file-selector');
    if (!selector) return;
    const filters = {
        recommended_only: !!document.getElementById('recommended-only-checkbox')?.checked,
        include_hidden: !!document.getElementById('include-hidden-checkbox')?.checked,
        task_name: document.getElementById('task-name-filter')?.value || 'all',
        keyword: document.getElementById('keyword-filter')?.value || 'all',
        ai_criteria: document.getElementById('ai-criteria-filter')?.value || 'all',
        manual_keyword: document.getElementById('manual-keyword-filter')?.value || ''
    };
    try {
        resultViewPreference = await resultManagementRequest('view-preferences', {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ expected_revision: resultViewPreference.revision,
                task_ref: resultTaskRef(selector.value), filters,
                sort_by: document.getElementById('sort-by-selector')?.value || 'crawl_time',
                sort_order: document.getElementById('sort-order-selector')?.value || 'desc' })
        });
    } catch (error) {
        console.error('保存结果筛选偏好失败:', error);
        Notification.warning(`筛选偏好未保存：${error.message}`);
        try { resultViewPreference = await resultManagementRequest('view-preferences'); }
        catch (reloadError) { console.error('重读结果筛选偏好失败:', reloadError); }
    }
}

function scheduleResultPreferenceSave() {
    if (resultPreferenceTimer) clearTimeout(resultPreferenceTimer);
    resultPreferenceTimer = setTimeout(saveResultViewPreference, 500);
}

async function fetchAndRenderResults(options = {}) {
    const { silent = false, force = false } = options;
    const scrollContainer = document.querySelector('main');
    const scrollTop = scrollContainer ? scrollContainer.scrollTop : window.scrollY;
    const restoreScroll = () => {
        if (scrollContainer) {
            scrollContainer.scrollTop = scrollTop;
        } else {
            window.scrollTo(0, scrollTop);
        }
    };

    const selector = document.getElementById('result-file-selector');
    const checkbox = document.getElementById('recommended-only-checkbox');
    const sortBySelector = document.getElementById('sort-by-selector');
    const sortOrderSelector = document.getElementById('sort-order-selector');
    const taskNameFilter = document.getElementById('task-name-filter');
    const keywordFilter = document.getElementById('keyword-filter');
    const aiCriteriaFilter = document.getElementById('ai-criteria-filter');
    const manualKeywordFilter = document.getElementById('manual-keyword-filter');
    const includeHiddenCheckbox = document.getElementById('include-hidden-checkbox');
    const container = document.getElementById('results-grid-container');
    const selectToggleBtn = document.getElementById('toggle-results-selection');

    if (!selector || !checkbox || !container || !sortBySelector || !sortOrderSelector || !taskNameFilter || !keywordFilter || !aiCriteriaFilter || !manualKeywordFilter || !selectToggleBtn) return;

    const selectedFile = selector.value;
    const restored = pendingResultFilters;
    const recommendedOnly = restored ? !!restored.recommended_only : checkbox.checked;
    const taskName = restored?.task_name || taskNameFilter.value;
    const keyword = restored?.keyword || keywordFilter.value;
    const manualKeyword = restored?.manual_keyword ?? manualKeywordFilter.value;
    const aiCriteria = restored?.ai_criteria || aiCriteriaFilter.value;
    const sortBy = sortBySelector.value;
    const sortOrder = sortOrderSelector.value;

    if (!selectedFile) {
        container.innerHTML = '<p>请先选择一个结果文件。</p>';
        lastResultsSignature = null;
        restoreScroll();
        return;
    }

    if (!silent) {
        container.innerHTML = '<p>正在加载结果...</p>';
    }
    let dataForDisplay = null;
    try {
        dataForDisplay = await fetchResultContent(selectedFile, recommendedOnly, taskName, keyword,
            aiCriteria, sortBy, sortOrder, manualKeyword, resultViewPage, includeHiddenCheckbox?.checked || false);
    } catch (error) {
        console.error('结果加载失败:', error);
        container.innerHTML = '<p>结果加载失败，请稍后重试。</p>';
        restoreScroll();
        return;
    }

    // 总是更新筛选控件的选项，无论当前筛选条件是什么
    if (dataForDisplay && dataForDisplay.filter_options) {
        const taskNames = dataForDisplay.filter_options.task_names || [];
        const keywords = dataForDisplay.filter_options.keywords || [];
        const aiCriterias = dataForDisplay.filter_options.ai_criteria || [];

        // 更新任务名称筛选
        taskNameFilter.replaceChildren(new Option('所有任务', 'all'), ...taskNames.map(name => new Option(name, name)));
        // 恢复当前选择
        taskNameFilter.value = taskNames.includes(taskName) ? taskName : 'all';

        // 更新关键词筛选
        keywordFilter.replaceChildren(new Option('所有关键词', 'all'), ...keywords.map(value => new Option(value, value)));
        // 恢复当前选择
        keywordFilter.value = keywords.includes(keyword) ? keyword : 'all';

        // 更新AI标准筛选，优化显示内容，仅保留核心信息
        aiCriteriaFilter.replaceChildren(new Option('所有AI标准', 'all'), ...aiCriterias.map(criteria => {
            // 移除前缀和后缀，仅保留核心信息
            const displayText = criteria
                .replace(/^criteria\//i, '') // 移除前缀
                .replace(/_criteria\.txt$/i, '') // 移除后缀
                .replace(/^prompts\/(.*?)_criteria\.txt$/i, '$1'); // 处理旧路径

            return new Option(displayText, criteria);
        }));
        // 恢复当前选择
        aiCriteriaFilter.value = aiCriterias.includes(aiCriteria) ? aiCriteria : 'all';
    }
    pendingResultFilters = null;
    if (taskNameFilter.value !== taskName || keywordFilter.value !== keyword || aiCriteriaFilter.value !== aiCriteria) {
        resultViewPage = 1;
        scheduleResultPreferenceSave();
        await fetchAndRenderResults({ force: true });
        return;
    }
    const total = Number(dataForDisplay.total_items || 0);
    const pageCount = Math.max(1, Math.ceil(total / Number(dataForDisplay.limit || 20)));
    document.getElementById('results-page-label').textContent = `第 ${resultViewPage}/${pageCount} 页`;
    document.getElementById('results-prev-page').disabled = resultViewPage <= 1;
    document.getElementById('results-next-page').disabled = resultViewPage >= pageCount;
    const stats = dataForDisplay.view_stats || {};
    document.getElementById('results-view-stats').textContent = `当前筛选 ${total} 条；屏蔽 ${stats.hidden_count || 0} 条，黑名单命中 ${stats.blacklist_count || 0} 条。`;
    const priceStats = document.getElementById('results-price-stats');
    if (priceStats) {
        const groups = dataForDisplay.price_market_groups || [];
        const status = dataForDisplay.price_observation_status;
        priceStats.textContent = status === 'unavailable' ? '价格采样暂不可用。' :
            status === 'limit' ? '价格观察过多，请缩小任务或时间范围。' :
            groups.length ? groups.map(group => `${group.task_name || '当前任务'} · 本人该任务采样参考：${group.currency} 中位数 ${group.median_amount}，${group.sample_count} 件商品${group.reference_insufficient ? '（参考不足）' : ''}；规格、成色可能不可比。`).join(' ') :
            '近 30 天暂无可统计的价格观察。';
    }

    const signature = JSON.stringify({
        file: selectedFile,
        recommendedOnly,
        taskName,
        keyword,
        aiCriteria,
        sortBy,
        sortOrder,
        manualKeyword,
        includeHidden: includeHiddenCheckbox?.checked || false,
        page: resultViewPage,
        items: dataForDisplay?.items || [],
    });
    if (force || signature !== lastResultsSignature) {
        container.innerHTML = renderResultsGrid(dataForDisplay);
        lastResultsSignature = signature;
    }
    if (typeof window.updateSelectionControls === 'function') {
        window.updateSelectionControls();
    }
    restoreScroll();
}

async function initializeResultsView() {
    resultViewPage = 1;
    if (resultPreferenceTimer) clearTimeout(resultPreferenceTimer);
    const selector = document.getElementById('result-file-selector');
    const checkbox = document.getElementById('recommended-only-checkbox');
    const refreshBtn = document.getElementById('refresh-results-btn');
    const deleteBtn = document.getElementById('delete-results-btn');
    const feedbackTrustedBtn = document.getElementById('feedback-trusted-btn');
    const feedbackUntrustedBtn = document.getElementById('feedback-untrusted-btn');
    const selectToggleBtn = document.getElementById('toggle-results-selection');
    const sortBySelector = document.getElementById('sort-by-selector');
    const sortOrderSelector = document.getElementById('sort-order-selector');
    const advancedToggleBtn = document.getElementById('toggle-advanced-filters');
    const advancedPanel = document.getElementById('advanced-filters-panel');
    const enterSelectionBtn = document.getElementById('enter-selection-mode-btn');
    const exitSelectionBtn = document.getElementById('exit-selection-mode-btn');
    const selectionModePanel = document.getElementById('selection-mode-panel');
    const includeHidden = document.getElementById('include-hidden-checkbox');
    localStorage.removeItem('lastSelectedResultFile');
    try {
        const [preference, taskResponse] = await Promise.all([
            resultManagementRequest('view-preferences'), fetch('/api/tasks')
        ]);
        if (!taskResponse.ok) throw new Error('无法读取任务列表');
        resultViewTasks = await taskResponse.json();
        resultViewPreference = preference;
        pendingResultFilters = preference.filters || {};
        checkbox.checked = !!pendingResultFilters.recommended_only;
        includeHidden.checked = !!pendingResultFilters.include_hidden;
        document.getElementById('manual-keyword-filter').value = pendingResultFilters.manual_keyword || '';
        if (['crawl_time', 'publish_time', 'price'].includes(preference.sort_by)) sortBySelector.value = preference.sort_by;
        if (['asc', 'desc'].includes(preference.sort_order)) sortOrderSelector.value = preference.sort_order;
    } catch (error) {
        console.error('读取结果偏好失败:', error);
        Notification.warning('结果筛选偏好未能读取，将使用本次页面默认值。');
    }

    const readCardFeedbackContext = (card) => {
        if (!card) return null;
        const resultId = String(card.dataset.itemId || '').trim();
        if (!resultId) return null;

        let productData = {};
        try {
            productData = card.dataset.feedbackPayload ? JSON.parse(card.dataset.feedbackPayload) : {};
        } catch (error) {
            productData = {};
        }

        const profileVersion = String(
            card.dataset.feedbackProfile
            || productData?.profile_version
            || productData?.bayes_profile
            || productData?.ml_precalc?.bayes?.profile
            || productData?.ml_precalc?.bayes?.version
            || 'bayes_v1'
        ).trim();

        return {
            result_id: resultId,
            product_data: productData,
            keyword: String(card.dataset.feedbackKeyword || '').trim() || null,
            profile_version: profileVersion || 'bayes_v1',
        };
    };

    const updateCardFeedbackVisualState = (card, feedbackType) => {
        if (!card) return;
        const trustedBtn = card.querySelector('.overlay-trusted-btn');
        const untrustedBtn = card.querySelector('.overlay-untrusted-btn');
        const isTrusted = feedbackType === 'trusted';
        card.dataset.feedbackStatus = feedbackType;
        if (trustedBtn) {
            trustedBtn.classList.toggle('is-active', isTrusted);
            const tIcon = trustedBtn.querySelector('.fb-icon');
            const tText = trustedBtn.querySelector('.fb-text');
            if (tIcon) tIcon.textContent = isTrusted ? '✅' : '👍';
            if (tText) tText.textContent = isTrusted ? '已可信' : '可信';
        }
        if (untrustedBtn) {
            untrustedBtn.classList.toggle('is-active', !isTrusted);
            const uIcon = untrustedBtn.querySelector('.fb-icon');
            const uText = untrustedBtn.querySelector('.fb-text');
            if (uIcon) uIcon.textContent = !isTrusted ? '⛔' : '👎';
            if (uText) uText.textContent = !isTrusted ? '已不可信' : '不可信';
        }
    };

    const fileData = await fetchResultFiles();
    if (fileData && fileData.files && fileData.files.length > 0) {
        let fileToSelect = 'all';
        if (resultViewPreference?.task_ref) {
            const task = resultViewTasks.find(item => item.stable_task_id === resultViewPreference.task_ref);
            const savedFile = task ? `${String(task.task_name || '').replace(/ /g, '_').replace(/\//g, '_')}_full_data.jsonl` : '';
            if (savedFile && fileData.files.includes(savedFile)) fileToSelect = savedFile;
        }

        // Add "所有结果" option
        const options = [new Option('所有结果', 'all')].concat(
            fileData.files.map(f => {
                // 优化显示内容，仅保留核心文件名
                const displayText = f
                    .replace(/_full_data\.jsonl$/i, '') // 移除_full_data.jsonl后缀
                    .replace(/_full_data\.json$/i, '') // 移除_full_data.json后缀
                    .replace(/\.jsonl$/i, '') // 移除.jsonl后缀
                    .replace(/\.json$/i, ''); // 移除.json后缀
                return new Option(displayText, f);
            })
        );
        selector.replaceChildren(...options);
        selector.value = fileToSelect;
        if (resultViewPreference?.task_ref && fileToSelect === 'all') scheduleResultPreferenceSave();

        // 选择器的值现在已通过'selected'属性正确设置。
        // 我们可以继续添加监听器并执行初始请求。

        // 为所有筛选器添加事件监听器
        const onFilterChange = () => {
            resultViewPage = 1;
            scheduleResultPreferenceSave();
            fetchAndRenderResults();
        };
        selector.addEventListener('change', onFilterChange);

        // Initialize the "仅看AI推荐" button state
        checkbox.setAttribute('data-checked', 'false');

        // 直接处理复选框更改事件，因为它现在是input type="checkbox"类型
        checkbox.addEventListener('change', () => {
            onFilterChange();
        });

        const taskNameFilter = document.getElementById('task-name-filter');
        const keywordFilter = document.getElementById('keyword-filter');
        const aiCriteriaFilter = document.getElementById('ai-criteria-filter');
        const manualKeywordFilter = document.getElementById('manual-keyword-filter');
        if (taskNameFilter) taskNameFilter.addEventListener('change', onFilterChange);
        if (keywordFilter) keywordFilter.addEventListener('change', onFilterChange);
        if (aiCriteriaFilter) aiCriteriaFilter.addEventListener('change', onFilterChange);
        if (manualKeywordFilter) manualKeywordFilter.addEventListener('input', onFilterChange);
        includeHidden.addEventListener('change', onFilterChange);

        // 添加现有的事件监听器
        sortBySelector.addEventListener('change', onFilterChange);
        sortOrderSelector.addEventListener('change', onFilterChange);
        refreshBtn.addEventListener('click', () => fetchAndRenderResults({ force: true }));
        document.getElementById('results-prev-page').addEventListener('click', () => {
            resultViewPage = Math.max(1, resultViewPage - 1);
            fetchAndRenderResults({ force: true });
        });
        document.getElementById('results-next-page').addEventListener('click', () => {
            resultViewPage += 1;
            fetchAndRenderResults({ force: true });
        });
        document.getElementById('export-results-btn').addEventListener('click', async () => {
            const params = resultViewParams(selector.value, checkbox.checked,
                taskNameFilter?.value || 'all', keywordFilter?.value || 'all', aiCriteriaFilter?.value || 'all',
                sortBySelector.value, sortOrderSelector.value, manualKeywordFilter?.value || '', includeHidden.checked);
            try {
                const response = await fetch(`/api/result-management/export.csv?${params}`);
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data?.message || data?.detail?.message || '导出失败');
                }
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'results-view.csv';
                link.click();
                URL.revokeObjectURL(url);
            } catch (error) {
                console.error('结果导出失败:', error);
                Notification.error(error.message);
            }
        });
        document.getElementById('export-prices-btn')?.addEventListener('click', async () => {
            const params = resultViewParams(selector.value, checkbox.checked,
                taskNameFilter?.value || 'all', keywordFilter?.value || 'all', aiCriteriaFilter?.value || 'all',
                sortBySelector.value, sortOrderSelector.value, manualKeywordFilter?.value || '', includeHidden.checked);
            try {
                const response = await fetch(`/api/price-observations/export.csv?${params}`);
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data?.detail?.message || '价格观察导出失败');
                }
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'price-observations.csv';
                link.click();
                URL.revokeObjectURL(url);
            } catch (error) {
                console.error('价格观察导出失败:', error);
                Notification.error(error.message);
            }
        });
        document.getElementById('manage-blacklist-btn').addEventListener('click', async () => {
            const panel = document.getElementById('blacklist-panel');
            panel.classList.toggle('hidden');
            if (!panel.classList.contains('hidden')) await loadResultBlacklistRules();
        });
        document.getElementById('preview-blacklist-btn').addEventListener('click', async () => {
            const label = document.getElementById('blacklist-preview');
            try {
                const data = await resultManagementRequest('blacklist-rules/preview', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(resultRulePayload())
                });
                label.textContent = `前 ${data.sampled} 条抽样中命中 ${data.matched} 条：${data.items.map(item => item.title).join('、')}`;
            } catch (error) {
                console.error('预览黑名单规则失败:', error);
                label.textContent = error.message;
            }
        });
        document.getElementById('add-blacklist-btn').addEventListener('click', async () => {
            try {
                const payload = resultRulePayload();
                if (editingResultRule) {
                    await resultManagementRequest(`blacklist-rules/${encodeURIComponent(editingResultRule.id)}`, {
                        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ...payload, expected_revision: editingResultRule.revision })
                    });
                } else {
                    await resultManagementRequest('blacklist-rules', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ...payload, expected_revision: 0 })
                    });
                }
                editingResultRule = null;
                document.getElementById('add-blacklist-btn').textContent = '新增规则';
                document.getElementById('blacklist-pattern').value = '';
                await loadResultBlacklistRules();
                await fetchAndRenderResults({ force: true });
            } catch (error) {
                console.error('保存黑名单规则失败:', error);
                Notification.error(error.message);
            }
        });

        if (advancedToggleBtn && advancedPanel) {
            const isDesktop = !window.matchMedia("(max-width: 1366px) and (hover: none) and (pointer: coarse)").matches;
            let isAdvancedOpen = isDesktop;
            const updateAdvancedToggle = () => {
                advancedToggleBtn.checked = isAdvancedOpen;
                advancedToggleBtn.setAttribute('aria-expanded', isAdvancedOpen ? 'true' : 'false');
                advancedPanel.classList.toggle('is-open', isAdvancedOpen);
            };
            updateAdvancedToggle();
            advancedToggleBtn.addEventListener('change', () => {
                if (advancedToggleBtn.dataset.locked === 'true') {
                    advancedToggleBtn.checked = isAdvancedOpen;
                    return;
                }
                advancedToggleBtn.dataset.locked = 'true';
                isAdvancedOpen = advancedToggleBtn.checked;
                updateAdvancedToggle();
                setTimeout(() => {
                    advancedToggleBtn.dataset.locked = 'false';
                }, 200);
            });
        }

        const updateDeleteButtonState = () => {
            deleteBtn.disabled = !selector.value;
        };
        const updateSelectionControls = () => {
            const checkboxes = Array.from(document.querySelectorAll('.result-select-checkbox'));
            const checkedBoxes = checkboxes.filter(checkbox => checkbox.checked);
            selectToggleBtn.textContent = checkedBoxes.length === checkboxes.length && checkboxes.length > 0 ? '取消全选' : '全选';
            selectToggleBtn.disabled = checkboxes.length === 0;
            updateDeleteButtonState();
            if (feedbackTrustedBtn) feedbackTrustedBtn.disabled = checkedBoxes.length === 0;
            if (feedbackUntrustedBtn) feedbackUntrustedBtn.disabled = checkedBoxes.length === 0;
            // 更新选中计数徽章
            const badge = document.getElementById('selection-count-badge');
            if (badge) {
                if (checkedBoxes.length > 0) {
                    badge.textContent = `已选 ${checkedBoxes.length}/${checkboxes.length}`;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
            // 同步卡片选中高亮
            checkboxes.forEach(checkbox => {
                const card = checkbox.closest('.result-card');
                if (card) card.classList.toggle('is-selected', checkbox.checked);
            });
        };
        window.updateSelectionControls = updateSelectionControls;
        selector.addEventListener('change', updateDeleteButtonState);
        updateDeleteButtonState();
        updateSelectionControls();

        selectToggleBtn.addEventListener('click', () => {
            const checkboxes = Array.from(document.querySelectorAll('.result-select-checkbox'));
            if (!checkboxes.length) return;
            const shouldSelectAll = checkboxes.some(checkbox => !checkbox.checked);
            checkboxes.forEach(checkbox => {
                checkbox.checked = shouldSelectAll;
            });
            updateSelectionControls();
        });

        // 删除按钮功能
        deleteBtn.addEventListener('click', async () => {
            const selectedFile = selector.value;
            if (!selectedFile) {
                Notification.warning('请先选择一个结果文件。');
                return;
            }

            const selectedItemIds = Array.from(document.querySelectorAll('.result-select-checkbox:checked'))
                .map(checkbox => checkbox.dataset.itemId)
                .filter(Boolean);
            const taskNameFilter = document.getElementById('task-name-filter');
            const keywordFilter = document.getElementById('keyword-filter');
            const aiCriteriaFilter = document.getElementById('ai-criteria-filter');
            const manualKeywordFilter = document.getElementById('manual-keyword-filter');
            const sortBySelector = document.getElementById('sort-by-selector');
            const sortOrderSelector = document.getElementById('sort-order-selector');
            const recommendedOnly = checkbox.checked;
            const taskName = taskNameFilter ? taskNameFilter.value : 'all';
            const keyword = keywordFilter ? keywordFilter.value : 'all';
            const aiCriteria = aiCriteriaFilter ? aiCriteriaFilter.value : 'all';
            const manualKeyword = manualKeywordFilter ? manualKeywordFilter.value : '';
            const deleteBySelection = selectedItemIds.length > 0;
            const confirmMessage = deleteBySelection
                ? `你确定要删除选中的 ${selectedItemIds.length} 条结果吗？此操作不可恢复。`
                : `你确定要按当前筛选条件删除结果吗？此操作不可恢复。`;

            const confirmResult = await Notification.confirm(confirmMessage);
            if (!confirmResult.isConfirmed) {
                return;
            }

            const payload = {
                filename: selectedFile,
                filters: {
                    recommended_only: recommendedOnly,
                    task_name: taskName,
                    keyword: keyword,
                    ai_criteria: aiCriteria,
                    manual_keyword: manualKeyword || null
                },
                item_ids: deleteBySelection ? selectedItemIds : []
            };
            const result = await deleteResultsBatch(payload);
            if (result) {
                Notification.success(result.message);
                await fetchAndRenderResults({ force: true });
                updateSelectionControls();
            }
        });

        const submitBatchFeedbackByType = async (feedbackType) => {
            const checkedBoxes = Array.from(document.querySelectorAll('.result-select-checkbox:checked'));
            if (!checkedBoxes.length) {
                Notification.warning('请先勾选要反馈的商品');
                return;
            }

            const selectedCards = checkedBoxes
                .map(checkbox => checkbox.closest('.result-card'))
                .filter(card => !!card);

            const feedbacks = selectedCards
                .map(card => {
                    const context = readCardFeedbackContext(card);
                    if (!context) return null;
                    return {
                        result_id: context.result_id,
                        feedback_type: feedbackType,
                        product_data: context.product_data,
                        profile_version: context.profile_version,
                    };
                })
                .filter(item => !!item);

            if (!feedbacks.length) {
                Notification.warning('未识别到有效商品ID，无法批量反馈');
                return;
            }

            const confirmMessage = feedbackType === 'trusted'
                ? `确定将选中的 ${feedbacks.length} 条结果标记为可信吗？`
                : `确定将选中的 ${feedbacks.length} 条结果标记为不可信吗？`;
            const confirmResult = await Notification.confirm(confirmMessage);
            if (!confirmResult.isConfirmed) {
                return;
            }

            if (feedbackTrustedBtn) feedbackTrustedBtn.disabled = true;
            if (feedbackUntrustedBtn) feedbackUntrustedBtn.disabled = true;

            const result = await submitBayesBatchFeedback({ feedbacks });

            if (feedbackTrustedBtn) feedbackTrustedBtn.disabled = false;
            if (feedbackUntrustedBtn) feedbackUntrustedBtn.disabled = false;

            if (!result) {
                updateSelectionControls();
                return;
            }

            const stats = result.stats || {};
            const successCount = Number(stats.success || 0);
            const failedCount = Number(stats.failed || 0);

            if (successCount > 0) {
                selectedCards.forEach(card => updateCardFeedbackVisualState(card, feedbackType));
            }

            checkedBoxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            updateSelectionControls();

            if (failedCount > 0) {
                Notification.warning(`批量反馈完成：成功 ${successCount} 条，失败 ${failedCount} 条`);
                return;
            }
            Notification.success(`批量反馈成功：${successCount} 条`);
        };

        if (feedbackTrustedBtn) {
            feedbackTrustedBtn.addEventListener('click', async () => {
                await submitBatchFeedbackByType('trusted');
            });
        }
        if (feedbackUntrustedBtn) {
            feedbackUntrustedBtn.addEventListener('click', async () => {
                await submitBatchFeedbackByType('untrusted');
            });
        }

        // ============== 选择模式进入/退出 ==============
        let isSelectionMode = false;
        const gridContainer = document.getElementById('results-grid-container');
        const priceDialog = document.getElementById('price-history-dialog');
        const priceContent = document.getElementById('price-history-content');
        const priceMore = document.getElementById('price-history-more');
        let priceQuery = null;
        let priceCursor = null;
        document.getElementById('price-history-close')?.addEventListener('click', () => priceDialog?.close());
        const loadPriceHistory = async (append = false) => {
            if (!priceQuery || !priceContent) return;
            const params = new URLSearchParams(priceQuery);
            if (append && priceCursor) params.set('cursor', priceCursor);
            try {
                const itemId = params.get('item_id');
                params.delete('item_id');
                const response = await fetch(`/api/price-observations/items/${encodeURIComponent(itemId)}?${params}`);
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data?.detail?.message || '价格历史读取失败');
                }
                const data = await response.json();
                if (!append) {
                    priceContent.replaceChildren();
                    const summary = document.createElement('p');
                    const first = data.summaries?.[0];
                    const change = first?.change_amount === null || first?.change_amount === undefined ? '暂无可比变动' :
                        Number(first.change_amount) > 0 ? `较上次上涨 ${first.change_amount}` :
                        Number(first.change_amount) < 0 ? `较上次下降 ${Math.abs(Number(first.change_amount)).toFixed(2)}` : '较上次持平';
                    summary.textContent = first ? `观察 ${first.observation_count} 次；最低 ${first.currency || ''} ${first.lowest_amount ?? '无有效金额'}；最高 ${first.highest_amount ?? '无有效金额'}；${change}。` : '近 30 天暂无观察。';
                    priceContent.appendChild(summary);
                    const currency = first?.currency;
                    const points = (data.items || []).filter(row => row.currency === currency && row.amount !== null)
                        .map(row => Number(row.amount)).filter(Number.isFinite).reverse();
                    if (points.length > 1) {
                        const title = document.createElement('p');
                        title.textContent = `最近 ${points.length} 次有效观察走势（${currency}，仅本页）`;
                        priceContent.appendChild(title);
                        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                        svg.setAttribute('viewBox', '0 0 320 88');
                        svg.setAttribute('role', 'img');
                        svg.setAttribute('aria-label', title.textContent);
                        svg.classList.add('price-history-chart');
                        const low = Math.min(...points);
                        const high = Math.max(...points);
                        const range = Math.max(high - low, 1);
                        const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
                        line.setAttribute('points', points.map((amount, index) =>
                            `${8 + index * 304 / (points.length - 1)},${76 - (amount - low) * 64 / range}`).join(' '));
                        line.setAttribute('fill', 'none');
                        line.setAttribute('stroke', '#2563eb');
                        line.setAttribute('stroke-width', '2.5');
                        svg.appendChild(line);
                        priceContent.appendChild(svg);
                    }
                }
                for (const row of data.items || []) {
                    const line = document.createElement('p');
                    const moment = new Date(row.observed_at);
                    line.textContent = `${Number.isNaN(moment.getTime()) ? row.observed_at : moment.toLocaleString()} · ${row.currency} · ${row.amount ?? row.raw_price} · 来源：${row.source}`;
                    priceContent.appendChild(line);
                }
                priceCursor = data.next_cursor;
                if (priceMore) priceMore.hidden = !priceCursor;
            } catch (error) {
                console.error('价格历史读取失败:', error);
                if (!append) priceContent.textContent = `价格历史读取失败：${error.message}`;
                else Notification.error(error.message);
            }
        };
        priceMore?.addEventListener('click', () => loadPriceHistory(true));

        const hasActiveSelections = () => {
            return document.querySelectorAll('.result-select-checkbox:checked').length > 0;
        };

        const toggleSelectionMode = (enter) => {
            isSelectionMode = enter;
            if (gridContainer) gridContainer.classList.toggle('selection-mode', enter);
            if (selectionModePanel) selectionModePanel.classList.toggle('hidden', !enter);
            if (enterSelectionBtn) enterSelectionBtn.classList.toggle('is-active', enter);
            // 退出选择模式时不清除勾选 — 保留选中状态
        };
        const clearAllSelections = () => {
            document.querySelectorAll('.result-select-checkbox').forEach(cb => { cb.checked = false; });
            updateSelectionControls();
        };
        // 暴露到 window，供移动端长按调用
        window._toggleSelectionMode = toggleSelectionMode;
        window._isSelectionMode = () => isSelectionMode;

        if (enterSelectionBtn) {
            enterSelectionBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止冒泡到 document 的 click-outside
                toggleSelectionMode(!isSelectionMode);
            });
        }

        // ============== 点击卡片快速选中（选择模式内外均可） ==============
        if (gridContainer) {
            gridContainer.addEventListener('click', async (e) => {
                const priceButton = e.target.closest('.price-history-btn');
                if (priceButton) {
                    e.stopPropagation();
                    if (!priceButton.dataset.itemId || !priceDialog) return;
                    const params = resultViewParams(selector.value, checkbox.checked,
                        taskNameFilter?.value || 'all', keywordFilter?.value || 'all', aiCriteriaFilter?.value || 'all',
                        sortBySelector.value, sortOrderSelector.value, manualKeywordFilter?.value || '', includeHidden.checked);
                    params.set('item_id', priceButton.dataset.itemId);
                    if (priceButton.dataset.taskRef) params.set('task_ref', priceButton.dataset.taskRef);
                    priceQuery = params;
                    priceCursor = null;
                    priceContent.textContent = '正在加载价格历史...';
                    if (priceMore) priceMore.hidden = true;
                    priceDialog.showModal();
                    await loadPriceHistory();
                    return;
                }
                const hideButton = e.target.closest('.result-hide-btn');
                if (hideButton) {
                    e.stopPropagation();
                    const itemId = hideButton.dataset.itemId;
                    if (!itemId) return;
                    try {
                        await resultManagementRequest(`hidden-items/${encodeURIComponent(itemId)}`, {
                            method: hideButton.textContent === '恢复屏蔽' ? 'DELETE' : 'PUT'
                        });
                        await fetchAndRenderResults({ force: true });
                    } catch (error) {
                        console.error('修改商品屏蔽状态失败:', error);
                        Notification.error(error.message);
                    }
                    return;
                }
                // 不拦截按钮、链接、overlay 按钮、复选框
                if (e.target.closest('button, a, .overlay-fb-btn, .result-select-checkbox, .delete-card-btn, label.result-select-box')) return;
                const card = e.target.closest('.result-card');
                if (!card) return;
                e.preventDefault();
                e.stopPropagation(); // 阻止冒泡到 document 的 click-outside
                const cb = card.querySelector('.result-select-checkbox');
                if (cb) {
                    cb.checked = !cb.checked;
                    updateSelectionControls();
                    // 如果选中了卡片但还不在选择模式，自动进入
                    if (cb.checked && !isSelectionMode) {
                        toggleSelectionMode(true);
                    }
                }
            });
        }

        // ============== 点击卡片外区域：退出选择模式 / 清除选中 ==============
        document.addEventListener('click', (e) => {
            // 忽略工具栏面板内的点击
            if (e.target.closest('.selection-mode-panel, .results-select-group, .results-batch-actions')) return;
            // 忽略卡片区域内的点击（由上面的 gridContainer handler 处理）
            if (e.target.closest('.result-card')) return;

            if (isSelectionMode) {
                // 第一次点外面 → 退出选择模式，保留选中
                toggleSelectionMode(false);
            } else if (hasActiveSelections()) {
                // 第二次点外面（已不在选择模式但有选中） → 清除选中
                clearAllSelections();
            }
        });

        // ============== 移动端长按进入选择模式 ==============
        if (gridContainer) {
            let longPressTimer = null;
            let longPressTriggered = false;

            gridContainer.addEventListener('touchstart', (e) => {
                if (isSelectionMode) return; // 已在选择模式时不需要长按
                const card = e.target.closest('.result-card');
                if (!card) return;
                longPressTriggered = false;
                longPressTimer = setTimeout(() => {
                    longPressTriggered = true;
                    toggleSelectionMode(true);
                    // 选中被长按的卡片
                    const cb = card.querySelector('.result-select-checkbox');
                    if (cb) {
                        cb.checked = true;
                        updateSelectionControls();
                    }
                    // 触觉反馈
                    if (navigator.vibrate) navigator.vibrate(30);
                }, 500);
            }, { passive: true });

            gridContainer.addEventListener('touchmove', () => {
                if (longPressTimer) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }
            }, { passive: true });

            gridContainer.addEventListener('touchend', (e) => {
                if (longPressTimer) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }
                if (longPressTriggered) {
                    e.preventDefault(); // 阻止长按后触发 click
                }
            });
        }


        await fetchAndRenderResults({ force: true });

        if (resultsRefreshInterval) {
            clearInterval(resultsRefreshInterval);
        }
        let resultsRefreshTimer = null;
        let resultsRefreshInFlight = false;
        const resultsRefreshDelayMs = 5000;
        const scheduleResultsRefresh = () => {
            if (resultsRefreshTimer) {
                clearTimeout(resultsRefreshTimer);
            }
            resultsRefreshTimer = setTimeout(async () => {
                const currentSection = location.hash.substring(1) || 'tasks';
                if (currentSection !== 'results' || resultsRefreshInFlight) {
                    scheduleResultsRefresh();
                    return;
                }
                resultsRefreshInFlight = true;
                const containerEl = document.getElementById('results-grid-container');
                const scrollTop = containerEl ? containerEl.scrollTop : 0;
                try {
                    await fetchAndRenderResults({ silent: true });
                    if (containerEl) {
                        containerEl.scrollTop = scrollTop;
                    }
                } finally {
                    resultsRefreshInFlight = false;
                    scheduleResultsRefresh();
                }
            }, resultsRefreshDelayMs);
        };
        resultsRefreshInterval = {
            stop() {
                if (resultsRefreshTimer) {
                    clearTimeout(resultsRefreshTimer);
                    resultsRefreshTimer = null;
                }
            }
        };
        scheduleResultsRefresh();
    } else {
        selector.innerHTML = '<option value="">没有可用的结果文件</option>';
        document.getElementById('results-grid-container').innerHTML = '<p>没有找到任何结果文件。请先运行监控任务。</p>';
    }
}


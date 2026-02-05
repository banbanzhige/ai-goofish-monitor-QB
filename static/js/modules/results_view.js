﻿﻿﻿// 结果视图
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
    const container = document.getElementById('results-grid-container');
    const selectToggleBtn = document.getElementById('toggle-results-selection');

    if (!selector || !checkbox || !container || !sortBySelector || !sortOrderSelector || !taskNameFilter || !keywordFilter || !aiCriteriaFilter || !manualKeywordFilter || !selectToggleBtn) return;

    const selectedFile = selector.value;
    const recommendedOnly = checkbox.checked;
    const taskName = taskNameFilter.value;
    const keyword = keywordFilter.value;
    const manualKeyword = manualKeywordFilter.value;
    const aiCriteria = aiCriteriaFilter.value;
    const sortBy = sortBySelector.value;
    const sortOrder = sortOrderSelector.value;

    if (!selectedFile) {
        container.innerHTML = '<p>请先选择一个结果文件。</p>';
        lastResultsSignature = null;
        restoreScroll();
        return;
    }

    localStorage.setItem('lastSelectedResultFile', selectedFile);

    if (!silent) {
        container.innerHTML = '<p>正在加载结果...</p>';
    }
    let dataForFilters = null;
    let dataForDisplay = null;
    try {
        // 使用所有筛选条件获取结果，但如果是查看所有结果或切换结果文件，则获取所有结果以更新筛选选项
        dataForFilters = await fetchResultContent(selectedFile, false, 'all', 'all', 'all', 'crawl_time', 'desc');
        dataForDisplay = await fetchResultContent(selectedFile, recommendedOnly, taskName, keyword, aiCriteria, sortBy, sortOrder, manualKeyword);
    } catch (error) {
        console.error('结果加载失败:', error);
        container.innerHTML = '<p>结果加载失败，请稍后重试。</p>';
        restoreScroll();
        return;
    }

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

    const signature = JSON.stringify({
        file: selectedFile,
        recommendedOnly,
        taskName,
        keyword,
        aiCriteria,
        sortBy,
        sortOrder,
        manualKeyword,
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
    const selector = document.getElementById('result-file-selector');
    const checkbox = document.getElementById('recommended-only-checkbox');
    const refreshBtn = document.getElementById('refresh-results-btn');
    const deleteBtn = document.getElementById('delete-results-btn');
    const selectToggleBtn = document.getElementById('toggle-results-selection');
    const sortBySelector = document.getElementById('sort-by-selector');
    const sortOrderSelector = document.getElementById('sort-order-selector');
    const advancedToggleBtn = document.getElementById('toggle-advanced-filters');
    const advancedPanel = document.getElementById('advanced-filters-panel');

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
        refreshBtn.addEventListener('click', () => fetchAndRenderResults({ force: true }));

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


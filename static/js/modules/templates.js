﻿// --- 各部分的模板 ---
var templates = {
    tasks: () => `
            <section id="tasks-section" class="content-section">
                <div class="section-header">
                    <h2>任务管理</h2>
                    <button id="add-task-btn" class="control-button primary-btn">➕ 创建新任务</button>
                </div>
                <div id="tasks-table-container">
                    <p>正在加载任务列表...</p>
                </div>
            </section>`,
    results: () => `
            <section id="results-section" class="content-section">
                <div class="section-header">
                    <h2>结果查看</h2>
                </div>
                <div class="results-filter-bar">
                    <div class="results-filter-primary">
                        <div class="filter-group results-file-group">
                            <div class="filter-label">结果文件</div>
                            <select id="result-file-selector">
                                <option value="">正在加载...</option>
                            </select>
                        </div>
                        <div class="filter-group results-manual-group">
                            <div class="filter-label">手动筛选</div>
                            <input type="text" id="manual-keyword-filter" class="results-manual-input" placeholder="输入关键词筛选">
                        </div>
                        <div class="filter-group results-refresh-group">
                            <div class="filter-label">刷新</div>
                            <button id="refresh-results-btn" class="control-button results-refresh-btn">🔄 刷新</button>
                        </div>
                        <div class="filter-group results-select-group">
                            <div class="filter-label">选择</div>
                            <button id="toggle-results-selection" class="control-button results-select-btn">全选</button>
                        </div>
                        <div class="filter-group">
                            <div class="filter-label">删除</div>
                            <button id="delete-results-btn" class="control-button danger-btn" disabled>删除结果</button>
                        </div>
                        <div class="results-filter-switches">
                            <div class="filter-group compact">
                                <div class="filter-label">仅看AI推荐</div>
                                <label class="switch">
                                    <input type="checkbox" id="recommended-only-checkbox">
                                    <span class="slider round"></span>
                                </label>
                            </div>
                            <div class="filter-group compact">
                                <div class="filter-label">高级筛选</div>
                                <label class="switch">
                                    <input type="checkbox" id="toggle-advanced-filters" aria-expanded="false">
                                    <span class="slider round"></span>
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="results-filter-secondary" id="advanced-filters-panel">
                        <div class="filter-group">
                            <div class="filter-label">任务名称</div>
                            <select id="task-name-filter">
                                <option value="all">所有任务</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <div class="filter-label">关键词</div>
                            <select id="keyword-filter">
                                <option value="all">所有关键词</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <div class="filter-label">AI标准</div>
                            <select id="ai-criteria-filter">
                                <option value="all">所有AI标准</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <div class="filter-label">排序字段</div>
                            <select id="sort-by-selector">
                                <option value="crawl_time">按浏览时间</option>
                                <option value="publish_time">按发布时间</option>
                                <option value="price">按价格</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <div class="filter-label">排序方式</div>
                            <select id="sort-order-selector">
                                <option value="desc">降序</option>
                                <option value="asc">升序</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div id="results-grid-container">
                    <p>请先选择一个结果文件。</p>
                </div>
            </section>`,
    logs: () => `
            <section id="logs-section" class="content-section">
                <div class="section-header">
                    <h2>运行日志</h2>
                    <div class="log-controls">
                        <div class="filter-group">
                            <label for="auto-refresh-logs-checkbox">
                                <div class="switch">
                                    <input type="checkbox" id="auto-refresh-logs-checkbox" checked>
                                    <span class="slider round"></span>
                                </div>
                                自动刷新
                            </label>
                        </div>
                        <div class="filter-group">
                            <select id="log-task-filter">
                                <option value="">所有任务</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <select id="log-display-limit">
                                <option value="100" selected>100条</option>
                                <option value="200">200条</option>
                                <option value="500">500条</option>
                                <option value="1000">1000条</option>
                            </select>
                        </div>
                        <div class="filter-group">
                            <button id="refresh-logs-btn" class="control-button">🔄 刷新</button>
                        </div>
                        <div class="filter-group">
                            <button id="clear-logs-btn" class="control-button danger-btn">🗑️ 清空日志</button>
                        </div>
                    </div>
                </div>
                <pre id="log-content-container">正在加载日志...</pre>
            </section>`,
    notifications: () => `
            <section id="notifications-section" class="content-section">
                <div class="section-header">
                    <h2>通知配置</h2>
                </div>
                <div class="settings-card">
                    <div id="notification-settings-container">
                        <p>正在加载通知配置...</p>
                    </div>
                </div>
            </section>`,
    settings: () => `
            <section id="settings-section" class="content-section">
                <h2>系统设置</h2>
                <div class="settings-tabs" role="tablist" aria-label="系统设置分组">
                    <button type="button" class="settings-tab active" data-tab="settings-tab-ai" role="tab" aria-controls="settings-tab-ai" aria-selected="true">AI模型配置</button>
                    <button type="button" class="settings-tab" data-tab="settings-tab-proxy" role="tab" aria-controls="settings-tab-proxy" aria-selected="false">代理设置</button>
                    <button type="button" class="settings-tab" data-tab="settings-tab-generic" role="tab" aria-controls="settings-tab-generic" aria-selected="false">通用配置</button>
                </div>
                <div class="settings-tab-panel active" id="settings-tab-ai" data-tab="settings-tab-ai" role="tabpanel">
                    <div class="settings-card">
                        <h3>系统状态检查</h3>
                        <div id="system-status-container"><p>正在加载状态...</p></div>
                    </div>
                    <div id="ai-settings-panel"></div>
                </div>
                <div class="settings-tab-panel" id="settings-tab-proxy" data-tab="settings-tab-proxy" role="tabpanel" hidden>
                    <div id="proxy-settings-panel"></div>
                </div>
                <div class="settings-tab-panel" id="settings-tab-generic" data-tab="settings-tab-generic" role="tabpanel" hidden>
                    <div id="generic-settings-panel"></div>
                </div>
            </section>`,
    'model-management': () => `
            <section id="model-management-section" class="content-section">
                <h2>模型管理</h2>
                <div class="settings-tabs" role="tablist" aria-label="模型管理分组">
                    <button type="button" class="settings-tab active" data-tab="settings-tab-prompt" role="tab" aria-controls="settings-tab-prompt" aria-selected="true">Prompt 管理</button>
                    <button type="button" class="settings-tab" data-tab="settings-tab-bayes" role="tab" aria-controls="settings-tab-bayes" aria-selected="false">Bayes 管理</button>
                </div>
                <div class="settings-tab-panel active" id="settings-tab-prompt" data-tab="settings-tab-prompt" role="tabpanel">
                    <div class="settings-card">
                        <h3>Prompt 管理</h3>
                        <div class="prompt-manager">
                            <div class="prompt-list-container">
                                <label for="prompt-selector">选择要编辑的 Prompt:</label>
                                <select id="prompt-selector"><option>加载中...</option></select>
                            </div>
                            <div class="prompt-editor-container">
                                <textarea id="prompt-editor" spellcheck="false" disabled placeholder="请先从上方选择一个 Prompt 文件进行编辑..."></textarea>
                                <button id="save-prompt-btn" class="control-button primary-btn" disabled>保存更改</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="settings-tab-panel" id="settings-tab-bayes" data-tab="settings-tab-bayes" role="tabpanel" hidden>
                    <div id="bayes-visual-manager-container">
                        <div class="bayes-toolbar">
                            <div class="bayes-version-selector">
                                <label for="bayes-version-select">版本:</label>
                                <select id="bayes-version-select">
                                    <option value="bayes_v1" selected>bayes_v1</option>
                                </select>
                            </div>
                            <div class="bayes-actions">
                                <button id="bayes-copy-btn" class="control-button success-btn">复制</button>
                                <button id="bayes-delete-btn" class="control-button danger-btn">删除</button>
                                <button id="bayes-reset-btn" class="control-button outline-dark-btn">重置</button>
                                <button id="bayes-save-btn" class="control-button primary-btn">保存</button>
                            </div>
                        </div>
                        <div id="bayes-cards-container">
                            <!-- 卡片将由 bayes_visual_manager.js 动态生成 -->
                        </div>
                    </div>
                </div>
            </section>`,
    scheduled: () => `
            <section id="scheduled-section" class="content-section">
                <div class="section-header">
                    <h2>定时任务</h2>
                    <button id="refresh-scheduled-btn" class="control-button" style="background-color: #52c41a; border-color: #52c41a; color: white;">🔄 刷新</button>
                </div>
                <div id="scheduled-table-container">
                    <p>正在加载定时任务...</p>
                </div>
            </section>`,
    accounts: () => `
            <section id="accounts-section" class="content-section">
                <div class="section-header">
                    <h2>闲鱼账号管理</h2>
                    <div class="header-buttons" style="justify-content: flex-end;">
                        <button id="cleanup-expired-accounts-btn" class="control-button" style="background-color: #ff4d4f; border-color: #ff4d4f; color: white;">🧹 批量清空失效账号</button>
                        <button id="import-from-login-btn" class="control-button" style="background-color: #52c41a; border-color: #52c41a; color: white;">🚀 自动获取账号</button>
                        <button id="add-account-btn" class="control-button primary-btn">✏️ 手动添加账号</button>
                    </div>
                </div>
                <div id="accounts-table-container">
                    <p>正在加载账号列表...</p>
                </div>
            </section>`
};

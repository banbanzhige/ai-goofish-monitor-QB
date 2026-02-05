/**
 * Bayes 参数可视化管理器
 * 提供基于卡片的可视化配置界面，替代JSON文本编辑器
 */

class BayesVisualManager {
    constructor() {
        this.config = null;
        this.currentVersion = 'bayes_v1';
        this.container = null;
        this.isDirty = false; // 跟踪是否有未保存的更改
        this.sampleLegacyCache = { trusted: [], untrusted: [] };
        this.trainingSampleEventsBound = false;
        this.availableVersions = [];
    }

    /**
     * 初始化管理器
     */
    async initialize() {
        this.container = document.getElementById('bayes-cards-container');
        if (!this.container) {
            console.error('Bayes cards container not found');
            return;
        }

        // 显示加载状态
        this.container.innerHTML = '<div class="loading-spinner">正在加载配置...</div>';

        try {
            const activeVersion = await this.refreshVersionOptions(this.currentVersion);
            await this.loadConfig(activeVersion);
            this.render();
            this.setupEventListeners();
        } catch (error) {
            console.error('Failed to initialize Bayes manager:', error);
            this.container.innerHTML = `
                <div class="error-message">
                    <p>❌ 加载配置失败: ${error.message}</p>
                    <button onclick="window.bayesManager.initialize()" class="control-button">重试</button>
                </div>
            `;
        }
    }

    /**
     * 加载配置文件
     */
    async loadConfig(version) {
        const response = await fetch(`/api/system/bayes/config?version=${version}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        this.config = await response.json();
        this.migrateLegacySamples();
        this.currentVersion = version;
        this.isDirty = false;
    }

    /**
     * 获取可用版本列表
     */
    async fetchVersions() {
        const response = await fetch('/api/system/bayes/versions');
        if (!response.ok) {
            throw new Error(`获取版本列表失败: ${response.status}`);
        }
        const data = await response.json();
        return Array.isArray(data.versions) ? data.versions : [];
    }

    /**
     * 刷新版本选择器
     */
    async refreshVersionOptions(preferredVersion) {
        let versions = [];
        try {
            versions = await this.fetchVersions();
        } catch (error) {
            console.warn('获取Bayes版本列表失败，将使用当前版本兜底', error);
        }

        if (!Array.isArray(versions) || versions.length === 0) {
            versions = [preferredVersion || this.currentVersion || 'bayes_v1'];
        }

        versions = Array.from(new Set(versions));

        const versionSelect = document.getElementById('bayes-version-select');
        const selectedVersion = versions.includes(preferredVersion) ? preferredVersion : versions[0];

        if (versionSelect) {
            versionSelect.innerHTML = '';
            versions.forEach((version) => {
                const option = document.createElement('option');
                option.value = version;
                option.textContent = version;
                versionSelect.appendChild(option);
            });
            versionSelect.value = selectedVersion;
        }

        const deleteBtn = document.getElementById('bayes-delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = versions.length <= 1;
        }

        this.availableVersions = versions;
        this.currentVersion = selectedVersion;
        return selectedVersion;
    }

    /**
     * 规范化版本名称
     */
    normalizeVersionName(name) {
        const trimmed = (name || '').trim();
        if (!trimmed) {
            return '';
        }
        if (trimmed.endsWith('.json')) {
            return trimmed.slice(0, -5);
        }
        return trimmed;
    }

    /**
     * 校验版本名称
     */
    isValidVersionName(version) {
        return /^[a-zA-Z0-9_-]+$/.test(version);
    }

    /**
     * 复制当前版本
     */
    async copyCurrentVersion() {
        if (!this.config) {
            Notification.warning('配置尚未加载完成');
            return;
        }

        const defaultName = `${this.currentVersion}_copy`;
        const inputResult = await Notification.input('请输入新版本名称（仅支持字母/数字/下划线/短横线）', {
            title: '复制版本',
            defaultValue: defaultName
        });
        if (!inputResult.isConfirmed) {
            return;
        }
        const inputName = (inputResult.value || '').toString();

        const newVersion = this.normalizeVersionName(inputName);
        if (!newVersion) {
            Notification.warning('版本名称不能为空。');
            return;
        }

        if (!this.isValidVersionName(newVersion)) {
            Notification.info('版本名称仅支持字母、数字、下划线和短横线。');
            return;
        }

        const versions = await this.fetchVersions().catch(() => this.availableVersions);
        if (versions && versions.includes(newVersion)) {
            Notification.warning('该版本名称已存在，请更换名称。');
            return;
        }

        if (this.isDirty) {
            const confirmResult = await Notification.confirm('当前有未保存的更改，复制将基于当前编辑内容继续，确定要继续吗？');
            if (!confirmResult.isConfirmed) {
                return;
            }
        }

        this.collectDataFromUI();
        const payload = JSON.parse(JSON.stringify(this.config));
        payload.version = newVersion;

        try {
            const response = await fetch('/api/system/bayes/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                const errorMsg = error.errors ? error.errors.join('\n') : error.detail || '复制失败';
                throw new Error(errorMsg);
            }

            await this.refreshVersionOptions(newVersion);
            await this.loadConfig(newVersion);
            this.render();
            this.setupEventListeners();
            Notification.success('✅ 复制成功');
        } catch (error) {
            console.error('Copy failed:', error);
            Notification.error(`❌ 复制失败: ${error.message}`);
        }
    }

    /**
     * 删除当前版本
     */
    async deleteCurrentVersion() {
        const versions = await this.fetchVersions().catch(() => this.availableVersions);
        if (!Array.isArray(versions) || versions.length <= 1) {
            Notification.info('至少保留一个 Bayes 版本，无法删除。');
            return;
        }

        const versionToDelete = this.currentVersion;
        if (!versionToDelete) {
            Notification.info('未选择版本，无法删除。');
            return;
        }

        if (this.isDirty) {
            const confirmDirtyResult = await Notification.confirmDelete('当前有未保存的更改，删除后无法恢复，确定要继续吗？');
            if (!confirmDirtyResult.isConfirmed) {
                return;
            }
        }

        const confirmResult = await Notification.confirmDelete(`确定要删除版本 "${versionToDelete}" 吗？此操作不可恢复。`);
        if (!confirmResult.isConfirmed) {
            return;
        }

        const fallbackVersion = versions.find((version) => version !== versionToDelete);

        try {
            const response = await fetch(`/api/system/bayes/config?version=${encodeURIComponent(versionToDelete)}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                const errorMsg = error.detail || '删除失败';
                throw new Error(errorMsg);
            }

            await this.refreshVersionOptions(fallbackVersion);
            await this.loadConfig(this.currentVersion);
            this.render();
            this.setupEventListeners();
            Notification.success('✅ 删除成功');
        } catch (error) {
            console.error('Delete failed:', error);
            Notification.error(`❌ 删除失败: ${error.message}`);
        }
    }

    /**
     * 兼容旧版训练样本结构（"可信/不可信"）
     */
    migrateLegacySamples() {
        if (!this.config || typeof this.config !== 'object') {
            return;
        }

        this.ensureSampleBuckets();
    }

    /**
     * 将旧结构样本合并到新结构，并缓存旧数据以便回写
     */
    mergeLegacySamples(samples, modernKey, legacyKey, defaultLabel) {
        const current = Array.isArray(samples[modernKey]) ? samples[modernKey] : [];
        const legacy = Array.isArray(samples[legacyKey]) ? samples[legacyKey] : [];

        const normalizedCurrent = current.map(item => this.normalizeSampleItem(item, defaultLabel));
        const signatures = new Set(normalizedCurrent.map(item => `${item.name || ''}|${item.note || ''}`));
        const merged = [...normalizedCurrent];
        const cache = new Array(normalizedCurrent.length).fill(null);

        legacy.forEach((item) => {
            const normalized = this.normalizeSampleItem(item, defaultLabel);
            const signature = `${normalized.name}|${normalized.note}`;
            if (signatures.has(signature)) {
                return;
            }
            signatures.add(signature);
            merged.push(normalized);
            cache.push(item);
        });

        samples[modernKey] = merged;
        this.sampleLegacyCache[modernKey] = cache;
    }

    /**
     * 规范化样本结构，兼容旧字段
     */
    normalizeSampleItem(item, defaultLabel) {
        if (!item || typeof item !== 'object') {
            return { id: '', name: '', vector: [], label: defaultLabel, note: '' };
        }

        const id = item.id || '';
        const name = item.name || item.title || '';
        const note = item.note || '';
        const label = typeof item.label === 'number' ? item.label : defaultLabel;

        let vector = [];
        if (Array.isArray(item.vector)) {
            vector = item.vector;
        } else if (typeof item.vector === 'string') {
            vector = this.parseVectorString(item.vector);
        }

        return { id, name, vector, label, note };
    }

    /**
     * 确保样本桶结构完整，并同步旧结构数据
     */
    ensureSampleBuckets() {
        console.log('ensureSampleBuckets: START');
        if (!this.config || typeof this.config !== 'object') {
            console.warn('ensureSampleBuckets: config is invalid');
            return { trusted: [], untrusted: [] };
        }


        if (!this.config._samples || typeof this.config._samples !== 'object') {
            this.config._samples = {};
        }

        const samples = this.config._samples;
        this.sampleLegacyCache = { trusted: [], untrusted: [] };

        this.mergeLegacySamples(samples, 'trusted', '可信', 1);
        this.mergeLegacySamples(samples, 'untrusted', '不可信', 0);

        if (!Array.isArray(samples.trusted)) {
            samples.trusted = [];
        }
        if (!Array.isArray(samples.untrusted)) {
            samples.untrusted = [];
        }

        return samples;
    }

    /**
     * 解析特征向量输入
     */
    parseVectorString(value) {
        if (!value) {
            return [];
        }
        return value
            .split(',')
            .map(item => parseFloat(item.trim()))
            .filter(item => !Number.isNaN(item));
    }

    /**
     * 保存配置
     */
    async saveConfig() {
        // 验证配置
        const errors = this.validateConfig();
        if (errors.length > 0) {
            Notification.error('配置验证失败:\n' + errors.join('\n'));
            return false;
        }

        // 确认保存
        const confirmResult = await Notification.confirm('确定要保存配置吗？');
        if (!confirmResult.isConfirmed) {
            return false;
        }

        const saveBtn = document.getElementById('bayes-save-btn');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = '保存中...';
        saveBtn.disabled = true;

        try {
            // 从UI收集最新数据
            this.collectDataFromUI();

            const response = await fetch('/api/system/bayes/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.config)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.errors ? error.errors.join('\n') : '保存失败');
            }

            this.isDirty = false;
            Notification.success('✅ 配置保存成功');
            return true;
        } catch (error) {
            console.error('Save failed:', error);
            Notification.error('❌ 保存失败: ' + error.message);
            return false;
        } finally {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    }

    /**
     * 从UI收集数据并更新config对象
     */
    collectDataFromUI() {
        const fusion = this.config.recommendation_fusion;

        // 收集融合权重
        fusion.weights.bayesian = parseFloat(document.getElementById('weight-with-img-bayesian').value);
        fusion.weights.visual = parseFloat(document.getElementById('weight-with-img-visual').value);
        fusion.weights.ai = parseFloat(document.getElementById('weight-with-img-ai').value);

        fusion.weights_no_visual.bayesian = parseFloat(document.getElementById('weight-no-img-bayesian').value);
        fusion.weights_no_visual.visual = parseFloat(document.getElementById('weight-no-img-visual').value);
        fusion.weights_no_visual.ai = parseFloat(document.getElementById('weight-no-img-ai').value);

        // 收集贝叶斯特征权重
        const bayesFeatures = ['seller_tenure', 'positive_rate', 'seller_credit_level',
            'sales_ratio', 'used_years', 'freshness', 'has_guarantee'];
        bayesFeatures.forEach(feature => {
            const input = document.getElementById(`bayes-feature-${feature}`);
            if (input) {
                fusion.bayesian_features[feature] = parseFloat(input.value);
            }
        });

        // 收集视觉AI特征权重
        const visualFeatures = ['image_quality', 'condition', 'authenticity', 'completeness'];
        visualFeatures.forEach(feature => {
            const input = document.getElementById(`visual-feature-${feature}`);
            if (input) {
                fusion.visual_features[feature] = parseFloat(input.value);
            }
        });

        // 收集风险惩罚配置
        fusion.risk_penalty.per_tag_penalty = parseInt(document.getElementById('risk-per-tag-penalty').value);
        fusion.risk_penalty.max_penalty = parseInt(document.getElementById('risk-max-penalty').value);

        // 收集评分规则
        this.collectScoringRules();

        // 收集训练样本
        this.collectTrainingSamples();
    }

    /**
     * 收集评分规则配置
     */
    collectScoringRules() {
        if (!this.config.recommendation_fusion) {
            this.config.recommendation_fusion = {};
        }
        if (!this.config.recommendation_fusion.scoring_rules) {
            this.config.recommendation_fusion.scoring_rules = {};
        }

        const rules = this.config.recommendation_fusion.scoring_rules;
        this.collectUsedYearsRules(rules);
        this.collectSellerCreditRules(rules);
        this.collectSalesRatioRule(rules);
        this.collectFreshnessRule(rules);
        this.collectVisualAiRules(rules);
    }

    /**
     * 收集商品使用年限规则
     */
    collectUsedYearsRules(rules) {
        const tbody = document.getElementById('used-years-rules');
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const mappings = rows.map(row => {
            const desc = row.querySelector('.rule-desc-input')?.value || '';
            const keywordsText = row.querySelector('.rule-keywords-input')?.value || '';
            const scoreValue = parseFloat(row.querySelector('.rule-score-input')?.value || '0');
            const keywords = keywordsText
                .split(',')
                .map(item => item.trim())
                .filter(item => item);
            return {
                keywords,
                score: Number.isFinite(scoreValue) ? scoreValue : 0,
                _说明: desc
            };
        });

        if (!rules.used_years) {
            rules.used_years = {};
        }
        rules.used_years.text_mappings = mappings;
        const missingInput = document.getElementById('used-years-missing');
        const fallbackInput = document.getElementById('used-years-fallback');
        if (missingInput) {
            rules.used_years.missing_score = parseFloat(missingInput.value || '0');
        }
        if (fallbackInput) {
            rules.used_years.default_score = parseFloat(fallbackInput.value || '0');
        }
    }

    /**
     * 收集卖家信用等级规则
     */
    collectSellerCreditRules(rules) {
        const tbody = document.getElementById('seller-credit-rules');
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const mappings = rows.map(row => {
            const keywordsText = row.querySelector('.credit-keywords-input')?.value || '';
            const desc = row.querySelector('.credit-desc-input')?.value || '';
            const scoreValue = parseFloat(row.querySelector('.credit-score-input')?.value || '0');
            const keywords = keywordsText
                .split(',')
                .map(item => item.trim())
                .filter(item => item);
            return {
                keywords,
                score: Number.isFinite(scoreValue) ? scoreValue : 0,
                _说明: desc
            };
        });

        if (!rules.seller_credit_level) {
            rules.seller_credit_level = {};
        }
        rules.seller_credit_level.text_mapping = mappings;
    }

    /**
     * 收集销售比例评分规则
     */
    collectSalesRatioRule(rules) {
        if (!rules.sales_ratio) {
            rules.sales_ratio = {};
        }

        const rule = rules.sales_ratio;
        const denominatorInput = document.getElementById('sales-ratio-denominator');
        const zeroScoreInput = document.getElementById('sales-ratio-zero-score');
        const boostThresholdInput = document.getElementById('sales-ratio-boost-threshold');
        const neutralThresholdInput = document.getElementById('sales-ratio-neutral-threshold');
        const boostFactorInput = document.getElementById('sales-ratio-boost-factor');
        const penaltyFactorInput = document.getElementById('sales-ratio-penalty-factor');
        const missingScoreInput = document.getElementById('sales-ratio-missing-score');

        if (denominatorInput) {
            rule.sold_score_denominator = parseFloat(denominatorInput.value || '0');
        }
        if (zeroScoreInput) {
            rule.sold_zero_score = parseFloat(zeroScoreInput.value || '0');
        }
        if (boostThresholdInput) {
            rule.ratio_boost_threshold = parseFloat(boostThresholdInput.value || '0');
        }
        if (neutralThresholdInput) {
            rule.ratio_neutral_threshold = parseFloat(neutralThresholdInput.value || '0');
        }
        if (boostFactorInput) {
            rule.ratio_boost_factor = parseFloat(boostFactorInput.value || '0');
        }
        if (penaltyFactorInput) {
            rule.ratio_penalty_factor = parseFloat(penaltyFactorInput.value || '0');
        }
        if (missingScoreInput) {
            rule.missing_score = parseFloat(missingScoreInput.value || '0');
        }
    }

    /**
     * 收集发布新鲜度评分规则
     */
    collectFreshnessRule(rules) {
        if (!rules.freshness) {
            rules.freshness = {};
        }

        const rule = rules.freshness;
        const recentScoreInput = document.getElementById('freshness-recent-score');
        const missingScoreInput = document.getElementById('freshness-missing-score');
        const dayScoreInputs = document.querySelectorAll('[data-freshness-index]');

        if (recentScoreInput) {
            rule.recent_score = parseFloat(recentScoreInput.value || '0');
        }
        if (missingScoreInput) {
            rule.missing_score = parseFloat(missingScoreInput.value || '0');
        }

        if (!Array.isArray(rule.day_scores)) {
            rule.day_scores = [];
        }

        dayScoreInputs.forEach((input) => {
            const index = parseInt(input.getAttribute('data-freshness-index'), 10);
            if (Number.isNaN(index)) {
                return;
            }
            if (!rule.day_scores[index]) {
                rule.day_scores[index] = { max_days: 0, score: 0 };
            }
            rule.day_scores[index].score = parseFloat(input.value || '0');
        });
    }

    /**
     * 收集视觉AI评分细则
     */
    collectVisualAiRules(rules) {
        const rows = Array.from(document.querySelectorAll('[data-visual-key]'));

        if (!rules.visual) {
            rules.visual = {};
        }

        const visualRules = rules.visual;
        const detailMap = {};

        document.querySelectorAll('.visual-default-score').forEach((input) => {
            const key = input.getAttribute('data-visual-key');
            if (!key) return;
            if (!visualRules[key]) {
                visualRules[key] = {};
            }
            const value = parseFloat(input.value || '0');
            visualRules[key].default_score = Number.isFinite(value) ? value : 0;
        });

        const completenessMax = document.getElementById('visual-completeness-max');
        const completenessMin = document.getElementById('visual-completeness-min');
        const completenessFormula = document.getElementById('visual-completeness-formula');
        const completenessNote = document.getElementById('visual-completeness-note');
        if (completenessMax || completenessMin || completenessFormula || completenessNote) {
            if (!visualRules.completeness) {
                visualRules.completeness = {};
            }
            const maxValue = parseFloat(completenessMax?.value || '0');
            const minValue = parseFloat(completenessMin?.value || '0');
            visualRules.completeness.max_images = Number.isFinite(maxValue) ? maxValue : 0;
            visualRules.completeness.min_score = Number.isFinite(minValue) ? minValue : 0;
            if (completenessFormula) {
                visualRules.completeness._description_formula = completenessFormula.value || '';
            }
            if (completenessNote) {
                visualRules.completeness._description_note = completenessNote.value || '';
            }
        }

        rows.forEach((row) => {
            const visualKey = row.getAttribute('data-visual-key');
            const groupKey = row.getAttribute('data-group-key');
            if (!visualKey || !groupKey) return;

            const keywordsText = row.querySelector('.visual-keywords-input')?.value || '';
            const scoreValue = parseFloat(row.querySelector('.visual-score-input')?.value || '0');
            const desc = row.querySelector('.visual-desc-input')?.value || '';

            const keywords = keywordsText
                .split(',')
                .map(item => item.trim())
                .filter(item => item);

            if (!visualRules[visualKey]) {
                visualRules[visualKey] = {};
            }

            detailMap[`${visualKey}.${groupKey}`] = desc;

            if (visualKey === 'image_quality') {
                this.applyVisualGroupRule(visualRules[visualKey], groupKey, keywords, scoreValue, {
                    high: ['high_keywords', 'high_score'],
                    mid: ['mid_keywords', 'mid_score'],
                    low: ['low_keywords', 'low_score']
                });
            } else if (visualKey === 'condition') {
                this.applyVisualGroupRule(visualRules[visualKey], groupKey, keywords, scoreValue, {
                    high: ['high_keywords', 'high_score'],
                    good: ['good_keywords', 'good_score'],
                    normal: ['normal_keywords', 'normal_score'],
                    bad: ['bad_keywords', 'bad_score']
                });
            } else if (visualKey === 'authenticity') {
                this.applyVisualGroupRule(visualRules[visualKey], groupKey, keywords, scoreValue, {
                    good: ['good_keywords', 'good_score'],
                    suspect: ['suspect_keywords', 'suspect_score'],
                    bad: ['bad_keywords', 'bad_score']
                });
            }
        });

        const existingDetail = visualRules._说明明细 || {};
        visualRules._说明明细 = { ...existingDetail, ...detailMap };
    }

    /**
     * 视觉规则分组写回
     */
    applyVisualGroupRule(targetRule, groupKey, keywords, scoreValue, mapping) {
        const mapItem = mapping[groupKey];
        if (!mapItem) return;
        const [keywordsKey, scoreKey] = mapItem;
        targetRule[keywordsKey] = keywords;
        if (Number.isFinite(scoreValue)) {
            targetRule[scoreKey] = scoreValue;
        }
    }

    /**
     * 验证配置
     */
    validateConfig() {
        const errors = [];
        const fusion = this.config.recommendation_fusion;

        // 验证融合权重（有图片）
        const weightSum = fusion.weights.bayesian + fusion.weights.visual + fusion.weights.ai;
        if (Math.abs(weightSum - 1.0) > 0.001) {
            errors.push(`有图片权重和必须为1.0，当前为${weightSum.toFixed(3)}`);
        }

        // 验证融合权重（无图片）
        const weightSumNoVisual = fusion.weights_no_visual.bayesian +
            fusion.weights_no_visual.visual +
            fusion.weights_no_visual.ai;
        if (Math.abs(weightSumNoVisual - 1.0) > 0.001) {
            errors.push(`无图片权重和必须为1.0，当前为${weightSumNoVisual.toFixed(3)}`);
        }

        // 验证贝叶斯特征权重
        const bayesSum = fusion.bayesian_features.seller_tenure +
            fusion.bayesian_features.positive_rate +
            fusion.bayesian_features.seller_credit_level +
            fusion.bayesian_features.sales_ratio +
            fusion.bayesian_features.used_years +
            fusion.bayesian_features.freshness +
            fusion.bayesian_features.has_guarantee;
        if (Math.abs(bayesSum - 1.0) > 0.001) {
            errors.push(`贝叶斯特征权重和必须为1.0，当前为${bayesSum.toFixed(3)}`);
        }

        // 验证视觉AI特征权重
        const visualSum = fusion.visual_features.image_quality +
            fusion.visual_features.condition +
            fusion.visual_features.authenticity +
            fusion.visual_features.completeness;
        if (Math.abs(visualSum - 1.0) > 0.001) {
            errors.push(`视觉AI特征权重和必须为1.0，当前为${visualSum.toFixed(3)}`);
        }

        return errors;
    }

    /**
     * 渲染整个界面
     */
    render() {
        if (!this.config) return;

        const collapseState = this.captureCollapseState();

        this.container.innerHTML = `
            <div class="config-group">
                <div class="config-group-title">
                    <span>⚖️ 推荐度融合配置</span>
                </div>
                ${this.renderFusionWeightsCard()}
            </div>
            
            <div class="config-group">
                <div class="config-group-title">
                    <span>🎲 贝叶斯特征配置</span>
                </div>
                ${this.renderBayesianFeaturesCard()}
                ${this.renderScoringRulesCard()}
            </div>
            
            <div class="config-group">
                <div class="config-group-title">
                    <span>🎨 视觉AI配置</span>
                </div>
                ${this.renderVisualFeaturesCard()}
            </div>
            
            <div class="config-group">
                <div class="config-group-title">
                    <span>⚙️ 其他配置</span>
                </div>
                ${this.renderTrainingSamplesCard()}
                ${this.renderRiskPenaltyCard()}
            </div>
        `;

        this.restoreCollapseState(collapseState);

        // 绑定训练样本的事件监听器
        this.bindTrainingSampleEvents();
    }

    /**
     * 记录折叠面板展开状态
     */
    captureCollapseState() {
        if (!this.container) {
            return {};
        }

        const state = {};
        this.container.querySelectorAll('details[data-collapse-key]').forEach((detail) => {
            const key = detail.dataset.collapseKey;
            if (key) {
                state[key] = detail.open;
            }
        });
        return state;
    }

    /**
     * 恢复折叠面板展开状态
     */
    restoreCollapseState(state) {
        if (!this.container || !state) {
            return;
        }

        this.container.querySelectorAll('details[data-collapse-key]').forEach((detail) => {
            const key = detail.dataset.collapseKey;
            if (key && state[key]) {
                detail.open = true;
            }
        });
    }

    /**
     * 渲染推荐度融合权重卡片
     */
    renderFusionWeightsCard() {
        const weights = this.config.recommendation_fusion.weights;
        const weightsNoVisual = this.config.recommendation_fusion.weights_no_visual;
        const sumWith = weights.bayesian + weights.visual + weights.ai;
        const sumNoVisual = weightsNoVisual.bayesian + weightsNoVisual.visual + weightsNoVisual.ai;

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="bayes-features">
                <summary class="bayes-card-header">
                    <h3>📊 推荐度融合权重配置</h3>
                </summary>
                <div class="bayes-card-body">
                    <table class="bayes-weight-table">
                        <colgroup>
                            <col style="width: 30%">
                            <col style="width: 35%">
                            <col style="width: 35%">
                        </colgroup>
                        <thead>
                            <tr>
                                <th>配置场景</th>
                                <th>有图片时</th>
                                <th>无图片时</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>贝叶斯权重</strong></td>
                                <td><input type="number" id="weight-with-img-bayesian" step="0.01" min="0" max="1" value="${weights.bayesian}"/></td>
                                <td><input type="number" id="weight-no-img-bayesian" step="0.01" min="0" max="1" value="${weightsNoVisual.bayesian}"/></td>
                            </tr>
                            <tr>
                                <td><strong>视觉AI权重</strong></td>
                                <td><input type="number" id="weight-with-img-visual" step="0.01" min="0" max="1" value="${weights.visual}"/></td>
                                <td><input type="number" id="weight-no-img-visual" step="0.01" min="0" max="1" value="${weightsNoVisual.visual}"/></td>
                            </tr>
                            <tr>
                                <td><strong>AI分析权重</strong></td>
                                <td><input type="number" id="weight-with-img-ai" step="0.01" min="0" max="1" value="${weights.ai}"/></td>
                                <td><input type="number" id="weight-no-img-ai" step="0.01" min="0" max="1" value="${weightsNoVisual.ai}"/></td>
                            </tr>
                        </tbody>
                        <tfoot>
                            <tr class="sum-row">
                                <td><strong>合计</strong></td>
                                <td id="weight-sum-with-img" class="sum-cell">
                                    <span class="sum-value">${sumWith.toFixed(2)}</span>
                                    <span class="sum-status ${Math.abs(sumWith - 1.0) < 0.001 ? 'success' : 'error'}">
                                        ${Math.abs(sumWith - 1.0) < 0.001 ? '✓' : '✗'}
                                    </span>
                                </td>
                                <td id="weight-sum-no-img" class="sum-cell">
                                    <span class="sum-value">${sumNoVisual.toFixed(2)}</span>
                                    <span class="sum-status ${Math.abs(sumNoVisual - 1.0) < 0.001 ? 'success' : 'error'}">
                                        ${Math.abs(sumNoVisual - 1.0) < 0.001 ? '✓' : '✗'}
                                    </span>
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                    <p class="hint">💡 每列权重之和必须为 1.0</p>
                </div>
            </details>
        `;
    }

    /**
     * 渲染贝叶斯特征权重卡片
     */
    renderBayesianFeaturesCard() {
        const features = this.config.recommendation_fusion.bayesian_features;
        const featureLabels = {
            seller_tenure: '卖家注册时长',
            positive_rate: '卖家好评率',
            seller_credit_level: '卖家信用等级',
            sales_ratio: '销售比例',
            used_years: '商品使用年限',
            freshness: '发布新鲜度',
            has_guarantee: '担保服务'
        };

        const featureDesc = features._特征说明 || {};

        let rows = '';
        let sum = 0;
        for (const [key, label] of Object.entries(featureLabels)) {
            const value = features[key] || 0;
            sum += value;
            const desc = featureDesc[key] || '';
            rows += `
                <tr>
                    <td><strong>${label}</strong></td>
                    <td><code>${key}</code></td>
                    <td><input type="number" id="bayes-feature-${key}" class="bayes-feature-input" step="0.01" min="0" max="1" value="${value}"/></td>
                    <td>${desc}</td>
                </tr>
            `;
        }

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="visual-features">
                <summary class="bayes-card-header">
                    <h3>⚖️ 贝叶斯特征权重 (7项)</h3>
                </summary>
                <div class="bayes-card-body">
                    <table class="bayes-feature-table">
                        <thead>
                            <tr>
                                <th style="width: 25%">特征名称</th>
                                <th style="width: 20%">英文字段</th>
                                <th style="width: 18%">权重</th>
                                <th style="width: 37%">说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                        <tfoot>
                            <tr class="sum-row">
                                <td><strong>合计</strong></td>
                                <td></td>
                                <td id="bayes-features-sum" class="sum-cell">
                                    <span class="sum-value">${sum.toFixed(2)}</span>
                                    <span class="sum-status ${Math.abs(sum - 1.0) < 0.001 ? 'success' : 'error'}">
                                        ${Math.abs(sum - 1.0) < 0.001 ? '✓' : '✗'}
                                    </span>
                                </td>
                                <td></td>
                            </tr>
                        </tfoot>
                    </table>
                    <p class="hint">💡 所有特征权重之和必须为 1.0</p>
                </div>
            </details>
        `;
    }

    /**
     * 渲染视觉AI特征权重卡片
     */
    renderVisualFeaturesCard() {
        const features = this.config.recommendation_fusion.visual_features;
        const featureLabels = {
            image_quality: '图片质量',
            condition: '商品成色',
            authenticity: '图片真实性',
            completeness: '图片完整性'
        };

        const featureDesc = features._特征说明 || {};

        let rows = '';
        let sum = 0;
        for (const [key, label] of Object.entries(featureLabels)) {
            const value = features[key] || 0;
            sum += value;
            const desc = featureDesc[key] || '';
            rows += `
                <tr>
                    <td><strong>${label}</strong></td>
                    <td><code>${key}</code></td>
                    <td><input type="number" id="visual-feature-${key}" class="visual-feature-input" step="0.01" min="0" max="1" value="${value}"/></td>
                    <td>${desc}</td>
                </tr>
            `;
        }

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="scoring-rules">
                <summary class="bayes-card-header">
                    <h3>🎨 视觉AI特征权重 (4项)</h3>
                </summary>
                <div class="bayes-card-body">
                    <table class="bayes-feature-table">
                        <thead>
                            <tr>
                                <th style="width: 25%">特征名称</th>
                                <th style="width: 20%">英文字段</th>
                                <th style="width: 18%">权重</th>
                                <th style="width: 37%">说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                        <tfoot>
                            <tr class="sum-row">
                                <td><strong>合计</strong></td>
                                <td></td>
                                <td id="visual-features-sum" class="sum-cell">
                                    <span class="sum-value">${sum.toFixed(2)}</span>
                                    <span class="sum-status ${Math.abs(sum - 1.0) < 0.001 ? 'success' : 'error'}">
                                        ${Math.abs(sum - 1.0) < 0.001 ? '✓' : '✗'}
                                    </span>
                                </td>
                                <td></td>
                            </tr>
                        </tfoot>
                    </table>
                    <p class="hint">💡 所有特征权重之和必须为 1.0</p>
                </div>
            </details>
            ${this.renderVisualAiRulesCard(this.getScoringRules().visual)}
        `;
    }

    /**
     * 获取评分规则配置（兼容不同版本结构）
     */
    getScoringRules() {
        const fusionRules = this.config?.recommendation_fusion?.scoring_rules;
        if (fusionRules && typeof fusionRules === 'object') {
            return fusionRules;
        }
        const fallbackRules = this.config?.bayes_feature_rules;
        if (fallbackRules && typeof fallbackRules === 'object') {
            return fallbackRules;
        }
        return {};
    }

    /**
     * 归一化卖家注册时长规则（兼容 year_scores/month_scores）
     */
    normalizeSellerTenureRanges(rule) {
        if (!rule || typeof rule !== 'object') {
            return [];
        }
        if (Array.isArray(rule.ranges) && rule.ranges.length > 0) {
            return rule.ranges;
        }
        const ranges = [];
        const yearScores = Array.isArray(rule.year_scores) ? rule.year_scores : [];
        yearScores.forEach((item) => {
            const minYears = Number(item.min_years);
            const score = Number(item.score);
            if (Number.isFinite(minYears) && Number.isFinite(score)) {
                ranges.push({
                    min_months: minYears * 12,
                    score,
                    _说明: item._说明 || ''
                });
            }
        });
        const monthScores = Array.isArray(rule.month_scores) ? rule.month_scores : [];
        monthScores.forEach((item) => {
            const minMonths = Number(item.min_months);
            const score = Number(item.score);
            if (Number.isFinite(minMonths) && Number.isFinite(score)) {
                ranges.push({
                    min_months: minMonths,
                    score,
                    _说明: item._说明 || ''
                });
            }
        });
        return ranges;
    }

    /**
     * 渲染评分规则配置卡片
     */
    renderScoringRulesCard() {
        const rules = this.getScoringRules();

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="visual-ai-rules">
                <summary class="bayes-card-header">
                    <h3>📋 评分规则详细配置</h3>
                </summary>
                <div class="bayes-card-body">
                    <p class="hint">💡 配置各特征的评分规则，支持关键词匹配、数值范围等多种规则类型</p>
                    
                    ${this.renderUsedYearsRule(rules.used_years)}
                    ${this.renderSellerTenureRule(rules.seller_tenure)}
                    ${this.renderPositiveRateRule(rules.positive_rate)}
                    ${this.renderSellerCreditLevelRule(rules.seller_credit_level)}
                    ${this.renderSalesRatioRule(rules.sales_ratio)}
                    ${this.renderFreshnessRule(rules.freshness)}
                    ${this.renderHasGuaranteeRule(rules.has_guarantee)}
                    </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染商品使用年限评分规则 ⭐重点
     */
    renderUsedYearsRule(rule) {
        if (!rule) rule = { text_mappings: [], missing_score: 0.5, default_score: 0.5 };
        const mappings = rule.text_mappings || [];

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-used-years">
                <summary>
                    <strong>🎯 商品使用年限 (used_years)</strong>
                    <span class="badge badge-info">关键词匹配</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <div class="rule-description">
                        <p>根据商品使用年限描述文本匹配关键词并给分</p>
                    </div>
                    <table class="scoring-rule-table">
                        <thead>
                            <tr>
                                <th style="width: 35%">条件描述</th>
                                <th style="width: 40%">关键词（多个用逗号分隔）</th>
                                <th style="width: 15%">得分 (0.0-1.0)</th>
                                <th style="width: 10%">操作</th>
                            </tr>
                        </thead>
                        <tbody id="used-years-rules">
                            ${mappings.map((m, idx) => this.renderScoringRuleRow('used_years', m, idx)).join('')}
                        </tbody>
                    </table>
                    <button class="control-button add-rule-btn" data-rule="used_years">+ 添加规则</button>
                    
                    <div class="rule-defaults">
                        <div class="form-group inline">
                            <label>缺失时默认分：</label>
                            <input type="number" id="used-years-missing" step="0.1" min="0" max="1" value="${rule.missing_score || 0.5}" />
                        </div>
                        <div class="form-group inline">
                            <label>兜底分数：</label>
                            <input type="number" id="used-years-fallback" step="0.1" min="0" max="1" value="${rule.default_score || 0.5}" />
                        </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染评分规则行
     */
    renderScoringRuleRow(ruleType, mapping, index) {
        const keywords = Array.isArray(mapping.keywords) ? mapping.keywords.join(', ') : '';
        const description = mapping._说明 || mapping.description || '';
        return `
            <tr data-rule-type="${ruleType}" data-index="${index}">
                <td><input type="text" class="rule-desc-input" value="${description}" placeholder="例如：未使用" /></td>
                <td><input type="text" class="rule-keywords-input" value="${keywords}" placeholder="未使用, 全新, 0年" /></td>
                <td><input type="number" class="rule-score-input" step="0.1" min="0" max="1" value="${mapping.score || 0.5}" /></td>
                <td><button class="control-button danger-btn-sm delete-rule-btn">删除</button></td>
            </tr>
        `;
    }

    /**
     * 渲染卖家注册时长评分规则
     */
    renderSellerTenureRule(rule) {
        if (!rule) rule = { ranges: [], default_score: 0.0 };
        const ranges = this.normalizeSellerTenureRanges(rule);
        const yearRegex = rule.year_regex || '(\\d+)\\s*年';
        const monthRegex = rule.month_regex || '(\\d+)\\s*月';

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-seller-tenure">
                <summary>
                    <strong>📅 卖家注册时长 (seller_tenure)</strong>
                    <span class="badge badge-info">数值范围</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <div class="rule-description">
                        <p><strong>计算逻辑：</strong>从文本中提取年份或月份，按分段规则给分</p>
                        <p class="formula">📐 公式：if 月数 ≥ min_months → 使用对应score，否则继续匹配下一档</p>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">🔧 正则表达式配置</h4>
                        <div class="param-grid">
                            <div class="param-item">
                                <label>年份提取：</label>
                                <input type="text" class="regex-input" value="${yearRegex}" readonly />
                                <span class="param-hint">如："3年" → 提取数字3</span>
                            </div>
                            <div class="param-item">
                                <label>月份提取：</label>
                                <input type="text" class="regex-input" value="${monthRegex}" readonly />
                                <span class="param-hint">如："6个月" → 提取数字6</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">📊 分段评分规则</h4>
                        <table class="scoring-rule-table detailed">
                            <thead>
                                <tr>
                                    <th style="width: 20%">最小月数</th>
                                    <th style="width: 20%">得分</th>
                                    <th style="width: 40%">说明</th>
                                    <th style="width: 20%">示例</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${ranges.map(r => `
                                    <tr>
                                        <td><input type="number" class="tenure-min-months" value="${r.min_months || 0}" min="0" /></td>
                                        <td><input type="number" class="tenure-score" step="0.1" min="0" max="1" value="${r.score || 0}" /></td>
                                        <td class="desc-cell">${r._说明 || ''}</td>
                                        <td class="example-cell">${r.min_months >= 12 ? Math.floor(r.min_months / 12) + '年' : r.min_months + '个月'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                        
                        <div class="param-row">
                            <label class="param-label">🔄 默认分数（无法匹配时）：</label>
                            <input type="number" class="param-input" id="seller-tenure-default" step="0.1" min="0" max="1" value="${rule.default_score || 0.0}" />
                            <span class="param-hint">数据缺失或无法解析时使用</span>
                        </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染卖家好评率评分规则
     */
    renderPositiveRateRule(rule) {
        if (!rule) rule = { missing_score: 0.5, scale: 100, percentage_regex: '(\\d+(?:\\.\\d+)?)\\s*%' };

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-positive-rate">
                <summary>
                    <strong>⭐ 卖家好评率 (positive_rate)</strong>
                    <span class="badge badge-success">百分比转换</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <div class="rule-description">
                        <p><strong>计算逻辑：</strong>从百分比字符串中提取数值并除以100转换为0-1分数</p>
                        <p class="formula">📐 公式：score = min(max(提取的数值 / 100, 0.0), 1.0)</p>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">🔧 正则表达式配置</h4>
                        <div class="param-item">
                            <label>百分比提取：</label>
                            <input type="text" class="regex-input" value="${rule.percentage_regex || '(\\d+(?:\\.\\d+)?)\\s*%'}" readonly />
                            <span class="param-hint">如："98.5%" → 提取98.5</span>
                        </div>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">📊 评分参数</h4>
                        <table class="param-table">
                            <tr>
                                <td class="param-name">缩放比例</td>
                                <td><input type="number" class="param-input" id="positive-rate-scale" value="${rule.scale || 100}" readonly /></td>
                                <td class="param-desc">提取的数值除以此值得到最终分数</td>
                            </tr>
                            <tr>
                                <td class="param-name">最小分数</td>
                                <td><input type="number" class="param-input" value="${rule.min_score || 0.0}" readonly /></td>
                                <td class="param-desc">分数下限（通常为0.0）</td>
                            </tr>
                            <tr>
                                <td class="param-name">最大分数</td>
                                <td><input type="number" class="param-input" value="${rule.max_score || 1.0}" readonly /></td>
                                <td class="param-desc">分数上限（通常为1.0）</td>
                            </tr>
                            <tr>
                                <td class="param-name">缺失默认分</td>
                                <td><input type="number" class="param-input" id="positive-rate-missing" step="0.1" min="0" max="1" value="${rule.missing_score || 0.5}" /></td>
                                <td class="param-desc">数据缺失时使用此分数</td>
                            </tr>
                        </table>
                        
                        <div class="example-box">
                            <strong>💡 计算示例：</strong>
                            <ul>
                                <li>"98.5%" → 98.5 / 100 = <strong>0.985</strong></li>
                                <li>"100%" → 100 / 100 = <strong>1.0</strong></li>
                                <li>"85%" → 85 / 100 = <strong>0.85</strong></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染卖家信用等级评分规则
     */
    renderSellerCreditLevelRule(rule) {
        if (!rule) rule = { text_mapping: [], missing_score: 0.5 };
        const mappings = rule.text_mapping || [];

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-seller-credit">
                <summary>
                    <strong>👑 卖家信用等级 (seller_credit_level)</strong>
                    <span class="badge badge-warning">关键词 + 等级</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <p class="rule-description">根据信用等级文本匹配关键词给分</p>
                    
                    <div class="param-section">
                        <h4 class="param-title">📝 文本映射规则</h4>
                        <table class="scoring-rule-table">
                            <thead>
                                <tr>
                                    <th style="width: 40%">关键词</th>
                                    <th style="width: 20%">得分</th>
                                    <th style="width: 30%">说明</th>
                                    <th style="width: 10%">操作</th>
                                </tr>
                            </thead>
                            <tbody id="seller-credit-rules">
                                ${mappings.map((m, idx) => this.renderSellerCreditRuleRow(m, idx)).join('')}
                            </tbody>
                        </table>
                        <button class="control-button add-rule-btn" data-rule="seller_credit_level">+ 添加规则</button>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染卖家信用等级规则行
     */
    renderSellerCreditRuleRow(mapping, index) {
        const keywords = Array.isArray(mapping.keywords) ? mapping.keywords.join(', ') : '';
        const description = mapping._说明 || mapping.description || '';
        return `
            <tr data-rule-type="seller_credit_level" data-index="${index}">
                <td><input type="text" class="credit-keywords-input" value="${keywords}" placeholder="极好, 优秀" /></td>
                <td><input type="number" class="credit-score-input" step="0.1" min="0" max="1" value="${mapping.score || 0.5}" /></td>
                <td><input type="text" class="credit-desc-input" value="${description}" placeholder="说明" /></td>
                <td><button class="control-button danger-btn-sm delete-rule-btn">删除</button></td>
            </tr>
        `;
    }

    /**
     * 渲染销售比例评分规则
     */
    renderSalesRatioRule(rule) {
        if (!rule) {
            rule = {
                missing_score: 0.5,
                pair_regex: '(\\d+)\\s*/\\s*(\\d+)',
                sold_zero_score: 0.2,
                sold_score_denominator: 100,
                ratio_boost_threshold: 0.5,
                ratio_neutral_threshold: 1.0,
                ratio_boost_factor: 1.2,
                ratio_penalty_factor: 0.8
            };
        }

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-sales-ratio">
                <summary>
                    <strong>📈 销售比例 (sales_ratio)</strong>
                    <span class="badge badge-info">复合计算</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <div class="rule-description">
                        <p><strong>计算逻辑：</strong>根据在售和已售数量计算基础分，再根据比例调整</p>
                        <p class="formula">📐 公式：</p>
                        <ol class="formula-steps">
                            <li>base_score = min(已售数 / ${rule.sold_score_denominator || 100}, 1.0)</li>
                            <li>ratio = 在售数 / 已售数</li>
                            <li>if ratio < ${rule.ratio_boost_threshold} → score = base_score × ${rule.ratio_boost_factor}</li>
                            <li>if ratio > ${rule.ratio_neutral_threshold} → score = base_score × ${rule.ratio_penalty_factor}</li>
                            <li>else → score = base_score</li>
                        </ol>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">🔧 正则表达式配置</h4>
                        <div class="param-item">
                            <label>数量对提取：</label>
                            <input type="text" class="regex-input" value="${rule.pair_regex || '(\\d+)\\s*/\\s*(\\d+)'}" readonly />
                            <span class="param-hint">如："5 / 100" → 提取(5, 100)</span>
                        </div>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">📊 评分参数</h4>
                        <table class="param-table">
                            <tr>
                                <td class="param-name">已售分数分母</td>
                                <td><input type="number" id="sales-ratio-denominator" class="param-input sales-ratio-input" min="1" step="1" value="${rule.sold_score_denominator || 100}" /></td>
                                <td class="param-desc">已售数除以此值得到基础分</td>
                            </tr>
                            <tr>
                                <td class="param-name">零销量分数</td>
                                <td><input type="number" id="sales-ratio-zero-score" class="param-input sales-ratio-input" step="0.1" min="0" max="1" value="${rule.sold_zero_score || 0.2}" /></td>
                                <td class="param-desc">已售为0时的分数</td>
                            </tr>
                            <tr>
                                <td class="param-name">加分阈值</td>
                                <td><input type="number" id="sales-ratio-boost-threshold" class="param-input sales-ratio-input" step="0.1" min="0" value="${rule.ratio_boost_threshold || 0.5}" /></td>
                                <td class="param-desc">比例低于此值时加分</td>
                            </tr>
                            <tr>
                                <td class="param-name">中立阈值</td>
                                <td><input type="number" id="sales-ratio-neutral-threshold" class="param-input sales-ratio-input" step="0.1" min="0" value="${rule.ratio_neutral_threshold || 1.0}" /></td>
                                <td class="param-desc">比例在加分阈值和中立阈值间维持原分</td>
                            </tr>
                            <tr>
                                <td class="param-name">加分系数</td>
                                <td><input type="number" id="sales-ratio-boost-factor" class="param-input sales-ratio-input" step="0.1" min="0" value="${rule.ratio_boost_factor || 1.2}" /></td>
                                <td class="param-desc">比例低时的乘数</td>
                            </tr>
                            <tr>
                                <td class="param-name">惩罚系数</td>
                                <td><input type="number" id="sales-ratio-penalty-factor" class="param-input sales-ratio-input" step="0.1" min="0" value="${rule.ratio_penalty_factor || 0.8}" /></td>
                                <td class="param-desc">比例高时的乘数</td>
                            </tr>
                            <tr>
                                <td class="param-name">缺失默认分</td>
                                <td><input type="number" id="sales-ratio-missing-score" class="param-input sales-ratio-input" step="0.1" min="0" max="1" value="${rule.missing_score || 0.5}" /></td>
                                <td class="param-desc">数据缺失时使用</td>
                            </tr>
                        </table>
                        
                        <div class="example-box">
                            <strong>💡 计算示例：</strong>
                            <ul>
                                <li>"5 / 100" → base=1.0, ratio=0.05 < 0.5 → 1.0×1.2 = <strong>1.0</strong> (顶满)</li>
                                <li>"80 / 100" → base=1.0, ratio=0.8 (0.5-1.0间) → <strong>1.0</strong></li>
                                <li>"150 / 100" → base=1.0, ratio=1.5 > 1.0 → 1.0×0.8 = <strong>0.8</strong></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染发布新鲜度评分规则
     */
    renderFreshnessRule(rule) {
        if (!rule) {
            rule = {
                missing_score: 0.5,
                recent_keywords: ['分钟', '小时'],
                recent_score: 1.0,
                day_regex: '(\\d+)\\s*天前',
                day_scores: [{ max_days: 1, score: 1.0 }, { max_days: 3, score: 0.8 }, { max_days: 7, score: 0.6 }]
            };
        }

        const dayScores = rule.day_scores || [];

        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-freshness">
                <summary>
                    <strong>🕒 发布新鲜度 (freshness)</strong>
                    <span class="badge badge-info">时间计算</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <div class="rule-description">
                        <p><strong>计算逻辑：</strong>根据发布时间距今的天数计算分数，越近越好</p>
                        <p class="formula">📐 公式：if 天数 ≤ max_days → 使用对应score</p>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">🔧 正则表达式配置</h4>
                        <div class="param-grid">
                            <div class="param-item">
                                <label>天数提取：</label>
                                <input type="text" class="regex-input" value="${rule.day_regex || '(\\d+)\\s*天前'}" readonly />
                                <span class="param-hint">如："3天前" → 提取3</span>
                            </div>
                            <div class="param-item">
                                <label>最近关键词：</label>
                                <input type="text" class="regex-input" value="${(rule.recent_keywords || ['分钟', '小时']).join(', ')}" readonly />
                                <span class="param-hint">包含这些词视为最新</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="param-section">
                        <h4 class="param-title">📊 分段评分规则</h4>
                        <table class="scoring-rule-table detailed">
                            <thead>
                                <tr>
                                    <th style="width: 25%">最大天数</th>
                                    <th style="width: 25%">得分</th>
                                    <th style="width: 30%">说明</th>
                                    <th style="width: 20%">示例</th>
                                </tr>
                            </thead>
                            <tbody>
                                  <tr class="highlight-row">
                                      <td><strong>分钟/小时</strong></td>
                                      <td><input type="number" id="freshness-recent-score" class="param-input freshness-score-input" step="0.1" min="0" max="1" value="${rule.recent_score || 1.0}" /></td>
                                      <td>包含关键词的超新发布</td>
                                      <td>5分钟前, 2小时前</td>
                                  </tr>
                                  ${dayScores.map((d, idx) => `
                                      <tr>
                                          <td>≤ ${d.max_days}天</td>
                                          <td><input type="number" class="param-input freshness-score-input" data-freshness-index="${idx}" step="0.1" min="0" max="1" value="${d.score}" /></td>
                                          <td>${d._说明 || ''}</td>
                                          <td>${d.max_days}天内</td>
                                      </tr>
                                  `).join('')}
                              </tbody>
                          </table>
                          
                          <div class="param-row">
                              <label class="param-label">🔄 默认分数：</label>
                              <input type="number" id="freshness-missing-score" class="param-input freshness-score-input" step="0.1" min="0" max="1" value="${rule.missing_score || 0.5}" />
                              <span class="param-hint">数据缺失或无法解析时使用</span>
                          </div>
                        
                        <div class="example-box">
                            <strong>💡 计算示例：</strong>
                            <ul>
                                <li>"5分钟前" → 包含"分钟" → <strong>1.0</strong></li>
                                <li>"3天前" → 3 ≤ 3 → <strong>0.8</strong></li>
                                <li>"10天前" → 10 ≤ 14 → <strong>0.4</strong></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染担保服务评分规则
     */
    renderHasGuaranteeRule(rule) {
        return `
            <details class="scoring-rule-panel" data-collapse-key="rule-has-guarantee">
                <summary>
                    <strong>🛡️ 担保服务 (has_guarantee)</strong>
                    <span class="badge badge-success">布尔值</span>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                    <p class="rule-description">是否有担保服务（有=1.0，无=0.0）</p>
                    <p class="hint-sm">💡 此规则为布尔判断，无需配置</p>
                </div>
            </details>
        `;
    }

    /**
     * 渲染视觉AI评分细则
     */
    renderVisualAiRulesCard(rule) {
        const visualRule = rule || {};
        const imageRule = visualRule.image_quality || {};
        const conditionRule = visualRule.condition || {};
        const authenticityRule = visualRule.authenticity || {};
        const completenessRule = visualRule.completeness || {};

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="training-samples">
                <summary class="bayes-card-header">
                    <h3>🎨 视觉AI评分细则 (visual)</h3>
                </summary>
                <div class="bayes-card-body">
                    <div class="rule-content">
                        <p class="rule-description">根据AI分析的 reason 与 criteria_analysis 提取分数</p>
                    ${this.renderVisualKeywordSection('图片质量', 'image_quality', imageRule, [
            { groupKey: 'high', label: '高质量关键词', keywords: imageRule.high_keywords, score: imageRule.high_score, desc: '高质量匹配' },
            { groupKey: 'mid', label: '中质量关键词', keywords: imageRule.mid_keywords, score: imageRule.mid_score, desc: '中等质量匹配' },
            { groupKey: 'low', label: '低质量关键词', keywords: imageRule.low_keywords, score: imageRule.low_score, desc: '低质量匹配' }
        ], imageRule.default_score)}
                    ${this.renderVisualKeywordSection('商品成色', 'condition', conditionRule, [
            { groupKey: 'high', label: '高成色关键词', keywords: conditionRule.high_keywords, score: conditionRule.high_score, desc: '成色极好' },
            { groupKey: 'good', label: '良好关键词', keywords: conditionRule.good_keywords, score: conditionRule.good_score, desc: '成色良好' },
            { groupKey: 'normal', label: '一般关键词', keywords: conditionRule.normal_keywords, score: conditionRule.normal_score, desc: '成色一般' },
            { groupKey: 'bad', label: '较差关键词', keywords: conditionRule.bad_keywords, score: conditionRule.bad_score, desc: '成色较差' }
        ], conditionRule.default_score)}
                    ${this.renderVisualKeywordSection('图片真实性', 'authenticity', authenticityRule, [
            { groupKey: 'good', label: '真实关键词', keywords: authenticityRule.good_keywords, score: authenticityRule.good_score, desc: '实拍可信' },
            { groupKey: 'suspect', label: '可疑关键词', keywords: authenticityRule.suspect_keywords, score: authenticityRule.suspect_score, desc: '存疑需核实' },
            { groupKey: 'bad', label: '不真实关键词', keywords: authenticityRule.bad_keywords, score: authenticityRule.bad_score, desc: '疑似网图/假图' }
        ], authenticityRule.default_score)}
                    ${this.renderVisualCompletenessSection(completenessRule)}
                    </div>
                </div>
            </details>
        `;
    }

    /**
     * 渲染视觉AI关键词评分区块
     */
    renderVisualKeywordSection(title, key, rule, groups, defaultScore) {
        const descMap = rule._说明明细 || {};
        const rows = groups.map(item => {
            const keywordsText = Array.isArray(item.keywords) ? item.keywords.join(', ') : '';
            const scoreText = typeof item.score === 'number' ? item.score : 0;
            const desc = descMap[item.groupKey] || item.desc || '';
            return `
                <tr data-visual-key="${key}" data-group-key="${item.groupKey}">
                    <td>${item.label}</td>
                    <td><input type="text" class="visual-keywords-input" value="${keywordsText}" placeholder="关键词，用逗号分隔" /></td>
                    <td><input type="number" class="visual-score-input" step="0.1" min="0" max="1" value="${scoreText}" /></td>
                    <td><input type="text" class="visual-desc-input" value="${desc}" placeholder="说明" /></td>
                </tr>
            `;
        }).join('');

        return `
            <div class="param-section">
                <h4 class="param-title">🎯 ${title} (${key})</h4>
                <table class="scoring-rule-table">
                    <thead>
                        <tr>
                            <th style="width: 20%">规则类型</th>
                            <th style="width: 45%">关键词</th>
                            <th style="width: 15%">得分</th>
                            <th style="width: 20%">说明</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows || '<tr><td colspan="4" class="desc-cell">暂无关键词规则</td></tr>'}
                    </tbody>
                </table>
                <div class="param-row">
                    <label class="param-label">🔄 默认分数：</label>
                    <input type="number" class="param-input visual-default-score" data-visual-key="${key}" value="${typeof defaultScore === 'number' ? defaultScore : 0}" />
                    <span class="param-hint">未匹配任何关键词时使用</span>
                </div>
            </div>
        `;
    }

    /**
     * 渲染图片完整性规则区块
     */
    renderVisualCompletenessSection(rule) {
        const maxImages = Number.isFinite(rule.max_images) ? rule.max_images : '';
        const minScore = Number.isFinite(rule.min_score) ? rule.min_score : '';
        const formula = rule._计算公式 || 'score = min(1.0, 图片数量 / max_images)';
        const note = rule._说明 || '图片数量越多越好';

        return `
            <div class="param-section">
                <h4 class="param-title">🧩 图片完整性 (completeness)</h4>
                <table class="param-table">
                    <tr>
                        <td class="param-name">最大图片数</td>
                        <td><input type="number" class="param-input visual-completeness-input" id="visual-completeness-max" value="${maxImages}" /></td>
                        <td class="param-desc">达到该数量视为满分</td>
                    </tr>
                    <tr>
                        <td class="param-name">最小分数</td>
                        <td><input type="number" class="param-input visual-completeness-input" id="visual-completeness-min" value="${minScore}" /></td>
                        <td class="param-desc">分数下限</td>
                    </tr>
                    <tr>
                        <td class="param-name">计算公式</td>
                        <td colspan="2" class="param-desc">
                            <input type="text" class="param-input param-input-wide" id="visual-completeness-formula" value="${formula}" />
                        </td>
                    </tr>
                    <tr>
                        <td class="param-name">说明</td>
                        <td colspan="2" class="param-desc">
                            <input type="text" class="param-input param-input-wide" id="visual-completeness-note" value="${note}" />
                        </td>
                    </tr>
                </table>
            </div>
        `;
    }

    /**
     * 渲染训练样本管理卡片
     */
    renderTrainingSamplesCard() {
        const samples = this.ensureSampleBuckets();

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="fusion-weights">
                <summary class="bayes-card-header">
                    <h3>📚 训练样本管理</h3>
                </summary>
                <div class="bayes-card-body">
                    <p class="hint">💡 用于贝叶斯模型训练的卖家样本，帮助模型学习可信和不可信卖家的特征模式</p>
                    
                    ${this.renderTrustedSamplesSection(samples.trusted || [])}
                    ${this.renderUntrustedSamplesSection(samples.untrusted || [])}
                </div>
            </details>
        `;
    }

    /**
     * 渲染可信样本部分
     */
    renderTrustedSamplesSection(samples) {
        return `
            <details class="sample-panel" data-collapse-key="samples-trusted">
                <summary>
                    <strong>✅ 可信样本 (${samples.length})</strong>
                    <span class="badge badge-success">用于正样本训练</span>
                </summary>
                <div class="sample-content">
                    <p class="sample-description">标记为可信的卖家样本，具有稳定、可靠、值得信任的特征</p>
                    
                    <div class="features-guide" style="background: #e3f2fd; padding: 12px; border-radius: 6px; margin: 10px 0; font-size: 13px; line-height: 1.6;">
                        <strong>📊 特征向量说明（8维，按顺序）：</strong><br>
                        <span style="color: #555; margin-left: 20px;">
                            ① <strong>信用等级</strong> | ② <strong>卖家好评率</strong> | ③ <strong>注册时长</strong> | ④ <strong>在售/已售比</strong> | 
                            ⑤ <strong>图片数量</strong> | ⑥ <strong>描述质量</strong> | ⑦ <strong>商品热度</strong> | ⑧ <strong>品类集中度</strong>
                        </span><br>
                        <span style="color: #666; font-size: 12px; margin-left: 20px;">💡 数值范围：0.0-1.0，越接近1.0表示该特征越优秀</span>
                    </div>
                    
                    <table class="sample-table" id="trusted-samples-table">
                        <thead>
                            <tr>
                                <th style="width: 22%">样本名称</th>
                                <th style="width: 38%">特征向量（${(this.config.feature_names || []).length}维）</th>
                                <th style="width: 30%">备注说明</th>
                                <th style="width: 10%">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${samples.length > 0 ? samples.map((s, idx) => this.renderSampleRow('trusted', s, idx)).join('') : '<tr><td colspan="4" class="empty-row">暂无可信样本</td></tr>'}
                        </tbody>
                    </table>
                    
                    <button class="control-button add-sample-btn" data-type="trusted">+ 添加可信卖家样本</button>
                </div>
            </details>
        `;
    }

    /**
     * 渲染不可信样本部分
     */
    renderUntrustedSamplesSection(samples) {
        return `
            <details class="sample-panel" data-collapse-key="samples-untrusted">
                <summary>
                    <strong>❌ 不可信样本 (${samples.length})</strong>
                    <span class="badge badge-danger">用于负样本训练</span>
                </summary>
                <div class="sample-content">
                    <p class="sample-description">标记为不可信的卖家样本，具有高风险、异常、需警惕的特征</p>
                    
                    <div class="features-guide" style="background: #fff3e0; padding: 12px; border-radius: 6px; margin: 10px 0; font-size: 13px; line-height: 1.6;">
                        <strong>📊 特征向量说明（8维，按顺序）：</strong><br>
                        <span style="color: #555; margin-left: 20px;">
                            ① <strong>信用等级</strong> | ② <strong>卖家好评率</strong> | ③ <strong>注册时长</strong> | ④ <strong>在售/已售比</strong> | 
                            ⑤ <strong>图片数量</strong> | ⑥ <strong>描述质量</strong> | ⑦ <strong>商品热度</strong> | ⑧ <strong>品类集中度</strong>
                        </span><br>
                        <span style="color: #666; font-size: 12px; margin-left: 20px;">💡 数值范围：0.0-1.0，越接近1.0表示该特征越优秀</span>
                    </div>
                    
                    <table class="sample-table" id="untrusted-samples-table">
                        <thead>
                            <tr>
                                <th style="width: 22%">样本名称</th>
                                <th style="width: 38%">特征向量（${(this.config.feature_names || []).length}维）</th>
                                <th style="width: 30%">备注说明</th>
                                <th style="width: 10%">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${samples.length > 0 ? samples.map((s, idx) => this.renderSampleRow('untrusted', s, idx)).join('') : '<tr><td colspan="4" class="empty-row">暂无不可信样本</td></tr>'}
                        </tbody>
                    </table>
                    
                    <button class="control-button add-sample-btn" data-type="untrusted">+ 添加不可信卖家样本</button>
                </div>
            </details>
        `;
    }

    /**
     * 渲染样本行
     */
    renderSampleRow(type, sample, index) {
        const vectorValue = Array.isArray(sample.vector) ? sample.vector.join(', ') : (sample.vector || '');
        const nameValue = sample.name || sample.title || '';
        return `
            <tr data-type="${type}" data-index="${index}">
                <td><input type="text" class="sample-name-input" value="${nameValue}" placeholder="卖家样本名称" /></td>
                <td><input type="text" class="sample-vector-input" value="${vectorValue}" placeholder="例如: 1, 0.5, 0.8, 0.6, 1, 0.4, 0.7, 0.9" /></td>
                <td><input type="text" class="sample-note-input" value="${sample.note || ''}" placeholder="备注说明" /></td>
                <td>
                    <button class="control-button danger-btn-sm delete-sample-btn" data-type="${type}" data-index="${index}">删除</button>
                </td>
            </tr>
        `;
    }

    /**
     * 绑定训练样本事件
     */
    bindTrainingSampleEvents() {
        if (this.trainingSampleEventsBound || !this.container) {
            return;
        }

        this.trainingSampleEventsBound = true;

        this.container.addEventListener('click', (e) => {
            const addBtn = e.target.closest('.add-sample-btn');
            if (addBtn) {
                e.preventDefault();
                e.stopPropagation();
                this.addSample(addBtn.dataset.type);
                return;
            }

            const deleteBtn = e.target.closest('.delete-sample-btn');
            if (deleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                const type = deleteBtn.dataset.type;
                const index = parseInt(deleteBtn.dataset.index, 10);
                this.deleteSample(type, index);
            }
        });
    }

    /**
     * 添加样本
     */
    addSample(type) {
        this.ensureSampleBuckets();

        const newSample = {
            id: '',
            name: '',
            vector: [],
            label: type === 'trusted' ? 1 : 0,
            note: ''
        };

        if (type === 'trusted') {
            this.config._samples.trusted = this.config._samples.trusted || [];
            this.config._samples.trusted.push(newSample);
            this.sampleLegacyCache.trusted = this.sampleLegacyCache.trusted || [];
            this.sampleLegacyCache.trusted.push(null);
        } else {
            this.config._samples.untrusted = this.config._samples.untrusted || [];
            this.config._samples.untrusted.push(newSample);
            this.sampleLegacyCache.untrusted = this.sampleLegacyCache.untrusted || [];
            this.sampleLegacyCache.untrusted.push(null);
        }

        // 重新渲染
        this.isDirty = true;
        this.render();
    }

    /**
     * 删除样本
     */
    async deleteSample(type, index) {
        if (!this.config._samples) return;

        const confirmResult = await Notification.confirmDelete('确定要删除这个样本吗？');
        if (!confirmResult.isConfirmed) {
            return;
        }

        if (type === 'trusted') {
            this.config._samples.trusted.splice(index, 1);
            this.sampleLegacyCache.trusted.splice(index, 1);
        } else {
            this.config._samples.untrusted.splice(index, 1);
            this.sampleLegacyCache.untrusted.splice(index, 1);
        }

        // 重新渲染
        this.isDirty = true;
        this.render();
    }

    /**
     * 收集训练样本
     */
    collectTrainingSamples() {
        this.ensureSampleBuckets();
        // 收集可信样本
        const trustedRows = document.querySelectorAll('#trusted-samples-table tbody tr[data-type="trusted"]');
        this.config._samples.trusted = Array.from(trustedRows).map(row => {
            const name = row.querySelector('.sample-name-input')?.value || row.querySelector('.sample-title-input')?.value || '';
            const vectorRaw = row.querySelector('.sample-vector-input')?.value || '';
            const vector = this.parseVectorString(vectorRaw);
            return {
                id: '',
                name,
                vector,
                label: 1,
                note: row.querySelector('.sample-note-input')?.value || ''
            };
        });

        // 收集不可信样本
        const untrustedRows = document.querySelectorAll('#untrusted-samples-table tbody tr[data-type="untrusted"]');
        this.config._samples.untrusted = Array.from(untrustedRows).map(row => {
            const name = row.querySelector('.sample-name-input')?.value || row.querySelector('.sample-title-input')?.value || '';
            const vectorRaw = row.querySelector('.sample-vector-input')?.value || '';
            const vector = this.parseVectorString(vectorRaw);
            return {
                id: '',
                name,
                vector,
                label: 0,
                note: row.querySelector('.sample-note-input')?.value || ''
            };
        });

        // 同步回写旧版样本结构（保留向量与标签）
        this.config._samples['可信'] = this.config._samples.trusted.map(sample => ({
            name: sample.name || '',
            vector: Array.isArray(sample.vector) ? sample.vector : [],
            label: 1,
            note: sample.note || ''
        }));

        this.config._samples['不可信'] = this.config._samples.untrusted.map(sample => ({
            name: sample.name || '',
            vector: Array.isArray(sample.vector) ? sample.vector : [],
            label: 0,
            note: sample.note || ''
        }));
    }

    /**
     * 渲染风险惩罚配置卡片
     */
    renderRiskPenaltyCard() {
        const penalty = this.config.recommendation_fusion.risk_penalty;

        return `
            <details class="bayes-card collapsible-card" data-collapse-key="risk-penalty">
                <summary class="bayes-card-header">
                    <h3>⚠️ 风险惩罚配置</h3>
                </summary>
                <div class="bayes-card-body">
                    <table class="bayes-config-table">
                        <thead>
                            <tr>
                                <th>配置项</th>
                                <th>值</th>
                                <th>说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>每个标签扣分</strong></td>
                                <td><input type="number" id="risk-per-tag-penalty" min="0" max="100" value="${penalty.per_tag_penalty}"/></td>
                                <td>每识别到一个风险标签扣除的分数</td>
                            </tr>
                            <tr>
                                <td><strong>最大惩罚分数</strong></td>
                                <td><input type="number" id="risk-max-penalty" min="0" max="100" value="${penalty.max_penalty}"/></td>
                                <td>风险惩罚的上限</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </details>
        `;
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 监听所有权重输入的变化，实时计算总和
        document.querySelectorAll('.bayes-weight-table input[type="number"]').forEach(input => {
            input.addEventListener('input', (e) => {
                this.isDirty = true;
                this.updateFusionColumnSums();
            });
        });

        // 监听贝叶斯特征权重输入
        document.querySelectorAll('.bayes-feature-input').forEach(input => {
            input.addEventListener('input', () => {
                this.isDirty = true;
                this.updateBayesianFeaturesSum();
            });
        });

        // 监听视觉特征权重输入
        document.querySelectorAll('.visual-feature-input').forEach(input => {
            input.addEventListener('input', () => {
                this.isDirty = true;
                this.updateVisualFeaturesSum();
            });
        });

        // 监听风险惩罚输入
        document.querySelectorAll('#risk-per-tag-penalty, #risk-max-penalty').forEach(input => {
            input.addEventListener('input', () => {
                this.isDirty = true;
            });
        });

        // 监听销售比例/新鲜度输入
        document.querySelectorAll('.sales-ratio-input, .freshness-score-input').forEach(input => {
            input.addEventListener('input', () => {
                this.isDirty = true;
            });
        });

        // 保存按钮
        const saveBtn = document.getElementById('bayes-save-btn');
        if (saveBtn && !saveBtn.dataset.bound) {
            saveBtn.addEventListener('click', () => this.saveConfig());
            saveBtn.dataset.bound = 'true';
        }

        // 重置按钮
        const resetBtn = document.getElementById('bayes-reset-btn');
        if (resetBtn && !resetBtn.dataset.bound) {
            resetBtn.addEventListener('click', async () => {
                if (this.isDirty) {
                    const confirmResult = await Notification.confirm('有未保存的更改，确定要重置吗？');
                    if (!confirmResult.isConfirmed) {
                        return;
                    }
                }
                await this.initialize();
            });
            resetBtn.dataset.bound = 'true';
        }

        // 复制按钮
        const copyBtn = document.getElementById('bayes-copy-btn');
        if (copyBtn && !copyBtn.dataset.bound) {
            copyBtn.addEventListener('click', () => this.copyCurrentVersion());
            copyBtn.dataset.bound = 'true';
        }

        // 删除按钮
        const deleteBtn = document.getElementById('bayes-delete-btn');
        if (deleteBtn && !deleteBtn.dataset.bound) {
            deleteBtn.addEventListener('click', () => this.deleteCurrentVersion());
            deleteBtn.dataset.bound = 'true';
        }

        // 版本选择器
        const versionSelect = document.getElementById('bayes-version-select');
        if (versionSelect && !versionSelect.dataset.bound) {
            versionSelect.addEventListener('change', async (e) => {
                if (this.isDirty) {
                    const confirmResult = await Notification.confirm('有未保存的更改，确定要切换版本吗？');
                    if (!confirmResult.isConfirmed) {
                        e.target.value = this.currentVersion;
                        return;
                    }
                }
                await this.loadConfig(e.target.value);
                this.render();
                this.setupEventListeners();
            });
            versionSelect.dataset.bound = 'true';
        }

        // 添加规则按钮
        document.querySelectorAll('.add-rule-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ruleType = e.target.getAttribute('data-rule');
                this.addScoringRule(ruleType);
            });
        });

        // 删除规则按钮 (使用事件委托)
        document.addEventListener('click', async (e) => {
            if (e.target.classList.contains('delete-rule-btn')) {
                const row = e.target.closest('tr');
                if (!row) {
                    return;
                }
                const confirmResult = await Notification.confirmDelete('确定要删除这条规则吗？');
                if (!confirmResult.isConfirmed) {
                    return;
                }
                row.remove();
                this.isDirty = true;
            }
        });
    }

    /**
     * 更新融合权重行的总和显示
     */
    updateFusionColumnSums() {
        const withImgSum = this.sumInputs([
            'weight-with-img-bayesian',
            'weight-with-img-visual',
            'weight-with-img-ai'
        ]);
        const noImgSum = this.sumInputs([
            'weight-no-img-bayesian',
            'weight-no-img-visual',
            'weight-no-img-ai'
        ]);

        this.updateSumCell('weight-sum-with-img', withImgSum);
        this.updateSumCell('weight-sum-no-img', noImgSum);
    }

    sumInputs(ids) {
        return ids.reduce((acc, id) => {
            const input = document.getElementById(id);
            return acc + parseFloat(input?.value || 0);
        }, 0);
    }

    updateSumCell(cellId, sum) {
        const cell = document.getElementById(cellId);
        if (!cell) return;
        const sumValueSpan = cell.querySelector('.sum-value');
        const statusSpan = cell.querySelector('.sum-status');
        sumValueSpan.textContent = sum.toFixed(2);
        if (Math.abs(sum - 1.0) < 0.001) {
            statusSpan.textContent = '✓';
            statusSpan.className = 'sum-status success';
        } else {
            statusSpan.textContent = '✗';
            statusSpan.className = 'sum-status error';
        }
    }

    /**
     * 更新贝叶斯特征权重总和
     */
    updateBayesianFeaturesSum() {
        const inputs = document.querySelectorAll('.bayes-feature-input');
        const sum = Array.from(inputs).reduce((acc, input) => {
            return acc + parseFloat(input.value || 0);
        }, 0);

        const sumCell = document.getElementById('bayes-features-sum');
        const sumValueSpan = sumCell.querySelector('.sum-value');
        const statusSpan = sumCell.querySelector('.sum-status');

        sumValueSpan.textContent = sum.toFixed(2);

        if (Math.abs(sum - 1.0) < 0.001) {
            statusSpan.textContent = '✓';
            statusSpan.className = 'sum-status success';
        } else {
            statusSpan.textContent = '✗';
            statusSpan.className = 'sum-status error';
        }
    }

    /**
     * 更新视觉特征权重总和
     */
    updateVisualFeaturesSum() {
        const inputs = document.querySelectorAll('.visual-feature-input');
        const sum = Array.from(inputs).reduce((acc, input) => {
            return acc + parseFloat(input.value || 0);
        }, 0);

        const sumCell = document.getElementById('visual-features-sum');
        const sumValueSpan = sumCell.querySelector('.sum-value');
        const statusSpan = sumCell.querySelector('.sum-status');

        sumValueSpan.textContent = sum.toFixed(2);

        if (Math.abs(sum - 1.0) < 0.001) {
            statusSpan.textContent = '✓';
            statusSpan.className = 'sum-status success';
        } else {
            statusSpan.textContent = '✗';
            statusSpan.className = 'sum-status error';
        }
    }

    /**
     * 添加评分规则
     */
    addScoringRule(ruleType) {
        const tbodyId = ruleType === 'seller_credit_level' ? 'seller-credit-rules' : `${ruleType}-rules`;
        const tbody = document.getElementById(tbodyId);
        if (!tbody) {
            console.error(`Table body not found for rule type: ${ruleType}`);
            return;
        }

        const newRow = ruleType === 'seller_credit_level'
            ? this.renderSellerCreditRuleRow({
                keywords: [],
                score: 0.5,
                _说明: ''
            }, tbody.children.length)
            : this.renderScoringRuleRow(ruleType, {
                keywords: [],
                score: 0.5,
                _说明: ''
            }, tbody.children.length);

        tbody.insertAdjacentHTML('beforeend', newRow);
        this.isDirty = true;
    }
}

// 导出给全局使用
window.BayesVisualManager = BayesVisualManager;

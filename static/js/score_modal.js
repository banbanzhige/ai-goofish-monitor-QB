// 字段名中文映射（支持新旧字段名）
const FIELD_NAME_MAP = {
    // 贝叶斯特征
    'seller_tenure': '卖家注册时长',
    'positive_rate': '卖家好评率',
    'seller_credit_level': '卖家信用等级',
    'zhima_credit': '卖家信用等级', // 兼容旧数据
    'sales_ratio': '在售/已售比',
    'used_years': '已用年限',
    'price_reasonable': '已用年限',  // 兼容旧数据
    'freshness': '发布新鲜度',
    'has_guarantee': '担保服务',

    // 视觉AI特征
    'image_quality': '图片质量',
    'condition': '成色评估',
    'authenticity': '真实性',
    'completeness': '完整性'
};

// 推荐度详情模态框函数
window.showScoreDetailModal = function (element) {
    const data = JSON.parse(element.getAttribute('data-score-detail'));

    // 格式化特征详情的辅助函数
    const formatFeatureDetails = (features) => {
        if (!features || typeof features !== 'object') return '';
        return Object.entries(features).map(([key, value]) => {
            const displayName = FIELD_NAME_MAP[key] || key;
            const isNumber = typeof value === 'number';
            const displayValue = isNumber ? `${(value * 100).toFixed(1)}%` : (value ?? '缺失');
            return `<div class="detail-item"><span>${displayName}:</span> <span>${displayValue}</span></div>`;
        }).join('');
    };

    // 格式化风险标签列表
    const formatRiskTags = (riskTags, perTagPenalty) => {
        if (!riskTags || !Array.isArray(riskTags) || riskTags.length === 0) return '';
        return riskTags.map(tag =>
            `<div class="risk-tag-item"><span class="tag-text">${tag}</span><span class="tag-penalty">-${perTagPenalty}分</span></div>`
        ).join('');
    };

    // 创建模态框HTML
    const modalHtml = `
        <div id="scoreDetailModal" class="score-modal-overlay" onclick="closeScoreModal(event)">
            <div class="score-modal-content" onclick="event.stopPropagation()">
                <div class="score-modal-header">
                    <h3>推荐度详细分解</h3>
                    <button class="score-modal-close" onclick="closeScoreModal()">&times;</button>
                </div>
                <div class="score-modal-body">
                    <div class="score-final">
                        <div class="score-final-label">综合推荐度</div>
                        <div class="score-final-value">${data.finalScore}分</div>
                    </div>
                    
                    <div class="score-breakdown">
                        <h4>评分组成 (三维度融合)</h4>
                        <div class="score-component">
                            <div class="score-component-header">
                                <span class="score-component-name">🔢 贝叶斯用户评分</span>
                                <span class="score-component-weight">权重: ${(data.fusion?.weights?.bayesian * 100 || 40).toFixed(0)}%</span>
                            </div>
                            <div class="score-component-value">${data.bayesian}分</div>
                            ${data.bayesianDetails?.features ? `
                                <div class="score-component-details">
                                    ${formatFeatureDetails(data.bayesianDetails.features)}
                                </div>
                            ` : ''}
                        </div>
                        
                        <div class="score-component">
                            <div class="score-component-header">
                                <span class="score-component-name">👁️ 视觉AI产品评分</span>
                                <span class="score-component-weight">权重: ${(data.fusion?.weights?.visual * 100 || 35).toFixed(0)}%</span>
                            </div>
                            <div class="score-component-value">${data.visual}分</div>
                            ${data.visualDetails?.breakdown ? `
                                <div class="score-component-details">
                                    ${formatFeatureDetails(data.visualDetails.breakdown)}
                                </div>
                            ` : ''}
                        </div>
                        
                        <div class="score-component">
                            <div class="score-component-header">
                                <span class="score-component-name">🤖 AI分析置信度</span>
                                <span class="score-component-weight">权重: ${(data.fusion?.weights?.ai * 100 || 25).toFixed(0)}%</span>
                            </div>
                            <div class="score-component-value">${data.ai}分</div>
                        </div>
                    </div>
                    
                    ${data.fusion?.risk_penalty > 0 ? `
                        <div class="score-penalty">
                            <div class="penalty-header">
                                <div class="penalty-label">⚠️ 风险标签惩罚</div>
                                <div class="penalty-value">-${data.fusion.risk_penalty}分</div>
                            </div>
                            ${data.fusion?.risk_tags && data.fusion.risk_tags.length > 0 ? `
                                <div class="risk-tags-list">
                                    ${formatRiskTags(data.fusion.risk_tags, 5)}
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;

    // 添加到body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
};

window.closeScoreModal = function (event) {
    if (event && event.target.classList.contains('score-modal-content')) return;
    const modal = document.getElementById('scoreDetailModal');
    if (modal) modal.remove();
};

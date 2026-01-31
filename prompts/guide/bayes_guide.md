## Bayes 参数文件结构（bayes_v1.json）
文件包含两块：
1. **recommendation_fusion**：推荐度融合权重与评分规则（可配置）。
2. **bayes_feature_rules + feature_names + _samples**：Bayes 先验参数与样本集。

---

### 1) 推荐度融合配置（recommendation_fusion）
用于计算最终推荐度（0-100 分）。配置项：
- `weights`：有图片时三维融合权重
  - `bayesian`：贝叶斯用户评分权重
  - `visual`：视觉 AI 评分权重
  - `ai`：AI 置信度权重
- `weights_no_visual`：无图片时降级权重（visual 自动为 0）
- `bayesian_features`：贝叶斯用户评分 7 个特征权重
  - seller_tenure（卖家注册时长）
  - positive_rate（好评率）
  - seller_credit_level（卖家信用等级）
  - sales_ratio（在售/已售比）
  - used_years（已用年限）
  - freshness（发布新鲜度）
  - has_guarantee（担保服务）
- `visual_features`：视觉评分 4 个特征权重
  - image_quality（图片质量）
  - condition（成色评估）
  - authenticity（真实性）
  - completeness（完整性）
- `risk_penalty`：风险标签扣分
- `scoring_rules`：推荐度评分规则模板（核心可配置项）
  - `missing_rule_score`：规则缺失时默认分；若未填则会标记“缺失”
  - `seller_tenure/positive_rate/seller_credit_level/sales_ratio/used_years/freshness/has_guarantee`：各维度规则
  - `visual`：视觉维度关键词与默认分

**注意**：评分规则缺失将不会回退硬编码，会在结果中标记 `missing_rules/missing_features`。

---

### 2) Bayes 先验参数（bayes_feature_rules + feature_names + _samples）
- `feature_names`：8 维特征名称（顺序与样本向量一致）
- `bayes_feature_rules`：8 维打分规则模板（与 `feature_names` 一一对应）
  - `missing_rule_score`：缺失规则时默认分；未配置则视为缺失
  - `seller_credit_level_score/positive_rate_score/register_score/on_sale_score/img_score/desc_score/heat_score/category_score`
- `_samples`：可信 / 不可信样本集，用于自动估计 priors / mean / var
- `_priors_mode` / `_stats_mode`：auto_from_samples 或 manual
- `_min_variance`：方差下限，避免过拟合

**注意**：当 Bayes 规则缺失时，预计算会直接返回缺失状态，不再使用硬编码兜底。

---

### 使用建议
1. 复制 `bayes_v1.json` 为新文件（如 `bayes_custom.json`）。
2. 修改 `scoring_rules` 与 `bayes_feature_rules`，再调整权重配置。
3. 保持权重合计为 1.0，避免评分偏移。
4. 规则缺失会导致评分标记为“缺失”，请确保规则完整。

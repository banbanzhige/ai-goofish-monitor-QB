import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple, Any


# Bayes 配置文件目录
BAYES_DIR = os.path.join("prompts", "bayes")


def _safe_text(value: Any) -> str:
    return str(value) if value is not None else ""


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = _safe_text(value)
    matches = re.findall(r"\d+", text)
    if not matches:
        return None
    try:
        return int(matches[0])
    except ValueError:
        return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _safe_text(value).replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _get_rule_score(rule: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    value = rule.get(key) if isinstance(rule, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def _get_rule_config(rules: Optional[Dict[str, Any]], key: str, missing_rules: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(rules, dict):
        missing_rules.append(key)
        return None
    rule = rules.get(key)
    if not isinstance(rule, dict):
        missing_rules.append(key)
        return None
    return rule


def _get_missing_rule_score(rules: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rules, dict):
        return None
    value = rules.get("missing_rule_score")
    return float(value) if isinstance(value, (int, float)) else None


def _map_seller_credit_level_score(text: str, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not text:
        return missing_score

    credit_text = str(text).strip()
    if not credit_text:
        return missing_score

    for item in rule.get("text_mapping", []):
        keywords = item.get("keywords")
        score = item.get("score")
        if isinstance(keywords, list) and isinstance(score, (int, float)):
            if any(keyword in credit_text for keyword in keywords if isinstance(keyword, str)):
                return float(score)

    match = re.search(r"(\d+)", credit_text)
    level = int(match.group(1)) if match else None

    level_rules = rule.get("level_rules", {})
    for key in ["heart", "diamond", "crown"]:
        level_rule = level_rules.get(key)
        if not isinstance(level_rule, dict):
            continue
        keyword = level_rule.get("keyword")
        if not (isinstance(keyword, str) and keyword in credit_text):
            continue

        missing_level_score = _get_rule_score(level_rule, "missing_level_score")
        if level is None:
            return missing_level_score if isinstance(missing_level_score, (int, float)) else missing_score

        base = _get_rule_score(level_rule, "base")
        step = _get_rule_score(level_rule, "step")
        level_offset = level_rule.get("level_offset", 0)
        min_score = _get_rule_score(level_rule, "min")
        max_score = _get_rule_score(level_rule, "max")
        if not isinstance(base, (int, float)) or not isinstance(step, (int, float)):
            return missing_score

        if not isinstance(level_offset, (int, float)):
            level_offset = 0

        score = float(base) + float(step) * max(0, level - float(level_offset))
        if isinstance(min_score, (int, float)):
            score = max(float(min_score), score)
        if isinstance(max_score, (int, float)):
            score = min(float(max_score), score)
        return score

    return _get_rule_score(rule, "default_score")



def _map_positive_rate(text: str, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not text or text in ["N/A", "??"]:
        return missing_score
    value = _parse_float(text)
    if value is None:
        return missing_score
    for item in rule.get("buckets", []):
        min_value = item.get("min")
        score = item.get("score")
        if isinstance(min_value, (int, float)) and isinstance(score, (int, float)):
            if value >= min_value:
                return float(score)
    return missing_score



def _map_register_score(text: str, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not text:
        return missing_score
    year_regex = rule.get("year_regex")
    if isinstance(year_regex, str):
        match = re.search(year_regex, str(text))
        if match:
            try:
                years = int(match.group(1))
            except ValueError:
                years = None
            if years is not None:
                for item in rule.get("year_scores", []):
                    min_years = item.get("min_years")
                    score = item.get("score")
                    if isinstance(min_years, (int, float)) and isinstance(score, (int, float)):
                        if years >= min_years:
                            return float(score)
    if "?" in str(text):
        month_score = _get_rule_score(rule, "month_score")
        return month_score if isinstance(month_score, (int, float)) else missing_score
    return _get_rule_score(rule, "default_score")



def _map_on_sale_score(value: Any, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    count = _parse_int(value)
    if count is None:
        return missing_score
    for item in rule.get("buckets", []):
        min_value = item.get("min")
        max_value = item.get("max")
        score = item.get("score")
        if not isinstance(score, (int, float)):
            continue
        if isinstance(min_value, (int, float)) and isinstance(max_value, (int, float)):
            if min_value <= count <= max_value:
                return float(score)
        elif isinstance(min_value, (int, float)) and count >= min_value:
            return float(score)
        elif isinstance(max_value, (int, float)) and count <= max_value:
            return float(score)
    return missing_score



def _map_img_score(images: Any, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not isinstance(images, list):
        return missing_score
    count = len(images)
    for item in rule.get("count_scores", []):
        min_count = item.get("min_count")
        score = item.get("score")
        if isinstance(min_count, (int, float)) and isinstance(score, (int, float)):
            if count >= min_count:
                return float(score)
    return _get_rule_score(rule, "default_score")



def _map_desc_score(title: str, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not title:
        return missing_score
    negative_words = rule.get("negative_keywords", [])
    positive_words = rule.get("positive_keywords", [])
    if isinstance(negative_words, list) and any(word in title for word in negative_words if isinstance(word, str)):
        return _get_rule_score(rule, "negative_score")
    if isinstance(positive_words, list) and any(word in title for word in positive_words if isinstance(word, str)):
        return _get_rule_score(rule, "positive_score")
    return _get_rule_score(rule, "default_score")



def _map_heat_score(view_value: Any, want_value: Any, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    want_count = _parse_int(want_value)
    if want_count is None:
        return missing_score
    if want_count == 0:
        return _get_rule_score(rule, "want_zero_score")
    view_count = _parse_int(view_value)
    if view_count is None:
        return missing_score
    ratio = view_count / max(want_count, 1)
    for item in rule.get("ratio_scores", []):
        max_ratio = item.get("max_ratio")
        score = item.get("score")
        if isinstance(max_ratio, (int, float)) and isinstance(score, (int, float)):
            if ratio <= max_ratio:
                return float(score)
    return _get_rule_score(rule, "default_score")



def _categorize_title(title: str, category_rules: List[Dict[str, Any]]) -> str:
    for item in category_rules:
        keywords = item.get("keywords")
        if isinstance(keywords, list) and any(word in title for word in keywords if isinstance(word, str)):
            category = item.get("category")
            if isinstance(category, str):
                return category
    return "??"



def _map_category_score(goods_list: Any, rule: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(rule, dict):
        return None
    missing_score = _get_rule_score(rule, "missing_score")
    if not isinstance(goods_list, list) or not goods_list:
        return missing_score
    category_rules = rule.get("category_keywords", [])
    if not isinstance(category_rules, list):
        return missing_score
    categories = []
    for item in goods_list:
        title = _safe_text(item.get("商品标题")) if isinstance(item, dict) else ""
        categories.append(_categorize_title(title, category_rules))
    unique_count = len(set(categories))
    for item in rule.get("unique_scores", []):
        max_unique = item.get("max_unique")
        score = item.get("score")
        if isinstance(max_unique, (int, float)) and isinstance(score, (int, float)):
            if unique_count <= max_unique:
                return float(score)
    return _get_rule_score(rule, "default_score")



def extract_features(final_record: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Tuple[Optional[List[float]], Dict[str, Any], Dict[str, Any], List[str], List[str]]:
    '''从 final_record 提取 8 维特征向量'''
    goods = final_record.get("商品信息", {}) or {}
    seller = final_record.get("卖家信息", {}) or {}

    rules = profile.get("bayes_feature_rules") if isinstance(profile, dict) else None
    missing_rules: List[str] = []
    missing_rule_score = _get_missing_rule_score(rules)

    credit_rule = _get_rule_config(rules, "seller_credit_level_score", missing_rules)
    seller_credit_text = _safe_text(seller.get("卖家信用等级") or seller.get("买家信用等级"))
    seller_credit_level_score = _map_seller_credit_level_score(seller_credit_text, credit_rule)

    positive_rule = _get_rule_config(rules, "positive_rate_score", missing_rules)
    positive_rate_text = _safe_text(seller.get("作为卖家的好评率"))
    positive_rate_score = _map_positive_rate(positive_rate_text, positive_rule)

    register_rule = _get_rule_config(rules, "register_score", missing_rules)
    register_text = _safe_text(seller.get("卖家注册时长"))
    register_score = _map_register_score(register_text, register_rule)

    on_sale_rule = _get_rule_config(rules, "on_sale_score", missing_rules)
    on_sale_score = _map_on_sale_score(seller.get("卖家在售/已售商品数"), on_sale_rule)

    img_rule = _get_rule_config(rules, "img_score", missing_rules)
    img_score = _map_img_score(goods.get("商品图片列表"), img_rule)

    desc_rule = _get_rule_config(rules, "desc_score", missing_rules)
    title_text = _safe_text(goods.get("商品标题"))
    desc_score = _map_desc_score(title_text, desc_rule)

    heat_rule = _get_rule_config(rules, "heat_score", missing_rules)
    heat_score = _map_heat_score(goods.get("浏览量"), goods.get('"想要"人数'), heat_rule)

    category_rule = _get_rule_config(rules, "category_score", missing_rules)
    category_score = _map_category_score(seller.get("卖家发布的商品列表"), category_rule)

    feature_map_raw = {
        "seller_credit_level_score": seller_credit_level_score,
        "positive_rate_score": positive_rate_score,
        "register_score": register_score,
        "on_sale_score": on_sale_score,
        "img_score": img_score,
        "desc_score": desc_score,
        "heat_score": heat_score,
        "category_score": category_score,
    }

    missing_features = [key for key, value in feature_map_raw.items() if not isinstance(value, (int, float))]
    feature_map_used = dict(feature_map_raw)
    if missing_features:
        if isinstance(missing_rule_score, (int, float)):
            for key in missing_features:
                feature_map_used[key] = float(missing_rule_score)
        else:
            feature_display = {key: (value if isinstance(value, (int, float)) else "缺失") for key, value in feature_map_raw.items()}
            return None, feature_display, feature_map_used, missing_rules, missing_features

    feature_names = [
        "seller_credit_level_score",
        "positive_rate_score",
        "register_score",
        "on_sale_score",
        "img_score",
        "desc_score",
        "heat_score",
        "category_score",
    ]
    features = [feature_map_used[name] for name in feature_names]
    feature_display = {key: (value if isinstance(value, (int, float)) else "缺失") for key, value in feature_map_raw.items()}
    return features, feature_display, feature_map_used, missing_rules, missing_features



def _load_bayes_profile(profile_name: str) -> Optional[Dict[str, Any]]:
    if not profile_name or profile_name == "disabled":
        return None
    filename = profile_name
    if not filename.endswith(".json"):
        filename += ".json"
    filepath = os.path.join(BAYES_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_vectors(samples: List[Dict[str, Any]], feature_len: int) -> List[List[float]]:
    vectors = []
    for item in samples:
        vector = item.get("vector") if isinstance(item, dict) else None
        if not isinstance(vector, list) or len(vector) != feature_len:
            continue
        try:
            vectors.append([float(x) for x in vector])
        except (TypeError, ValueError):
            continue
    return vectors


def _calc_mean_var(vectors: List[List[float]], feature_len: int, min_variance: float) -> Tuple[List[float], List[float]]:
    if not vectors:
        return [0.5] * feature_len, [max(min_variance, 0.05)] * feature_len
    count = len(vectors)
    means = [0.0] * feature_len
    for vec in vectors:
        for idx, value in enumerate(vec):
            means[idx] += value
    means = [value / count for value in means]

    variances = [0.0] * feature_len
    for vec in vectors:
        for idx, value in enumerate(vec):
            diff = value - means[idx]
            variances[idx] += diff * diff
    variances = [max(v / count, min_variance) for v in variances]
    return means, variances


def _prepare_stats(profile: Dict[str, Any]) -> Tuple[List[float], List[float], List[float]]:
    feature_names = profile.get("feature_names") or []
    feature_len = len(feature_names)
    samples = profile.get("_samples") or {}
    credible = samples.get("可信") or []
    untrusted = samples.get("不可信") or []
    credible_vectors = _collect_vectors(credible, feature_len)
    untrusted_vectors = _collect_vectors(untrusted, feature_len)

    priors_mode = profile.get("_priors_mode", "auto_from_samples")
    stats_mode = profile.get("_stats_mode", "auto_from_samples")
    min_variance = float(profile.get("_min_variance", 1e-4))

    if priors_mode == "manual" and isinstance(profile.get("priors"), list) and len(profile["priors"]) == 2:
        priors = [float(profile["priors"][0]), float(profile["priors"][1])]
    else:
        total = len(credible_vectors) + len(untrusted_vectors)
        if total == 0:
            priors = [0.5, 0.5]
        else:
            priors = [len(untrusted_vectors) / total, len(credible_vectors) / total]

    if stats_mode == "manual" and isinstance(profile.get("mean"), dict) and isinstance(profile.get("var"), dict):
        mean_untrusted = profile["mean"].get("0") or [0.5] * feature_len
        mean_credible = profile["mean"].get("1") or [0.5] * feature_len
        var_untrusted = profile["var"].get("0") or [max(min_variance, 0.05)] * feature_len
        var_credible = profile["var"].get("1") or [max(min_variance, 0.05)] * feature_len
    else:
        mean_untrusted, var_untrusted = _calc_mean_var(untrusted_vectors, feature_len, min_variance)
        mean_credible, var_credible = _calc_mean_var(credible_vectors, feature_len, min_variance)

    return priors, mean_untrusted, var_untrusted, mean_credible, var_credible


def _gaussian_logpdf(x: float, mean: float, var: float) -> float:
    return -0.5 * (math.log(2 * math.pi * var) + ((x - mean) ** 2) / var)


def predict_proba(features: List[float], profile: Dict[str, Any]) -> Tuple[float, List[float]]:
    priors, mean0, var0, mean1, var1 = _prepare_stats(profile)
    logp0 = math.log(max(priors[0], 1e-12))
    logp1 = math.log(max(priors[1], 1e-12))
    for idx, value in enumerate(features):
        logp0 += _gaussian_logpdf(value, mean0[idx], var0[idx])
        logp1 += _gaussian_logpdf(value, mean1[idx], var1[idx])
    m = max(logp0, logp1)
    p0 = math.exp(logp0 - m)
    p1 = math.exp(logp1 - m)
    p_credible = p1 / (p0 + p1)
    return p_credible, [logp0, logp1]


def build_bayes_precalc(final_record: Dict[str, Any], profile_name: str) -> Optional[Dict[str, Any]]:
    profile = _load_bayes_profile(profile_name)
    if not profile:
        return None

    features, feature_display, feature_used, missing_rules, missing_features = extract_features(final_record, profile)
    if features is None:
        return {
            "version": profile.get("version", profile_name),
            "profile": profile_name,
            "status": "missing_rules",
            "missing_rules": missing_rules,
            "missing_features": missing_features,
            "features": feature_display,
            "features_used": feature_used,
            "notes": "Bayes评分规则缺失，无法完成先验预计算。"
        }
    p_credible, logps = predict_proba(features, profile)

    feature_names = profile.get("feature_names") or list(feature_used.keys())
    # 使用单特征 log-likelihood 差异做简易贡献度
    priors, mean0, var0, mean1, var1 = _prepare_stats(profile)
    contributions = []
    for idx, name in enumerate(feature_names):
        value = features[idx]
        diff = _gaussian_logpdf(value, mean1[idx], var1[idx]) - _gaussian_logpdf(value, mean0[idx], var0[idx])
        contributions.append((name, abs(diff)))
    contributions.sort(key=lambda x: x[1], reverse=True)
    top_features = [name for name, _ in contributions[:3]]

    return {
        "version": profile.get("version", profile_name),
        "profile": profile_name,
        "p_bayes": round(float(p_credible), 4),
        "features": feature_display,
        "features_used": feature_used,
        "top_features": top_features,
        "missing_rules": missing_rules,
        "missing_features": missing_features,
        "notes": "Bayes先验由样本自动估计（priors/mean/var），不参与AI证据评分。"
    }

"""
Bayes 参数管理 API

v1.0.0: 集成反馈闭环系统
- 用户反馈 API
- 样本管理
- 特征提取
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import re

# v1.0.0: 存储层和反馈模块集成
from src.web.auth import get_current_user, is_multi_user_mode
from src.logging_config import get_logger
from src.user_file_store import list_scoped_files, resolve_virtual_task_file

router = APIRouter(prefix="/api/system/bayes", tags=["bayes"])
logger = get_logger(__name__, service="web")
VALID_FEEDBACK_TYPES = {"trusted", "untrusted"}


class BayesConfigUpdate(BaseModel):
    """贝叶斯配置更新模型"""
    version: str = 'bayes_v1'
    recommendation_fusion: dict
    feature_names: list = []
    bayes_feature_rules: dict = {}
    _samples: dict = {}


class FeedbackRequest(BaseModel):
    """用户反馈请求模型"""
    result_id: str
    feedback_type: str  # 'trusted' 或 'untrusted'
    product_data: Dict[str, Any] = {}
    keyword: Optional[str] = None
    profile_version: Optional[str] = None


class BatchFeedbackRequest(BaseModel):
    """批量反馈请求模型"""
    feedbacks: List[FeedbackRequest]
    keyword: Optional[str] = None


def _get_owner_id(request: Request = None) -> Optional[str]:
    """获取当前用户ID，用于数据隔离"""
    if not is_multi_user_mode():
        return None
    if request:
        user = get_current_user(request)
        if user:
            return user.get('user_id')
    return None


def _require_feedback_owner_id(request: Request) -> Optional[str]:
    """反馈接口统一校验用户上下文，避免多用户模式下匿名写入"""
    owner_id = _get_owner_id(request)
    if is_multi_user_mode() and not owner_id:
        raise HTTPException(status_code=401, detail="未登录或用户上下文失效")
    return owner_id


def _require_config_owner_id(request: Request) -> Optional[str]:
    """配置接口在多用户模式下必须具备用户上下文。"""
    owner_id = _get_owner_id(request)
    if is_multi_user_mode() and not owner_id:
        raise HTTPException(status_code=401, detail="未登录或用户上下文失效")
    return owner_id


def _normalize_profile_version(version: str) -> str:
    """标准化并校验 Bayes 版本号。"""
    text = str(version or "bayes_v1").strip()
    if text.endswith(".json"):
        text = text[:-5]
    if not text:
        text = "bayes_v1"
    if not re.fullmatch(r"[0-9A-Za-z._-]+", text):
        raise HTTPException(status_code=400, detail="无效的版本名称")
    return text


def _merge_runtime_feedback_samples(
    config: Dict[str, Any],
    version: str,
    owner_id: Optional[str]
) -> None:
    """
    多用户模式下，将数据库中的用户反馈样本合并到返回配置中。

    说明：
    - 页面样本管理当前依赖 config._samples 展示数量；
    - 反馈打标在 PostgreSQL 模式写入 bayes_samples 表；
    - 此处在读取配置时做只读合并，避免“打标成功但样本数不变”。
    """
    if not is_multi_user_mode() or not owner_id:
        return

    try:
        from src.storage import get_storage

        storage = get_storage()
        user_samples = storage.get_bayes_samples(
            profile_version=version,
            owner_id=owner_id,
            include_system=False
        )
        if not user_samples:
            return

        if not isinstance(config.get("_samples"), dict):
            config["_samples"] = {}
        if not isinstance(config["_samples"].get("可信"), list):
            config["_samples"]["可信"] = []
        if not isinstance(config["_samples"].get("不可信"), list):
            config["_samples"]["不可信"] = []

        trusted_bucket = config["_samples"]["可信"]
        untrusted_bucket = config["_samples"]["不可信"]

        existing_ids = set()
        existing_item_ids = set()
        for sample in trusted_bucket + untrusted_bucket:
            sample_id = str(sample.get("id") or "").strip()
            item_id = str(sample.get("item_id") or "").strip()
            if sample_id:
                existing_ids.add(sample_id)
            if item_id:
                existing_item_ids.add(item_id)

        for sample in user_samples:
            sample_id = str(sample.get("id") or "").strip()
            item_id = str(sample.get("item_id") or "").strip()

            if sample_id and sample_id in existing_ids:
                continue
            if item_id and item_id in existing_item_ids:
                continue

            label = 1 if int(sample.get("label", 0)) == 1 else 0
            normalized = {
                "id": sample_id or item_id or "",
                "name": sample.get("name") or "用户反馈样本",
                "vector": sample.get("vector") if isinstance(sample.get("vector"), list) else [],
                "label": label,
                "source": sample.get("source") or "user",
                "item_id": item_id or None,
                "note": sample.get("note") or "",
                "timestamp": sample.get("created_at") or sample.get("timestamp") or ""
            }

            if label == 1:
                trusted_bucket.append(normalized)
            else:
                untrusted_bucket.append(normalized)

            if normalized["id"]:
                existing_ids.add(normalized["id"])
            if normalized["item_id"]:
                existing_item_ids.add(normalized["item_id"])

    except Exception as e:
        logger.warning(
            "合并运行期反馈样本失败，将回退为文件样本展示",
            extra={"event": "bayes_runtime_samples_merge_failed", "version": version, "owner_id": owner_id},
            exc_info=e
        )


@router.get('/config')
async def get_bayes_config(request: Request, version: str = 'bayes_v1'):
    """获取贝叶斯配置"""
    owner_id = _require_config_owner_id(request)
    normalized_version = _normalize_profile_version(version)
    config_file = resolve_virtual_task_file(
        f"prompts/bayes/{normalized_version}.json",
        owner_id=owner_id,
        for_write=False
    )

    if not config_file.exists():
        raise HTTPException(status_code=404, detail=f'Config file {normalized_version} not found')
    
    try:
        with open(str(config_file), 'r', encoding='utf-8') as f:
            config = json.load(f)

        _merge_runtime_feedback_samples(config=config, version=normalized_version, owner_id=owner_id)
        
        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put('/config')
async def save_bayes_config(request: Request, data: dict):
    """保存贝叶斯配置"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail='No data provided')
        
        version = _normalize_profile_version(data.get('version', 'bayes_v1'))
        owner_id = _require_config_owner_id(request)
        
        # 验证配置
        errors = validate_bayes_config(data)
        if errors:
            raise HTTPException(status_code=400, detail={'errors': errors})
        
        # 保存文件
        config_file = resolve_virtual_task_file(
            f"prompts/bayes/{version}.json",
            owner_id=owner_id,
            for_write=True
        )
        
        # 备份原文件
        if config_file.exists():
            backup_file = config_file.with_suffix(f"{config_file.suffix}.backup")
            with open(str(config_file), 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(str(backup_file), 'w', encoding='utf-8') as f:
                f.write(backup_data)
        
        # 保存新文件
        with open(str(config_file), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {'success': True, 'message': '配置保存成功'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete('/config')
async def delete_bayes_config(request: Request, version: str = 'bayes_v1'):
    """删除贝叶斯配置"""
    normalized_version = _normalize_profile_version(version)
    owner_id = _require_config_owner_id(request)
    if owner_id:
        config_file = resolve_virtual_task_file(
            f"prompts/bayes/{normalized_version}.json",
            owner_id=owner_id,
            for_write=True
        )
    else:
        config_file = resolve_virtual_task_file(
            f"prompts/bayes/{normalized_version}.json",
            owner_id=None,
            for_write=False
        )

    if not config_file.exists():
        raise HTTPException(status_code=404, detail=f'Config file {normalized_version} not found')

    if owner_id is None:
        versions = list_scoped_files("bayes", owner_id=None, include_shared=True)
        if len(versions) <= 1:
            raise HTTPException(status_code=400, detail='至少保留一个 Bayes 配置版本')

    try:
        os.remove(str(config_file))
        return {'success': True, 'message': '配置删除成功'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/config/validate')
async def validate_config_endpoint(data: dict):
    """验证配置"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail='No data provided')
        
        errors = validate_bayes_config(data)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    except HTTPException:
        raise
    except Exception as e:
        return {'valid': False, 'errors': [str(e)]}


@router.get('/versions')
async def get_versions(request: Request):
    """获取所有可用的贝叶斯配置版本"""
    try:
        owner_id = _require_config_owner_id(request)
        files = list_scoped_files("bayes", owner_id=owner_id, include_shared=True)
        versions = sorted({str(name).replace(".json", "") for name in files if str(name).endswith(".json")})
        return {'versions': versions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# v1.0.0: 反馈闭环 API
# ============================================================

@router.post('/feedback')
async def submit_feedback(request: Request, data: FeedbackRequest):
    """
    提交用户反馈
    
    将商品标记为可信/不可信，提取特征并加入训练样本
    """
    try:
        from src.feedback import get_sample_manager

        feedback_type = str(data.feedback_type or "").strip().lower()
        if feedback_type not in VALID_FEEDBACK_TYPES:
            raise HTTPException(status_code=400, detail="feedback_type 必须为 trusted 或 untrusted")

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)
        
        result = sample_manager.add_feedback(
            result_id=data.result_id,
            feedback_type=feedback_type,
            product_data=data.product_data,
            keyword=data.keyword,
            profile_version=data.profile_version
        )
        
        if result:
            return {
                'success': True,
                'message': f'反馈已提交: {feedback_type}',
                'feedback_id': result.get('id')
            }
        else:
            raise HTTPException(status_code=500, detail='反馈保存失败')
    except HTTPException:
        raise
    except ImportError:
        # 反馈模块未安装
        raise HTTPException(status_code=501, detail='反馈模块未启用')
    except Exception as e:
        logger.error(
            "提交反馈失败",
            extra={"event": "bayes_feedback_submit_failed", "result_id": data.result_id},
            exc_info=e
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete('/feedback')
async def cancel_feedback(request: Request, result_id: str):
    """
    取消用户反馈

    撤销该商品的反馈标记，同时清除关联贝叶斯样本
    """
    try:
        from src.feedback import get_sample_manager

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)

        success = sample_manager.cancel_feedback(result_id=result_id)

        if success:
            return {
                'success': True,
                'message': '反馈已取消'
            }
        else:
            raise HTTPException(status_code=404, detail='未找到对应反馈记录')
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail='反馈模块未启用')
    except Exception as e:
        logger.error(
            "取消反馈失败",
            extra={"event": "bayes_feedback_cancel_failed", "result_id": result_id},
            exc_info=e
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/feedback/batch')
async def submit_batch_feedback(request: Request, data: BatchFeedbackRequest):
    """
    批量提交用户反馈
    """
    try:
        from src.feedback import get_sample_manager

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)

        feedbacks = [
            {
                'result_id': f.result_id,
                'feedback_type': str(f.feedback_type or "").strip().lower(),
                'product_data': f.product_data,
                'profile_version': f.profile_version
            }
            for f in data.feedbacks
        ]

        invalid_feedbacks = [
            idx + 1 for idx, item in enumerate(feedbacks)
            if item['feedback_type'] not in VALID_FEEDBACK_TYPES
        ]
        if invalid_feedbacks:
            raise HTTPException(
                status_code=400,
                detail=f"第 {invalid_feedbacks[0]} 条反馈的 feedback_type 非法，仅支持 trusted/untrusted"
            )
        
        stats = sample_manager.batch_add_feedback(feedbacks, keyword=data.keyword)
        
        return {
            'success': True,
            'message': f'批量反馈完成',
            'stats': stats
        }
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail='反馈模块未启用')
    except Exception as e:
        logger.error(
            "批量提交反馈失败",
            extra={"event": "bayes_feedback_batch_submit_failed", "count": len(data.feedbacks or [])},
            exc_info=e
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/samples/stats')
async def get_sample_stats(request: Request):
    """
    获取样本统计信息
    """
    try:
        from src.feedback import get_sample_manager

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)
        
        stats = sample_manager.get_sample_stats()
        return stats
    except ImportError:
        return {
            'total': 0,
            'trusted': 0,
            'untrusted': 0,
            'user_samples': 0,
            'preset_samples': 0
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete('/samples/user')
async def clear_user_samples(request: Request):
    """
    清空当前用户的所有反馈样本
    """
    try:
        from src.feedback import get_sample_manager

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)
        
        count = sample_manager.clear_user_samples()
        
        return {
            'success': True,
            'message': f'已清空 {count} 个样本',
            'deleted_count': count
        }
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail='反馈模块未启用')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/samples/reset')
async def reset_to_preset(request: Request):
    """
    重置为系统预置样本
    """
    try:
        from src.feedback import get_sample_manager

        owner_id = _require_feedback_owner_id(request)
        sample_manager = get_sample_manager(owner_id)
        
        result = sample_manager.reset_to_preset()
        
        return {
            'success': True,
            'message': '已重置为系统预置样本',
            **result
        }
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail='反馈模块未启用')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def validate_bayes_config(config):
    """验证贝叶斯配置的有效性"""
    errors = []
    
    try:
        fusion = config.get('recommendation_fusion', {})
        
        # 验证融合权重（有图片）
        weights = fusion.get('weights', {})
        weight_sum = sum([
            weights.get('bayesian', 0),
            weights.get('visual', 0),
            weights.get('ai', 0)
        ])
        if abs(weight_sum - 1.0) > 0.001:
            errors.append(f'有图片权重和必须为1.0，当前为{weight_sum:.3f}')
        
        # 验证融合权重（无图片）
        weights_no_visual = fusion.get('weights_no_visual', {})
        weight_sum_nv = sum([
            weights_no_visual.get('bayesian', 0),
            weights_no_visual.get('visual', 0),
            weights_no_visual.get('ai', 0)
        ])
        if abs(weight_sum_nv - 1.0) > 0.001:
            errors.append(f'无图片权重和必须为1.0，当前为{weight_sum_nv:.3f}')
        
        # 验证贝叶斯特征权重
        bayes_features = fusion.get('bayesian_features', {})
        feature_keys = ['seller_tenure', 'positive_rate', 'seller_credit_level', 
                        'sales_ratio', 'used_years', 'freshness', 'has_guarantee']
        feature_sum = sum([bayes_features.get(k, 0) for k in feature_keys])
        if abs(feature_sum - 1.0) > 0.001:
            errors.append(f'贝叶斯特征权重和必须为1.0，当前为{feature_sum:.3f}')
        
        # 验证视觉AI特征权重
        visual_features = fusion.get('visual_features', {})
        visual_keys = ['image_quality', 'condition', 'authenticity', 'completeness']
        visual_sum = sum([visual_features.get(k, 0) for k in visual_keys])
        if abs(visual_sum - 1.0) > 0.001:
            errors.append(f'视觉AI特征权重和必须为1.0，当前为{visual_sum:.3f}')
        
        # 验证分数范围
        all_keys = feature_keys + visual_keys
        for key in all_keys:
            if key in bayes_features:
                value = bayes_features[key]
                if not (0.0 <= value <= 1.0):
                    errors.append(f'{key} 权重必须在0.0-1.0之间，当前为{value}')
            if key in visual_features:
                value = visual_features[key]
                if not (0.0 <= value <= 1.0):
                    errors.append(f'{key} 权重必须在0.0-1.0之间，当前为{value}')
    
    except Exception as e:
        errors.append(f'验证过程出错: {str(e)}')
    
    return errors


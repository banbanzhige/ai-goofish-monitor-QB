"""
Bayes 参数管理 API
提供配置的获取、保存和验证接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os

router = APIRouter(prefix="/api/system/bayes", tags=["bayes"])

class BayesConfigUpdate(BaseModel):
    """贝叶斯配置更新模型"""
    version: str = 'bayes_v1'
    recommendation_fusion: dict
    feature_names: list = []
    bayes_feature_rules: dict = {}
    _samples: dict = {}

@router.get('/config')
async def get_bayes_config(version: str = 'bayes_v1'):
    """获取贝叶斯配置"""
    config_file = f'prompts/bayes/{version}.json'
    
    if not os.path.exists(config_file):
        raise HTTPException(status_code=404, detail=f'Config file {version} not found')
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 使用JSONResponse确保所有字段都被序列化
        from fastapi.responses import JSONResponse
        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put('/config')
async def save_bayes_config(data: dict):
    """保存贝叶斯配置"""
    try:
        if not data:
            raise HTTPException(status_code=400, detail='No data provided')
        
        version = data.get('version', 'bayes_v1')
        
        # 验证配置
        errors = validate_bayes_config(data)
        if errors:
            raise HTTPException(status_code=400, detail={'errors': errors})
        
        # 保存文件
        config_file = f'prompts/bayes/{version}.json'
        
        # 备份原文件
        if os.path.exists(config_file):
            backup_file = f'{config_file}.backup'
            with open(config_file, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(backup_data)
        
        # 保存新文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {'success': True, 'message': '配置保存成功'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/config')
async def delete_bayes_config(version: str = 'bayes_v1'):
    """删除贝叶斯配置"""
    if '/' in version or '..' in version:
        raise HTTPException(status_code=400, detail='无效的版本名称')

    bayes_dir = 'prompts/bayes'
    config_file = f'{bayes_dir}/{version}.json'

    if not os.path.exists(config_file):
        raise HTTPException(status_code=404, detail=f'Config file {version} not found')

    if os.path.exists(bayes_dir):
        versions = [
            file for file in os.listdir(bayes_dir)
            if file.endswith('.json') and not file.endswith('.backup')
        ]
        if len(versions) <= 1:
            raise HTTPException(status_code=400, detail='至少保留一个 Bayes 配置版本')

    try:
        os.remove(config_file)
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
async def get_versions():
    """获取所有可用的贝叶斯配置版本"""
    try:
        bayes_dir = 'prompts/bayes'
        if not os.path.exists(bayes_dir):
            return {'versions': []}
        
        versions = []
        for file in os.listdir(bayes_dir):
            if file.endswith('.json') and not file.endswith('.backup'):
                version_name = file.replace('.json', '')
                versions.append(version_name)
        
        return {'versions': versions}
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

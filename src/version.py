#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本信息文件
"""

VERSION = "V0.9.0"

VERSION_HISTORY = [
    {
        "version": "V0.9.0",
        "date": "2026-01-01",
        "changes": [
            "元旦快乐",
            "添加了自动获取cookie登录按钮，优化了login.py的登录逻辑",
            "在搜索结果添加了手动搜索，并且能高光显示搜索匹配内容",
            "优化了管理界面的UI视觉效果，现在更好看了",
            "添加了版本号，与docker版本号接轨",
            "优化了start_web_server.bat的字体颜色和添加了版本号，引导更清晰了",
            "优化了微信群机器人等渠道通知逻辑：如果选择了发送手机连接则微信群机器人不发送电脑端链接",
            "商品卡如果没有抓取刀图片则选择默认logo",     
            "卖家名字过长的分行到第二行，避免挤压到发送通知",            
            "修改了scraper.py和ai_handler.py里的冗余通知代码，通知全部转移到专用的notifier里"                
        ]
    }
]

# 获取当前版本
def get_current_version():
    """获取当前版本号"""
    return VERSION

# 获取当前版本信息
def get_current_version_info():
    """获取当前版本的详细信息"""
    for version_info in VERSION_HISTORY:
        if version_info["version"] == VERSION:
            return version_info
    return None

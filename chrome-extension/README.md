# 咸鱼登录态提取 Chrome 插件

这个 Chrome 插件用于提取 Goofish（咸鱼）页面的完整登录态信息，包括：`cookies + 浏览器环境 + 请求头 + storage 快照`。

## 安装方式

1. 打开 Chrome，进入 `chrome://extensions`
2. 打开右上角的**开发者模式**
3. 点击**加载已解压的扩展程序**，选择 `chrome-extension` 目录
4. 确认插件已出现在工具栏

## 使用步骤

1. 打开 [https://www.goofish.com](https://www.goofish.com) 并确认已登录
2. 打开插件弹窗
3. 点击 **1) 采集完整快照**
4. 点击 **2) 复制账号文件 JSON（推荐）**
5. 将复制出的 JSON 保存为 `state/你的账号.json`（例如 `state/my_account.json`）

## 输出类型

- 账号文件 JSON（推荐）
  - 包含字段：`display_name`、`created_at`、`cookies`、`env`、`headers`、`page`、`storage`
  - 与自动登录生成的账号文件结构兼容
- 原始快照 JSON
  - 直接输出当前标签页提取结果

## 图标说明

- 插件图标使用：`images/logo/favicon 32x32.png`

## 备注

- 插件通过 `chrome.cookies` 读取并包含 HttpOnly cookies。
- 如果后端导入流程只存 `cookies`，也建议直接保存完整 JSON 到 `state/*.json`，便于保留完整快照字段。

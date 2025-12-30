# 咸鱼智能监控机器人
基于 Playwright 和 AI 的闲鱼多任务实时监控工具机器人，提供完整的 Web 管理界面，调用ai帮助用户过滤商品链接，自动个性化挑选商品，支持多种通知方式即时触达。
基于原仓库地址代码：https://github.com/Usagi-org/ai-goofish-monitor 大量修改优化代码与操作逻辑调整到更舒适的使用体验风格。

新手和ai agent合作的练习作品，希望多多指教
## 核心功能

- **Web管理界面**：提供直观的Web UI，方便配置和管理
- **定时商品监控**：定时监控咸鱼平台上的商品信息与新上
- **高度可定制**: 每个监控任务均可配置独立的关键词、价格范围、个性需求，筛选条件和AI分析指令 (Prompt)。
- **AI智能分析**：利用AI自动分析商品信息，结合商品图文和卖家画像进行深度分析，精准筛选符合条件的商品，并且给出个性化建议
- **多种通知方式**：企业微信群机器人、企业微信应用通知、支持Ntfy、Gotify、Bark、Telegram等多种通知渠道
- **多任务管理**：支持配置多个监控任务，每个任务可以设置不同的关键词、价格范围等、支持并发运行
- **灵活的调度**：支持定时任务配置，可自定义监控频率
- **Docker 一键部署**: 提供 `docker-compose` 配置，实现开箱即用

# 新特性
<details>
<summary>📋任务管理界面：优化了整体ui排版，拆分了运行逻辑，增加了更多的任务状态指示与操作，减少了任务阻塞。现在可以复制任务，详细定制每条任务的ai筛选标准了</summary>

![任务管理1.png](Example/任务管理1.png)
![任务管理2.png](Example/任务管理2.png)
![任务管理3.png](Example/任务管理3.png)
</details>
<details>
<summary>🎯结果查看界面：添加了更多结果可选筛选项，添加了手动发送通知到通知渠道，现在可以更详细的管理所有商品结果了</summary>

![结果查看1.png](Example/结果查看1.png)
![结果查看2.png](Example/结果查看2.png)
![结果查看3.png](Example/结果查看3.png)

</details>

<details>
<summary>📊运行日志界面：添加了更多结果可选筛选项，添加了手动发送通知到通知渠道，现在可以更详细的管理所有商品结果了</summary>

![运行日志.png](Example/运行日志.png)
![运行日志2.png](Example/运行日志2.png)

</details>

<details>
<summary>📱通知配置界面：拆分优化了通知模块，把通知配置界面也单独拎到导航栏，添加在通知中手机版5H链接，方便在通信软件如微信中直接打开移动版咸鱼，并且添加了企业微信应用渠道支持，添加了测试通知</summary>

![通知配置.png](Example/通知配置.png)
![通知配置2.png](Example/通知配置2.png)
![企业微信群机器人2.jpg](Example/企业微信群机器人2.jpg)
![企业微信应用渠道2.jpg](Example/企业微信应用渠道2.jpg)


</details>


<details>
<summary>🖥️系统设置界面：优化了.env与系统同步逻辑，web里添加了更多可选的环境设置，并且双向保存同步了，对docker用户更加友好。现在可以直接在系统管理里管理Prompt实现了核心ai标准的增删改查工作，能更方便配置自定义个性化ai需求了。</summary>

![系统设置1.png](Example/系统设置1.png)
![系统设置2.png](Example/系统设置2.png)

</details>

# 截图展示
<div style="text-align: center; margin: 20px 0;">
  <img src="Example/任务管理1.png" 
       style="width: 100%; max-width: 1200px; height: auto; 
              border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); 
              border: 4px solid #fff; background: #f9f9f9;" 
       alt="新任务管理界面">
  <p style="font-size: 0.9em; color: #666; margin-top: 8px;">
    新任务管理界面
  </p>
</div>

<div style="text-align: center; margin: 20px 0;">
  <img src="Example/结果查看1.png" 
       style="width: 100%; max-width: 1200px; height: auto; 
              border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); 
              border: 4px solid #fff; background: #f9f9f9;" 
       alt="新任务管理界面">
  <p style="font-size: 0.9em; color: #666; margin-top: 8px;">
    新结果管理界面
  </p>
</div>


# 快速部署

## 🐳Docker部署（推荐）

使用 Docker 可以将应用及其所有依赖项打包到一个标准化的单元中，实现快速、可靠和一致的部署。

docker项目地址
  - https://hub.docker.com/r/banbanzhige/ai-goofish-monitor-qb
  

**使用docker compose开箱即用**:

    ```yaml:
    services:
    app:
    image: banbanzhige/ai-goofish-monitor-qb:latest
    container_name: ai-goofish-monitor-qb
    pull_policy: always
    ports:
        - "8001:8000"
    volumes:
    #  - ./.env:/app/.env (一般情况下不需要，如果你想单独管理可以挂载）
        - ./logs:/app/logs
        - ./jsonl:/app/jsonl
        - ./images:/app/images
        - ./criteria:/app/criteria
        - ./requirement:/app/requirement
    restart: unless-stopped
    ```


## windows部署

### 0.拉取项目代码
    ```bash
    git clone https://github.com/banbanzhige/ai-goofish-monitor-QB.git
    cd banbanzhige/ai-goofish-monitor-QB
    ```
### 方式1：
    直接使用start_web_server.bat启动 (推荐)

### 方式2：
### 1. 安装依赖

    ```bash
    docker push banbanzhige/ai-goofish-monitor-qb:tagname
    ```
### 2. 配置环境变量

- 1，直接编辑.env文件：
- 2，或者在web界面中系统设置中直接配置环境变量（推荐）

### 3. 启动Web管理界面与后端代码

```bash
python web_server.py
```


# 快速开始

### 1. 打开Web管理界面
部署完成后
在浏览器中访问：http://localhost:8000

- 默认登录用户名：**admin**
- 默认登录密码：**admin123**

### 2. 登录咸鱼账号

方式一：在线获取Chrome插件获取登录信息

-    1.在您的个人电脑上，使用Chrome浏览器安装[闲鱼登录状态提取扩展](https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa)
-    2.打开并登录闲鱼官网
-    3.登录成功后，点击浏览器工具栏中的扩展图标
-    4.点击"提取登录状态"按钮获取登录信息
-    5.点击"复制到剪贴板"按钮
-    6.将复制的内容粘贴到Web UI中保存即可


<details>
<summary>方式二：本地安装Chrome插件获取登录信息</summary>

-    1. 打开Chrome浏览器
-    2. 访问chrome://extensions/
-    3. 开启"开发者模式"
-    4. 点击"加载已解压的扩展程序"
-    5. 选择chrome-extension/目录
</details>


<details>
<summary>方式三：运行登录脚本，生成登录状态文件：</summary>


    ```bash
    python login.py
    ```

    根据提示完成登录操作，登录状态将保存到xianyu_state.json文件中。
</details>


### 3. 配置系统配置
  默认配置存储在工作路径下的`.env`文件内，可以直接配置，前后端保存同步
  #### AI模型配置 
  - API Key *：你的AI模型服务商提供的API Key
  - API Base URL *：AI模型的API接口地址，必须兼容OpenAI格式
  - 模型名称 *：你要使用的具体模型名称，必须支持图片分析（推荐doubao-seed模型）

  #### Prompt 管理
  - 使用默认即可，熟悉相关的知识可以根据模板自行新建编辑，不推荐直接改动模板

  #### 通用配置
  - 保持默认即可，可以根据模型调整需求，默认配置满足大部分模型和场景
  - **发送URL格式图片：如果模型允许尽量开启这个，能节省大理IO资源，节省大量模型api运算消耗token，未勾选时使用base64编码格式发送图片，相比直接发送URL可能增加的token消耗多300%或以上。**
  #### 服务器端口
  - 默认即可
  #### Web服务用户名

- 默认登录用户名：**admin**
- 默认登录密码：**admin123**

### 4. 配置通知
- 按web指提交引渠道的配置URL或密钥保存即可，这部分设置也保存在`.env`内
### 5. 配置监控任务

在Web界面中：
-这部分设置保存在`config.json`中
1. 点击"任务管理"
2. 点击"创建新任务"
3. 填写任务信息：
   - 任务名称
   - 关键词
   - 价格范围
   - 监控频率（Cron表达式）
   - 核心需求等
4. 保存任务

### 6.生成ai运行标准

- AI标准-点击生成-等待生成完成（可多任务并发请求）

### 7. 运行监控任务

- 可以手动启动任务
- 或等待定时任务自动执行


### Cron表达式

Cron表达式用于配置任务的执行频率，格式：

```
分 时 日 月 周
```

示例：
- `*/30 * * * *`：每30分钟执行一次
- `0 9 * * *`：每天上午9点执行一次
- `0 18 * * 1-5`：每周一至周五下午6点执行一次
- `0 0 */2 * *`:每两小时执行一次

## 通知配置

支持以下通知渠道：

1. **Ntfy**
2. **Gotify**
3. **Bark**
4. **企业微信机器人**
5. **企业微信应用**
6. **Telegram**
7. **Webhook**

可以根据Web界面的"系统设置"中提供的示例配置通知渠道

## 日志管理

日志文件存储在logs/目录下：
- scraper.log：爬虫日志
- web_server.log：Web服务器日志

可以在Web界面中查看和清空日志。

## 结果查看

监控结果以JSONL格式存储在jsonl/目录下，每个文件对应一个任务的结果。

在Web界面的"结果管理"中可以查看和下载结果文件。


## 技术架构
### 后端技术栈
<details>

<summary>点击展开后端技术栈</summary>

- **Python 3.9+**：主要开发语言
- **FastAPI**：Web服务器框架，提供RESTful API
- **Playwright**：浏览器自动化工具，用于商品数据采集
- **APScheduler**：任务调度器，用于定时任务
- **Uvicorn**：ASGI服务器，用于运行FastAPI应用
- **OpenAI API**：AI智能分析功能
- **Pydantic**：数据验证和序列化

</details>

### 前端技术栈
<details>

<summary>点击展开前端技术栈</summary>

- **HTML5/CSS3/JavaScript**：基础前端技术
- **jQuery**：JavaScript库
- **Bootstrap**：UI框架
</details>


### 核心组件

<details>

<summary>点击展开核心组件</summary>

1. **登录模块 (login.py)**：处理咸鱼账号登录，生成登录状态文件（可选，大部分情况下浏览器插件即可满足）
2. **爬虫模块 (spider_v2.py)**：执行商品监控任务，采集商品数据
3. **Web服务器 (web_server.py)**：提供Web管理界面和API
4. **AI分析模块 (src/ai_handler.py)**：利用AI分析商品信息
5. **通知模块 (src/notifier/)**：处理各种通知渠道
6. **配置模块 (src/config.py)**：管理系统配置
7. **任务管理模块 (src/task.py)**：处理任务的增删改查
8. **文件操作模块 (src/file_operator.py)**：处理文件的读写操作

</details>

## 项目结构

<details>

<summary>点击展开项目结构</summary>

```
.
├── ai-goofish-monitor-QB-0.8.8/
│   ├── .env                      # 环境变量配置文件
│   ├── config.json               # 任务配置文件
│   ├── Dockerfile                # Docker配置文件
│   ├── login.py                  # 登录模块（可选）
│   ├── prompt_generator.py       # AI Prompt生成工具
│   ├── requirements.txt          # 项目依赖
│   ├── spider_v2.py              # 爬虫模块
│   ├── web_server.py             # Web服务器
│   ├── chrome-extension/         # Chrome扩展（可选）
│   ├── logo/                     # 项目Logo
│   ├── prompts/                  # AI Prompt模板
│   │   └── base_prompt.txt       # 基础Prompt模板
│   ├── src/                      # 核心源代码
│   │   ├── __init__.py
│   │   ├── ai_handler.py         # AI分析模块
│   │   ├── config.py             # 配置模块
│   │   ├── file_operator.py      # 文件操作模块
│   │   ├── parsers.py            # 解析器模块
│   │   ├── prompt_utils.py       # Prompt工具
│   │   ├── scraper.py            # 爬虫核心
│   │   ├── task.py               # 任务管理
│   │   ├── utils.py              # 工具函数
│   │   └── notifier/             # 通知模块
│   ├── static/                   # 静态文件
│   ├── templates/                # HTML模板
│   ├── requirement/              # 用户需求文件
│   ├── criteria/                 # AI分析标准
│   ├── logs/                     # 日志文件
│   ├── jsonl/                    # 结果存储
│   └── xianyu_state.json         # 登录状态文件（自动生成）
```
</details>

### 项目依赖


<details>

<summary>点击展开项目依赖</summary>

```
aiofiles==22.1.0
apscheduler==3.10.4
fastapi==0.100.0
openai==0.27.8
playwright==1.37.0
pydantic==2.1.1
python-dotenv==1.0.0
uvicorn==0.23.2
```
</details>

## 许可证

MIT License

## 致谢

<details>

<summary>点击展开致谢</summary>

本项目在开发过程中参考了以下优秀项目，特此感谢：

- [Usagi-org/ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor)

以及感谢 doubao-seed-code/qwen3-code 等国产模型/工具给新手小白的我提供了便宜便捷且有用的编成助力

</details>

## ⚠️ 注意事项

<details>

<summary>点击注意事项</summary>

- 本项目 90%+ 的代码都由AI生成，包括项目原型以及后续中 ISSUE 中涉及的 PR 。
- 请遵守闲鱼的用户协议和robots.txt规则，不要进行过于频繁的请求，以免对服务器造成负担或导致账号被限制。
- 本项目仅供学习和技术研究使用，请勿用于非法用途。
- 本项目采用 [MIT 许可证](LICENSE) 发布，按"现状"提供，不提供任何形式的担保。
- 项目作者及贡献者不对因使用本软件而导致的任何直接、间接、附带或特殊的损害或损失承担责任。
- 如需了解更多详细信息，请查看 [免责声明](DISCLAIMER.md) 文件。

</details>

## 体会

<details>
<summary>点击体会</summary>

- 现阶段由于ai上下文的限制，ai只能提供部分代码的解决方案，无法全局架构，导致项目会逐渐变成一个缝合怪，最后可能会演变成多个ai编译成的屎山代码，让项目重构和再编译十分棘手
- 真正有价值的能力不是会用某个框架，而是理解底层原理，做出正确的技术判断

</details>
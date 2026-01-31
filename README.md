<a href="https://github.com/banbanzhige/ai-goofish-monitor-QB" title="ai-goofish-monitor-QB">
  <img src="/images/logo/banner.png" alt="ai-goofish-monitor-QB Banner" width="100%">
</a>


# 咸鱼AI智能推荐机器人
基于 Playwright 和 AI 的朴素贝叶斯模型+AI人群画像判断+AI视觉判断加权推荐的闲鱼智能推荐机器人，提供完整的 Web 管理界面，调用ai帮助用户过滤商品链接，自动个性化挑选商品，支持多种通知方式即时触达。

脱胎于：[Usagi-org/ai-goofish-monitor](https://github.com/Usagi-org/ai-goofish-monitor) 大量修改优化代码与操作逻辑添加了朴素贝叶斯网模型与ai多模态视觉模型评分与人群画像评分，支持微调评分参数与长期迭代置信模型样本，且调整到更舒适的UI与使用体验。
- 本项目仅供学习和技术研究使用，请勿用于非法用途。
- 请遵守闲鱼的用户协议和robots.txt规则，不要进行过于频繁的请求，以免对服务器造成负担或导致账号被限制。




## ✨ 核心功能

- **Web管理界面**：提供直观清晰的Web UI，方便配置和管理，多端UI配适，支持PC端，移动端，pad端多端登录管理
- **定时商品监控**：定时监控咸鱼平台上的商品信息与新上，支持验货宝 / 验号担保 / 包邮 / 新发布时间 / 区域等筛选逻辑
- **高度可定制**: 每个监控任务均可配置独立的关键词、价格范围、个性需求，筛选条件和AI分析指令 (Prompt)。
- **AI评分体系**：有完善评分标准利用AI自动分析商品信息，结合商品图文和卖家画像进行深度分析，精准筛选符合条件的商品，在推荐分数计分板ai推荐显示逻辑更透明。
- **贝叶斯模型评分体系**综合卖家注册时长，卖家好评率，卖家信用等级，销售比例，商品使用年限，发布新鲜度，担保服务八个维度参数进行模型先验计算，与ai评分体系加权推荐。
- **多种通知方式**：企业微信群机器人、企业微信应用通知、钉钉机器人、支持Ntfy、Gotify、Bark、Telegram等多种通知渠道
- **多任务管理**：支持配置多个监控任务，每个任务可以设置不同的关键词、价格范围等、支持并发运行
- **多账号管理**：支持多咸鱼账号管理界面，支持任务绑定账号，风控自动切换账号保证任务续航
- **灵活的调度**：支持定时任务配置，可自定义监控频率
- **Docker 一键部署**: 提供 `docker-compose` 配置，实现开箱即用


# 📸 界面展示
<div align="center" style="margin: 2em 0;">
  <img src="images/Example/0.9.8/任务管理.png" 
       style="width: 100%; max-width: 1200px; height: auto; border-radius: 8px;" 
       alt="新任务管理界面">
  <p style="font-size: 0.9em; color: #555; margin-top: 0.5em;">
    新任务管理界面
  </p>
</div>


| 结果管理界面 | AI评分界面 |
|:---:|:---:|
| ![结果管理界面](images/Example/0.9.9/结果查看01.png) | ![AI打分界面](images/Example/0.9.9/结果查看02.png) |








<details open>
<summary>移动端界面展示</summary>

| 账号管理-移动端 | 任务管理-移动端 | 结果查看-移动端 |定时任务-移动端 |
|:---:|:---:|:---:|:---:|
| ![账号管理-移动端效果](images/Example/0.9.8/账号管理-移动端.jpg) | ![任务管理-移动端效果](images/Example/0.9.8/任务管理-移动端.jpg) | ![结果查看-移动端效果](images/Example/0.9.9/结果查看-移动端.jpg) |![定时任务-移动端效果](images/Example/0.9.8/定时任务-移动端.jpg) |

</details>




</div>

<details>
<summary>其他界面展示</summary>

| 账号管理界面 | 定时任务界面 |
|:---:|:---:|
| ![账号管理界面](images/Example/0.9.8/账号管理.png) | ![定时任务界面](images/Example/0.9.8/定时任务.png) |

![贝叶斯模型管理界面](images/Example/0.9.9/贝叶斯模型管理.png)
</details>



# token消耗

<details>

<summary>1.token消耗优化</summary>

本项目对ai调用api的token使用进行过优化，如果模型条件允许推荐开启`发送URL格式图片`将大大降低token使用情况
![发送URL格式图片](/images/Example/0.9.5/启用发送URL格式图片.png)
![优化后](/images/Example/0.9.5/优化后token使用量.png)

</details>

<details>

<summary>2.token消耗预期</summary>

截止2026年1月6日，在启用`发送URL格式图片`后这是优化使用豆包1.8模型20个产品分析token使用量情况
![20个产品分析使用量](/images/Example/0.9.5/优化后20个产品分析token使用情况.png)
![豆包1.8定价](/images/Example/0.9.5/doubao1.8模型定价测算.png)
根据测算可得出20个产品分析预估模型调用费用约0.2元人民币，成本消耗控制十分可观


</details>

# 🆕 新特性
**近期更新：**

[上限设置与判断](#如何判断你的ai-API默认输出token上限是否足够)


<details open>
<summary>v0.9.9 更新日志 - 2026-01-31</summary>

  <ul>
    <li><strong>添加了解锁API输出token上限功能</strong>：本次更新后AI分析能力增强，需拓展输出token字段，大部分模型支持比默认更高的输出字段设置，详情见[上限设置与判断](#如何判断你的ai-api默认输出token上限是否足够)</li>
    <li><strong>推荐策略重构升级</strong>：重构了AI推荐模型，现使用朴素贝叶斯网模型先验+AI视觉模型判断+AI综合融合加权评分，已实现完整的评分体系和推荐分数</li>
    <li><strong>添加了代理设置tab</strong>：对模型和渠道单独设置了代理开关</li>
    <li><strong>多模态功能强化升级</strong>：强化启用多模态模型的AI视觉功能，在推荐和评分中发挥重要作用</li>
    <li><strong>更新了base_prompt</strong>：适配0.9.9版本的推荐模型和工作流</li>
    <li><strong>新添bayes管理tab</strong>：可更细致定制筛选和推荐模型</li>
    <li><strong>优化了cookie容易失效情况</strong>：优化cookie易失效问题，新增cookie回填功能</li>
    <li><strong>修复了其他一些已知问题</strong></li>
  </ul>

</details>

<details>
<summary>v0.9.8 更新日志 - 2026-01-25</summary>

  <ul>
    <li><strong>高级筛选功能焕新</strong>：将高级筛选功能悬浮框升级为胶囊标签开关，新增验货宝、验号担保、超赞鱼小铺等 6 项筛选项；优化区域三级联动、发布时间选项，隐藏冗余标签文案，压缩面板高度</li>
    <li><strong>移动端交互全面适配</strong>：新增移动端卡片式管理布局，任务 / 账号 / 定时任务列表支持触控长按拖拽排序，配套占位线、动画反馈及滚动锁定机制；，优化操作按钮、风险标签排版；调整导航栏、表头字号与安全边距，避免界面重叠。</li>
    <li><strong>系统功能补全与体验修复</strong>：新增结果数据批量删除、过期账号批量清理接口；AI 配置页合并测试按钮，系统 / 通知配置页改为横向 Tab 分组</li>
    <li><strong>前后端逻辑贯通</strong>：新增筛选字段同步至任务模型与爬虫逻辑，确保前端筛选配置可精准落地；旧任务自动补充默认值，保障版本兼容无感知升级。</li>


</details>

<details>
<summary>v0.9.7 更新日志 - 2026-01-18</summary>

  <ul>
    <li><strong>任务管理界面优化改版</strong>：整合了操作按钮，优化了最小边距，各个列表下添加可编辑容器，点击即可直接修改参数，给web界面多端配适打底</li>
    <li><strong>新增多账号管理系统</strong>：支持添加、编辑、删除多个咸鱼账号，支持从当前登录状态一键导入。</li>
    <li><strong>新增加定时任务界面</strong>：对定时任务掌控更加全面与精确，可立刻执行或跳过一轮任务
    <li><strong>任务绑定账号</strong>：任务创建时支持选择使用的账号，支持风控时自动切换账号功能。</li>
    <li><strong>自定义登录页面</strong>：替代浏览器Basic Auth弹窗，登录认证改用签名Cookie Session方案，支持7天免登录。</li>
    <li><strong>账号状态管理</strong>：新增Cookie有效性检测、复制账号、定期自动检测状态（每5分钟）。</li>
    <li><strong>新增钉钉机器人通知</strong>：支持加签验证和ActionCard图文卡片格式。</li>
    <li><strong>运行日志优化</strong>：默认限制100条避免内存消耗，支持选择展示条数(100/200/500/1000)。迁移了部分cmd的系统通知到运行日志内</li>
    <li><strong>任务编辑优化</strong>：新增AI标准Tab切换、参考文件模板选择和预览。</li>
    <li><strong>多项Bug修复</strong>：修复模态框可见性、账号创建、AI标准生成、表单回车刷新等问题，优化系统稳定性。</li>

</details>


<details>
<summary>v0.9.6 更新日志 - 2026-01-16</summary>

  <ul>
    <li><strong>新增定时任务管理界面</strong>：添加了独立的定时任务执行列表，支持查看任务执行顺序、计算并显示下次执行时间。</li>
    <li><strong>Cron 表达式在线编辑</strong>：支持直接在列表中修改 Cron 表达式，并在修改后自动同步更新到任务配置。</li>
    <li><strong>更灵活的任务控制</strong>：新增了跳过本次任务、立即执行任务、取消任务（保留配置但关闭启用）的操作功能。</li>
    <li><strong>重构项目架构</strong>：将 web_server.py 拆分为 main.py, auth.py, scheduler.py 等 9 个独立模块，大幅提升代码可维护性。</li>
    <li><strong>统一配置与规范管理</strong>：统一了配置管理逻辑，新增了项目规范文档，规范了代码结构。</li>
    <li><strong>功能增强与修复</strong>：
      <ul>
        <li>整合系统日志到控制台输出，方便调试查看。</li>
        <li>添加了任务开始和结束的通知推送，增加了统计计数。</li>
        <li>修复了启用按钮开关报错、创建表达式未载入任务等 bug。</li>
        <li>升级了新闲鱼登录状态提取器，支持捕获更完整的浏览器环境信息。</li>
      </ul>
    </li>
  </ul>
</details>


<details>
<summary>v0.9.5更新日志-2026-01-04</summary>

  <ul>
    <li>修改了项目中部分具有争议词汇替换为中性、合规的表述，详见<a href="archive/争议词汇修改落地实施文档.md">争议词汇修改文档.md</a></li>
    <li>修复了任务运行中，通知没有检查通知渠道是否开启通知的问题，现在自动通知发送前会检查渠道是否开启通知，任务过程中关闭或开启通知渠道都能正确的通知了</li>
    <li>修复了自动触发发送的企业微信群机器人图文消息会出现标题，价格时间等文案信息不对的情况</li>
    <li>添加了完成任务后会推送一条通知消息到通知渠道</li>
    <li>修复了没有手动任务在结束任务后没有更新任务状态的bug，这个bug会导致任务面板上看到的任务一直是在执行中，但是后台任务已经其实结束了</li>
    <li>添加了测试任务完成通知按钮</li>
    <li>现在通知配置和系统设置的Switch开关都能自动保存设置了</li>
    <li>优化了筛选框的文字显示去除了没必要的后缀提高了可读性</li>
    <li>优化了单独删除卡片时会删除错误的卡片的问题</li>
  </ul>
</details>



<details>


<summary>v0.9.2更新日志-2026-01-02</summary>
  <ul>
    <li>优化了通知模板尽量满足图文通知需求</li>
    <li>添加数据筛滤机制，解决部分情况下前端按钮卡死问题</li>
    <li>对自动登录程序添加追踪与限制，避免重复触发占用资源</li>
    <li>优化修改了部分文案</li>
    <li>添加了渠道通知开关</li>
  </ul>

  <p></p> 

  <img src="images/Example/0.9.2/Telegram通知渠道0101.jpg" alt="Telegram通知渠道">
  <img src="images/Example/0.9.2/微信群机器人通知渠道0101.jpg" alt="微信群机器人通知渠道">
  <img src="images/Example/0.9.2/删除与更新凭证.png" alt="删除与更新凭证">
</details>


<details>
<summary>v0.9.0更新日志-2026-01-01</summary>
  <ul>
    <li>元旦快乐</li>
    <li>添加了自动获取cookie登录按钮，优化了login.py的登录逻辑</li>
    <li>在搜索结果添加了手动搜索，并且能高光显示搜索匹配内容</li>
    <li>优化了管理界面的UI视觉效果，现在更好看了</li>
    <li>添加了版本号，与docker版本号接轨</li>
    <li>优化了start_web_server.bat的字体颜色和添加了版本号，引导更清晰了</li>
    <li>优化了微信群机器人等渠道通知逻辑：如果选择了发送手机链接则微信群机器人不发送电脑端链接</li>
    <li>商品卡如果没有抓取到图片则选择默认logo</li>
    <li>卖家名字过长的分行到第二行，避免挤压到发送通知</li>
    <li>修改了scraper.py和ai_handler.py里的冗余通知代码，通知全部转移到专用的notifier里</li>
  </ul>

  <p></p> <!-- 加一个空行，让列表和图片之间有间隔 -->

  <img src="images/Example/0.9.0/删除与更新凭证.png" alt="删除与更新凭证">
  <img src="images/Example/0.9.0/手动筛选.png" alt="手动筛选">
  <img src="images/Example/0.9.0/删除与更新凭证.png" alt="删除与更新凭证">
</details>

**归档日志**

我针对了原版goofish代码做出了一些优化，对我个人而言使用上更加顺畅，逻辑上更加清晰
<details>
<details>
<summary>📋任务管理界面：优化了整体ui排版，拆分了运行逻辑，增加了更多的任务状态指示与操作，减少了任务阻塞。现在可以复制任务，详细定制每条任务的ai筛选标准了</summary>

![任务管理1.png](images/Example/old/任务管理1.png)
![任务管理2.png](images/Example/old/任务管理2.png)
![任务管理3.png](images/Example/old/任务管理3.png)
</details>
<details>
<summary>🎯结果查看界面：添加了更多结果可选筛选项，添加了手动发送通知到通知渠道，现在可以更详细的管理所有商品结果了</summary>

![结果查看1.png](images/Example/old/结果查看1.png)
![结果查看2.png](images/Example/old/结果查看2.png)
![结果查看3.png](images/Example/old/结果查看3.png)

</details>

<details>
<summary>📊运行日志界面：添加了更多结果可选筛选项，添加了手动发送通知到通知渠道，现在可以更详细的管理所有商品结果了</summary>

![运行日志.png](images/Example/old/运行日志.png)
![运行日志2.png](images/Example/old/运行日志2.png)

</details>

<details>
<summary>📱通知配置界面：拆分优化了通知模块，把通知配置界面也单独拎到导航栏，添加在通知中手机版5H链接，方便在通信软件如微信中直接打开移动版咸鱼，并且添加了企业微信应用渠道支持，添加了测试通知</summary>

![通知配置.png](images/Example/old/通知配置.png)
![通知配置2.png](images/Example/old/通知配置2.png)
![企业微信群机器人2.jpg](images/Example/old/企业微信群机器人2.jpg)
![企业微信应用渠道2.jpg](images/Example/old/企业微信应用渠道2.jpg)


</details>


<details>
<summary>🖥️系统设置界面：优化了.env与系统同步逻辑，web里添加了更多可选的环境设置，并且双向保存同步了，对docker用户更加友好。现在可以直接在系统管理里管理Prompt实现了核心ai标准的增删改查工作，能更方便配置自定义个性化ai需求了。</summary>

![系统设置1.png](images/Example/old/系统设置1.png)
![系统设置2.png](images/Example/old/系统设置2.png)

</details>

</details>


## 🚀核心流程

-  **自然语言定制推荐**：每个任务都可以单独给 ai 分析配备独立的判断逻辑和分析思路，可以单独制定一条纯自然语言的推荐逻辑，可以通过编辑`prompt`列本来定制。**例如**：从卖家曾经的评论和出售的商品**判断**是否是二手贩子还是个人卖家，我要个人卖家的推荐
-  **多线程**：下图描述了单个监控任务从启动到完成的核心处理逻辑。在实际使用中，`web_server.py` 会作为主服务，根据用户操作或定时调度来启动一个或多个这样的任务进程。

<div style="width: 450px; margin: 0 auto;">

```mermaid

graph TD
    %% 1. 定义节点和形状，提高可读性
    A([开始]) --> B["搜索商品"]
    B --> C{"发现新商品?"}

    %% 2. 调整流程分支，避免线条交叉
    subgraph "处理新商品"
        direction LR
        C -- 是 --> D["抓取商品详情和卖家信息"]
        D --> E["下载商品图片或获取URL"]
        E --> F["调用AI分析"]
        F --> G{"AI是否推荐?"}
    end

    %% 3. 处理决策结果
    G -- 是 --> H["发送通知"]
    H --> I["保存记录到JSONL"]
    G -- 否 --> I

    %% 4. 处理“否”的分支和循环
    C -- 否 --> J["翻页/等待"]
    
    %% 5. 所有流程最终都汇总到这里，再开始下一轮循环
    I --> B
    J --> B
    %% 6.风控逻辑
    B --> L{触发风控/异常?};
    L -- 是 --> M[账号轮换并重试];
    M --> B;

```

</div>



**多维度**：ai会根据`collector.py`获取回来的数据进行分类分析，再加上定制化需求判断后得出推荐/不推荐结论，最后所有数据存储入jsonl里，并且条件满足就会触发通知渠道。

<div style="width: 1000px; margin: 0 auto;">

```mermaid
mindmap
  root((<b>推荐模型</b>))
    <b>贝叶斯模型处理用户评分40%</b>
      卖家人群画像分析
        交易时间维度
          <b>依据</b>：交易记录横跨数年，间隔期长
            <b>结论</b>：符合个人卖家特征
        售卖行为维度
          <b>依据</b>：商品品类多元，无批量同类型商品
            <b>结论</b>：售卖个人闲置
        购买行为维度
          <b>依据</b>：购买记录为个人闲置物品，无进货迹象
            <b>结论</b>：佐证个人消费属性
        行为逻辑总结
          <b>依据</b>：行为逻辑链完整，售卖个人闲置
            <b>结论</b>：个人卖家身份可信度高
        卖家信用资质评估
          <b>信用等级：</b>极好
          <b>合规情况：</b>无违规记录
          <b>近期差评：</b>近期无差评
          <b>卖家好评率：</b>好评比例        
       其他分析维度
    <b>ai视觉模型处理产品评分35%</b>
      商品本身分析
        <b>图片质量</b>
          <b>图片清晰度和拍摄质量</b>        
        <b>商品成色</b>
          <b>商品成色 全新/9成新/8成新等</b>      
        <b>功图片真实性</b>
          <b>商品成色 图片真实性 实拍/PS/网图</b>           
        <b>图片完整性</b>       
          <b>商品成色 图片完整性 数量是否充足</b>   
       其他分析维度          
    <b>AI置信度分析25%</b>
      证据链
        官方凭证
        实物证据
        第三方证明
        文字描述
        关键维度需**≥2个独立证据源**相互印证

      用户定制化需求
        <b>身份鉴别：</b>二手贩子/个人卖家/其他
        <b>性别标签：</b>男性/女性
        <b>职业属性：</b>学生/白领/其他
       其他分析维度
    <b>总结</b>
      首要结论：<font color="#ffffffff">个人卖家，可信度高</font>
```

</div>



**多模型**：

<div style="width: 500px; margin: 0 auto;">

```mermaid
graph TD
    A[商品数据] --> B[AI分析]
    B --> C{recommendation_scorer.py}
    
    C --> D1[贝叶斯用户评分<br/>7个特征×权重]
    C --> D2[视觉AI产品评分<br/>4个维度×权重]
    C --> D3[AI分析置信度<br/>confidence_score]
    
    D1 --> E[加权融合算法]
    D2 --> E
    D3 --> E
    
    E --> F[风险标签惩罚]
    F --> G[最终推荐度<br/>0-100分]
    
    G --> H1[前端商品卡]
    G --> H2[通知推送]
    G --> H3[数据存储]
```


</div>


# 🚀 快速部署

## 🐳Docker部署（推荐）

使用 Docker 可以将应用及其所有依赖项打包到一个标准化的单元中，实现快速、可靠和一致的部署。

docker项目地址
  - https://hub.docker.com/r/banbanzhige/ai-goofish-monitor-qb
  

**方式一：使用docker compose开箱即用**:

  - 提前下载`.env.example`并改名成`.env`放在`/工作文件夹根目录`下或者手动填入`.env.example`内的参数到你自己创建的`.env`文件内
  - 提前在`/工作文件夹根目录/config/`内创建空的`config.json`文件，以持久化管理你的监控任务
  - 在0.9.9版本后更新了`prompts`文件夹，所有挂载`prompts`的旧用户<b>必须</b>重新拉取一份`prompts`文件夹内所有的文件到你挂载的文件夹内，不然会导致bayes模型失效导致推荐不合理,如果有需要微调模型参数且持久化可以挂载`prompts`文件夹。

docker compose:
  - 支持 amd64架构和arm64架构
```yaml
services:
 app:
   image: banbanzhige/ai-goofish-monitor-qb:latest
   container_name: ai-goofish-monitor-qb
   pull_policy: always
   ports:
     - "8001:8000"
   volumes:
     - ./.env:/app/.env
     - ./config/config.json:/app/config.json
     - ./logs:/app/logs
     - ./jsonl:/app/jsonl
     - ./criteria:/app/criteria
     - ./requirement:/app/requirement
   # - ./prompts:/app/prompts 
   # - ./state:/app/state 
   restart: unless-stopped
```

**方式二**:  
备用链接：支持 amd64架构和arm64架构
```
docker pull ghcr.io/banbanzhige/ai-goofish-monitor-qb:latest
```

## 💻 Windows部署

### 环境准备




- python 3.10+
- Node.js + npm


### 方式一：1.使用start_web_server.bat启动(推荐)

   #### 拉取项目代码


  方式1：直接点击code→[download ZIP](https://github.com/banbanzhige/ai-goofish-monitor-QB/archive/refs/heads/master.zip)下载


  - 解压后双击打开`start_web_server.bat`启动

  方式2：git拉取
  ```PowerShell
  git clone https://github.com/banbanzhige/ai-goofish-monitor-QB.git
  cd banbanzhige/ai-goofish-monitor-QB
  ```

 -  双击打开`start_web_server.bat`启动

  ![start_web_server启动样式](images/Example/0.9.7/启动样式.png)

  - `start_web_server.bat`会自行创建虚拟环境，安装依赖，检测端口，并且自行启动`web_server.py`

### 方式二：用PowerShell终端打开


   - 拉取项目代码


  - 方式1：直接点击code-[download ZIP](https://github.com/banbanzhige/ai-goofish-monitor-QB/archive/refs/heads/master.zip)下载

  - 方式2：git拉取
  ```PowerShell
  git clone https://github.com/banbanzhige/ai-goofish-monitor-QB.git
  cd banbanzhige/ai-goofish-monitor-QB
  ```


```PowerShell
# 1. 获取PowerShell执行权限（首次执行即可，后续跳过）
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 4. 安装requirements.txt中的依赖
pip install -r requirements.txt
# . 启动主程序
python web_server.py
```






# 📋 快速开始
你需要提前准备的内容：
| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | AI 模型 API Key | 是 |
| `OPENAI_BASE_URL` | API 接口地址（兼容 OpenAI 格式） | 是 |
| `OPENAI_MODEL_NAME` | 多模态模型名称（如 `gpt-4o``doubao-seed-1-8-251228`） | 是 |
| `tokens上限字段名` | 多模态模型的token输出上限字段（如 豆包：`max_completion_tokens`，openAI：`max_tokens`） | 是 |
| `tokens上限` | `0.9.9`更新后ai分析能力增强，必须要拓展输出token字段大部分模型都支持比默认跟高的输出字段，推荐10000起 | 是 |
| `闲鱼账号` | 需要手机扫码或者[Chrome插件](https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa)获取登录 | 是 |
| `通知渠道token` | 企业微信机器人，Telegram，钉钉等 | 否|

### 1. 打开Web管理界面
部署完成后
在浏览器中访问：http://localhost:8000( `.env`里可以修改你的端口号)

- 默认登录用户名：**admin**
- 默认登录密码：**admin123**

### 2. 获取咸鱼账号
<details open>
<summary>方式一：在WEB管理界面右上角使用自动登录（推荐）</summary>
  <ul>
  <li><strong>**注意：docker用户可能无法使用此功能，建议使用方法二获取**</strong></li>
  <li>  1.程序自动打开咸鱼首页</li>
  <li>  2.在咸鱼首页扫码登录</li>
  <li>  3.登录完成后会自动刷新获取cookie，请不要手动关闭网页</li>
  <li>  4.获取登录信息完成后网页会自动关->登录成功->填写好账号名称即可</li>
 <img src="images/Example/0.9.7/自动获取账号.png" alt="自动登录按钮">
</details>


<details open>
<summary>方式二：在线获取Chrome插件获取登录信息</summary>

-    1.在您的个人电脑上，使用Chrome浏览器安装[闲鱼登录状态提取扩展](https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa)
-    2.打开并登录闲鱼官网
-    3.登录成功后，点击浏览器工具栏中的扩展图标
-    4.点击"提取登录状态"按钮获取登录信息
-    5.点击"复制到剪贴板"按钮
-    6.将复制的内容粘贴到Web UI中并填好账号名称保存即可


</details>

<details>
<summary>方式三：本地安装Chrome插件获取登录信息</summary>

-    1.打开Chrome浏览器
-    2.访问chrome://extensions/
-    3.开启"开发者模式"
-    4.点击"加载已解压的扩展程序"
-    5.选择chrome-extension/目录
-    6.重复方式二步骤
</details>




### 3. 配置系统配置
  推荐进入WEB界面直接填写保存配置
  默认配置存储在工作路径下的`.env`文件内，可以直接配置，前后端保存同步
  #### AI模型配置 
  - API Key ：你的AI模型服务商提供的API Key
  - API Base URL ：AI模型的API接口地址，必须兼容OpenAI格式
  - 模型名称 ：你要使用的具体模型名称，必须支持图片分析（推荐doubao-seed模型）
  - tokens上限字段名 ：多模态模型的token输出上限字段（如 豆包：`max_completion_tokens`，openAI：`max_tokens`）
| - tokens上限：`0.9.9`更新后ai分析能力增强，必须要拓展输出token字段大部分模型都支持比默认跟高的输出字段，推荐10000起

  #### 如何判断你的ai API默认输出token上限是否足够
  使用默认的`base_prompt`生成一次ai标准，然后检查ai标准最低下的文案，如果存在时间戳则表示完整的ai标准输出完成，反之亦然
| 被截断的ai标准 | 完整的ai标准 |
|:---:|:---:|
| ![被截断的ai标准](images/Example/0.9.9/截断.png) | ![完整的ai标准](images/Example/0.9.9/完整.png) |



  #### Prompt 管理
  - 使用默认即可，熟悉相关的知识可以根据模板自行新建编辑，不推荐直接改动模板

 ### bayes配置

  - 待补充



  #### 通用配置
  - 保持默认即可，可以根据模型调整需求，默认配置满足大部分模型和场景

  #### 服务器端口
  - 默认即可
  #### Web服务用户名

- 默认登录用户名：**admin**
- 默认登录密码：**admin123**

### 4. 配置通知
- 按web指提交引渠道的配置URL或密钥保存即可，这部分设置也保存在`.env`内
### 5. 配置监控任务

在Web界面中：
-这部分设置会自动生成并保存在`config.json`中
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

- AI标准-点击生成-等待生成完成（可多任务多线程请求）

### 7. 运行监控任务

- 可以手动启动任务
- 或等待定时任务自动执行


### ⏰ Cron表达式

Cron表达式用于配置任务的执行频率，格式：

```
分 时 日 月 周
```

示例：
- `*/30 * * * *`：每30分钟执行一次
- `0 9 * * *`：每天上午9点执行一次
- `0 18 * * 1-5`：每周一至周五下午6点执行一次
- `0 0 */2 * *`:每两小时执行一次

## 🔔 通知配置

支持以下通知渠道：

1. **Ntfy**
2. **Gotify**
3. **Bark**
4. **企业微信机器人**
5. **企业微信应用**
6. **Telegram**
7. **钉钉机器人**
8. **Webhook**

可以根据Web界面的"系统设置"中提供的示例配置通知渠道

## 📝 日志管理

日志文件存储在logs/目录下：
- scraper.log：Web服务器日志
- 日期_随机编号.log：产品信息发送ai请求文件

可以在Web界面中查看和清空日志。

## 📊 结果查看

监控结果以JSONL格式存储在jsonl/目录下，每个文件对应一个任务的结果。

在Web界面的"结果管理"中可以查看和下载结果文件。


## 🏗️ 技术架构
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
2. **服务启动入口 (web_server.py)**：启动FastAPI服务与任务调度
3. **任务执行入口 (collector.py)**：加载任务配置与Prompt，驱动单次或批量监控流程
4. **采集与解析模块 (src/scraper.py / src/parsers.py)**：商品抓取、字段解析与清洗
5. **AI分析与推荐评分 (src/ai_handler.py / src/bayes.py / src/recommendation_scorer.py)**：AI判定与贝叶斯/融合推荐度计算
6. **Web服务器核心 (src/web/)**：提供Web管理界面与API，包含以下模块：
   - **main.py**：FastAPI应用入口
   - **auth.py**：认证模块（Cookie Session方案）
   - **scheduler.py**：定时任务调度器
   - **task_manager.py**：任务管理接口
   - **log_manager.py**：日志管理
   - **result_manager.py**：结果管理
   - **settings_manager.py**：设置管理
   - **notification_manager.py**：通知管理
   - **ai_manager.py**：AI管理接口
   - **account_manager.py**：账号管理接口
   - **bayes_api.py**：贝叶斯配置接口
   - **models.py**：数据模型
7. **通知模块 (src/notifier/)**：处理各种通知渠道（企业微信、钉钉、Telegram等）
8. **配置模块 (src/config.py)**：统一管理系统配置与环境读取
9. **任务模型与调度 (src/task.py / src/web/scheduler.py)**：任务结构定义与调度执行
10. **规则与Prompt资源 (criteria/ / requirement/ / prompts/)**：AI标准与Prompt模板管理
11. **工具与文件操作 (src/utils.py / src/file_operator.py / src/prompt_utils.py)**：通用工具与文件读写
12. **版本管理模块 (src/version.py)**：管理项目版本信息

</details>

## 📁 项目结构

<details>

<summary>点击展开项目结构</summary>

```
.
├── ai-goofish-monitor-QB/
│   ├── .env                      # 环境变量配置文件
│   ├── .env.example              # 环境变量配置示例文件
│   ├── config.json               # 任务配置文件
│   ├── Dockerfile                # Docker配置文件
│   ├── docker-compose.yaml       # Docker Compose配置
│   ├── .dockerignore             # Docker忽略文件配置
│   ├── login.py                  # 登录模块
│   ├── prompt_generator.py       # AI Prompt生成工具
│   ├── requirements.txt          # 项目依赖
│   ├── collector.py              # 任务执行入口
│   ├── web_server.py             # Web服务器入口
│   ├── check_env.py              # 环境检查脚本
│   ├── start_web_server.bat      # Windows一键启动脚本
│   ├── README.md                 # 项目说明文档
│   ├── License                   # 许可证文件
│   ├── DISCLAIMER.md             # 免责声明
│   ├── gitattributes             # Git属性配置
│   ├── .gitignore                # Git忽略文件配置
│   ├── chrome-extension/         # Chrome扩展
│   ├── images/                   # 项目图片资源
│   │   ├── Example/              # 示例截图
│   │   └── logo/                 # Logo与Banner
│   ├── prompts/                  # AI Prompt与Bayes配置
│   │   ├── base_prompt.txt
│   │   ├── bayes/
│   │   │   └── bayes_v1.json
│   │   └── guide/
│   │       ├── bayes_guide.md
│   │       └── weight_framework_guide.md
│   ├── src/                      # 核心源代码
│   │   ├── __init__.py
│   │   ├── ai_handler.py         # AI分析模块
│   │   ├── bayes.py              # 贝叶斯模型
│   │   ├── config.py             # 配置模块（统一配置管理）
│   │   ├── file_operator.py      # 文件操作模块
│   │   ├── parsers.py            # 解析器模块
│   │   ├── prompt_utils.py       # Prompt工具
│   │   ├── recommendation_scorer.py # 推荐度评分
│   │   ├── scraper.py            # 数据收集核心
│   │   ├── task.py               # 任务管理
│   │   ├── utils.py              # 工具函数
│   │   ├── version.py            # 版本信息
│   │   ├── notifier/             # 通知模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # 通知基类
│   │   │   ├── channels.py       # 通知渠道实现
│   │   │   └── config.py         # 通知配置
│   │   └── web/                  # Web服务器核心模块（重构后）
│   │       ├── main.py           # FastAPI应用入口
│   │       ├── auth.py           # 认证模块
│   │       ├── scheduler.py      # 定时任务调度器
│   │       ├── task_manager.py   # 任务管理接口
│   │       ├── log_manager.py    # 日志管理
│   │       ├── result_manager.py # 结果管理
│   │       ├── settings_manager.py # 设置管理
│   │       ├── notification_manager.py # 通知管理
│   │       ├── ai_manager.py     # AI管理接口
│   │       ├── account_manager.py # 账号管理接口
│   │       ├── bayes_api.py      # 贝叶斯配置接口
│   │       └── models.py         # 数据模型
│   ├── static/                   # 静态文件
│   │   ├── css/                  # 样式文件
│   │   │   ├── style.css
│   │   │   └── bayes_visual.css
│   │   ├── js/                   # JavaScript文件
│   │   │   ├── main.js
│   │   │   ├── bayes_init.js
│   │   │   ├── score_modal.js
│   │   │   └── modules/          # 前端模块拆分
│   │   │       ├── api.js
│   │   │       ├── app_interactions.js
│   │   │       ├── app_state.js
│   │   │       ├── accounts_view.js
│   │   │       ├── bayes_visual_manager.js
│   │   │       ├── logs_view.js
│   │   │       ├── navigation.js
│   │   │       ├── notifications_view.js
│   │   │       ├── region.js
│   │   │       ├── render.js
│   │   │       ├── reorder.js
│   │   │       ├── results_view.js
│   │   │       ├── settings_view.js
│   │   │       ├── tasks_editor.js
│   │   │       ├── templates.js
│   │   │       └── ui_shell.js
│   │   └── china/                # 省市区数据
│   │       └── index.json
│   ├── templates/                # HTML模板
│   │   ├── index.html
│   │   └── login.html
│   ├── requirement/              # 用户需求文件
│   ├── criteria/                 # AI分析标准
│   ├── logs/                     # 日志文件
│   ├── jsonl/                    # 结果存储
│   ├── state/                    # 状态文件存储
│   ├── task_stats/               # 任务统计信息
│   ├── archive/                  # 归档文件
│   └── venv/                     # Python虚拟环境（可选）
```
</details>

### 📦 项目依赖


<details>

<summary>点击展开项目依赖</summary>

```
uvicorn
fastapi
pydantic
python-dotenv
aiofiles
apscheduler
openai
httpx
beautifulsoup4
lxml
requests
selenium
webdriver-manager
python-telegram-bot
playwright
jinja2
python-multipart
```
</details>

## 📄 许可证

MIT License

## 🙏 致谢

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
- 本项目采用 [MIT 许可证](License) 发布，按"现状"提供，不提供任何形式的担保。
- 项目作者及贡献者不对因使用本软件而导致的任何直接、间接、附带或特殊的损害或损失承担责任。
- 如需了解更多详细信息，请查看 [免责声明](DISCLAIMER.md) 文件。

</details>

## 💡 体会

<details>
<summary>点击体会</summary>

- 现阶段由于ai上下文的限制，ai只能提供部分代码的解决方案，无法全局架构，导致项目会逐渐变成一个缝合怪，最后可能会演变成多个ai编译成的屎山代码，让项目重构和再编译十分棘手
- 真正有价值的能力不是会用某个框架，而是理解底层原理，做出正确的技术判断

</details>

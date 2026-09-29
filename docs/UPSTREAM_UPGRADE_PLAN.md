# 父项目升级吸收与实施基线

版本：0.7；建立日期：2026-09-28。状态：B1、B2 已按各自范围验收；B3/U05 的源码、隔离真实 Web/数据库与便携包启动验收通过，用户人工 UI 验收及交互优化待后续进行。便携与服务器正式实例均未迁移，公开发行仍需 B7 放行；实际进度与部署差异见第 8 节。

## 1. 授权、目标与使用方式

用户在父项目调研后提出：“可以，都帮我升级一下，可以先做个方案，避免后续施工漂移”。本方案将上一轮建议转为有限范围的交付清单；初次建档只交付方案。后续用户确认价格只作事实参考、不同综合评分混用，并要求“帮我落地计划”，据此开始分批实施；不包含真实数据库迁移或公开发布。

目标：选择性吸收父项目的兼容修复、结果管理、价格洞察、生成进度、交互和 Docker 工程改进，同时保留 QB 的 PostgreSQL、多用户隔离、贝叶斯推荐、Windows 便携版和既有 Docker 路线。

“全部升级”指第 4 节全部项目达到明确结论，不指合并父项目全部提交或重做现有功能。项目可结案为“实现并通过验收”或“已有等价能力/不受影响且有测试证据”；不能用“已调研”代替交付。只有用户可以批准删减范围。

实施前先读根目录 `AGENTS.md`、`REPOSITORY_HYGIENE.md` 和本文；涉及 Launcher 时再读 `PORTABLE_LAUNCHER_PLAN.md` 及对应备份、后端、打包契约。本文不覆盖其安全边界，也不构成依赖安装、真实账号测试或外部发布的授权。

## 2. 冻结基线与依据

### 2.1 本地基线

- 本次建档 HEAD：`2d08472693040368de00b3bbac58244bd537e3b1`（2026-09-28，`feat: refine portable setup and launcher experience`）。建档前工作区干净；上一轮调研看到的未提交 Launcher 改动不再作为当前状态引用。
- 当前源码版本：`V1.1.0.0-beta`；下一发行版本不在本文预定，也不复用父项目 2.4 版本号。
- 现有 Web 为 `src/web/` 与 `static/js/modules/`，不是父项目 Vue 前端；存储接口在 `src/storage/interface.py`，有本地文件及 PostgreSQL 适配器。
- 已有结果单条/批量删除、上次所选结果文件记忆、调度下次执行时间与跳过一次执行；只补实际差距。
- `src/portable/schema.py` 当前声明 schema v1，已有库升级不能用 `create_all` 代替；`src/portable/backup_restore.py` 校验固定表集合和版本。新增持久化能力必须先解决版本迁移、权限和备份恢复的联动。
- `monitoring_results` 当前按 `(owner_id, item_id)` 唯一，不能直接当作完整的多次价格观察历史；新价格历史不得破坏此既有唯一性。

以上是源码核对结论，不表示本轮已运行其业务测试。后续 HEAD 改变时，只复核涉及模块并记录差异，不重置本方案、不覆盖其他任务工作。

### 2.2 上游参考快照

父项目：<https://github.com/Usagi-org/ai-goofish-monitor>。2026-09-28 调研参考为 master `f85d140b6b`（2026-05-18），最新 Release 为 [2.4](https://github.com/Usagi-org/ai-goofish-monitor/releases/tag/2.4)（2026-04-27）。不是以浮动 master 自动同步。

| 参考 | 用途 |
| --- | --- |
| [AI 参数回退 #395](https://github.com/Usagi-org/ai-goofish-monitor/pull/395)、[结构化错误 #464](https://github.com/Usagi-org/ai-goofish-monitor/pull/464)、[响应解析 #450](https://github.com/Usagi-org/ai-goofish-monitor/pull/450) | temperature / response_format 兼容、空响应回退 |
| [代理环境兼容 #463](https://github.com/Usagi-org/ai-goofish-monitor/pull/463) | NO_PROXY IPv6 CIDR 场景 |
| [Windows 路径安全 #489](https://github.com/Usagi-org/ai-goofish-monitor/pull/489) | Prompt 文件路径边界与回归样例 |
| [分页修复 c9a4e26dc3](https://github.com/Usagi-org/ai-goofish-monitor/commit/c9a4e26dc3) | 搜索响应识别、下一页定位、点击超时 |
| [商品屏蔽 #476](https://github.com/Usagi-org/ai-goofish-monitor/pull/476)、[黑名单 65fea72783](https://github.com/Usagi-org/ai-goofish-monitor/commit/65fea72783)、[正则别名 5ccb33bd37](https://github.com/Usagi-org/ai-goofish-monitor/commit/5ccb33bd37) | 非删除式屏蔽、规则与筛选记忆 |
| [价格洞察 3282926b08](https://github.com/Usagi-org/ai-goofish-monitor/commit/3282926b08) | 观察历史、趋势、参考价格与导出 |
| [任务生成接口说明](https://github.com/Usagi-org/ai-goofish-monitor#任务创建-api) | 后台 job 与进度查询；实施时固定对应源文件提交 |
| [调度 #425](https://github.com/Usagi-org/ai-goofish-monitor/pull/425)、[移动端 #447](https://github.com/Usagi-org/ai-goofish-monitor/pull/447)、[区域 #471](https://github.com/Usagi-org/ai-goofish-monitor/pull/471) | 交互与边界用例，不迁移 UI 框架 |
| [通知配置 #456](https://github.com/Usagi-org/ai-goofish-monitor/pull/456)、[渠道测试 #444](https://github.com/Usagi-org/ai-goofish-monitor/pull/444) | 陈旧配置、独立渠道校验 |
| [Docker 分层 #409](https://github.com/Usagi-org/ai-goofish-monitor/pull/409) | 依赖层复用及构建缓存 |

参考 PR 可能含无关改动。只移植符合本文契约的逻辑和测试，记录实际使用的提交、文件及必要署名；不执行整分支 merge、不直接套用上游数据库或鉴权实现。出现新的上游提交先登记为候选，不自动扩大当前批次。

## 3. 不可变边界与默认决策

1. 保留 MIT、PostgreSQL 与本地文件后端、C# / Avalonia / 自包含 .NET、首期 Windows x64 和 Docker；不新增 SQLite、Vue、跨平台桌面包或通用插件系统。
2. 不改抓取周期、页数上限、并发默认值、账号绑定/轮换、代理轮换、通知触发条件、去重语义、贝叶斯样本与推荐权重。原因：功能吸收不能悄悄改变成本、风控或推荐结果。
3. AI 兼容只在既有用户触发的调用和既有总重试预算内工作；不新增自动探测、双发、自动换模型或后台付费调用。新增会改变调用语义的兼容回退须显式配置，默认沿用原行为。
4. 商品屏蔽和黑名单只控制结果查询、当前视图统计和导出，不影响抓取、AI 调用、推送或样本训练；UI 明示此边界。隐藏不是删除。
5. 价格能力只提供事实与统计证据，首版不新增任何性价比分数，不新增 AI 估价调用、不改 Prompt 评分契约、不改变推荐排序和通知门槛、不启用降价通知。未来价格融合评分须另立版本与验证方案。
6. 所有新数据由服务端确认 owner；不能信任客户端 owner_id，不能以缺失 owner 回退全局或跨用户聚合。无 owner 的本地模式须单独明确存储空间，不与数据库多用户语义混用。
7. 不自动迁移真实数据库、不扫描或导入真实业务文件；开发验收使用合成数据和隔离实例。真实抓取、付费模型、真实通知、公开发布、推送标签或镜像另需明确授权。
8. 默认不新增依赖。确需新增或升级运行依赖时，先列用途、现有替代、版本、许可和对便携/Docker 的影响，请用户确认；不能借上次 Launcher 依赖授权扩大本次范围。
9. 文件 UTF-8 无 BOM、中文直接输出；外部 I/O 必须处理错误并脱敏记录，前端失败有可见提示和 `console.error`。普通产物继承项目 ACL；凭据保护维持独立。
10. 不启用上游日志自动清理，不扩展删除范围。本文只约束执行，不宣称自动容量、清理或升级保护已实现。

## 4. 交付范围与验收契约

### U01：AI 请求和响应兼容（增强）

入口：`src/ai_handler.py`、`src/config.py`、`src/prompt_utils.py`；核对 `src/web/ai_health.py`，但不以兼容改造放松其地址、代理和超时安全策略。

- 提取可独立测试的参数错误识别与响应解析小模块；保留当前 Chat Completions 主链，不把 Responses API 迁移作为前提。
- 仅对可确认的参数不支持错误去掉对应参数，使用剩余重试次数；401/403、余额、限流和网络超时不误判为参数问题。参数变化不得污染其他用户、模型或请求。
- `content` 非空时优先使用；为空时，只有显式启用且返回内容满足既有完整业务 schema 才允许 reasoning_content 兼容。不能以任意推理文字制造推荐，也不能把推理全文写日志。
- 保持现有 JSON 校验、失败阈值和私有配置优先级；兼容失败仍明确失败，不生成“成功”占位数据。
- 通过条件：支持/不支持参数、嵌套错误体、空 choices/content、多段文本、Markdown/多个 JSON、结构缺字段、鉴权/限流/超时、串行及并发用户隔离用例；mock 请求次数不超过原总预算，未启用时行为不变。

### U02：Windows 文件边界（核验，缺口才修）

入口：`src/web/settings_manager.py`、`src/user_file_store.py`、相关适配器。

- 已有文件名校验不回退；补绝对路径、盘符相对路径、UNC、反斜杠、编码分隔符、冒号/ADS、保留设备名和目录输入测试。
- 文件模式核验最终路径与允许根的关系、符号链接/junction 越界；数据库模式核验 Prompt 所有权。不能只证明字符串安全便声称全部文件访问安全。
- 通过条件：越界读写均拒绝且无文件/数据库副作用；合法中文文件正常；未登录、无权限、跨用户请求被拒绝；错误不泄露绝对路径或敏感内容。

### U03：抓取响应与翻页稳定性（核验并增强）

入口：`src/scraper.py`、`tests/test_scraper_request_binding.py`。

- 在现有请求头和价格响应绑定修复上，核对搜索请求方法、API 路径、页码/筛选关联；避免异步旧响应覆盖当前页。
- 改善下一页按钮可见性、禁用态和点击超时处理；异常终止原因可诊断，不能形成重复翻页或无限重试。
- 通过条件：最后一页、按钮缺失/禁用、点击超时、响应晚到、非搜索响应、排序筛选切换、重复响应与停止请求；既有抓取配置和睡眠/重试总预算不变。使用 fake 页面/响应，不触发真实平台。

### U04：增量数据契约、迁移与备份兼容（前置必要工作）

入口：`src/storage/`、`src/portable/schema.py`、`src/portable/backup_*`，仅在契约需要时联动 Launcher 维护与打包接线。

- 在增加 ORM 表之前先列出 schema v1 到目标版本的增量 DDL、索引、owner 约束、读写权限、数据布局和备份清单；文档更新后才施工。
- PostgreSQL 只做明确版本的增量迁移：识别已知旧结构、互斥、事务、版本记录、失败不前进；未知或过新结构拒绝。不得以重建库或放宽结构校验“修复”。
- 便携路径复用维护门控、实例归属和备份机制，不给普通业务账号 DDL 权限；Docker/源码由显式管理员迁移入口执行，不以 Web 启动自动升级真实库。
- 本地文件后端提供对应版本化旁文件/目录、原子写入和并发保护；不能新增接口后只实现 PostgreSQL 让本地模式运行时报错。
- 更新新安装初始化、业务结构检查、备份导出/恢复、包版本兼容声明和所需权限；旧备份先恢复到新隔离目标并验证旧版本，再显式升级，原实例保留。
- 回退默认：保留旧制品和迁移前备份，在新隔离目标恢复。不能承诺旧程序直接读取新 schema；已有新写入时先说明回退丢失窗口并取得恢复选择，不自动执行删表降级。
- 通过条件：全新安装、已知旧版本升级、重复执行、并发迁移、故障回滚、未知版本拒绝、最小权限、含新增数据的备份恢复；本地与 PG 合成数据语义一致。不修改真实实例。

### U05：结果屏蔽、黑名单、筛选记忆（新增并增强）

入口：`src/web/result_manager.py`、存储层、`static/js/modules/results_view.js`、`api.js` 和必要模型。

- 支持按商品 ID 屏蔽/恢复、显示隐藏项、黑名单规则管理和命中原因；保存筛选、排序、当前任务等偏好，按登录用户隔离。已有删除接口及确认机制保留，不用删除替代隐藏。
- 默认个人级商品屏蔽（本人所有任务可见范围内生效）；黑名单默认只作用当前任务，个人全局规则须显式选择。跨任务同商品隐藏行为必须 UI 说明。
- 规则支持普通关键词、英数字边界及正则别名。正则采用明确受限语法并限制规则数、输入长度及执行成本；不得把用户任意表达式直接交给无超时正则引擎。需要新引擎依赖时走确认流程。
- 非法/不支持规则保存时明确报错；支持预览命中样例和恢复，不把规则错误当作“零命中”。
- 分页、总数、统计和导出共享过滤契约，避免先分页再过滤导致空页/总数矛盾。缓存与浏览器偏好带用户命名空间，退出清除当前用户敏感状态。
- 通过条件：屏蔽/恢复与刷新持久化、规则修改重算、大小写/中文/型号别名、恶意正则输入有界、跨用户不可见、批量操作幂等、旧删除行为回归；对比屏蔽前后 AI/通知调用计数不变。

### U06：价格历史、统计洞察与导出（新增）

入口：抓取结果处理边界、存储层、`result_manager.py` 与现有结果页；在既有原生前端呈现，不新增图表依赖作为前提。

- 不新增独立价格导航：商品卡片显示简要变动/历史低价，现有详情弹窗显示趋势与观察记录，结果页统计区显示当前任务采样参考。

- 新增不可变价格观察记录：owner、商品 ID、稳定任务标识、运行/观察幂等标识、观察时间、货币、原始价格、标准化金额和来源；同商品不同运行可记录，单运行重复响应不重复计数。
- 从既有搜索响应已取得的价格记录观察，接线须位于“已见商品跳过 AI”之前；不新增详情请求、刷新频率或 AI 分析。若原链无法获得某次价格，显示缺测，不为曲线补抓。
- 使用十进制定点金额；面议、异常、缺失、非有限值、不同币种不强制转换成 0 混算。统一 UTC 存储、按用户当前展示时区呈现。
- 显示观察次数、首次/最近观察、最低/最高价、较上次变动、趋势及同任务同窗口的有效样本中位数；默认 30 天查询窗口不是数据保留/自动删除期限。
- 市场参考仅为“本人该任务采样参考”，去重后展示样本数；不足 5 个有效商品样本或规格/成色明显不可比时提示“参考不足”，不据此下性价比结论，不能称为全市场公允价格或真实成交价。
- 首版不创建 value_score/deal_score 等第二套评分字段，也不新增价格评分公式；历史最低价与变动均来自实际观察，不覆盖现有推荐字段。
- 旧结果默认不自动回填历史；提供显式范围预览/导入能力时保留来源标识、幂等和无可靠时间时跳过的规则，不伪造过去价格。首版无历史显示“暂无观察”。
- CSV 导出与当前用户/筛选范围一致，处理公式注入、换行引号、空数据、大量记录和取消；UTF-8 无 BOM，新增历史/统计字段不能破坏旧结果 API。
- 通过条件：跨运行价格变化、重复观察、任务改名/删除关联、跨用户隔离、缺测/异常金额、样本不足、窗口边界与时区、过滤统计一致、导出安全及迁移恢复后历史不丢失。

### U07：AI 标准生成后台 job（增强）

入口：`src/web/task_manager.py`、`src/web/ai_manager.py`、`src/prompt_utils.py`、任务编辑前端和存储层。

- 保留当前“创建任务”和“生成标准”的业务区别；不能把原来不调用 AI 的创建动作变成自动生成。只将用户现有显式生成动作移为可查询后台任务。
- 状态固定为 `queued / running / succeeded / failed / interrupted`；展示阶段与耗时，不伪造百分比。job 带 owner、任务稳定标识、输入版本、幂等键和脱敏失败原因。
- 刷新/重新登录后可查询本人 job；同任务同版本重复提交只对应一个有效 job。沿用现有生成并发约束，不引入分布式队列或提高 AI 并发。
- 成功写回前校验任务仍存在、输入版本未变化，避免晚到响应覆盖新标准；失败不覆盖旧标准、不遗留永久生成锁。
- 重启把未完成 job 标为 interrupted，用户明确重试；不自动重放可能已经计费的请求。退出/维护期间停止接收新生成，运行任务按有界退出策略结束，不能拖住 Launcher 停机。
- 新异步接口与旧同步入口兼容迁移，不直接把旧客户端期望的 task 响应改成 job；首次施工记录路由/请求/响应和弃用策略。
- 通过条件：重复提交、刷新恢复、两用户同时生成、超时/失败解锁、重启、维护停机、任务删除/输入变更、旧客户端回归；全部模型调用由 fake 代替。

### U08：调度、区域和移动端体验（增强/回归）

入口：`static/js/modules/reorder.js`、`tasks_editor.js`、`region.js`、相关 CSS 及调度只读接口。

- 复用已有下次运行时间，改善绝对时间/倒计时、时区和空状态；增加清晰 Cron 预设/校验提示，但不自动修改任何存量表达式或默认频率。
- 不默认引入秒级调度。别名仅在明确周起始/时区语义并通过测试后提供；客户端展示不作为实际调度依据。
- 省/市无下级时可选中当前层级；清空、回显和旧区域值正常，不自动将区域筛选放宽到全国。
- 360px、768px、1280px 视口验证任务、结果、筛选、进度和设置；弹窗可滚动、键盘可用，破坏性按钮不能误触或遮挡。
- 通过条件：既有 next_run/跳过一次行为不变、区域边界回归和可追溯截图/交互测试。只改相关页面，不整体换皮或重写前端。

### U09：代理与通知配置兼容（核验，缺口才修）

入口：`src/config.py`、`src/notifier/`、设置/通知 API；复用 `tests/test_ntfy_compat.py`。

- 用当前锁定 httpx 版本复现 NO_PROXY IPv6 CIDR 问题；不受影响则留测试证据，不照抄全局环境改写。受影响时仅在相应客户端边界修复，不清空 NO_PROXY、不把回环流量送入代理、不关闭 TLS 校验。
- 核验设置保存后的缓存失效与下一次调用生效；保持私有配置、便携配置修订号、服务器环境及本地 .env 的既有优先级，不照搬上游“.env 总是优先”。
- 单渠道测试只校验所选渠道，不能因其他未配置渠道拒绝测试；重复请求不发送多份测试通知。维持已有 ntfy 新旧配置兼容和通知触发条件。
- 通过条件：大小写 NO_PROXY、IPv4/IPv6/空值、显式代理与禁用代理、两用户配置隔离、配置更新与缓存、独立渠道校验；用 fake 通知端点，无真实发送。
- Telegram 自建 API 反代、新通知渠道或账号/代理池轮换不在本批新增范围；有需求另立变更，不把“兼容修复”扩展成新的出站策略。

### U10：Docker 构建优化（增强）

入口：`Dockerfile`、`.dockerignore`、现有两份 Compose、必要构建说明。当前 Dockerfile 已为多阶段构建，不重复建设。

- 测量现有冷/热构建，改进依赖/浏览器层复用和缓存失效粒度；评估独立基础 target，默认仍支持从源码单次构建，不依赖先发布私有基础镜像。
- 核对 Docker 与便携锁定依赖差异；发现风险列明再决定，不能顺手升级全部 requirements。涉及新增/升级依赖遵循第 3 节。
- 如新增 CI，只提供经确认的构建/测试工作流；上传仓库、令牌、标签及发布触发策略另行确认，不借此自动推镜像。
- 通过条件：两份 Compose 配置校验；全新及复用缓存构建；更改业务代码时依赖层可复用、更改依赖时正确失效；隔离容器健康/静态页/合成存储冒烟。保留端口、挂载、入口和默认行为，记录镜像体积与耗时，不虚报提速比例。
- 不执行全局 Docker prune；BuildKit 占用单独盘点，不能为节省空间删除其他项目镜像、卷或缓存。

## 5. 最小数据与 API 设计冻结点

以下为逻辑契约，物理表名和路由在对应批次开始前填入实施记录，不能在跨文件实现过程中各自发挥。

| 数据 | 身份/作用域 | 最小持久化与一致性要求 |
| --- | --- | --- |
| 商品屏蔽 | 当前用户 + 平台商品 ID | 可恢复；与商品原始结果和删除记录分离 |
| 黑名单 | 当前用户 + 规则 ID + 任务或个人全局作用域 | 规则版本、启用态、类型、表达式；查询/统计/导出同一版本 |
| 筛选偏好 | 当前用户 + 页面/任务上下文 | 缺失/失效任务回退安全默认，不能继承前一个登录用户 |
| 价格观察 | 当前用户 + 商品 ID + 任务稳定标识 + 运行/观察标识 | 幂等追加，保留历史；不修改现有结果唯一约束 |
| 生成 job | 当前用户 + job ID，关联任务与输入版本 | 持久化状态、幂等、重启中断、成功写回版本校验 |

必须先明确：任务改名/删除后新数据如何关联和保留；无 owner 的本地空间；增量索引和查询上限；版本冲突错误；备份包含关系；权限类别复用。新功能不得悄悄扩大“删除任务/结果”的级联删除范围。

新增 API 返回稳定错误码和可展示原因，不暴露密钥、Cookie、数据库 URL 或模型原始推理。写操作鉴权与查询一致；批量操作必须有数量上限、幂等及部分失败策略。异步生成、导出及迁移都必须有明确上限与终止行为。

### 5.1 B2a 冻结：身份、物理数据与生命周期（设计，未实现）

目标版本为 PostgreSQL schema v2，一次迁移引入 U05/U06/U07 的**空结构**；业务写入和 UI 分别在 B3/B4/B5 接通。五张新增业务表的 `owner_id` 均为非空 UUID、引用 `users.id`，不接受客户端提供的 owner；所有业务查询和写入都从已认证会话取 owner 并同时过滤 owner。迁移审计表由管理员独立管理。现有 `monitoring_results(owner_id,item_id)` 唯一约束、评分字段与删除 API 不变。`tasks.id` 是 PG 稳定 UUID；Web 当前数字 `id` 仅为列表索引，绝不能存入新表。新 API 对外给出 `stable_task_id`，不替换旧接口的数字 `id`。

| 表（均在 `public`） | 必要字段、约束与索引 | 删除和改名语义 |
| --- | --- | --- |
| `result_hidden_items` | `(owner_id, item_id)` 主键；`created_at` UTC；商品 ID 非空、长度上限 128 | 与结果行无外键；删除结果/任务不自动取消屏蔽；显式恢复才删除本表行 |
| `result_blacklist_rules` | `id` UUID 主键、`owner_id`、`scope`（`task/global`）、可空 `task_ref` UUID、`task_name_snapshot`、`kind`、`pattern`、`enabled`、`revision`、UTC 时间；检查 scope 与 task_ref 一致；索引 `(owner_id,scope,task_ref,enabled)` | 不外键级联到任务；任务改名仍以 UUID 命中，删除后任务级规则保留但不再命中，新同名任务不继承；全局规则须显式选择 |
| `result_view_preferences` | `(owner_id, page_key)` 主键；`task_ref` 可空 UUID、`filters` JSONB、`sort_by/order`、`revision`、`updated_at`；`page_key` 首版固定 `results` | 已删除任务回退“所有结果”，不能按旧名称自动绑定新任务；跨登录用户不复用浏览器缓存 |
| `price_observations` | `id` UUID 主键、`owner_id`、`task_ref` UUID、`task_name_snapshot`、`item_id`、`run_id` UUID、`observed_at` UTC、`currency`、`raw_price`、可空 `amount` NUMERIC(14,2)、`source`；唯一 `(owner_id,task_ref,item_id,run_id)`；查询索引 `(owner_id,task_ref,observed_at DESC)`、`(owner_id,item_id,observed_at DESC)` | 不外键级联到任务/结果；改名保留历史，删任务/结果后历史仍在本人空间，默认结果页仅展示仍存在任务关联的观察；历史删除需未来独立显式流程 |
| `criteria_generation_jobs` | `id` UUID 主键、`owner_id`、`task_ref` UUID、任务名快照、`input_digest` SHA-256、`idempotency_key`、`attempt`、`status`、`stage`、安全错误码/摘要、UTC 创建/开始/结束时间；唯一 `(owner_id,idempotency_key)` 与 `(owner_id,task_ref,input_digest,attempt)`；同任务运行态唯一部分索引 | 不外键级联到任务；任务被删则终止/标失败且禁止写回；保留脱敏 job 记录，不保留原始 Prompt、模型推理或密钥 |
| `app_schema_migrations` | `migration_id` 文本主键、`checksum`、`applied_at` UTC；v2 精确一条 `002_upstream_features` | 管理员迁移审计；只读应用与探测角色不得写 |

新表中任务引用采用“无任务外键的稳定 UUID + 创建时名称快照”；执行时必须以 owner、稳定 UUID 回查当前任务，不能凭快照授权或把孤儿历史认作新任务。PG `owner_id` 的用户级联仍沿用现有账号删除的策略；账号删除是独立破坏性操作，不由结果/任务删除触发。`price_observations` 的金额只接受有限、非负、两位精度可表达值；不支持的货币/面议/异常原文可保留受限长度的 `raw_price`，`amount=NULL`，统计排除；不做汇率换算。`run_id` 在每次既有监控运行开始时生成并传到观察写入边界，同一运行同商品重复响应冲突即无副作用；不因结果已存在而漏记价格，不能为价格重新请求平台。观察缺测不插零值、不补造时间。

本地单用户使用固定内部空间 `local_admin`，不能把它映射为 PG UUID，也不能在缺失认证时自动视作多用户全局权限。B2 给 `config.json` 中任务追加 `stable_task_id` UUID，已有任务在显式版本化升级时一次生成，创建/复制生成新值，改名/排序/编辑保留，删除后永不复用。必须先修所有本地任务写入路径（含 Pydantic 模型和旧 `update_task`）对该字段的保留，再升级现有配置；数字列表索引继续只服务旧路由。新数据在 `state/upstream/v2/` 使用按功能分离的 UTF-8 JSON/JSONL 旁文件及版本标记；按同一文件锁读改写、临时文件落盘后原子替换，并对中断/并发/损坏文件 fail closed。价格观察采用可恢复的追加日志和唯一键索引重建策略；不可仅靠进程内 set 去重。旧本地文件保留、没有可靠任务身份时不猜测映射；不自动扫描/导入真实历史结果。

### 5.2 B2a 冻结：API 与读取边界（设计，未实现）

新增路由避开既有 `/api/results/{filename}` 与数字任务索引路由；旧结果 JSON、删除语义和同步更新入口保持兼容。首版公开请求/响应只含业务字段，`owner_id` 由服务端确定，`stable_task_id` 是 UUID 字符串。所有列表均有服务端上限、稳定排序和 `next_cursor`；无权限资源统一返回 404，不泄露其他用户是否存在。

| 范围 | 路由契约 | 权限与关键语义 |
| --- | --- | --- |
| U05 屏蔽 | `GET /api/result-management/hidden-items`；`PUT/DELETE /api/result-management/hidden-items/{item_id}` | 复用 `results` 权限；PUT/DELETE 幂等，批量未来入口不得复用旧不可恢复删除路由 |
| U05 规则 | `GET/POST /api/result-management/blacklist-rules`；`PATCH/DELETE /api/result-management/blacklist-rules/{rule_id}`；`POST /api/result-management/blacklist-rules/preview` | 复用 `results`；写入带 `expected_revision`，冲突 409；预览不写入、不改变抓取/AI/通知 |
| U05 偏好 | `GET/PUT /api/result-management/view-preferences` | 复用 `results`；只保存白名单筛选/排序字段与合法任务 UUID；写入修订号冲突 409 |
| U06 价格 | `GET /api/price-observations/items/{item_id}`、`GET /api/price-observations/summary`、`GET /api/price-observations/export.csv` | 复用 `results`；任务 UUID/时间窗/筛选上下文同一服务端查询契约；30 天只是默认查询窗；CSV 公式注入防护和有界流式导出，取消即停止读取 |
| U07 生成 | `POST/GET /api/task-criteria-jobs`、`GET /api/task-criteria-jobs/{job_id}` | 复用 `tasks` + `ai` 权限；POST 带 `stable_task_id` 和 `Idempotency-Key`，202 返回 job 状态，重复键返回原 job；GET 列表可按任务 UUID 查询本人最近 job，以便刷新/重新登录后找回；旧 `PATCH /api/tasks/{task_id}` 保留原同步响应直到兼容迁移完成 |

通用错误体为 `{ "code": "STABLE_CODE", "message": "可展示的脱敏说明" }`；400 为无效输入/不支持规则，401/403 为现有鉴权权限，404 为本人范围内不存在，409 为修订/运行竞争，429 为有界请求限制，503 为维护停写。U05 列表、总数、当前视图统计及其导出须在同一个过滤函数/查询版本中先过滤再分页；默认不展示屏蔽项，显式 `include_hidden` 才展示。黑名单首版只控制查询视图，不改变数据写入、训练、推送。正则首版限定安全语法子集及长度/规则数/预览样本上限，具体解析器和拒绝用例在 B3 冻结测试；不得调用无超时的任意用户正则。

U06 统计以同币种有效金额计算，按 `item_id` 去重后求任务窗口样本中位数，返回样本数、时间窗、币种和“参考不足”标志；不足 5 个有效商品或明显规格不同时不输出价值判断。价格不进入现有推荐分数、排序或通知。默认页长 20、最大页长 100；价格查询窗口最大 365 天，首版 CSV 单次最多 50,000 行，超过明确拒绝并提示缩小范围，不静默截断。U07 的 `Idempotency-Key` 限 1–128 个可打印 ASCII 字符；`input_digest` 由服务端对生成实际读取的任务描述、参考 Prompt 内容、生成配置及稳定任务 UUID 做规范化 SHA-256，不能把密钥或完整输入写入 job 行/日志。U07 只由用户既有显式生成操作触发；同任务同输入摘要的 queued/running/succeeded 请求复用原 job，failed/interrupted 只有用户显式重试才增加 `attempt`。启动时把遗留 queued/running 标记 interrupted，不重放付费调用；写回前以 owner、任务 UUID 和输入摘要再校验，失败保留旧标准。旧同步入口何时弃用必须在 B5 另记兼容证据，不在 B2 自动改变。

### 5.3 B2a 冻结：迁移、权限、备份与回退（设计，未实现）

`002_upstream_features` 是唯一 v1→v2 迁移 ID；用仓库内显式 SQL/代码列出每张表、检查约束、索引和固定校验和。先在管理员连接、维护停写和所属实例核验后取得与初始化相同的事务 advisory lock，再严格核验 v1 版本行及 v1 表/列/索引指纹；未知、半成品或过新结构拒绝。一个事务内建空表/索引/迁移记录，替换 `app_schema_version` 当前仅允许 1 的检查约束，写入版本 2，再按固定授权计划提交。失败整个事务回滚，版本仍为 1；重复执行在精确 v2 指纹与迁移校验和匹配时仅报告已完成，不再次建表。不得调用 ORM `create_all` 修补既有库，不在普通 Web 启动时自动迁移真实数据库。新安装直接初始化精确 v2 并记录相同的 002 校验和；测试保留精确 v1 夹具用于升级和旧备份恢复，不能让动态 ORM 表集合污染 v1 校验。

便携版沿用 Launcher 的实例租约、维护门控、停写/备份/隔离恢复及用户确认切换；普通 app 角色只获新业务表的 SELECT/INSERT/UPDATE/DELETE，probe 只读版本表，迁移表和 DDL 只给管理员。Docker/源码部署提供显式管理员迁移命令及预检说明，不能让 app 角色临时拥有 CREATE。迁移前备份必须完成且可校验；Launcher 组件兼容清单将目标 schema 与适用源版本写明。未接入签名更新链前不宣称自动安全升级已经可用。

现有完整业务备份、数据库 dump 与恢复校验固定 schema v1、表/索引清单、`portable-schema-v1` 授权策略。B2 实现必须按版本分别维护 v1/v2 静态清单与指纹：v2 备份包含 5 张业务新表和迁移记录表，manifest 保留外层 `format_version=1`，但 `schema_version=2` 和 `grant_policy=portable-schema-v2`；表计数和恢复后记录/关键字段对账覆盖新增表。本地旁文件如进入便携数据根的 `state/`，须纳入现有加密业务备份目录清单；Docker/本地模式须明确卷与文件备份说明，不把 PG dump 当作本地文件备份。旧 v1 备份只恢复到新隔离的 v1 目标，完成旧版清单/权限验证后显式执行 002，再做 v2 校验；绝不改写原归档或直接在原实例恢复。v2 包不由 v1 程序直接读取。回退优先旧制品＋迁移前备份在隔离目标恢复；若迁移后已有新写入，先展示丢失窗口并由用户选择，不能静默降级/删表。

B2b 实施与验收门槛：先冻结 v1/v2 结构清单和迁移测试，再修改 ORM/迁移器/权限/备份恢复/本地适配器；合成测试覆盖新库、旧库、重复/并发/故障、未知结构/版本拒绝、app 无 DDL、双用户隔离、本地重启/并发、含新数据的 v2 备份恢复、v1 备份隔离恢复再升级。全部通过才将 U04/B2 写为验收通过；B2a 文档核对绝不替代这些测试。

## 6. 分批顺序与依赖

| 批次 | 内容 | 进入下一批的门槛 |
| --- | --- | --- |
| B0 | 冻结本方案；记录当前基线、可用测试入口和受影响既有缺陷 | 需求 ID 与验收清单完整；初次方案交付已完成 |
| B1 | U01/U02/U03/U09 的小补丁及针对性回归 | 不改变默认业务策略；fake 外部调用用例、现有相关回归通过 |
| B2 | U04；冻结 U05/U06/U07 的数据和 API 契约 | 旧库升级、新库初始化、权限、备份恢复的合成验收通过 |
| B3 | U05 屏蔽/黑名单/偏好 | 本地与 PG 一致；分页/统计/导出过滤边界通过 |
| B4 | U06 价格历史/洞察/CSV | 观察幂等、数据隔离、样本解释与导出安全通过 |
| B5 | U07 后台生成 job | 刷新/重启/版本竞争/维护停机和旧入口兼容通过 |
| B6 | U08 交互收尾、U10 Docker 优化 | 页面矩阵和隔离 Docker 验收通过；无额外平台承诺 |
| B7 | 两条部署路线的整合验收与交付说明 | 第 7 节全部有证据；未覆盖项逐项列出，不能宣称发布完成 |

每批可以拆成小补丁，但不能跳过 B2 直接加表。当前默认单一实施流，不因本文自动派多个 agent；若用户后续明确授权分工，各执行者仍按同一 ID/契约交付，避免重复编辑共享文件。

## 7. 验证、回退与交付门槛

- 测试分层：无副作用纯逻辑 → mock API/文件后端 → 隔离 PostgreSQL → 浏览器交互 → Docker/便携整合。测试不得直接加载真实 .env、Cookie、数据库或通知配置。
- 开始 B1 前盘点可用 Python/Node/便携运行时和测试入口；不存在的命令、未执行的测试、需要下载的依赖不得写成通过。失败区分原有问题和本批引入问题。
- 复用现有 `test_scraper_request_binding.py`、`test_ntfy_compat.py`、`test_storage_import_isolation.py`、便携配置/维护/worker/schema/backup 测试；新增每个 U-ID 的专项测试。按实际依赖选择运行器，不为测试擅自安装框架。
- 涉及 JS 做语法/交互验证；涉及 Python 做定向测试和隔离导入检查。所有新增文本检查 UTF-8 无 BOM；交付前 `git diff --check` 和完整状态核对。
- 双后端：正常数据、旧数据缺省字段、并发写入、用户隔离、拒绝访问、重启与失败恢复都验证。新表/文件进入备份清单后，必须做含新增记录的恢复对账。
- 便携版：真实隔离 PG + Web + 当前 Launcher 的初始化/已有实例升级/启动/停止/维护/备份恢复；重新核对 schema 指纹、版本和打包输入。不能只编译 C# 或只跑 Python 就声称整包兼容。
- Docker：保留源码本地模式与服务器 PostgreSQL 模式的既有能力，隔离卷与网络；构建成功不等于运行验收完成。
- 无真实账号情况下明确写“抓取响应仿真通过，真实平台未验”；无真实模型/通知授权时明确标注。不能为了闭环擅自调用外部服务。
- 回退必须说明代码版本、配置格式、schema 版本和数据兼容；停用功能不等于 schema 降级。所有破坏性恢复仍走单独确认。
- B7 更新用户说明、升级步骤、限制和变更来源；版本号与公开发布时机另行确认。不自动 git commit/push、开 PR、发布镜像或覆盖现有发行候选。

## 8. 防漂移与续办记录

### 8.1 每批开工记录

在本文末尾追加一条记录，至少包含：日期、批次/U-ID、实际 HEAD、准确拟改文件、冻结的数据/API 决策、拟跑测试、临时空间登记、已知限制。若未列出的文件是正常实现所需，先补记录并说明原因，再修改。

状态只能使用：`未开始 / 实施中 / 已实现待验收 / 验收通过 / 已有等价能力 / 待用户决定`。“已有等价能力”必须列测试证据；某环境不可用时只将该验收项列为未验证，不能全批虚报完成。

### 8.2 必须先请求用户决策的变更

- 新增依赖、扩展部署平台、变更数据库路线/推荐权重/抓取或通知策略。
- 为价格历史增加外部请求、自动导入真实历史、自动生成标准或改变付费调用预算。
- 引入任意正则引擎、通用队列/微服务、全前端重写或仓库级无关重构。
- 碰到未知真实库结构、必须破坏性迁移/恢复、删除旧数据/缓存、发布到外部。

此时记录“原契约、证据、拟变更、影响、备选与回退”，仅暂停依赖该决定的工作，其他安全且独立项目可继续。内部命名等低风险选择由实施者决定并留档，不为无关细节反复追问。

### 8.3 临时空间与收尾

本任务使用通用卫生预算，不继承便携 Launcher 自动落地任务的容量豁免。新增临时产物统一为 `.tmp/upstream-upgrade/<批次-任务标识>/`，创建前登记生产者、用途、预估峰值、可重建性及清理/复核日期。

单任务预计超过 512 MiB 的成功可重建产物须先确认；通用任务专属可重建总预算 2 GiB。共享依赖和获准保留的状态型夹具另账，仍须在重型任务前后盘点 `.tmp` 全部实际占用，枚举失败报告下限；磁盘低于 10 GiB 或 5% 暂停重型新增。轻量失败诊断最多 7 天且每用途最近 3 次，状态型失败夹具到期只复核。

只清理本任务确认闲置、自有且可重建文件；其他任务产物、旧发行包、数据库和凭据不动。普通目录继承项目 ACL，禁止携带私有临时目录 ACL 进入发行目录。每批记录实际用量、自有清理结果和保留项，不将忽略规则当作自动清理能力。

### 8.4 当前进度

| 项目 | 状态 | 证据/下一步 |
| --- | --- | --- |
| B0 方案 | 验收通过 | 10 个交付节完整；UTF-8 无 BOM、21 处显式本地文件引用检查通过；仅文档验收，不代表业务升级完成 |
| B1 小补丁 | 按既定范围验收通过 | U01/U02/U03/U09 的针对性回归通过；U09 仅限用户确认的单 Web 进程。此结论不等于完整监控任务、便携发行或 B7 整体验收通过 |
| B1 / U01 | 验收通过 | 显式 opt-in、响应解析、参数回退、双用户隔离和原重试预算的离线契约通过；不代表真实第三方网关均兼容 |
| B1 / U02 | 验收通过 | 隔离 PG 双用户 Prompt 专项通过；真实 junction、模拟 reparse 及用户在管理员 PowerShell 中运行的普通文件 symlink 实物测试通过。普通权限窗口仍会因无法创建 symlink 而跳过 |
| B1 / U03 | B1 契约验收通过 | 真实账号手工搜索与自动筛选确认 `keyword`、`pageNumber`、筛选字段及翻页；请求绑定已有字段级反例测试。完整监控任务端到端另属后续整体验收 |
| B1 / U09 | 验收通过 | 用户确认仅按现有单 Web 进程部署验收；IPv6 CIDR、私有配置保存、当前进程内通知测试请求 ID 去重和前端点击 ID 测试通过。多进程/重启持久去重留 B2，扩大 Web 进程数前必须补验 |
| B2 / U04 | 源码与隔离合成验收通过 | 本地稳定任务 ID、v2 旁文件、便携 PG17 新装/升级/备份/隔离恢复和最终 r3 Launcher 实际升级链路通过；独立 PG15 服务器显式迁移、恢复后再升级、负向/回滚/并发、受限角色、双用户、Compose 配置和本地固定标签镜像 Web 健康检查通过。正式实例未迁移、镜像未推送、预览 ZIP 未公开发布；真实数据升级需单独按运行手册演练与授权 |
| B2 / U09 持久测试去重 | 共享持久 `state` 范围验收通过 | `request_id` 持久占位/结果记录的重启、第二进程、损坏记录合成测试通过；Docker 本地 Compose 已挂载 `state`，两个断网测试容器共享同一合成目录验证重启不重复占位。既有部署若曾把 `state` 留在容器内部，启用挂载前须停写、备份/迁出；不承诺跨机器无共享目录的保证 |
| B3 / U05 | 源码与隔离真实运行验收通过，人工 UI 待验 | 真实 Web 浏览器操作、本地持久化、PG15 双用户及含新增记录的备份恢复、当前源码便携预览包启动均通过；不包含正式数据与真实平台调用，任务筛选和规则归属的提示待人工 UI 验收后优化 |
| U06–U08、U10 | 未开始 | 按依赖次序施工，不能将调研算作实现 |
| B7 整体验收 | 未开始 | 不承诺真实平台验收或公开发布已完成 |

### 2026-09-28 / B0 建档

- 生产者：当前聊天；基线：`2d08472693040368de00b3bbac58244bd537e3b1`。
- 改动文件：`docs/UPSTREAM_UPGRADE_PLAN.md` 和 `.gitignore` 中该文档的单文件放行规则；原有 `/docs/*` 会隐藏新文档，故纳入版本控制可见范围，其他历史文档继续忽略。未修改 Launcher 文档或业务源码。
- 关键决策：选择性吸收；隐藏不改变推送；价格不进入推荐权重；生成不自动调用；持久化功能前置迁移和恢复兼容；两种后端/两条部署路线均需证据。
- 本轮临时目录：无；新增临时产物：0 B；未运行重型构建，未对历史 `.tmp` 做删除或全量盘点，不复用旧盘点数字冒充当前实测。
- 已验证：文档状态/范围完整性、UTF-8 无 BOM、21 处显式本地文件引用存在；Git 差异及未跟踪文档空白检查在最终交付前复核。业务测试不适用于仅建档交付；未提交或推送。

### 2026-09-28 / B1a 开工

- HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`；保留本聊天已有 `.gitignore` 和本文改动。
- 用户澄清冻结：价格整合在结果页，不增加独立导航；只展示价格事实，无新增价格分数或推荐权重变化。
- 拟改：`src/ai_response.py`（新增无 I/O 响应提取）、`src/ai_handler.py`、`src/prompt_utils.py`、`src/search_requests.py`（新增请求匹配/绑定/翻页助手）、`src/scraper.py`、`tests/test_upstream_ai_response.py`、`tests/test_upstream_search_requests.py`、`tests/test_scraper_request_binding.py` 及本文。若需无副作用业务接线测试，新增 `tests/test_upstream_call_sites.py`。
- 契约：本小批先修空 choices/content、文本分段及拒绝/截断输出识别；保持现有 JSON 校验、评分函数与重试循环。推理回退和参数删除涉及显式配置与用户隔离，留在 U01 后续，不以纯 helper 冒充接线完成。
- 搜索改动：限定正确 host/path/POST；已有价格提交和翻页绑定新 request 的 response，保留 5–8 秒等待与原有次数；新增等待有界和超时终止，不增加点击重试。
- 测试：纯模块 unittest + 业务函数隔离 mock；不得导入真实配置/调用服务。已发现现有抓取/ntfy 测试直接导入业务模块，先完善隔离入口再运行，不能在仓库 cwd 直接加载真实 .env。
- 临时产物登记：纯测试优先无文件，需隔离导入时只用 `.tmp/upstream-upgrade/b1a-20260928/`，生产者本聊天，可重建合成数据，预计峰值 < 10 MiB；成功且无引用即清理，失败轻量证据于 2026-10-05 前复核。无构建或发行包；不适用 Launcher 容量豁免。
- OpenAI Docs 核对：[JSON mode 仍需业务 schema 校验](https://developers.openai.com/api/docs/guides/structured-outputs)。未升级 SDK、改变模型或切换 Responses API；第三方 reasoning_content 不是标准最终答案，当前不启用。

### 2026-09-28 / B1a 结果

- 已接入 `extract_final_text` 到商品分析与 AI 标准生成：支持 SDK/字典/裸字符串、文本分段；对空 choices/message/content、明确截断/过滤/拒绝/工具输出返回不带原始响应的错误。保留业务原有 JSON 清理、结构校验、评分调用和重试循环；未读取 reasoning_content。
- 搜索统一校验 host/path/POST，避免查询串或相似 API 名误匹配。价格提交与翻页使用本次新 request 对应的 response；动作、请求与响应等待有界；翻页一次点击、原 5–8 秒等待不变，超时/取消不在新助手内部重试。
- 请求头过滤移入无配置助手，规则不变；旧抓取测试改为导入该纯模块，避免只测请求绑定却加载真实 .env/通知模块。其他原有测试不擅自改造。
- 验证命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_call_sites tests.test_scraper_request_binding -q`，**44 项通过**。包括实际安装的 SDK 响应对象、评分输入/owner 传递、单次分析循环预算、标准生成单请求、超时取消、最后一页和新旧请求隔离。
- 调用体测试以 AST 加载真实函数，刻意不执行模块启动及外层重试装饰器；模型、评分器与文件 I/O 为 mock。它验证接线与参数传递，不证明评分器本身、全服务多用户隔离、外层/SDK 叠加重试或真实平台可用。U01/U03 整项继续保持“实施中”。
- 11 个本轮相关文件 UTF-8 无 BOM 检查及 9 个 Python 文件 AST 语法检查通过；Git 差异检查通过，保留原有 LF/CRLF 提示。未新增依赖、业务数据、配置、数据库表、UI、发行包、提交或推送。
- 无本批临时目录，新增临时产物 0 B。收尾 `.tmp` 枚举得到可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，不将下限当总量；F 盘可用 **100,380,028,928 B**。未删除任何历史文件。
- 下一步：继续 B1 的参数回退/私有配置开关及 U02/U09，再补 U03 页码/筛选关联和离线 DOM 验证；B1 完成前不开始新增表。后续价格 UI、黑名单、后台 job 和 Docker 优化尚未实施。

### 2026-09-28 / B1b 开工

- 基线仍为 `2d08472693040368de00b3bbac58244bd537e3b1`；保留 B1a 未提交改动。本小批优先 U02 文件边界和 U09 离线兼容核验，不扩展评分、UI 或数据库结构。
- 已发现：Web 校验未覆盖 Windows 设备名；文件路径缺少逐层符号链接/reparse point 检查。拟改 `src/file_safety.py`（新增纯校验模块）、`src/user_file_store.py`、`src/web/settings_manager.py`，新增 `tests/test_upstream_file_safety.py`、`tests/test_upstream_notification_compat.py`；必要时调整 `tests/test_portable_app_paths.py` 的本轮测试临时根入口，通知缺口需先补登记再修。
- 契约：Web 输入拒绝路径及编码分隔符、设备名、ADS、目录；已有本地内部 basename 兼容与非便携历史绝对任务路径暂不改变。作用域路径在返回/创建目录前校验受信根下各层并拒绝链接，错误不向 API 暴露磁盘路径。不是对恶意本地进程并发换链的原子文件沙箱。
- 拟验收：纯校验 + 实际合成文件/链接 + 隔离 API 接线、权限和存储 owner 传递；继续 B1a 回归。代理与通知仅 fake/no-network 核验，不加载真实 .env 或真实数据库、不发送通知、不新增依赖。
- 临时空间：本聊天 `.tmp/upstream-upgrade/b1b-20260928/`，合成可重建夹具，预计 < 10 MiB；普通目录继承项目 ACL，成功即清理自有文件，轻量失败证据最迟 2026-10-05 复核。不触碰历史 `.tmp`。

### 2026-09-28 / B1b 结果

- 新增 `src/file_safety.py`，Web 在追加扩展名前校验完整文件名；拒绝盘符/UNC/反斜杠/ADS、设备名、编码路径控制字符和目录输入。文件存储在受信根下逐层 lstat，拒绝符号链接和 Windows reparse point，写入目录前后复核；列表不跟随不安全条目。
- Prompt、criteria、Bayes 文件接口增加错误边界，客户端不接收真实磁盘路径或底层异常；合法中文文件、扩展名补全、共享/默认模板回退和私有写入正常。未改变历史非便携绝对任务路径与内部 basename 兼容规则，不宣称旧任务任意路径已被全面收紧，也不宣称可抵抗本地恶意进程的并发换链。
- 新增两个定向测试文件；未修改原有便携路径测试文件、通知业务代码或代理策略。使用实际 FastAPI 路由/依赖包装的隔离函数体验证 Prompt 创建、读取、更新、删除、列表、401/403、owner 传递和错误脱敏；不等同于启动完整应用或真实 PG 行级权限验收。
- 通知真实函数体 + fake 配置/发送端验证单渠道不调用其他渠道、配置 reload 后下一次调用生效、并发 owner/config_id 隔离、失败不内部重试与上下文恢复；ntfy 旧 URL 的 IPv6/反代路径/token 兼容正常。该测试不覆盖重复 HTTP 请求的端到端幂等、不证明设置保存/便携修订号全链路，不宣称 U09 完成。
- 代理诊断使用已安装且与便携锁一致的 httpx **0.28.1**：空值、IPv4、IPv6 单地址、大小写 NO_PROXY 可以构造；`NO_PROXY=::1/128` 加环境代理时出现 `httpx.InvalidURL: Invalid port: ':1'`。显式 proxy 或 `trust_env=False` 构造成功，仅是边界证据，不能直接作为业务修复（可能改变代理绕过语义）；未改环境变量、TLS 或出站策略。缺陷保留为 `expectedFailure` 待下一批修复，不能计为通过。
- 验证命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_call_sites tests.test_scraper_request_binding tests.test_upstream_file_safety tests.test_upstream_notification_compat -q`。共 **71 项：69 通过、1 跳过、1 已知预期失败**。真实 Windows junction 读/写/列表拒绝且目标未变通过；普通符号链接因环境创建权限不足跳过，另有 lstat 仿真覆盖。
- 本批合成夹具按用例清理，仅移除本用例文件和链接本身，未清理任何历史数据；这些可重建夹具已永久移除。本批临时目录不存在，留存 0 B。收尾 `.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**；F 盘可用 **100,379,987,968 B**。不将下限当作总量。
- 收尾 16 个当前改动文件 UTF-8 无 BOM、14 个 Python 文件 AST、跟踪/新增文件空白检查通过（仅有原有 LF/CRLF 提示）；71 项回归复跑结果一致。无新依赖、真实外部调用、业务数据迁移、提交、推送或发行包。
- 下一批继续 U01 参数兼容、U03 页码/筛选关联、U02 剩余接口/真实 PG 权限核验及 U09 代理缺陷与设置全链路；B1 未结案，不开始新增数据表。

### 2026-09-28 / B1c 开工

- HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`；保留 B1a/B1b 未提交改动。先修 U09 已复现的环境代理 IPv6 CIDR 构造缺陷。
- 拟改 `src/httpx_compat.py`（新增实例级兼容）、`src/config.py`、`src/prompt_utils.py`、`src/web/ai_health.py` 的旧 SDK 探测构造入口、`tests/test_upstream_notification_compat.py`，新增 `tests/test_upstream_httpx_compat.py` 及本文。便携手工探测的 `trust_env=False`/安全 transport 不改。
- 实现冻结：复用 HTTPX 原有代理映射，仅将 IPv6 CIDR 旁路规则提取为实例级 IP 网段匹配；普通 host/port/域名和显式 proxy 继续原有语义，不修改进程 NO_PROXY，不做额外 DNS 解析。SDK 客户端沿用 SDK 默认 limits/redirects 与各调用点原超时、重试。此兼容层封装 HTTPX 的两个私有扩展点，锁定版回归必须覆盖，未来升级 HTTPX 时需重验。
- 测试不联网：实际 HTTPX/SDK 构造、fake transport 的 direct/proxy 路由、IPv6 网段边界/回环/重定向、普通旁路回归、显式 proxy/禁用环境代理、TLS/关闭/用户并发隔离，以及实际调用体接线。无新依赖和真实 AI/通知。
- 临时空间：新测试优先内存，无临时产物；复跑 B1b 时只使用其合成夹具目录并由用例清理。若需新增，限 `.tmp/upstream-upgrade/b1c-20260928/`，本聊天生产，预计 < 10 MiB，可重建成功即清理，失败轻量证据 2026-10-05 前复核。

### 2026-09-28 / B1c 结果

- 新增实例级 `httpx_compat`：从原代理映射中提取合法 IPv6 CIDR，每次请求以目标 IP 字面量做网段匹配，命中使用原直连 transport；不额外 DNS、不改进程环境、不关闭 TLS。其他映射仍交 HTTPX。非法 CIDR 保留原失败行为，不因兼容而静默放行。
- 接入全局 AI 客户端、私有标准生成客户端、三个旧版 SDK 健康探测入口；显式代理分支维持原实现。保留 SDK 的 timeout/limits/follow_redirects 默认值和调用点的 30 秒、900 秒配置，未改 SDK 或业务重试次数。临时客户端由原 finally 关闭，兼容类保留 SDK 原默认 wrapper 的尽力销毁关闭行为（异步仅在事件循环仍活动时安排，不承诺进程退出时强制排空）。
- 便携手工探测未使用此兼容层，其 `trust_env=False`、`follow_redirects=False`、安全 transport 和地址校验未修改；增加相关 AST 接线保护，不把静态检查算作完整便携整包验收。
- 按 OpenAI Docs 技能核对[官方 SDK 入口](https://developers.openai.com/api/docs/libraries)，具体已安装 SDK 的默认值以本地源码与实际对象对比为准；未升级 SDK 或切换 API。无 API-key 配置工具可用，本批仅合成 key 与 fake transport，不发起真实模型请求。
- 测试覆盖同步/异步、IPv6 网段边界与回环、IPv4/localhost/域名/端口混合旁路、大小写环境变量、通配旁路、显式代理原优先级、`trust_env=False`、重定向逐目标路由、两个客户端配置快照隔离、TLS 配置传递、关闭与 SDK 默认值；通过实际 SDK 的假传输 completion 验证单次请求及业务构造入口。
- 完整定向命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_call_sites tests.test_scraper_request_binding tests.test_upstream_file_safety tests.test_upstream_notification_compat tests.test_upstream_httpx_compat -q`。**86 项：85 通过、1 跳过、0 已知预期失败**。跳过仍为 B1b 普通符号链接创建权限不足；此前 IPv6 CIDR 缺陷已转为兼容客户端通过用例。HTTPX 原库未被修改，不宣称其原生构造缺陷已消失。
- 收尾 20 个改动文件 UTF-8 无 BOM、18 个 Python AST、跟踪/新增文件空白检查通过；仅保留 LF/CRLF 提示。新增测试使用内存；B1b 重跑夹具已清理（可重建合成文件永久删除，不涉及业务数据），B1b/B1c 临时目录均不存在，留存 0 B。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**、**10 处枚举错误**，F 盘可用 **100,379,963,392 B**；没有删除任何历史产物。
- 限制与下一步：这是锁定 httpx 0.28.1 的实例级适配，未来升级须重验两个私有扩展点；未验证真实代理服务器/网络或全服务。U09 的设置保存/修订号/重复 HTTP 测试请求幂等仍未闭环，U01 参数兼容、U02 剩余验收和 U03 筛选页码关联继续待办，B1 不结案、不开始加表或价格 UI。未新增依赖、提交、推送或发布。

### 2026-09-28 / B1d 开工

- HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`，保留全部前批未提交改动。本小批落实 U01 显式参数回退；U03 后续单独施工。
- 拟改 `src/ai_parameter_fallback.py`（新增无 I/O 判别）、`src/ai_handler.py`、`src/config.py`、`src/web/settings_manager.py`、`src/web/task_manager.py`、`src/web/scheduler.py`、`static/js/modules/render.js`、`static/js/modules/settings_view.js`、`tests/test_upstream_call_sites.py`；新增 `tests/test_upstream_parameter_fallback.py`、`tests/upstream_parameter_fallback.test.cjs`，更新本文。
- 配置契约：`AI_PARAMETER_FALLBACK_ENABLED` 默认 false；设置 API 只接受 JSON boolean，省略则保留。文件后端用原 .env；PG 用当前用户默认 API 配置的 existing extra_config，便携沿用 config_id/revision CAS，不加表、不写 portable app.env。手动/定时 worker 均显式覆盖私有缺省 false，避免继承全局开关。仅新启动任务生效。
- 回退契约：仅 SDK BadRequestError / HTTP 400 且结构化 code=unsupported_parameter、param 精确为 temperature 或 response_format 时允许下一次已有尝试省略该参数。未知/纯文本/unsupported_value/鉴权/限流/余额/超时不猜测。状态仅在本次分析函数调用内；不移除 token 上限（含用户自定义字段）、模型、messages 或 extra_body，不修改配置或共享客户端。原三次内层循环、失败计数/阈值、外层及 SDK 重试均保留，不增加独立重试。
- UI 在现有 AI 设置内增加说明清晰的默认关闭开关；保存显式提交 false，便携冲突刷新回填。连接测试、标准生成保持原预算和参数，不启用此回退。reasoning_content 回退暂不实施，正常 JSON 校验与评分代码不改。
- OpenAI Docs 已核对[错误分类](https://developers.openai.com/api/docs/guides/error-codes)；第三方错误码并非通用保证，保守拒绝未明确结构化支持的响应。
- 验证：真实 SDK 合成异常、隔离实际业务函数体/设置保存/双 worker 环境、原内层及外层预算对照、并发调用不共享删除集合、UI 渲染/提交/刷新 Node 仿真与原便携修订号回归；累计 B1 Python 测试。无网络、真实配置、真实 PG、依赖安装和模型调用；浏览器视觉/完整服务验收另记。
- 临时登记：本聊天测试优先纯内存；如需文件仅 `.tmp/upstream-upgrade/b1d-20260928/`，可重建合成夹具 < 10 MiB，继承 ACL，成功即清理，轻量失败证据 2026-10-05 复核。复跑 B1b 仍由原用例清理其自有合成夹具，历史文件不动。

### 2026-09-28 / B1d 结果

- 本小批定向离线验收通过，U01/B1 整项仍为实施中。新增保守参数错误判别，只处理结构化 SDK 400 `unsupported_parameter`；不基于错误文本猜测，不将 `unsupported_value` 当成可删除参数，不改 token 上限、自定义上限字段、模型、messages 或 extra_body。
- 分析循环接入每次调用独立的省略集合；配置注入后再移除参数，防止重加。保留原失败计数/阈值、JSON 校验、评分器、内层/外层/SDK 重试。真实 SDK + 内存假传输验证 400 后一次剩余尝试成功共 2 请求；未知/鉴权/限流/超时错误不触发参数回退。
- 注意既有预算不是“整个函数最多 3 请求”：内层 3 次叠加外层 3 次，原全局失败阈值仍参与；本批隔离实际外层装饰器的持续失败对照为关闭/开启均 5 次 create。未改动或承诺修复该既有叠加行为，不宣称真实网络错误的 SDK 重试已全面验收。
- 新配置默认 false，API 严格 boolean；本地 .env 支持保存/省略保留/布尔读回。PG 复用私有 extra_config，便携沿用 config_id/revision 更新与 409/428 拒绝边界。手动启动与定时调度同时接入，私有旧配置缺省 false 并覆盖继承变量；存储失败保持原 fail-closed。未新增表或迁移真实数据。
- UI 在原 AI 设置内增加“参数兼容回退（默认关闭）”；关掉时显式提交 false，便携冲突刷新回填开关，连接测试不发送此分析专用字段。说明仅新启动任务生效，不用于连接测试/标准生成；没有新增导航、价格 UI 或修改打分/通知策略。
- OpenAI Docs 技能的错误分类核对用于收紧回退边界；第三方未提供明确结构化错误时继续原失败流程，不声称普遍支持所有兼容网关。未实现 reasoning_content 回退，也未启用任何用户的实际配置。
- Python 累计命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_call_sites tests.test_scraper_request_binding tests.test_upstream_file_safety tests.test_upstream_notification_compat tests.test_upstream_httpx_compat tests.test_upstream_parameter_fallback -q`，**111 项：110 通过、1 跳过、0 预期失败**。跳过仍为普通符号链接创建权限不足；本批新增 25 项全部通过。部分业务测试按 AST 提取函数体，不加载真实 .env 或服务；PG 为 mock，不等同于真实事务/权限或 worker 整进程验收。
- Node：`node --test tests/upstream_parameter_fallback.test.cjs tests/portable_settings_revision.test.cjs`，**9 项全部通过**（新表单测试 7 项、既有修订号测试 2 项）；两个改动 JS 文件 `node --check` 通过。测试执行真实渲染/提交/刷新片段，未做浏览器视觉或完整页面端到端验收。
- 收尾 27 个当前改动文件 UTF-8 无 BOM、22 个 Python AST、跟踪/新增文件空白检查通过，仅有原有 LF/CRLF 提示。新测试全内存，B1b 复跑合成夹具已由用例永久清理；B1b/B1d 临时目录不存在，留存 0 B。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，F 盘可用 **100,379,389,952 B**；没有清理任何历史文件。
- 下一步继续 U03 页码/筛选关联及 U02/U09 未验矩阵；reasoning_content 回退需独立显式开关与完整业务校验后再接入。B1 未结案，不开始加表或价格 UI；未新增依赖、真实模型调用、配置写入、提交、推送或发布。

### 2026-09-28 / B1e 开工

- HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`，保留前批全部未提交改动。落实 U03 中可确认的导航/筛选/排序新请求关联，不改采集频率、点击次数、睡眠、价格失败降级和评分策略。
- 证据边界：本地源码/测试没有已验证的搜索 POST 页码/筛选载荷样本；[父项目 scraper](https://raw.githubusercontent.com/Usagi-org/ai-goofish-monitor/master/src/scraper.py) 也只按搜索端点等待响应，未实现 post_data/pageNumber 解析。第三方搜索文档只能作线索，不能当本项目线上请求契约。本批不按猜测硬编码字段，也不声称完成字段级页码/筛选校验。
- 拟改 `src/search_requests.py`、`src/scraper.py`、`tests/test_upstream_search_requests.py`、`tests/test_upstream_call_sites.py`，新增 `tests/test_upstream_search_call_sites.py`，更新本文。
- 契约：新增上下文助手在动作前监听 request，仅选择第一个符合既有 host/path/POST 的新 Request，以对象身份匹配其 Response；沿用调用点原 expect_response 超时，不把导航 60 秒改成新的总超时。finally 移除自有 request 监听；不重发请求、不修改请求、不增加网络 I/O。原价格提交/翻页的有界 capture 助手保持不变。
- 将初始导航、新发布/最新、个人闲置、包邮、额外筛选、区域提交、价格排序 8 处原 expect_response 接入上下文助手，保留原动作体及睡眠/异常策略。取消/异常清理、旧响应/非目标请求/并行第二请求抢占通过 fake 页面核验；隔离实际 scraper 代码片段检查接线与原预算。
- 临时空间：本聊天生产，新增测试纯内存，无新目录。复跑 B1b 用例仅清理其自有可重建合成文件。如需临时文件，使用 `.tmp/upstream-upgrade/b1e-20260928/`，峰值 < 10 MiB，继承权限，成功即清理，轻量失败证据于 2026-10-05 前复核。历史缓存/数据不动，无新依赖、真实抓取或真实模型调用。

### 2026-09-28 / B1e 结果

- 完成 8 处搜索响应接线：初始导航、新发布/最新排序、个人闲置、包邮、额外筛选、区域提交、价格排序。新上下文先记录第一个符合 host/path/POST 的新 Request，再按同一对象匹配响应；旧在途响应、后发先至的第二个请求或相同 URL 的另一请求不会替换已选响应。
- 保持各动作体与原参数：导航 timeout=60000 / 响应 timeout=30000；一般筛选响应 20000；价格排序响应 12000、点击 3000；原随机睡眠逐项对照不变。原价格提交/翻页助手、重试次数、异常分支、降级策略、采集频率、评分和通知代码未改。
- finally 移除本助手自己的 request 监听，已有页面监听保留；动作错误、响应监听建立失败、无新请求、无响应、取消均有用例。保持原响应计时器从监听开始计时，不在动作结束后再补一份超时；响应先完成时不提前取消业务原有睡眠。
- 新增 13 项测试（上下文 11 项、实际 scraper 接线 2 项，其中动作测试逐一执行 8 个真实 AST 动作块），全部通过。无真实浏览器、网站、账号或网络调用；fake 事件页不证明线上页面结构或 Playwright 整进程生命周期已验收。
- 累计命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_search_call_sites tests.test_upstream_call_sites tests.test_scraper_request_binding tests.test_upstream_file_safety tests.test_upstream_notification_compat tests.test_upstream_httpx_compat tests.test_upstream_parameter_fallback -q`，**124 项：123 通过、1 跳过、0 预期失败**。跳过仍为 B1b 普通符号链接创建权限不足。原前端 Node 定向命令复跑 **9 项全部通过**。
- 28 个当前改动文件 UTF-8 无 BOM、23 个 Python AST、跟踪/新增文件空白检查通过，仅有原有 LF/CRLF 提示。新增测试全内存；B1b 复跑的自有合成夹具由用例永久清理，B1b/B1e 临时目录不存在，留存 0 B。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，F 盘可用 **100,379,365,376 B**；未清理历史文件。
- 未完成边界：这解决请求身份和响应时序，不证明请求里页码、价格、地区等字段符合任务意图。先前操作延迟到本次监听才发出的新请求仍可能被选中；缺少可核验的脱敏载荷/官方契约前不猜测字段或改成未验证的强制拒绝。字段级 U03 与离线 DOM/完整浏览器验证保持待办，不将本小批写成 U03 结案。
- 下一步可继续 U02 剩余文件接口矩阵、U09 设置/修订号验收；U03 字段级校验待可信载荷证据，取得真实账号或实际抓取授权不是本批隐含动作。B1 整体未完成，不提前新增表/价格 UI；没有新增依赖、实际配置写入、提交、推送或发布。

### 2026-09-28 / B1f 开工

- HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`；保留本聊天前批差异，继续 U02 文件接口矩阵与 U09 保存兼容。仅合成文件/内存存储，不接真实 PG、账号或外部通知。
- 拟改 `src/web/settings_manager.py`、`tests/test_upstream_file_safety.py`（扩展现有隔离路由装载器）、新增 `tests/test_upstream_settings_api.py`，更新本文。若发现范围外缺口先登记，不改 schema、评分、发送触发条件、UI 或依赖。
- 发现待复现：通知 model_dump 未 exclude_unset，部分更新可能把其他渠道设为模型默认 false；更换 ntfy server 而省略 token 时，保存层合并可能留下旧凭据；仅旧组合 URL 的读回可能泄露其中 token。冻结修复为只合并显式提交字段，空密钥保持原有规则，但 server 变更时不继承旧 token，GET 不返回 URL 内凭据，不自动发送测试通知。
- 文件边界：覆盖 criteria/requirement 优先读写、Bayes CRUD、权限/非法路径/失败脱敏、PG owner 传递及共享回退。便携默认种子目录只读：文件接口更新写入可写层，删除仅删除可写覆盖，不触碰 program/defaults；普通本地路径/PG 模板覆盖策略不变。无法用 mock 宣称真实数据库行权限或事务验收通过。
- 设置验收：真实 FastAPI 路由/依赖 + 合成 env；代理保存本地双缓存 reload、PG 用户私有 extra 保留、便携 revision/config_id 冲突和无变化保存；不改便携已有 CAS 协议或代理策略。真实 PG 并发、通知重复请求端到端幂等仍单独待验。
- 临时登记：复用 `tests/test_upstream_file_safety.py` 的 `.tmp/upstream-upgrade/b1b-20260928/<用例ID>/`，本聊天合成文件，新增峰值 < 10 MiB，继承 ACL，成功由用例清理；新增设置测试全内存。若需失败轻量证据限 2026-10-05 复核。历史临时产物、真实配置及凭据不动。

### 2026-09-28 / B1f 结果

- 本批新增 28 项离线测试（文件接口 10、设置接口 18），定向验收通过。修复前首轮 24 项出现 11 个失败实例（含子测试），复现部分更新覆盖其他通知渠道默认值、ntfy 旧 token 残留/回显，以及文件更新/删除触及内置种子；不是将未复现假设当作缺陷。
- 通知 PUT 只合并显式提交字段，保留未提交渠道和开关；更换 ntfy server 且没有提供新 token 时清空旧 token，反向代理路径大小写视为不同目标。ntfy 目标/凭据编辑时保留有效旧目标并转成独立字段、清空 legacy 组合 URL，防止显式清除 token 后被发送端兜底重新读取。无关渠道更新不重写 ntfy。
- 通知 GET 兼容仅旧 URL 配置且不回显其中 token，畸形/无 topic 的旧 URL 不原样返回；补读回后保存的凭据保留、显式清空旧地址、IPv6/反代路径与新 token 替换回归。未修改发送触发条件、实际用户配置或发出测试通知。
- Prompt/criteria/requirement/Bayes 文件更新统一解析可写路径；无 owner 的 Prompt/Bayes 删除只删除可写层，只有内置默认种子时拒绝删除。用 portable 路径布局的合成文件验证种子不变、覆盖可读、删除覆盖后回退；这不是宣称便携版采用文件存储，便携实际 PG 路线不变。
- 扩展真实 FastAPI 路由/依赖的隔离测试：文件 CRUD/扩展名/重复、requirement 优先、权限、路径拒绝、I/O 错误脱敏、PG owner/version 传递及 JSON 对象校验；设置本地 reload、私有代理 extra_config 合并与 owner 隔离、便携 409/428、无变化保存不增修订号。存储/CAS 为内存替身，非真实 PostgreSQL 事务/行权限或多进程并发验收；业务模块按 AST 隔离，未启动完整服务。
- 累计命令：`python -B -m unittest tests.test_upstream_ai_response tests.test_upstream_search_requests tests.test_upstream_search_call_sites tests.test_upstream_call_sites tests.test_scraper_request_binding tests.test_upstream_file_safety tests.test_upstream_notification_compat tests.test_upstream_httpx_compat tests.test_upstream_parameter_fallback tests.test_upstream_settings_api -q`，**152 项：151 通过、1 跳过、0 预期失败**。跳过仍为 Windows 普通符号链接创建权限不足，真实 junction 用例通过。错误日志来自预期的合成失败测试，不是实际发送失败。
- Node：`node --test tests/upstream_parameter_fallback.test.cjs tests/portable_settings_revision.test.cjs`，**9 项全部通过**；两个前批改动 JS 文件语法检查通过。本批没有 UI 修改；打分/贝叶斯权重、采集频率、AI 重试预算、通知触发策略不变。
- 收尾 29 个当前改动文件 UTF-8 无 BOM、24 个 Python AST、跟踪/新增文件空白检查通过，仅有 LF/CRLF 提示。设置用例全内存；文件用例永久清理其自有可重建合成夹具，B1b/B1f 临时目录均不存在，留存 **0 B**。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，F 盘可用 **100,379,332,608 B**；未删除历史文件或业务数据。
- B1 仍未结案：U01 reasoning_content 显式回退、U02 真实 PG/普通符号链接、U03 字段级请求关联及浏览器验证、U09 私有通知保存和重复 HTTP 测试请求端到端幂等继续待办。下一批可先做 U09 私有通知/幂等离线闭环；没有可信载荷前不猜测 U03 字段，不提前新增表或价格 UI。未新增依赖、迁移数据库、提交、推送或发布。

### 2026-09-28 / B1g 开工

- HEAD 与前批未提交差异保持不变。本小批只处理 U09 的私有通知配置更新与测试通知 HTTP 请求去重；计划改 `src/web/user_manager.py`、`src/web/notification_manager_v2.py`、`src/web/models.py`、`static/js/modules/notifications_view.js`，新增 `src/web/notification_test_guard.py` 和定向测试，更新本文。不改真实配置、通知自动触发逻辑或存储 schema。
- 私有更新契约：只更新明确提交的渠道字段；保留 UI 未提交的现有参数，显式空字符串可清除密码字段。ntfy server 变更时清空旧 token 与旧组合 URL，避免合并后又复用旧凭据。现有 owner 限定、事件开关、审计逻辑保留。
- 测试通知契约：浏览器每次人工点击产生一个请求 ID；同一 owner、ID、测试类型及目标的并发/重发只执行一次，冲突的目标返回 409。旧客户端不传 ID 仍按原行为发送；缓存仅限当前 Web 进程，设时效与容量边界，不宣称跨进程/重启持久幂等。三个测试通知入口共用机制，手动商品发送入口不变。
- 验证使用真实 FastAPI 路由与内存存储/发送端，覆盖两用户隔离、并发重发、结果复用、冲突、未知结果和配置保存；Node 检查前端请求接线。测试不发外部通知，新增夹具优先内存。如需临时文件，限 `.tmp/upstream-upgrade/b1g-20260928/`，本聊天生产，可重建峰值 < 10 MiB，成功即清理，失败诊断于 2026-10-05 复核。

### 2026-09-28 / B1g 结果

- 本批完成私有通知保存和测试通知请求去重。私有更新保留未提交的渠道参数、密钥、绑定任务与事件开关；页面明确提交空字段时可清空该值/解除任务绑定，并清除对应旧字段别名。ntfy 旧组合 URL 在编辑时转换为独立字段，服务器或反向代理路径变化时移除复用的旧 token 与旧 URL，保存回执同步清掉页面里未被后端保留的旧 token，防止随后再次保存复活。owner 限定与审计入口保留。
- 三种人工测试通知 API 接受可选 `request_id`；同一用户同一 ID 的并发/重发共用单次发送结果，ID 换目标或测试类型返回 409；鉴权先于发送。前端每次人工点击生成独立 ID，按钮从保存前起禁用，避免同一点击保存/发送阶段双击。旧客户端省略 ID 继续原行为；异常响应不回显发送端异常文本。
- 去重保存在单个 Web 进程内，发送完成后 300 秒有效，最多保留 512 个请求；缓存已满时拒绝新带 ID 的测试，不驱逐未过期结果。请求取消不取消已启动的发送；失败/未知结果不因同 ID 重发而重复推送。当前 `src/web/main.py` 使用单次 `uvicorn.run`，但多进程部署、重启后与真实 PostgreSQL 并发仍需后续持久协调；不把本批称作跨进程强幂等。
- 新增 14 项 Python 离线路由/并发测试和 3 项 Node 表单测试。累计 Python 命令在 B1f 既有列表后加 `tests.test_upstream_notification_api`，**166 项：165 通过、1 跳过**；跳过仍为普通符号链接创建权限。Node 三文件命令 `node --test tests/upstream_parameter_fallback.test.cjs tests/portable_settings_revision.test.cjs tests/upstream_notification_view.test.cjs`，**12 项全部通过**。三个改动 JS 文件 `node --check` 通过。测试使用内存存储和 fake 发送端；无真实 PG、浏览器视觉、外部通知或自动触发路径测试。
- 交付检查：当前 36 个改动文件 UTF-8 无 BOM、29 个 Python AST 与跟踪/新增空白检查通过，仅有既有 LF/CRLF 提示。测试产生的合成失败日志属于预期用例；本批无临时文件，B1b/B1g 自有夹具目录均不存在，留存 **0 B**。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，F 盘可用 **100,379,287,552 B**；历史文件未清理。
- B1 其他未完项维持原状态：U01 推理内容显式回退、U02 真实 PG/普通符号链接、U03 字段级请求与浏览器验证；U09 跨进程/重启持久去重和真实 PG 并发未完成。本批不新增表、不变更评分/抓取频率/自动通知触发，不提交、推送或发布。

### 2026-09-28 / B1h 开工

- 本小批落实 U01 剩余的 `reasoning_content` 兼容。按 [OpenAI 官方推理模型文档](https://developers.openai.com/api/docs/guides/reasoning)，标准 API 的推理 token 不向客户端作为正文开放；此字段仅按第三方兼容网关的非标准输出处理。OpenAI Docs 技能用于核对这一边界，本批不调用真实模型。
- 拟改 `src/ai_response.py`、`src/ai_handler.py`、`src/config.py`、`src/web/settings_manager.py`、`src/web/task_manager.py`、`src/web/scheduler.py`、`static/js/modules/render.js`、`static/js/modules/settings_view.js`，扩展相关 Python/Node 定向测试并更新本文。不改 `prompt_utils` 的标准生成、模型选择、重试次数、评分权重或 schema 存储。
- 新开关 `AI_REASONING_FALLBACK_ENABLED` 默认 false，独立于参数回退；本地 .env 和 PG 当前用户 extra_config 均可显式布尔保存，便携沿用 config_id/revision CAS，手动/定时 worker 以当前用户的私有值覆盖全局。只对分析调用启用；已有最终 `content` 永远优先，拒绝/工具调用/截断/非法 content 均不能退回推理字段。
- 推理候选只接受完整 JSON 对象；不从 Markdown、混合文字或多个对象中截取。进入既有校验/评分前，要求字段完整、推荐等级与布尔结论一致、置信度有效、`criteria_analysis.seller_type` 可用；不借旧回填制造缺失字段。失败仍占用原有尝试与失败阈值，不新增请求；推理原文不写日志，即使 AI_DEBUG_MODE 开启也只记录通过/拒绝状态。
- 验证使用合成 SDK 响应、隔离实际分析/设置/worker 函数和 Node 表单仿真；不读取真实密钥/用户数据、不发网络或付费请求。测试优先全内存，如需暂存仅 `.tmp/upstream-upgrade/b1h-20260928/`，本聊天生产、可重建峰值 < 10 MiB，成功即清理，失败诊断于 2026-10-05 复核。

### 2026-09-28 / B1h 结果

- 已完成 `reasoning_content` 显式回退。开关默认关闭，分别接入本地环境配置、当前用户私有 `extra_config`、便携修订号 CAS、手动和定时 worker，以及原有 AI 设置表单；连接测试与标准生成不读取该字段。最终 `content` 非空时始终优先，即使其业务 JSON 无效也不改用推理字段。
- 兼容候选先完整解析为单个无重复键 JSON，再按 `base_prompt.txt` 校验顶层字段、等级与布尔结论/置信度区间/否决标记一致、卖家画像及六项分析明细；有图片 URL 时还须有完整视觉摘要。缺失、截断、拒绝、工具调用、非文本、Markdown 或混合输出仍按原失败预算处理，不触发新请求；调试日志不写候选原文。此校验仅作用于显式回退，正常 `content` 的旧解析/回填及打分权重未改。
- 通过合成 `httpx.MockTransport` 与当前 OpenAI SDK 确认兼容网关扩展字段在 SDK 响应对象上可读取；不代表标准 OpenAI API 会提供原始推理正文。私有/便携/本地布尔读写和双 worker 用户隔离均为离线替身测试，未读取真实密钥或连接真实 PostgreSQL。
- 累计 Python 命令在 B1g 列表后加 `tests.test_upstream_reasoning_fallback`；**185 项：184 通过、1 跳过**，跳过仍为普通符号链接创建权限。Node 三文件命令 **12 项全部通过**，三个相关 JS 文件 `node --check` 通过。测试覆盖有效/残缺候选、最终内容优先、图片条件、调试脱敏和 SDK 合成响应；未做真实网关兼容、浏览器视觉或完整服务端到端验收。
- 交付检查：当前 37 个改动文件 UTF-8 无 BOM、30 个 Python AST、跟踪/新增空白检查通过，仅有既有 LF/CRLF 提示。B1h 未创建临时产物；B1b/B1g/B1h 自有夹具目录均不存在，留存 **0 B**。`.tmp` 可读下限 **25,694,702,788 B / 153,890 files**，**10 处枚举错误**，F 盘可用 **100,379,140,096 B**；历史文件与业务数据未清理。
- B1 仍未整体结案：U02 真实 PostgreSQL/普通符号链接、U03 字段级请求关联与浏览器验证、U09 跨进程/重启持久去重及真实 PG 并发仍待后续批次。B1h 无新增依赖、数据库表、价格 UI、许可证变更、真实模型调用、提交、推送或发布。

### 2026-09-28 / B1i 开工

- 本小批补 U02 的真实 PostgreSQL Prompt 路由与所有权矩阵，不用 mock 数据库结论替代真实事务。复用仓库已有的 Windows PG 隔离运行时及 schema 冒烟脚本，其安全清理边界固定为 `.tmp/tests/portable-pg/集成 冒烟-<随机值>/`；该固定目录作为本批复用的测试任务空间，成功后仅清理由脚本创建的精确子目录，不清理历史夹具。先确认二进制与磁盘条件，峰值预计低于 512 MiB。普通文件符号链接权限重试只在自有合成路径进行，不改系统权限。
- 验证合成双用户的中文 Prompt 创建、列出、读取、更新、删除与跨用户拒绝，并覆盖未登录/无权限、非法文件名、系统共享模板不可直接删除；所有请求走现有 FastAPI 路由，存储使用真实 PostgreSQL 适配器。失败时保留原测试夹具供复核，不触及旧 `.tmp`、真实实例、账号、密钥或业务数据。
- 本批优先只改测试和本文；发现可复现缺陷才做最小生产修复。结束后运行 U02 定向及 B1 累计回归、UTF-8/语法/空白检查和卫生盘点；记录清理结果与未验证项，不把此批扩展为 U03/U09 或 schema 迁移。

### 2026-09-28 / B1i 结果

- 补充真实 PG Prompt 路由验收：一次性 PostgreSQL 17.11 集群、schema v1、应用角色及真实 `PostgresAdapter`，FastAPI 路由以合成身份执行。验证中文文件创建/列出/读取/更新/删除、客户端伪造 owner 不生效、另一用户不能读改删私有文件、同名双用户互不覆盖、未登录/无权限和非法文件名拒绝、共享模板不能由普通用户删除；SQL 查询核对实际 owner 与最终行数。该专项模式退出码 0，成功集群已由既有安全清理器停机并移除。未使用真实用户登录态或真实业务库。
- 普通文件符号链接测试在常规及隔离提权运行下均因当前 Windows 环境不能创建而跳过；现有真实 junction 与模拟父级 reparse 防护通过。U02 的普通 symlink 实物验收仍未完成，不将跳过记作通过，也未修改系统权限。
- 首次常规运行停在 `pg_ctl` restricted-token 错误；隔离提权运行进入业务阶段且上述 Prompt 验收通过，但整套旧 schema 冒烟后来在独立 CLI 初始化场景失败，原因尚未确认，因此不宣称整套便携 PG 冒烟通过。本批以仅执行 U02 专项的 `prompt_only` 模式取得独立通过证据；默认全量模式保持原流程。未发现需要修改生产文件边界或 PG Prompt 逻辑的可复现缺陷。
- 累计 Python 回归在 B1h 列表后加 `tests.test_portable_schema`：**188 项：187 通过、1 跳过**；Node 三文件 **12 项全部通过**。当前 38 个改动文件 UTF-8 无 BOM、31 个 Python AST、Git 跟踪/新增空白检查通过，仅有既有 LF/CRLF 提示。测试日志中的通知异常来自合成失败用例，无真实通知。
- 两份本批失败状态夹具已停机且保留复核，未清理：`.tmp/tests/portable-pg/集成 冒烟-schema-q8w08u37/`（41,091,428 B，972 文件，restricted-token 启动失败）与 `.tmp/tests/portable-pg/集成 冒烟-schema-olqdyuf9/`（220,652,433 B，5,606 文件，后续 schema CLI 场景失败）。第二份含 PG 状态，维持原受保护 ACL；当前 agent 无法直接枚举，项目所有者对该精确目录只读盘点无错误。两者到 2026-10-05 仅复核价值和授权，不自动删除。`.tmp` 常规账号可读 **25,735,794,216 B / 154,862 文件**、11 处枚举错误；另计当前账号不可读的第二份后，已确认下限为 **25,956,446,649 B / 160,468 文件**。项目所有者账号另行全量遍历仍有 21 处访问错误，故不能宣称掌握 `.tmp` 精确总量。F 盘可用 **100,111,081,472 B**。没有清理任何历史夹具、共享缓存或业务数据。
- B1 尚余 U02 普通符号链接实物验收、U03 字段级请求关联/浏览器验证、U09 跨进程/重启持久通知去重及真实 PG 并发。本批不新增依赖、表、迁移、价格 UI，不改变评分/抓取/通知，也未提交、推送或发布。

### 2026-09-28 / B2a 开工

- 生产者：当前聊天；HEAD `2d08472693040368de00b3bbac58244bd537e3b1`，保留 B1a–B1i 未提交改动。拟改文件仅 `docs/UPSTREAM_UPGRADE_PLAN.md`；本批不触碰 ORM、真实库、UI、Launcher 或备份实现。
- 冻结范围：第 5.1–5.3 节的 v2 空结构、稳定任务身份、路由、权限、显式迁移、v1/v2 分版备份恢复及回退；本批只做源码核对与文档校验，不把 U04 标为实现或验收。B1 未验项独立保留，不以其环境缺口无限阻滞 B2 的安全设计和隔离实现。
- 拟验收：核对 `src/storage`、`src/web`、`src/portable/schema.py`、`backup_business.py`、`backup_postgres.py`、`backup_restore.py`、Launcher 计划现状；检查本文件 UTF-8 无 BOM、差异空白和状态，盘点 `.tmp` 与 F 盘可用量。不运行真实迁移、不加载 `.env`/账号/业务数据、不调用平台/模型/通知。
- 临时空间：本批不生成测试夹具或构建产物，新增 0 B；历史 `.tmp` 与 B1i 两份待复核状态夹具均不清理。

### 2026-09-28 / B2a 结果

- 文档契约已冻结在第 5.1–5.3 节，进度表已按 B1h/B1i 实际证据校正。源码核对确认：PG `tasks.id` 为 UUID，现有结果 `(owner_id,item_id)` 唯一且任务外键级联；本地 `config.json` 任务没有稳定 UUID，Web 任务数字 ID 是列表索引；当前同步标准生成发生在任务 PATCH 描述更新；便携初始化版本表只接受 v1，dump/完整备份/恢复均固定 v1 清单与授权策略。因此 B2b 必须分别处理稳定身份、版本化元数据、权限和双向备份兼容，不能直接加 ORM 表。
- 验证：本文件严格 UTF-8 解码通过、无 BOM、无行尾空白；`git diff --check` 退出码 0（仅提示既有 LF/CRLF 转换）；`git status --short` 仅显示既有 B1 改动与本计划文档，没有本批业务源码改动。文档为 `.gitignore` 单文件放行的未跟踪正式文件，仍需后续按用户意愿纳入提交；本批未提交。
- 本批新增临时产物 **0 B**。`.tmp` 当前账号可读下限 **25,735,794,216 B / 154,862 文件**，遍历有 **11 处访问错误**，因此不是精确总量；B1i 两份失败状态夹具保持原登记及 2026-10-05 复核点，未删除。F 盘 `DriveInfo` 可用 **100,111,069,184 B**；`Get-Volume` 因访问被拒未用作证据，已使用只读替代。没有读写真实数据库、配置、登录态或业务结果。
- B2a 是**设计批次完成**，不是 U04 迁移完成。B2b 仍须实现并通过隔离 PG/本地/备份恢复测试；B3–B7 业务功能及整合验收未开始。B1 的 U02 symlink、U03 字段关联/浏览器、U09 跨进程持久去重及 PG 并发仍独立待验。不新增依赖、不改变评分/抓取/通知策略，不推送或发布。

### 2026-09-28 / B2 整批实施开工

- 用户要求直接完成 B2 整批，不以 B2a 文档冻结代替代码交付；HEAD 仍为 `2d08472693040368de00b3bbac58244bd537e3b1`，保留 B1a–B1i 工作区改动。
- 拟改文件：`src/storage/models.py`、`src/storage/interface.py`、`src/storage/local_adapter.py`、`src/storage/postgres_adapter.py`、新增 `src/storage/upstream_local.py`、`src/task.py`、`src/web/models.py`、`src/web/task_manager.py`、`src/config.py`；`src/portable/schema.py`、`backup_postgres.py`、`backup_business.py`、`backup_restore.py`、`provision.py`、`maintenance.py`、必要的 Launcher 版本判断；B2 专项测试与本计划。补入 `src/task.py` 是因为 Web 本地任务写入实际委托它，补入本地旁文件模块是为保留一致性/并发边界；若需其他关联文件，先增补记录并说明。冻结契约仍为第 5.1–5.3 节，不在本批接 U05/U06/U07 业务 UI。
- 验收目标：schema v2 全新初始化、v1 显式原子迁移、重复/并发/故障/未知结构拒绝、应用角色无 DDL、v1/v2 加密业务备份隔离恢复、本地稳定任务身份/版本化旁文件与并发/重启、双用户隔离；相关既有测试与 Launcher/Docker 兼容检查。真实库、真实配置、平台、模型、通知均不触碰。
- 临时空间：首先复用现有隔离 PG 运行时；新合成夹具仅位于 `.tmp/upstream-upgrade/b2-20260928/` 或既有 PG 测试脚本自有受控目录，生产者当前聊天，成功可重建即收尾，失败状态型夹具仅登记复核、不自动删除。预计峰值 < 512 MiB；F 盘可用约 100 GiB，低磁盘阈值未触发。历史夹具不清理。

### 2026-09-28 / B2 未完成代码撤回

- 用户暂停并确认先恢复安全基线。本次仅撤回上一条开工记录中实际写入的 B2 半成品：schema v2/迁移草稿、五张业务表与迁移表模型、v1/v2 备份分支、本地任务稳定 ID 接线和新增的 `src/storage/upstream_local.py` 草稿；保留第 5.1–5.3 节 B2a 契约及所有 B1 改动。没有运行真实迁移，也没有触碰真实数据库、配置、任务、结果或历史夹具。
- `src/portable/schema.py`、`backup_business.py`、`backup_postgres.py`、`backup_restore.py`、`provision.py`、`src/storage/models.py`、`local_adapter.py`、`postgres_adapter.py`、`src/task.py`、两份便携单测与 HEAD 的差异均为零；`src/web/models.py`、`task_manager.py` 仅撤回本轮稳定 ID 行，原有 B1 差异保留。新增草稿文件已删除，不可恢复为工作区文件；正式设计仍在本文中。
- 回撤后 `python -B -m unittest tests.test_portable_schema tests.test_portable_backup_restore -q`：**8 项通过**；未重新运行真实 PG/Launcher/Docker 整包验收。当前 schema 版本仍为 1，不能称 B2 已完成或已具备升级能力。后续须从第 5.1–5.3 节契约重新完整实施与隔离验收，而不是直接沿用本次草稿结论。

### 2026-09-29 / B2b 重新开工（进行中）

- B1 已独立提交为 `e5485bd`；B2 不混入该提交、不推送或发布。当前先固定 v1 表/列/索引清单和 v2 待建表清单，建立迁移与备份恢复的版本分支测试，然后才启用 v2 写入。实施范围仍以第 5.1–5.3 节和上一轮 B2 拟改文件清单为准；若遇新增关联文件，在本记录补充原因。
- 本轮测试只使用合成数据和新建的隔离目标，不触碰真实 `config.json`、`.env`、Cookie、数据库或历史验收夹具。Python 单元测试的自有可重建暂存目录位于 `.tmp/tests/`，预计新增小于 50 MiB；测试结束由测试自身清理，未获授权不清理旧目录。PG 隔离测试启动前另行盘点磁盘和夹具引用。
- 完成判据仍是第 5.3 节的整批门槛；本记录是开工，不表示 U04/B2 已验收。
- 新增 `src/portable/schema_catalog.py` 保存 v1 表/列/索引静态快照和 v2 表名边界；`src/portable/upstream_ddl.py` 保存 002 的 5 张业务表、1 张审计表、索引和固定校验和。同步改动 `tests/portable_schema_pg_smoke.py` 的最小程序包清单，因为 `schema.py` 新增了对静态清单的导入；这是隔离测试夹具关联文件，不改变生产业务行为。尚未接入迁移执行器，DDL 清单存在不表示当前数据库已升级。
- 定向 `tests.test_portable_schema_catalog`、`tests.test_portable_schema`、`tests.test_portable_backup_restore` 共 11 项通过。隔离 PG 冒烟在 `pg_ctl` 启动前失败，stderr 为 `could not create restricted token: error code 87`；因此 v2 DDL **尚未经过真实 PostgreSQL 解析和事务回滚验证**。本轮失败夹具为 `.tmp/tests/portable-pg/集成 冒烟-schema-ta8yexj2/`，约 41,091,428 字节，供测试环境故障复核保留，负责人为本 B2b 任务，2026-10-06 复核；不按“可重建垃圾”自动删除，也不清理历史夹具。
- 全量 Python `unittest discover` 运行 456 项，7 项失败、1 项跳过；7 项均在 `test_portable_config` 子进程导入 `asyncio._overlapped` 时遇到 Windows `WinError 10106`（网络服务提供程序无法初始化），并非本次 schema 清单断言失败。须在可启动受限子进程/PG 的环境复跑，不据此宣称 B2 完成；未进行真实数据库迁移、v2 备份恢复或 Launcher 集成。
- `.tmp` 盘点读取到 155,834 个文件、至少 25,776,885,644 字节；多个历史 `portable-pg` 夹具目录拒绝访问，因此这是**不完整下限**，不是全部实际占用，不能据此判断可清理。F 盘盘点时剩余约 99.38 GB，未触发低磁盘阈值；未删除任何历史文件或失败夹具。

### 2026-09-29 / B2b 显式迁移核心进展（未整批验收）

- 新增 `src/portable/schema_fingerprint.py` 与 `src/portable/upstream_migration.py`，按 PostgreSQL 17 的真实表、列类型/默认值/非空、约束、索引及独立对象计算精确指纹；迁移核心要求匹配 PGDATA 归属标记、实例数据库注释和管理员角色，并在同一 advisory-lock 事务内建表、写 002 校验和、版本改为 2、授权新业务表。重复调用仅接受精确 v2 指纹与单条迁移记录；不在 Web 启动时调用，无面向真实数据的 CLI。
- `tests/portable_schema_pg_smoke.py --migration-only` 是本次新增的独立合成集群入口，避开既有完整冒烟中的间歇性备份/恢复故障；两套新 PG17.11 集群生成相同 v1/v2 指纹。最新隔离测试通过：DDL＋版本更新整笔回滚、v1→v2 实际提交、重复幂等、错误 PGDATA、未知 v1 结构拒绝、建表途中错误回滚、两路并发串行、app 无 DDL 且不能读审计表、probe 只读版本。用例中的维护/备份回调仅为合成证明，**不代表真实 Launcher 租约或备份验证已经接线**。
- B2 仍欠新安装直接 v2、ORM/本地任务稳定 UUID 与旁文件、v1/v2 备份恢复和 Launcher/源码显式迁移入口，亦未完成含新数据的双用户/恢复验收。因此当前正式便携运行仍是 schema v1，不能切换真实实例。之前完整冒烟在旧备份/恢复阶段失败的夹具另行保留，不以本次迁移专项通过替代其验收。
- 随后扩展 public 结构指纹到触发器、RLS 策略及自定义对象，并在迁移前单独拒绝额外应用 schema；两套新隔离集群再次计算出一致的 v1/v2 指纹并更新冻结值。迁移事务现在重申 v1 旧表和 v2 新表的授权，幂等重复调用验证所有业务表的 app/probe 权限与版本表只读；专项复跑通过未知 schema、授权漂移和审计校验和篡改拒绝。`--migration-only` 最终复跑通过，合成 PG17.11 测试成功后自清理。
- 完整 Python 回归在普通主机权限下重跑 456 项，仍为 7 项 `test_portable_config` 子进程 `WinError 10106`、1 项跳过，未新增其他失败。完整 PG 冒烟在既有备份/隔离恢复链路失败，保留本轮夹具 `.tmp/tests/portable-pg/集成 冒烟-schema-lmq5fl5x/`（2,761 文件、101,284,150 字节；负责人 B2b，2026-10-06 复核），不删除或当成 B2 迁移回归结论。当前 B2 源码尚未提交。
- 后续定位确认上述 7 项失败是 `tests/test_portable_config.py` 的隔离子进程环境漏传 Windows `SYSTEMROOT`，并非系统网络栈或便携配置逻辑故障；测试夹具现仅继承该变量。修正后定向 9 项通过，全量 Python 回归 456 项通过、1 项按原条件跳过（退出码 0）。这更新了前述全量测试结果，但不改变完整 PG 冒烟的间歇性恢复失败，也不表示 B2 整批验收完成。
- 再次运行完整 PG 冒烟，归档解密后在 `_inspect_dump_toc` 稳定复现 `database archive contains an unknown index`。根因是 B2 静态 `V1_INDEXES` 从原始 ORM 取了 4 个 `ix_...` 名称，而实际 v1 建库使用 `public` schema 的 metadata，PostgreSQL dump 中为 `ix_public_...`。已用真实隔离 dump 清单核对并修正 4 个静态索引名，单测改为核对实际建库 metadata，并新增真实 v1 索引接受、未知索引拒绝的回归用例；未放宽“未知索引拒绝”策略、未改业务数据或归档格式。修正后完整 PG schema/备份/归档/新集群恢复连续两次通过，v1→v2 隔离迁移专项再次通过，相关单测 26 项通过，全量 Python 457 项通过、1 项按原条件跳过。此结论只闭合本次索引误拒绝；B2 其他交付门槛仍未完成。
- 本轮 3 个失败隔离夹具均已停机，留作环境与索引误拒绝证据：`.tmp/tests/portable-pg/集成 冒烟-schema-4gfmgfo4/`（受限进程启动 PG 失败，972 文件、41,091,428 B）、`集成 冒烟-schema-__2s_zse/`（2,761 文件、101,284,483 B）、`集成 冒烟-schema-tbzf28k_/`（2,761 文件、101,284,557 B）。负责人为当前 B2b 任务，2026-10-06 仅复核，不自动删除；两次成功集群由测试自身清理，历史夹具未动。
- 收尾 `.tmp` 只读盘点可枚举 156,806 文件、25,817,977,072 B，另有 19 处访问错误，因此数值仅为下限而非全部实际占用；F 盘尚余 98,990,575,616 B，未触发低磁盘阈值。未据此清理任何历史或状态型夹具。

### 2026-09-28 / B1 验收补闭环开工

- 生产者：当前聊天；HEAD `4aa9b5aebc6e706870ef4a230669e98f76968b4f`，工作区起点干净。仅处理 U01/U02/U03/U09，不启动 B2 迁移或其他功能批次。
- 首轮拟改文件：本文；若取得可信脱敏搜索请求体，再按第 4 节契约修改 `src/search_requests.py`、`src/scraper.py` 及 `tests/test_upstream_search_requests.py`、`tests/test_upstream_search_call_sites.py`。通知跨进程边界若可在不新增数据库表和依赖的前提下安全闭环，先将存储/权限决策补记于本文，再修改 `src/web/notification_test_guard.py` 和对应专项测试。未知范围不预先施工。
- 冻结决策：默认抓取频率、页数/重试预算、评分、AI 与通知触发条件均不变；只用 fake 外部调用与隔离 PostgreSQL。不读取真实 `.env`、Cookie、业务库，不发真实通知或平台请求；U03 字段名不能凭猜测冻结，U09 不能把单进程缓存宣称为跨进程保证。
- 拟验收：累计 Python/Node 与语法回归、U02 真正隔离 PG Prompt/完整 schema 冒烟的区分、符号链接实物能力检查、U03 字段级反例、U09 重发/并发/重启/跨进程证据。无法实测的项逐项保留未验证，不以所有单元测试通过替代整批签收。
- 临时空间：只使用 `.tmp/upstream-upgrade/b1-acceptance-20260928/` 保存本任务可重建轻量夹具（预计 < 10 MiB，成功即清理），或复用既有 PG 冒烟脚本自身的 `.tmp/tests/portable-pg/集成 冒烟-schema-<随机值>/` 安全边界（单次预计 < 512 MiB）；失败状态夹具只登记并复核，不自动删除。低磁盘阈值及通用 2 GiB 预算仍适用；历史夹具不碰。
- 已知限制：本机普通文件 symlink 创建权限曾导致跳过；U03 可信请求体尚缺；U09 当前去重仅进程内；旧完整 PG schema 冒烟的独立 CLI 阶段曾失败，待复核是否影响 B1。

### 2026-09-28 / B1 验收复核中

- 本地提交 `4aa9b5aebc6e706870ef4a230669e98f76968b4f` 的累计离线回归重新执行：Python 188 项，187 通过、1 跳过；Node 12 项全过；三份相关 JS 语法检查通过。跳过项仍是 Windows 普通文件 symlink 实物创建，隔离提权重试该单项也只能跳过。真实 junction、模拟 reparse、文件权限与失败脱敏测试通过，但不把普通 symlink 实物测试记为通过。
- 完整隔离 PG schema 冒烟重新执行，在已生成加密业务备份后、归档解包恢复阶段返回 `BackupArchiveError`，没有到新的恢复目标和 Launcher 整合阶段。备份归档/业务备份/恢复的 27 项离线单测通过，不足以覆盖此真实集成失败。测试脚本已停止一次性集群，未触碰真实数据库；保留本轮失败状态夹具 `.tmp/tests/portable-pg/集成 冒烟-schema-8s1t05j9/`（50,769,155 B，1,387 文件，提权账号可读枚举 0 错误），2026-10-05 仅复核，不自动删除。此次失败与此前独立 CLI 阶段失败不是同一已定位原因，不能合并描述。
- 源码核对显示当前 `web_server.py`、`src/web/main.py`、`portable_web.py` 均默认启动单个 Uvicorn Web 进程；B1 的可用范围若限定当前部署可依托进程内去重，但跨进程/重启仍无保证。是否将多进程保证延期到 B2 已请求用户确认，不在确认前擅自改验收契约。
- U03 的 host/path/POST 和新请求对象身份绑定、翻页有界等待已通过 fake 测试，但代码明确不解析 POST 页码/筛选字段；可信脱敏载荷尚未取得，已请求样本，不猜测字段、不访问真实平台。
- 用户已同意 B1 按现有单 Web 进程部署验收，跨进程/重启去重进入后续 B2 数据契约；该决定不改变当前通知触发和单进程发送语义。后续若引入多 Web 进程，须先完成持久去重，不能继续沿用此项 B1 验收结论。
- 在完整 PG 冒烟重跑中，曾一次在归档恢复阶段失败；随后 Prompt 专项（含真实 PG 备份/恢复往返）通过；再一次完整运行归档恢复仍失败；最后一次完整运行通过了归档恢复，但停在独立 schema CLI 初始化。因存在两个未定位的集成失败，不宣称完整便携冒烟通过，也不把它们算作 B1 代码回归。为取得脱敏错误类型与阶段，拟增补 `tests/portable_schema_pg_smoke.py` 的 CLI 失败诊断（只在隔离测试失败时写入 `diagnostics/`，逐项替换已登记合成密钥，不输出原始请求），并只在必要时重跑一次。

### 2026-09-28 / B1 验收补闭环阶段结果

- 完整隔离 PG 冒烟的 CLI 失败已定位为测试最小程序包漏复制既有 `src/log_retention.py`，不是生产 schema 初始化缺陷；`tests/portable_schema_pg_smoke.py` 只补该夹具清单。临时的失败诊断写入已撤回，未修改生产代码、schema v1、备份清单或 Launcher。修正后完整 PG schema/Prompt/会话/Web/备份恢复往返连续两次通过；另有一次修正后运行在归档恢复阶段失败，显示该阶段仍有间歇性问题，不以两次通过消除该风险。
- 最终累计离线回归：Python 188 项（187 通过、1 跳过），Node 12 项通过；便携备份归档/业务备份/恢复单测 27 项通过。测试中的通知/备份失败日志来自合成故障用例。U01 按 fake 模型/隔离路由契约验收通过；U09 按用户确认的现有单 Web 进程范围验收通过。U02 普通 Windows symlink 实物测试仍跳过；U03 页码/筛选 POST 字段缺可信样本，仍为实施中。B1 整批不能宣称验收通过；真实平台、真实模型、真实通知、Launcher 整包发行仍未验证。
- 本轮隔离 PG 测试失败状态夹具（由当前聊天生成、集群已停机、2026-10-05 仅复核）：`.tmp/tests/portable-pg/集成 冒烟-schema-8s1t05j9/` 50,769,155 B / 1,387 文件，`集成 冒烟-schema-zy6d3c7k/` 101,271,776 B / 2,759 文件，`集成 冒烟-schema-du3zzru3/` 220,652,610 B / 5,606 文件，`集成 冒烟-schema-hd00wkob/` 220,653,646 B / 5,607 文件，`集成 冒烟-schema-35bi7dpy/` 101,280,222 B / 2,760 文件；提权账号对这些精确路径盘点 0 枚举错误。合计 694,627,409 B；成功集群由现有安全清理器自行收尾。本批没有删除旧夹具或真实业务文件。
- 收尾盘点：`.tmp` 常规账号可读下限 25,735,794,216 B / 154,862 文件，16 处枚举错误（含本轮受保护 PG 失败夹具），不是精确总量；本轮五份失败夹具另以精确路径提权盘点如上，不与可读下限重复相加为精确总量。F 盘可用 99,385,188,352 B，未触发低磁盘阈值。当前仅本文与 `tests/portable_schema_pg_smoke.py` 有未提交差异，UTF-8 严格解码/无 BOM、`git diff --check` 通过（仅 LF/CRLF 提示）；未提交、推送或发布。

### 2026-09-28 / U03 真实搜索只读观察开工

- 用户明确允许使用本人账号扫码测试，关键词采用“无人机”或“xbox”；此前“不访问真实平台”的冻结范围仅对这次 U03 手工搜索观察放开。仍不启动项目监控任务、不读取现有 Cookie/.env、不购买、不发消息、不导出登录态，也不将真实请求原文、令牌或账号信息写入日志。
- 生产者：当前聊天。临时探针放 `.tmp/upstream-upgrade/u03-live-search-20260928/`，只用本机现有 Playwright/Chromium，无新增依赖；预计源码与可重建临时浏览器状态 < 10 MiB，成功后按卫生规则核验并清理自有临时文件。目标是比较初次搜索、筛选、翻页的 POST 字段名及安全的搜索词/页码/筛选值，再决定是否修改生产请求绑定逻辑。若平台登录/风控阻断，不绕过。
- 实测证据：`/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/` 的表单 `data` JSON 包含 `keyword`、`pageNumber`、`propValueStr.searchFilter`、`sortField`、`sortValue`、`extraFilterValue` 等。首次搜索 `keyword=大疆无人机,pageNumber=1`；快捷筛选使 `propValueStr.searchFilter` 出现并改变；翻页到第 2 页时出现 `pageNumber=2`，且有第 1 页请求穿插。仅记录字段名、允许公开的搜索词/页码与筛选指纹，不保存 Cookie、令牌和完整载荷。
- 自动逐项验证：`个人闲置`、`包邮`、`验货宝`、`验号担保`、`超赞鱼小铺`、`全新`、`严选`、`转卖` 八项均可见，点击后发出与基线不同的搜索筛选请求。当前搜索页另有排序项 `新降价`；`新发布` 下仍有 `最新/1天内/3天内/7天内/14天内`。`新降价` 未纳入现有任务配置；它会改变用户选择的排序策略，本次只登记，不改默认排序或任务模型。
- 本小步拟修改 `src/search_requests.py`、`src/scraper.py` 和既有 U03 专项测试：只接受请求体中期望关键词/页码；筛选动作须与上一份响应的筛选语义不同，翻页须与上一份响应的筛选语义相同。字段缺失或无法解析时不猜测，按现有超时/降级分支处理。不加重试、请求或睡眠，不触碰 AI/评分/通知。
- 实施与核验：已按上述范围完成字段级绑定；模拟旧页/旧筛选、错筛选同页码、无效请求体等反例验证通过。真实页面显示 50 页，点击实际下一页箭头后从 `1/50` 变为 `2/50` 且加载结束。自动筛选探针在最后一次导航结果未加载完时报告 `NEXT_UNAVAILABLE`，不把它当成翻页失败证据；下一页的真实 POST 字段来自此前人工点击的脱敏观察。累计 B1 Python 191 项（190 通过、1 项 Windows symlink 权限跳过），Node 12 项通过；未运行完整真实监控任务。`新降价` 只是可选新排序候选，不纳入本次 B1 默认行为。
- 临时探针是本聊天创建的 1 个可重建 Python 文件（6,895 B），成功后已校验任务目录无其他内容并清理，留存 0 B；未保存浏览器登录态或完整请求。历史失败 PG 夹具与其他 `.tmp` 内容未触动。
- 2026-09-29 收尾：价格排序菜单仍提供“价格从低到高/价格从高到低”，既有 UI 选项未失效；`新降价` 为新增候选而非替代项。改动限本文、`src/search_requests.py`、`src/scraper.py`、两份 U03 测试及本轮此前已改的 `tests/portable_schema_pg_smoke.py`；`git diff --check`、所涉文件 UTF-8 无 BOM 检查通过。F 盘可用约 99.39 GB。未提交、推送或发布；B1 的 Windows symlink 实物权限跳过、完整 PG 冒烟间歇性恢复失败及完整真实监控任务仍须单独结案，不因本次 U03 通过而自动签收整批。

### 2026-09-29 / B1 最终验收范围确认

- 用户在普通 PowerShell 运行 `tests.test_upstream_file_safety.ScopedFileTests.test_real_symlink_blocks_read_write_and_listing` 得到 `OK (skipped=1)`，原因是当前普通进程无法创建 symlink；随后在标题显示“管理员: Windows PowerShell”的窗口，使用同一仓库与同一测试命令得到 `Ran 1 test`、`OK`，无跳过。测试输出显示越界路径被拒绝、列表跳过不安全条目。该实物测试已经在具备创建能力的环境通过；普通权限跳过仍如实保留，不把它改写为普通权限下通过。
- 按第 6 节 B1 原定门槛（默认策略不变、fake 外部调用和相关回归通过）签收 U01/U02/U03/U09 小补丁；U09 仅适用用户确认的现有单 Web 进程。完整监控任务端到端、完整 PG 备份冒烟间歇性恢复失败、Launcher/Docker 整合及公开发布属于后续独立验收，不再混作 B1 阻塞项。

### 2026-09-29 / B2 隔离验收继续（未签收）

- 用户要求用隔离数据继续验收到能用，不以发现未完成项目代替验收。本轮先修正本地任务身份测试末尾引用不存在文件的测试错误；补充本地 v2 价格观察日志的跨进程锁、重启后按 `(task_ref,item_id,run_id)` 重建去重、原子替换和损坏尾行拒绝。新增测试覆盖同运行重复、跨运行写入、并发重复、错误 owner 和中断尾行；本地专项 9 项通过。
- 当前未提交的 `src/storage/upstream_local.py` 是便携包中的明确程序资产，打包来源清单只增加该精确路径，不允许其他未知源码混入。`tests.test_portable_bundle` 与本地专项合计 35 项通过；全量 Python 468 项通过、1 项按既有 Windows 普通 symlink 条件跳过。测试的合成失败日志不代表真实通知或备份失败。
- 在普通受限进程运行 v2 PG 冒烟时，`pg_ctl` 因 `could not create restricted token: error code 87` 于启动前失败；在普通主机权限下重跑，`--v2-backup-only` 的新空库、五张表合成数据、加密备份和新集群恢复通过，`--migration-only` 的旧库迁移、事务回滚、并发、权限与指纹专项通过。两者均不代表 Launcher 真实维护/备份证明已经接线。
- 受限进程失败夹具 `.tmp/tests/portable-pg/集成 冒烟-schema-h09x3pon/` 已停机，972 文件、41,091,428 B，作为环境失败证据保留；负责人当前 B2b 任务，2026-10-06 只复核不自动删除。本轮成功 PG 夹具由测试自身清理；其他历史夹具不动。
- 尚未闭合：`config.json` 的所有正常写入路径未共享升级锁和原子提交；本地旁文件尚未接入业务适配器；Launcher 仍按 v1 初始化和校验完成记录，缺真实维护/备份证明及显式迁移入口；v2 启动、双用户业务访问、完整 Launcher/Docker 交付仍未验收。因此 B2 仍不能用于真实数据升级、不能提交为已完成版本。
- `.tmp` 只读盘点：可读下限 157,778 文件、25,859,068,500 B，另有 26 处枚举错误，不能当作精确总量；F 盘可用 98,192,961,536 B，未触发低磁盘暂停。`git diff --check` 通过（仅换行提示）；本轮未删除真实或历史数据、未提交/推送/发布。

### 2026-09-29 / B2 便携整合与部署差异复核（进行中）

- 便携 PG17 路线已用合成数据验收：新装 v2 的真实 Web 首设/登录/重启；v1→v2 事务、回滚、并发、重复调用；五张新表双用户 owner 查询；v1 备份在新隔离目标恢复后由 Launcher 完成备份、显式升级和 v2 重启。最后一条端到端输出 `LAUNCHER_SCHEMA_UPGRADE_E2E=PASS`，但其发行候选早于一次 Python 导入位置修正，必须按最终源码重新冻结并复跑，不能把旧包视作最终制品。
- 服务器 Compose 仍固定 `postgres:15-alpine`，旧数据库没有 `app_schema_version`，`DB_USER` 同时是数据库管理员；便携 002 则要求 PG17、v1 精确指纹、独立 admin/app/probe、Launcher 所属 PGDATA 证明。绝不在 PG15 旧库调用便携迁移器或以 `create_all` 冒充升级。保持现有 PG15 与 Docker 路线，不擅自升主版本；须设计独立、显式、停写且备份可核验的服务器兼容迁移，并在新隔离 PG15 运行后才能签收 B2。当前 Docker daemon 无法连接，尚无 PG15 真实验收。
- 服务器路线后续施工边界：保留 PG15，不原地升级数据库主版本；在隔离 PG15 中先冻结现有无版本表结构指纹，再实现独立管理员迁移入口。入口须明确核验停写、同库已完成且可恢复的备份、数据库/角色归属和未知结构拒绝，使用事务与互斥锁建 v2 空表、版本及校验和；运行账户须与管理员权限分离，不能因为旧 Compose 将 `DB_USER` 设为管理员就跳过 B2 权限门槛。应用启动不得以 ORM `create_all` 自动修补旧库。验收必须覆盖旧卷副本、新空库、失败回滚、重复/并发、双用户、权限和隔离恢复；只允许使用新 Compose project 名、新卷与合成凭据，不挂载正式 `postgres_data` 或 `.env`。这是待实施契约，不是已实现能力。
- U09 用户先前明确将跨进程/重启的人工测试通知请求去重留至 B2。本轮新增共享文件占位：首次发送前持久写入，成功/失败后记录结果；另一进程遇到未完成占位只返回结果未知，绝不立即补发；损坏记录停止发送。未完成占位不自动过期，完成结果 300 秒后可回收，记录上限 512 条。持久目录位于运行数据根 `state/notification-tests/`，便携加密业务备份清单覆盖它；多机器无共享数据根、Docker 本地模式未挂载 `state` 时不宣称跨机/重启保证。未改变自动通知触发条件、原有无 `request_id` 客户端行为或测试渠道配置。
- 本轮离线测试 `python -B -m unittest discover -s tests -p 'test_*.py' -q`：481 项，480 通过、1 项因普通 Windows 文件 symlink 创建权限跳过。新增通知专项 18 项通过，含第二进程占位、重启模拟、损坏记录拒绝；备份目录清单专项覆盖通知记录。测试中的失败日志均为合成故障，无真实通知发送。
- 从最新源码完整构建 Launcher：0 警告、0 错误，`PORTABLE_REAL_STACK=PASS`、`UI_SMOKE_PASS`、启动诊断与端口 UI 通过。冻结候选 `launcher/dist/portable-b2-final-20260929-r1/`，ZIP SHA-256 为 `c1bb680c5670737313c8eeb986da86a62a69eee53a572a2bd92216efdf5a299a`；包仍标记 `preview-integration`。此包的两轮真实宿主启动/停止 `BUNDLE_ACCEPTANCE=PASS`；使用独立合成 v1 加密备份的隔离恢复、备份、002 升级、v2 重启输出 `LAUNCHER_SCHEMA_UPGRADE_E2E=PASS`。合成口令文件仅原创建账号可读，验收进程未输出口令或连接正式数据。
- Docker Desktop 程序曾尝试启动，但 daemon 的 Linux engine 管道仍不存在，`com.docker.service` 未运行；当前会话启动服务被拒绝。因此 PG15 隔离验收仍缺，不能把便携 PG17 成功外推到 Docker/源码部署。没有清理旧候选或状态型失败夹具，未提交、推送或发布。
- 收尾复核：最新 ZIP 为 389,702,754 B，独立重算 SHA-256 与打包回执一致；源码和包内通知去重、通知 API、迁移核心三个文件逐字节哈希相同。新建 `.tmp/build/portable-acceptance/20260929-051810-c76ea5de4da9/` 为 518 文件 / 826,179,585 B，UI/测试资料 `.tmp/tests/portable-acceptance/20260929-051810-c76ea5de4da9/` 为 34 文件 / 2,033,633 B；两者及发行候选供复验，2026-10-06 复核而非自动删除。一次权限不匹配造成的预检夹具仅含空 `target-bundle` 目录，经精确路径、重解析和空目录检查后已移除；未删除成功验收数据或旧失败夹具。`.tmp` 当前账号可读下限 165,529 文件 / 28,499,854,512 B，27 处枚举错误，非精确总占用；F 盘可用 92,460,916,736 B。54 个改动/新增文件严格 UTF-8 无 BOM，`git diff --check` 无空白错误（仅既有 LF/CRLF 提示）。

### 2026-09-29 / Docker 可用后的 B2 PG15 服务器补验（未整批签收）

- Docker 29.8.0 已可连接。只使用固定隔离容器与独立卷 `qb-b2-pg15-fixture-20260929-1`，PG15 映射 `127.0.0.1:59538`；未访问正式 Compose project、`.env`、`postgres_data` 或真实账号。现有合成 `qb_b2_legacy` 的显式 CLI 升级和重复调用、`qb_b2_restored` 的迁移前备份隔离恢复及用户/任务核对通过。
- 独立服务器迁移器仅接受 PG15 严格旧/v2 指纹，先核验停写确认、管理员身份、同库备份 SHA/PG15 TOC、其他客户端和新应用角色；事务中上锁、建空业务表和审计/版本表、分配受限角色。新增 `qb_b2_negative` 合成库验证错误 SHA、错误库名、未知表拒绝，以及建表后注入故障时表和角色全部回滚；`qb_b2_concurrent` 验证并发调用不会产生半结构，后续单次重试可完成。两个库只含合成数据与各自备份，暂留作复核，不按临时垃圾自动删除。
- 已有镜像中的 Python 依赖配合**只读挂载当前源码**，在 Linux 测试容器连接隔离 PG15，输出 `SERVER_PG15_V2_RUNTIME=PASS`；验证低权限角色拒绝建表/读取迁移审计、管理员不能用作 v2 Web 角色，以及两个用户各自读取。另以合成 `.env` 验证容器内显式受限应用 DSN 优先于旧 dotenv 值。合成 `docker compose config` 分别通过旧默认和 v2 管理员/应用角色分离；未把这称作已构建最新 Docker 发行镜像。
- 完整 Python 回归首次因新服务器专用模块未登记于便携打包来源而有 1 项失败；已明确将它排除在便携包，复跑 481 项通过、1 项按当前 Windows 普通 symlink 权限跳过。`docs/SERVER_PG15_SCHEMA_V2.md` 固定部署、停写、备份、角色与回退顺序；README 不再复制一份易漂移的服务器 YAML。
- 当前仍未触碰真实库或发布。最新源码包含新服务器配置与便携打包来源调整，先前 `portable-b2-final-20260929-r1` 候选已不是最新快照；最终便携 ZIP 与正式 Docker 镜像的重建/对应启动复验仍是 B2 放行门槛。

### 2026-09-29 / B2 源码与隔离合成验收收口

- 服务器恢复后升级链路补齐：原 PG15 自定义备份已在 `qb_b2_restored` 隔离库恢复；再次从该 v1 库生成同库备份、核对 SHA/TOC 后，显式 CLI 升至 v2，前后均为 2 名合成用户、2 条任务；重复调用返回 `already_applied`。新空库按旧结构建表后显式升级的合成路径、错误备份/未知结构拒绝、注入故障回滚和并发保护亦通过。
- 新空库单独补测：在 `qb_b2_fresh` 先创建空 PG15 库，按旧版 ORM 建 v1 表并核对严格旧指纹与 0 用户；完成独立 PG15 备份和摘要后由显式 CLI 升 v2，复核版本 2、0 用户、0 任务、0 新业务记录。隔离容器重启后 Docker 把临时宿主端口从 `59538` 动态改为 `64176`；一次误连旧端口被拒，改用实际端口后通过，非数据库故障。测试结束容器再次正常停止，卷与备份保留。
- 最终便携候选为 `launcher/dist/portable-b2-pg15-20260929-r3/`，ZIP SHA-256 `43364a8d695b2af23c0bba045d32db61e77593400b25fe679bc3bc3656a9f27e`，8,089 个文件、源文件估计 985,623,153 B；打包器完成 manifest/hash/ZIP 校验。此包的 `BUNDLE_ACCEPTANCE=PASS` 和 `LAUNCHER_SCHEMA_UPGRADE_E2E=PASS` 均为本候选实测，不借用旧 r1/r2 结论。仍为 `preview-integration`，不是公开发行包。
- 从本轮源码构建本地固定标签 Docker 镜像（未推送、未替换 `latest`）；镜像内隔离 PG15 双用户/受限权限与合成 `.env` 优先级通过，随后真实 Web 容器 `/health` 返回 healthy，临时 Web 容器已停止并自动移除。服务器 Compose 的旧默认和 v2 管理员/应用角色分离均用合成环境文件渲染通过；未启动或修改正式 Compose project。
- 本地 Docker Compose 显式持久挂载 `./state:/app/state`；两个独立、断网的一次性容器复用合成目录，第一次人工测试通知 ID 占位、第二次返回 pending，未调用通知供应商。对既有本地 Docker 容器，挂载会遮蔽旧容器内部 `state`，README 已要求切换前停写并备份/迁出，代码不自动搬运用户状态。
- 最终源码全量 Python 回归运行 481 项：480 通过、1 项按当前普通 Windows symlink 创建权限跳过；PG15 专项、Launcher 和 Docker 单独验收如上。B2 在**源码与隔离合成数据**范围签收；正式数据迁移、干净 Windows 原生使用、真实平台抓取/AI/通知、公开发行和 B3–B7 功能均不包含在本次结论。
- PG15 隔离数据库容器 `qb-b2-pg15-fixture-20260929-1` 已正常停止；独立卷与 5 份合成 PG15 备份保留供复核（2026-10-06 复核，不自动删除），临时 Web 容器均已停止并自动移除。最终 Docker 本地测试标签为 `qb-b2-pg15-20260929-r4:local`，仅本机存在；r3 完成源码权限测试后，r4 按最终工作树重建并通过 PG15 角色/双用户及 `/health`。`.tmp/tests/server-pg15-20260929-1/` 中 5 份 dump、合成 Compose/.env 与通知占位约 194 KiB；其他旧夹具和预览候选未清理。
- 收尾卫生核对：本轮 17 个改动/新增文件严格 UTF-8 无 BOM，`git diff --check` 无空白错误（仅 LF/CRLF 提示）。`.tmp` 当前账号可读下限 166,641 文件 / 30,156,433,917 B，另有 27 处枚举错误，不能声称精确总量；F 盘可用 87,771,631,616 B，未触发低磁盘暂停。没有提交、推送、发布或清理历史业务数据。

### 2026-09-29 / B3 U05 施工边界（进行中）

- 本批只接结果视图的屏蔽、黑名单和筛选偏好；不改抓取、AI、训练、通知、旧永久删除路由或评分。隐藏按本人商品 ID 跨任务生效；黑名单默认具体任务，个人全局必须显式勾选。
- 规则首版上限 50 条，模式为大小写不敏感关键词、英数字边界及“正则别名”。别名仅接受 1–8 个以 `|` 分隔的纯字面词，每项至多 64 字符，可选整体 `^`/`$` 锚点；不执行任意用户正则。模式总长不超过 128 字符，匹配输入按字段有界；不支持的元字符保存时 400 拒绝。预览最多取前 100 条、最多返回 20 个样例，标明抽样数，不把零命中解释为全量零命中。
- 列表、总数、视图统计与 CSV 导出走同一服务端过滤函数，屏蔽/黑名单先于分页；默认隐藏，`include_hidden` 显式展示原因。单次结果读取最多 50,000 条，超出返回 429，不静默截断。视图导出不等于删除或原始业务数据导出；CSV 公式前缀做转义。
- 偏好仅保存结果页白名单字段、合法稳定任务 UUID 和排序；旧浏览器的未隔离文件键不再读取。新结果管理 API 需要已认证的 `results` 类别；本地要求显式 v2 旁文件，PG 要求 schema v2，不自动迁移真实数据。
- 本批测试只用 `.tmp/tests/b3-result-management/` 下自清理的合成临时目录，预估小于 20 MiB。PG 测试若复用 B2 夹具，只创建新的 B3 合成数据库，不改 B2 既有库与备份；验收前仍需接口、UI、PG 双用户、并发与全量回归，不因单元测试通过而签收。

### 2026-09-29 / B3 U05 第一轮实现与隔离验证

- 已接入本地 v2 旁文件和 PG15 v2 的屏蔽/规则/偏好读写；屏蔽与规则同锁/同事务快照读取，写入有界、规则与偏好按修订号防并发覆盖。结果列表、筛选选项、视图统计、分页和 CSV 导出共用先屏蔽/黑名单后分页的服务端视图；旧删除接口保留。
- 页面新增屏蔽/恢复、显式显示屏蔽项、黑名单预览/新增/编辑/停用/删除、视图统计、分页和 CSV 导出；偏好由服务端按 owner 保存，失效任务/筛选回退，不再读写旧的未隔离浏览器文件键。未新增导航、依赖、评分或任何抓取/通知行为。
- 隔离本地 HTTP 合成测试覆盖屏蔽/恢复、分页/总数/导出一致、任务规则、旧永久删除回归、API 修订冲突；独立 PG15 `qb_b3_result` 从已验证的 B2 合成 `qb_b2_restored` 克隆，使用 `SET ROLE qb_b2_restored_app` 受限角色验证双用户隔离、持久读写与并发偏好 CAS。B2 原库及备份未修改；B3 库留存供复核，负责人为本 B3 任务，2026-10-06 复核，不自动删除。测试后原隔离容器已正常停止。
- Python 全量回归最近一次运行 492 项，490 项通过、2 项跳过（普通 Windows symlink 权限和可选 PG 专项环境变量）；PG 专项另行显式运行 1 项通过；Node 15 项通过，JS 语法检查通过。便携构建来源清单已登记本批 3 个新增模块，便携来源测试通过；**尚未从本轮源码重新构建并启动便携 ZIP 或 Docker 镜像**。
- 尝试按照 Playwright CLI 技能进行真实浏览器交互检查：`npx` 存在，但拉取 CLI 时 npm registry 返回 `EACCES`，未运行浏览器；不安装新依赖、不用真实账号补测。静态 Node 页面测试不能代替视觉和交互验收，故 B3 尚未签收。
- 本批新建 `.tmp/tests/b3-result-management/` 自清理测试目录当前 0 文件；未删除历史夹具。`.tmp` 当前账号可读下限 166,642 文件 / 30,156,472,612 B，另有 27 处枚举错误，非精确总占用；F 盘剩余 87,748,734,976 B，未触发低磁盘暂停。未提交、推送或发布。

### 2026-09-29 / B3 U05 隔离真实运行验收

- 真实 Web 以独立本地 v2 存储、合成登录和 25 条合成商品启动；浏览器未替换 `fetch`。分页 20/5、屏蔽后刷新与 Web 重启持久、任务 A 黑名单预览/新增与 22 条命中、任务 B 的 3 条不受影响、筛选偏好重启保留均通过。真实 CSV 接口对任务 A 导出 0 条商品、任务 B 导出 3 条，与页面一致。任务均禁用，未调用真实闲鱼、AI 或通知。旧配置加载器会搜索源码位置的 `.env`，验收入口已显式禁用该读取并断言隔离路径；首次登录失败后立即停止旧测试进程，没有启动业务任务。该自建 Web 夹具约 44.4 MB，验收后已精确清理。
- 隔离 PG15 专项使用受限应用角色通过双用户、持久读写及并发偏好冲突。另从 `qb_b3_result` 克隆合成库，在副本写入屏蔽、规则和偏好后做 PG15 自定义备份，再恢复到新的空合成库；三类数据逐项与源库一致，另一用户不可见。PG17 的 `pg_dump` 产物恢复到 PG15 时因 `transaction_timeout` 不兼容而失败，改用容器内匹配版本 PG15 工具成功；失败尝试未接触原库或正式库。PG15 备份留在 `.tmp/tests/b3-backup/20260929/`，SHA-256 为 `3d2c0ee4dff9d587e26d80b4d97c9242fcda0253b50fe6af8c45bdad1a67e336`；两个新合成数据库与诊断备份供 2026-10-06 复核，不自动删除，容器已停止。
- 从当前源码重新发布 Launcher，构建 0 警告、0 错误，UI/启动诊断通过；生成 `launcher/dist/portable-b3-real-20260929-r1/` 及 ZIP，包内 B3 后端与前端 7 个关键模块与工作树逐字节哈希一致。包内真实 Host→PostgreSQL→Web 的双周期启动/停止得到 `BUNDLE_ACCEPTANCE=PASS`。ZIP 为 389,718,370 B，SHA-256 为 `58e188d62677b92a070bb7dc19a54097a09ff1eb16acbd681372f8d646e9f2e1`，仍标记 `preview-integration`，未公开发布。该验收不是干净 Windows、正式数据升级或真实平台抓取/AI/通知的 B7 放行。
- 已知交互点：只在“任务名称”高级筛选选择任务，不会替代上方“结果文件”作为黑名单规则归属；界面会提示先选具体结果文件或显式选择本人全部任务。功能没有静默错绑，但提示易混淆，按用户要求留到人工 UI 验收后决定优化。本批先提交现有实现，不以此宣称人工 UI 已签收。
- Python 全量 492 项中 490 通过、2 项按环境条件跳过；PG15 专项另测通过，Node 15 项与 JS 语法检查通过。`git diff --check` 无空白错误，仅有既有 LF/CRLF 提示。`.tmp` 当前账号可读下限 31,733,127,731 B，另有 27 处历史枚举拒绝，F 盘可用 84,657,213,440 B；本轮新建的可重建构建目录及预览候选留存到 2026-10-06 复核，不自动删除，未清理历史数据。

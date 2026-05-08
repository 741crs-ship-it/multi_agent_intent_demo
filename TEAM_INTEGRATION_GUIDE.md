# AI 财小资团队联调说明

本文档用于团队内部对齐：谁负责什么、怎么跟 Python Agent 侧联调、当前能联到什么程度、还缺哪些字段。

## 1. 

当前 Python Agent 侧已经具备：

- 统一入口：`AgentService.handle_user_message()`
- 统一返回结构：`reply`、`session_id`、`code`、`need_user_input`、`tasks`、`task_summary`
- 多轮上下文和历史会话
- 意图识别和 Agent 调度
- 转账缺字段追问
- 产品推荐/购买多轮流程框架
- 风控前置
- 真实业务接口占位层

当前还需要其他模块配合确认：

- Java/前端最终是函数调用还是 HTTP 调用。
- 产品接口字段和返回数据。
- 多模态附件、图片、语音的传参方式。
- 内网大模型接口地址、鉴权和返回格式。

## 2. 推荐整体链路

建议团队先按下面链路联调：

```text
前端
  -> Java 或服务层
  -> Python AgentService.handle_user_message()
  -> 意图识别 / 追问 / Agent 编排
  -> business_clients.py 或后续下游智能体
  -> Python 返回统一 dict/JSON
  -> Java 或服务层
  -> 前端展示 reply
```

一句话理解：

```text
前端负责展示，Java 负责转发和系统集成，Python 负责理解用户问题并编排 Agent，下游业务接口负责提供真实数据和真实交易能力。
```

## 3. 各模块怎么接

### 3.1 Java / 服务层

Java 侧建议先做转发和会话保持，不需要拆意图。义东如果希望 HTTP 调用，可以直接接 Python 提供的标准库 HTTP 服务。

启动 HTTP 服务：

```powershell
.\run_http.bat
```

默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

聊天接口：

```text
POST http://127.0.0.1:8000/api/chat
Content-Type: application/json
```

请求示例：

```json
{
  "user_input": "帮我查一下余额"
}
```

多轮请求示例：

```json
{
  "user_input": "我要转账100元",
  "session_id": "上一轮返回的 session_id"
}
```

需要传给 Python：

| 字段 | 是否必填 | 说明 |
|---|---:|---|
| `user_input` | 是 | 用户本轮输入原文 |
| `session_id` | 否 | 首轮不传，后续传 Python 上轮返回的 `session_id` |
| `user_id` | 后续可选 | 用户标识，接真实账户时需要 |
| `channel` | 后续可选 | 来源渠道，例如 web、mobile |

需要从 Python 接收并处理：

| 字段 | Java 处理方式 |
|---|---|
| `reply` | 原样给前端展示 |
| `session_id` | 保存并在下一轮传回 Python |
| `code` | 判断本轮状态 |
| `need_user_input` | 如果为 true，说明等待用户补充、选择或确认 |
| `task_summary` | 联调排查时看每个 Agent 是否执行 |

Java 侧暂时不要做：

- 不要自己判断用户是查余额还是转账。
- 不要自己决定调用哪个 Agent。
- 不要把大模型输出加工后再让 Python 二次理解。

如果 HTTP 联调失败，先按下面顺序排查：

- `GET /health` 是否成功。
- Python 服务是否已经启动，端口是否是 8000。
- Java 访问的是不是同一台机器的 `127.0.0.1`。如果不是同一台机器，不能用 `127.0.0.1`。
- 是否被内网防火墙或安全策略拦截。
- 请求头是否是 `Content-Type: application/json`。
- 请求体是否是合法 JSON。

### 3.2 前端对话模块

前端先按纯文本链路联调。

前端需要做：

- 用户输入后调用 Java 或 Python 包装服务。
- 展示返回的 `reply`。
- 保存并复用 `session_id`。
- 当 `need_user_input=true` 时，继续让用户输入下一句话，不要新建会话。
- 历史会话使用 `list_sessions()` 的结果展示。

前端第一批可测场景：

```text
帮我查一下余额
我要转账100元
给张三转账100元，工商银行，账号622200001111
我想买理财
低风险 3个月 1000元
选第1个
确认
```

附件上传、语音输入可以第二批接入。建议先让附件/语音模块输出文本或文件 ID，再传给 Python 外层接口。

### 3.3 产品 / 存款接口模块

产品接口优先对齐 `business_clients.query_products()`。

建议提供字段：

| 字段 | 说明 |
|---|---|
| `product_id` | 产品唯一编号 |
| `name` | 产品名称 |
| `risk_level` | 风险等级 |
| `term` | 期限 |
| `expected_yield` | 参考收益率 |
| `currency` | 币种 |
| `min_amount` | 起购金额 |
| `settlement_account` | 申购或划款账号 |
| `status` | 产品状态 |
| `source` | 数据来源 |

需要产品侧确认：

- 哪些字段必填。
- 哪些字段可能为空。
- 风险等级、产品状态等码值表。
- 是否分页。
- 一次最多返回多少条。
- 如果字段来自中台，字段名和实际取值来源是什么。

### 3.4 推荐 / 多模态模块

推荐和多模态模块可以作为 Python Agent 侧的下游能力接入。

推荐模块建议提供：

| 输入 | 输出 |
|---|---|
| 用户问题、最近上下文、可选业务标签 | 推荐问题列表、推荐理由、置信度 |

多模态模块建议提供：

| 输入 | 输出 |
|---|---|
| 文件 ID、文件类型、文件地址或上传结果 | 解析后的文本、图片摘要、处理状态 |

建议附件字段：

```json
{
  "attachments": [
    {
      "file_id": "F001",
      "file_name": "交易流水.png",
      "file_type": "image",
      "file_url": "内网文件地址或文件ID",
      "parsed_text": "多模态模块解析后的文字",
      "status": "parsed"
    }
  ]
}
```

当前 Python 核心入口还没有正式消费 `attachments`，所以今天联调建议先跑纯文本链路。附件、多模态和上下文压缩可以作为第二阶段联调。

## 4. 状态码怎么理解

| code | 意思 | 调用方动作 |
|---|---|---|
| `OK` | 本轮处理完成 | 展示 `reply` |
| `NEED_MORE_INFO` | 信息不够 | 展示 `reply`，等待用户补充，同一 `session_id` 继续 |
| `NEED_USER_SELECTION` | 需要用户选择 | 展示候选项，等待选择 |
| `NEED_CONFIRMATION` | 需要用户确认 | 等用户回复确认或取消 |
| `WORKFLOW_CANCELLED` | 用户取消流程 | 结束当前流程 |
| `NO_EXECUTABLE_TASK` | 没识别出可执行任务 | 展示兜底回复 |
| `EMPTY_INPUT` | 空输入 | 提示重新输入 |

## 5. 联调测试清单

第一阶段：纯文本基础链路。

- Java/调用方能调用 `handle_user_message()`。
- 前端能展示 `reply`。
- 前端或 Java 能保存 `session_id`。
- 连续两轮输入能进入同一会话。
- `need_user_input=true` 时不会新建会话。

第二阶段：业务流程。

- 查余额。
- 转账信息完整时执行风控和转账。
- 转账信息缺失时触发追问。
- 产品推荐流程能追问信息、返回候选产品、选择产品、二次确认。
- 历史会话能展示和删除。

第三阶段：真实接口替换。

- 替换产品查询接口。
- 替换余额接口。
- 替换风控接口。
- 替换转账/交易提交接口。
- 替换内网大模型接口。

第四阶段：多模态和上下文。

- 附件上传和展示。
- 图片/文件解析结果传给 Python。
- 语音转文字结果传给 Python。
- 上下文压缩策略对齐。
- 长上下文和大图片边界测试。

## 6. 当前同事模块对应关系

| 模块 | 当前汇报重点 | 与 Python Agent 侧联调点 |
|---|---|---|
| Java / 服务层 | 问接口、问输出流转 | 按 `AgentService` 入参和返回结构接，先保持 `session_id` |
| 前端对话 | 开关、问答、历史、详情 | 展示 `reply`，保存 `session_id`，处理 `need_user_input` |
| 产品/存款接口 | 产品接口文档、字段来源、测试数据 | 对齐 `query_products()` 字段，提供可用 mock 或测试数据 |
| 推荐功能 | 推荐输出不稳定、提示词调优 | 后续作为下游推荐能力接入，先确认输入输出结构 |
| 多模态附件 | 上传、回显、上下文封装 | 第二阶段对齐 `attachments` 字段和 `parsed_text` |
| 上下文压缩 | 设计流程、输出逻辑 | 当前 Python 有最近 5 轮上下文，摘要压缩后续再加 |

## 7. 团队的联调口径

Python Agent 侧已经提供统一联调入口 `AgentService.handle_user_message(user_input, session_id=None)`。调用方首轮传用户原文即可，Python 返回 `reply`、`session_id`、`code`、`need_user_input`、`task_summary` 等字段；后续多轮对话必须把上轮返回的 `session_id` 传回来。

如果需要 HTTP，启动 `run_http.bat`，调用 `POST /api/chat`。当前建议先做纯文本基础联调：Java/前端只负责传用户原文、保存会话 ID、展示 `reply`，不要在 Java/前端侧拆意图或决定 Agent 顺序。Python 侧负责意图识别、追问、Agent 编排和结构化返回。

产品、余额、风控、转账等真实业务接口后续统一替换 `agent_project/business_clients.py`；内网大模型统一替换 `agent_project/llm_client.py`。这样可以保证迁移内网时不维护两套业务代码。

# AI 财小资 Python 侧联调接口文档

本文档说明 Python Agent 侧如何被 Java、前端、多模态、产品接口等模块调用。当前接口设计目标是：外网 demo 可运行，内网迁移少改代码，调用方不需要理解内部 Agent 编排细节。

## 1. 当前可联调范围：

- 用户输入进 Python，Python 返回统一结构。
- 支持单轮问答、多轮会话、历史会话。
- 支持余额、转账、产品问答、闲聊兜底等基础意图。
- 支持转账缺字段追问。
- 支持理财产品推荐/购买的多轮流程框架。
- 支持风控前置和自动补风控。

暂不代表已完成真实生产接入：

- 真实内网大模型接口待接入 `llm_client.py`。
- 真实产品、余额、转账、风控接口待接入 `business_clients.py`。
- 附件、图片、语音等多模态字段需要与前端/多模态模块继续对齐。
- HTTP 服务形式尚未固定；当前稳定入口是 Python 函数。

## 2. 推荐调用入口

核心入口：

```text
agent_project/service_api.py
```

调用类：

```python
AgentService
```

主方法：

```python
handle_user_message(user_input: str, session_id: str | None = None) -> dict
```

含义：

| 参数 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| `user_input` | `str` | 是 | 用户本轮输入的原文 |
| `session_id` | `str \| None` | 否 | 会话 ID。首轮可不传，第二轮开始传回上一次返回的 `session_id` |

返回值是普通 Python `dict`，可以直接转成 JSON 给 Java 或前端。

## 3. 最小调用示例

如果调用方和 Python 代码在同一个工程内：

```python
import sys

sys.path.append("agent_project")

from service_api import AgentService

service = AgentService()

result = service.handle_user_message("帮我查一下余额")

print(result["reply"])
print(result["session_id"])
```

调用方最少只需要关心：

```text
reply：展示给用户看的回复
session_id：下一轮继续传回来
code：本轮状态
need_user_input：是否还需要用户补充信息
```

## 4. 多轮对话示例

多轮对话必须保留并传回 `session_id`。

```python
service = AgentService()

first = service.handle_user_message("我要转账100元")
session_id = first["session_id"]

second = service.handle_user_message(
    "收款人张三，工商银行，账号622200001111",
    session_id=session_id,
)

print(first["code"])
print(first["reply"])
print(second["reply"])
```

第一轮因为信息不全，会返回：

```json
{
  "code": "NEED_MORE_INFO",
  "need_user_input": true,
  "reply": "为了继续转账，请补充：收款人名称、收款账号、目标银行。"
}
```

第二轮继续传同一个 `session_id`，Python 会把它当成同一段对话继续处理。

## 5. 返回字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | `bool` | 本轮接口是否正常处理 |
| `code` | `str` | 状态码，见第 6 节 |
| `message` | `str` | 接口处理说明 |
| `request_id` | `str` | 本轮请求 ID，便于排查 |
| `session_id` | `str` | 当前会话 ID |
| `session_created` | `bool` | 本轮是否新建会话 |
| `session` | `dict \| None` | 当前会话摘要 |
| `reply` | `str` | 展示给用户的回复文本 |
| `need_user_input` | `bool` | 是否需要用户继续补充、选择或确认 |
| `tasks` | `list` | 本轮识别出的任务列表 |
| `task_summary` | `list` | 任务执行摘要，联调时优先看这个 |
| `results` | `dict` | 各 Agent 原始执行结果 |
| `context` | `dict` | 执行后的上下文数据 |
| `logs` | `list` | 调度日志 |
| `recent_context` | `list` | 当前会话最近上下文 |
| `pending_workflow` | `dict \| None` | 当前是否存在未完成流程 |
| `clarification` | `dict \| None` | 追问信息，只有需要追问时重点关注 |
| `workflow_completed` | `bool` | 本轮是否完成了一个复杂业务流程 |

## 6. code 状态码

| code | 含义 | 调用方处理方式 |
|---|---|---|
| `OK` | 处理成功 | 展示 `reply` |
| `EMPTY_INPUT` | 用户输入为空 | 提示用户重新输入 |
| `NO_EXECUTABLE_TASK` | 没有可执行任务 | 展示 `reply`，可引导用户换个说法 |
| `NEED_MORE_INFO` | 信息不完整，需要用户补充 | 展示 `reply`，等待下一轮，继续传同一 `session_id` |
| `NEED_USER_SELECTION` | 需要用户选择候选项 | 展示 `reply`，等待用户选择，继续传同一 `session_id` |
| `NEED_CONFIRMATION` | 交易前需要二次确认 | 展示 `reply`，等待用户确认或取消 |
| `WORKFLOW_CANCELLED` | 用户取消流程 | 展示 `reply`，结束当前流程 |
| `SESSION_NOT_FOUND` | 会话不存在 | 提示重新开始会话 |

调用方通用处理规则：

```text
始终展示 reply。
如果 need_user_input=true，等待用户下一轮输入，并继续传同一个 session_id。
如果 code=OK，本轮处理完成。
如果 pending_workflow 不为空，表示当前会话存在未完成业务流程。
如果 workflow_completed=true，表示本轮完成了一个复杂业务流程。
```

## 7. Java / HTTP 包装建议

当前已提供一个只依赖 Python 标准库的 HTTP 包装层：

```text
agent_project/http_server.py
```

启动方式：

```powershell
.\run_http.bat
```

默认地址：

```text
http://127.0.0.1:8000
```

如果 Java 端需要 HTTP 服务，优先使用这个入口。HTTP 层只负责收发 JSON，内部仍然调用 `AgentService.handle_user_message()`，Agent 编排不改。

### 7.1 健康检查

```text
GET /health
```

返回示例：

```json
{
  "success": true,
  "code": "OK",
  "message": "service healthy"
}
```

### 7.2 聊天接口

```text
POST /api/chat
Content-Type: application/json
```

请求体：

```json
{
  "user_input": "先查余额再转账",
  "session_id": "可选，首轮不传"
}
```

响应体：直接返回 `handle_user_message()` 的 dict/JSON。

首轮示例：

```json
{
  "user_input": "帮我查一下余额"
}
```

第二轮示例：

```json
{
  "user_input": "我要转账100元",
  "session_id": "上一轮返回的 session_id"
}
```

### 7.3 历史会话接口

```text
GET    /api/sessions?limit=20
POST   /api/sessions
DELETE /api/sessions/<session_id>
```

重要约定：

- Java 不需要自己拆意图。
- Java 不需要自己决定调用哪个 Agent。
- Java 只需要把用户原文、会话 ID、用户身份信息传给 Python。
- Python 返回 `reply` 和结构化字段后，Java 负责转给前端展示或继续流转。

## 8. 多模态 / 附件建议字段

当前核心入口正式入参只有 `user_input` 和 `session_id`。如果前端或多模态模块需要传附件，建议后续扩展为外层 HTTP 字段，不直接改内部 Agent 编排。

建议字段：

```json
{
  "attachments": [
    {
      "file_id": "F001",
      "file_name": "交易流水.png",
      "file_type": "image",
      "file_url": "内网文件地址或文件ID",
      "parsed_text": "多模态模块提取出的文字",
      "status": "parsed"
    }
  ]
}
```

联调优先级建议：

1. 先联通纯文本问答。
2. 再联通附件上传和展示。
3. 再让多模态模块把图片/文件解析结果作为 `parsed_text` 传入或拼入 `user_input`。
4. 最后再做图片尺寸、上下文长度、压缩策略等专项测试。

## 9. 产品接口建议字段

产品接口建议先对齐以下字段，方便替换 `business_clients.query_products()`：

| 字段 | 说明 |
|---|---|
| `product_id` | 产品唯一编号 |
| `name` | 产品名称 |
| `risk_level` | 风险等级，例如 low/medium/high 或行内码值 |
| `term` | 产品期限 |
| `expected_yield` | 参考收益率 |
| `currency` | 币种 |
| `min_amount` | 起购金额 |
| `settlement_account` | 申购/划款所需结算账号 |
| `status` | 产品状态，例如可售、停售 |
| `source` | 数据来源，便于排查 |

如果字段取不到，需要产品接口提供方明确：

- 字段是否必填。
- 字段为空时 Python 是否允许兜底。
- 字段码值含义。
- 是否需要分页。
- 一次最多返回多少个产品。

## 10. 真实业务接口替换位置

真实接口统一替换在：

```text
agent_project/business_clients.py
```

当前预留函数：

| 函数 | 用途 | 后续替换方向 |
|---|---|---|
| `query_balance` | 账户余额查询 | 接账户/余额服务 |
| `query_products` | 产品查询和筛选 | 接产品中心、理财或存款产品服务 |
| `run_risk_check` | 风控校验 | 接风控服务 |
| `submit_transfer` | 转账/付款提交 | 接支付/转账服务 |
| `submit_product_purchase` | 产品购买提交 | 接理财购买/申购服务 |

迁移原则：

- 尽量只替换 `business_clients.py` 的函数体。
- 不改 `AgentService.handle_user_message()` 的入参和返回字段。
- 不在代码里写死内网 key、token、地址。
- 模型接入只改 `llm_client.py` 或环境变量。

## 11. 历史会话接口

创建会话：

```python
service.create_session()
```

查询历史会话：

```python
service.list_sessions(limit=20)
```

删除会话：

```python
service.delete_session(session_id)
```

当前历史会话支持：

- 最近 20 条排序。
- 今天、近 7 天、近 30 天、近半年、更早分组。
- 最近 5 轮上下文参与意图识别。

## 12. 建议联调顺序

1. Java 或调用方先跑通 `AgentService.handle_user_message()`。
2. 前端展示 `reply`，并保存 `session_id`。
3. 验证 `need_user_input=true` 的追问场景。
4. 验证历史会话列表和删除。
5. 产品接口提供方对齐产品字段。
6. 多模态模块对齐附件字段和解析文本传递方式。
7. 内网替换真实模型和真实业务接口。
8. 做端到端回归测试。

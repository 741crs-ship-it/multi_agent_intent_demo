# AI Caixiaozi Agent Demo

这是一个用于银行企业内网多 Agent 系统的 Python demo。当前目标不是做完整前端页面，而是先把 Python 侧的核心能力打通：意图识别、Agent 编排、风控前置、会话上下文、历史对话、模型调用适配和科联调入口。

核心代码在 `agent_project/`，根目录只保留联调、迁移和本机运行需要的文件。

## 当前进度

已完成：

- Python 3.12.3 环境和项目 `.venv`
- 核心测试 `PASS=22, FAIL=0`
- 简单意图识别：余额、转账、产品问答、闲聊兜底
- 多 Agent 调度：按 `depends_on` 自动执行
- 转账前置风控：模型或规则漏掉风控时，调度层会自动补 `auto_risk`
- 最近 5 轮上下文：用于意图识别和多轮对话
- 最近 20 条历史会话：创建、命名、排序、删除、持久化
- 统一模型调用入口：`llm_client.call_llm(prompt)`
- 真实业务接口占位层：`business_clients.py`
- 追问单元：`clarification_unit.py`，用于调用智能体前检查信息是否完整
- 科联调入口：`service_api.AgentService`
- HTTP 联调入口：`http_server.py`，只用 Python 标准库，适合 Java/前端调用
- 复杂业务编排框架：支持信息追问、候选产品选择、二次确认、确认后进入风控和交易任务

尚未完成：

- 真实内网模型地址和 token 接入
- 真实账户、产品、转账、风控业务接口接入
- 真实产品筛选规则、真实购买接口和真实交易落库
- 前端悬浮窗、附件上传、语音输入、点赞点踩等页面交互

## 目录结构

```text
AiCaixiaoziDemo/
├── agent_project/
│   ├── service_api.py          # 给科/其他模块调用的统一入口
│   ├── http_server.py          # 标准库 HTTP 服务包装层
│   ├── main.py                 # 终端交互 demo
│   ├── config.py               # 基础配置
│   ├── llm_client.py           # 统一模型调用层
│   ├── business_clients.py     # 真实业务接口占位层
│   ├── clarification_unit.py   # 追问单元，检查缺失字段
│   ├── intent_classifier.py    # 意图识别，输出 JSON tasks
│   ├── intent_rules.json       # 本地意图规则
│   ├── master_agent.py         # 总控 Agent，按依赖调度子 Agent
│   ├── agents.py               # 产品、余额、转账、风控、闲聊 Agent
│   ├── context_manager.py      # 最近 5 轮上下文
│   ├── session_manager.py      # 历史会话管理
│   └── test_cases.py           # 回归测试
├── INTERFACE_DOC.md            # 联调接口文档
├── TEAM_INTEGRATION_GUIDE.md   # 团队联调说明，按 Java/前端/产品/多模态拆分
├── run_demo.bat                # 启动终端 demo
├── run_http.bat                # 启动 HTTP 联调服务
├── run_test.bat                # 运行核心测试
├── CHECK_PYTHON.bat            # 检查 Python 环境
├── INNER_NET_MIGRATION.md      # 内网迁移说明
└── requirements.txt            # 当前无第三方依赖
```

## 快速运行

在 Cursor 里打开：

```text
C:\Dev\AiCaixiaoziDemo
```

运行测试：

```powershell
.\run_test.bat
```

预期结果：

```text
测试完成：PASS=22, FAIL=0
```

运行交互 demo：

```powershell
.\run_demo.bat
```

运行 HTTP 联调服务：

```powershell
.\run_http.bat
```

默认地址：

```text
http://127.0.0.1:8000
```

如果需要指定监听地址和端口：

```powershell
.\run_http.bat 127.0.0.1 8000
```

说明：如果只给本机 Java/前端联调，用 `127.0.0.1`；如果要让其他电脑访问，需要内网安全策略允许后再改成对应内网 IP。

可测试输入：

```text
帮我查一下余额
我要转账100元
给张三转账100元，工商银行，账号622200001111
先查余额再转账
你们有什么理财产品
我想买理财
低风险 3个月 1000元
选第1个
确认
list
new
exit
```

## 联调入口

科优先调用 `agent_project/service_api.py`，不要直接调用内部模块。

完整字段说明见：

```text
INTERFACE_DOC.md
```

如果要发给 Java、前端、产品接口、多模态/推荐等同事看，优先发：

```text
TEAM_INTEGRATION_GUIDE.md
```

这份文档按各模块职责说明“传什么、收什么、先联什么、后面再联什么”。

示例：

```python
from service_api import AgentService

service = AgentService()

result = service.handle_user_message("先查余额再转账")
print(result["reply"])
print(result["session_id"])
```

返回结构是普通 `dict`，可以直接转成 JSON：

```json
{
  "success": true,
  "code": "OK",
  "message": "处理成功",
  "request_id": "xxx",
  "session_id": "xxx",
  "session_created": true,
  "session": {
    "session_id": "xxx",
    "title": "先查余额再转账",
    "turn_count": 1,
    "last_user_input": "先查余额再转账"
  },
  "reply": "风控校验通过 | 余额查询完成 | 转账成功，向 ACC-20002 转账 100.00 CNY",
  "need_user_input": false,
  "tasks": [],
  "task_summary": [],
  "results": {},
  "context": {},
  "logs": [],
  "recent_context": []
}
```

常用方法：

- `handle_user_message(user_input, session_id=None)`：处理一轮用户输入
- `create_session()`：创建新会话
- `list_sessions(limit=20)`：列出最近会话，默认带“今天/近7天/近30天/近半年/更早”分组
- `delete_session(session_id)`：删除会话

## HTTP 联调接口

如果 Java 或前端希望通过 HTTP 调用，启动：

```powershell
.\run_http.bat
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

聊天入口：

```text
POST http://127.0.0.1:8000/api/chat
Content-Type: application/json
```

请求体：

```json
{
  "user_input": "帮我查一下余额",
  "session_id": ""
}
```

说明：首轮 `session_id` 可以不传或传空；第二轮开始传上一次返回的 `session_id`。

历史会话：

```text
GET    http://127.0.0.1:8000/api/sessions?limit=20
POST   http://127.0.0.1:8000/api/sessions
DELETE http://127.0.0.1:8000/api/sessions/<session_id>
```

HTTP 只是外层包装，内部仍然调用同一个 `AgentService`，所以函数联调和 HTTP 联调用的是同一套业务逻辑。

## 当前编排能力

现在已经支持基础编排：

```text
用户输入 -> 意图识别 -> 生成 tasks -> 总控 Agent 按依赖调度 -> 子 Agent 执行 -> 汇总回复
```

例子：

```text
我要转账
```

会执行：

```text
风控 Agent -> 转账 Agent
```

```text
先查余额再转账
```

会执行：

```text
风控 Agent -> 余额 Agent -> 转账 Agent
```

复杂产品购买流程当前也有第一版框架：

```text
用户：我想买理财
系统：追问风险偏好、期限、金额
用户：低风险 3个月 1000元
系统：返回候选产品，等待用户选择
用户：选第1个
系统：要求二次确认
用户：确认
系统：执行风控 -> 交易提交
```

说明：当前产品候选和交易提交仍是模拟逻辑，适合验证流程和联调字段。后续接入真实产品接口后，把候选产品来源、筛选规则和交易接口替换掉即可。

## 追问单元

追问单元位于：

```text
agent_project/clarification_unit.py
```

它的职责是在意图识别之后、调用下游智能体之前，判断当前用户输入是否缺少必要信息。

当前已覆盖转账类追问：

```text
用户：我要转账100元
系统：为了继续转账，请补充：收款人名称、收款账号、目标银行。
```

如果信息完整，则继续进入 Agent 编排：

```text
用户：给张三转账100元，工商银行，账号622200001111
系统：风控校验通过 | 转账成功...
```

这个模块不负责下面六个智能体的业务能力，只负责“信息是否完整、缺什么就问什么”。

## 上下文和历史对话

需求文档中有历史对话和多轮上下文要求，当前 Python 侧已实现基础能力：

- 最近 5 轮上下文：用于下一轮意图识别
- 最近 20 条历史会话：按更新时间倒序
- 首轮问题生成会话标题；未接模型时用首轮输入兜底
- 支持创建、切换、删除、持久化

终端命令：

```text
new       创建新会话
list      查看最近 20 条历史会话
use <id>  切换会话
del <id>  删除会话
exit      退出
```

联调时也可以通过 `AgentService` 的 `session_id` 复用同一段对话。

## 模型接入

全项目只允许通过：

```python
call_llm(prompt: str) -> str
```

位置：

```text
agent_project/llm_client.py
```

内网接 OpenAI 兼容接口时，配置环境变量：

```powershell
$env:LLM_API_URL="http://your-internal-gateway/v1/chat/completions"
$env:LLM_API_TOKEN="your_token_here"
$env:LLM_MODEL="your-model-name"
$env:LLM_TIMEOUT_SECONDS="12"
$env:LLM_MAX_RETRIES="2"
```

当前代码使用 Python 标准库 `urllib`，不依赖 OpenAI SDK，适合第三方包受限的内网环境。

## 真实业务接口占位层

真实银行系统接口统一预留在：

```text
agent_project/business_clients.py
```

当前函数均为标准库 mock 实现，后续内网替换真实接口时，优先改这个文件：

- `query_balance()`：账户余额查询
- `query_products()`：产品查询和筛选
- `run_risk_check()`：风控校验
- `submit_transfer()`：转账/付款提交
- `submit_product_purchase()`：产品购买提交

原则：Agent 编排、会话、上下文和联调入口尽量不改；真实接口替换集中在 `business_clients.py`。

## 明天联调建议

建议先确认 4 件事：

1. 科调用方式：Python 函数、HTTP 服务，还是其他系统入口。
2. 输入输出格式：前端/科希望接收纯文本还是 JSON。
3. 真实业务接口：产品、余额、风控、转账分别由谁提供。
4. 复杂业务规则：哪些场景需要补充信息、筛选、确认、分支和拦截。

当前项目可以先做“基础链路联调”：用户输入进来，Python 返回结构化结果和回复文本。完整业务编排需要在业务规则明确后继续扩展。

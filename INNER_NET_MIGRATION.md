# AI 财小资内网迁移说明

本文档用于迁移到公司内网环境时检查代码、环境和联调入口。

## 1. 迁移目标

核心迁移目录是：

```text
agent_project/
```

迁移后尽量不维护两套业务代码。真实内网差异集中放在两个边界：

- `agent_project/llm_client.py`：大模型调用适配。
- `agent_project/business_clients.py`：真实余额、产品、风控、转账等业务接口适配。

如果 Java/前端需要 HTTP 调用，使用：

```text
agent_project/http_server.py
```

这个 HTTP 服务只用 Python 标准库，不依赖 Flask、FastAPI、requests 等第三方包。

## 2. 内网环境要求

最低要求：

- Python 3.10+
- 可以运行 Python 标准库
- 可以运行 `.bat` 脚本，或可以手工执行对应 Python 命令

从当前截图看，内网公司电脑 Python 是：

```text
Python 3.10.0
```

这满足当前项目要求。

## 3. 推荐迁移文件

建议迁移：

```text
agent_project/
scripts/
README.md
INTERFACE_DOC.md
TEAM_INTEGRATION_GUIDE.md
INNER_NET_MIGRATION.md
requirements.txt
run_demo.bat
run_http.bat
run_test.bat
CHECK_PYTHON.bat
```

不建议迁移：

```text
.venv/
__pycache__/
agent_project/__pycache__/
agent_project/sessions_store.json
```

说明：`.venv` 到内网后重新建；`sessions_store.json` 是本地运行产生的历史会话数据，不是源代码。

## 4. 启动方式

在项目根目录执行测试：

```powershell
.\run_test.bat
```

或手工执行：

```powershell
python agent_project\test_cases.py
```

启动终端 demo：

```powershell
.\run_demo.bat
```

启动 HTTP 联调服务：

```powershell
.\run_http.bat
```

默认地址：

```text
http://127.0.0.1:8000
```

如果要指定地址和端口：

```powershell
.\run_http.bat 127.0.0.1 8000
```

## 5. HTTP 联调入口

健康检查：

```text
GET http://127.0.0.1:8000/health
```

聊天入口：

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

历史会话：

```text
GET    http://127.0.0.1:8000/api/sessions?limit=20
POST   http://127.0.0.1:8000/api/sessions
DELETE http://127.0.0.1:8000/api/sessions/<session_id>
```

注意：

- 如果 Java 和 Python 在同一台机器上，Java 访问 `127.0.0.1:8000`。
- 如果 Java 和 Python 不在同一台机器上，不能用 `127.0.0.1`，需要使用 Python 所在机器的内网 IP，并确认防火墙/安全策略允许访问。
- 如果出现“目标机器积极拒绝连接”，通常是服务没启动、端口不对、地址不对、端口被拦截，或目标接口服务本身未开放。

## 6. 模型接口约定

全项目模型调用统一走：

```python
call_llm(prompt: str) -> str
```

位置：

```text
agent_project/llm_client.py
```

推荐环境变量：

```powershell
$env:LLM_API_URL="http://your-internal-gateway/v1/chat/completions"
$env:LLM_API_TOKEN="your_token_here"
$env:LLM_MODEL="your-internal-model-name"
$env:LLM_TIMEOUT_SECONDS="12"
$env:LLM_MAX_RETRIES="2"
```

当前适配 OpenAI Chat Completions 风格：

```json
{
  "choices": [
    {
      "message": {
        "content": "模型回复文本"
      }
    }
  ]
}
```

如果内网模型不是这个格式，只需要改 `llm_client.py` 的请求体和返回解析，不改 Agent 编排。

## 7. 真实业务接口约定

真实业务接口统一替换：

```text
agent_project/business_clients.py
```

当前预留函数：

- `query_balance(account_id, context=None)`：账户余额查询
- `query_products(requirements)`：产品查询和筛选
- `run_risk_check(params, config)`：风控校验
- `submit_transfer(params, context, config)`：转账/付款提交
- `submit_product_purchase(product, requirements, config)`：产品购买提交

迁移时优先只替换这些函数体，不改函数名和返回结构，减少对 Agent 编排层的影响。

## 8. 迁移验收

迁移后至少执行：

```powershell
python agent_project\test_cases.py
python agent_project\main.py
python agent_project\http_server.py
```

建议人工验证输入：

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
```

如果测试通过，再与 Java、前端、多模态、产品接口同事联调 HTTP、历史会话、附件和真实业务接口。

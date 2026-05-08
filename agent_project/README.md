# agent_project 说明

`agent_project` 是当前项目的核心迁移模块。外网和内网原则上维护同一套业务代码，内网只对齐模型接口和真实业务接口。

## 模块职责

- `service_api.py`：给科或其他模块调用的统一入口。
- `main.py`：终端交互 demo。
- `config.py`：基础配置，例如上下文轮数、转账限额、会话文件名。
- `llm_client.py`：唯一模型调用入口。
- `business_clients.py`：真实业务接口占位层，后续替换内网接口时优先改这里。
- `clarification_unit.py`：追问单元，在调用下游智能体前检查必要信息是否完整。
- `intent_classifier.py`：把用户输入转换为 JSON tasks。
- `intent_rules.json`：本地意图规则，便于无模型时也能运行。
- `master_agent.py`：总控调度器，按依赖关系执行任务。
- `agents.py`：具体业务 Agent。
- `context_manager.py`：轻量最近上下文。
- `session_manager.py`：历史会话创建、命名、排序、删除和持久化。
- `test_cases.py`：核心回归测试。

## 推荐联调方式

优先调用 `service_api.AgentService`：

```python
from service_api import AgentService

service = AgentService()
result = service.handle_user_message("我要转账100元")
```

返回结果是 JSON 友好的 `dict`：

```python
{
    "success": True,
    "code": "OK",
    "message": "处理成功",
    "request_id": "...",
    "session_id": "...",
    "session_created": True,
    "session": {...},
    "reply": "风控校验通过 | 转账成功，向 ACC-20002 转账 100.00 CNY",
    "need_user_input": False,
    "tasks": [...],
    "task_summary": [...],
    "results": {...},
    "context": {...},
    "logs": [...],
    "recent_context": [...],
    "pending_workflow": None,
    "workflow_completed": False,
}
```

如果前端或科模块需要 HTTP 接口，可以在这个类外面再包一层 Web 服务，内部仍然调用 `AgentService`。

## 会话和上下文

当前支持两类能力：

- 上下文：每个会话最近 5 轮问答会传给意图识别。
- 历史会话：最近 20 条会话按更新时间倒序展示。
- 历史分组：`list_sessions()` 默认返回今天、近7天、近30天、近半年、更早。

联调时保留 `session_id`，下一轮继续传回：

```python
first = service.handle_user_message("帮我查一下余额")
second = service.handle_user_message("我要转账100元", session_id=first["session_id"])
```

这样第二轮能挂在同一段历史对话下。

## 编排和风控

任务由 `IntentClassifier` 产出，例如：

```python
[
    {"id": "t1", "agent": "risk", "action": "risk_check", "params": {"amount": 100.0}, "depends_on": []},
    {"id": "t2", "agent": "transfer", "action": "transfer", "params": {"amount": 100.0}, "depends_on": ["t1"]},
]
```

`MasterAgent` 根据 `depends_on` 自动决定执行顺序。转账场景有额外保护：只要发现 `transfer` 任务缺少前置风控，就会自动补 `auto_risk`。

## 复杂业务编排框架

`AgentService` 已支持一类多轮流程：产品购买/推荐。

示例链路：

```text
我想买理财
-> NEED_MORE_INFO，追问风险偏好、期限、金额

低风险 3个月 1000元
-> NEED_USER_SELECTION，返回候选产品

选第1个
-> NEED_CONFIRMATION，等待二次确认

确认
-> OK，执行风控和交易任务
```

这个能力目前是框架和模拟数据，用来承接复杂流程：信息补充、用户选择、二次确认、确认后调度 Agent。接真实业务时，需要把候选产品和交易提交替换为真实接口。

## 测试

在项目根目录运行：

```powershell
.\run_test.bat
```

或在本目录运行：

```powershell
..\.venv\Scripts\python.exe test_cases.py
```

预期：

```text
PASS=21, FAIL=0
```

## 内网迁移点

需要重点对齐：

1. `llm_client.py`：内网模型网关地址、token、请求体和返回字段。
2. `business_clients.py`：把当前 mock 实现替换成真实余额、产品、风控、转账、购买接口。
3. `intent_rules.json`：补充更多业务关键词和固定规则。
4. `service_api.py`：复杂业务流程状态、追问、选择和确认入口。
5. `clarification_unit.py`：补充更多意图的追问字段规则。
6. `master_agent.py`：复杂任务依赖和执行顺序。

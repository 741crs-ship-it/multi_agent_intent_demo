"""各业务 Agent 定义。"""

from dataclasses import dataclass
from typing import Any, Dict

import business_clients
from config import AppConfig
from llm_client import call_llm


@dataclass
class AgentResult:
    """单个 Agent 执行结果。"""

    success: bool
    message: str
    data: Dict[str, Any]


class ProductQAAgent:
    def handle(self, task: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        question = task.get("params", {}).get("question", "")
        reply = call_llm(f"你是产品问答助手，请回答：{question}")
        return AgentResult(success=True, message="产品问答完成", data={"answer": reply})


class BalanceAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def handle(self, task: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        account_id = str(task.get("params", {}).get("account_id", self.config.account_id))
        result = business_clients.query_balance(account_id=account_id, context=context)
        return AgentResult(
            success=bool(result.get("success")),
            message=str(result.get("message", "余额查询完成")),
            data=result,
        )


class RiskAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def handle(self, task: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        result = business_clients.run_risk_check(params=task.get("params", {}), config=self.config)
        return AgentResult(
            success=bool(result.get("success")),
            message=str(result.get("message", "风控校验完成")),
            data=result,
        )


class TransferAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def handle(self, task: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        result = business_clients.submit_transfer(
            params=task.get("params", {}),
            context=context,
            config=self.config,
        )
        return AgentResult(
            success=bool(result.get("success")),
            message=str(result.get("message", "转账处理完成")),
            data=result,
        )


class ChitChatAgent:
    def handle(self, task: Dict[str, Any], context: Dict[str, Any]) -> AgentResult:
        message = task.get("params", {}).get("message", "")
        reply = call_llm(f"你是闲聊助手，请友好回复：{message}")
        return AgentResult(success=True, message="闲聊兜底完成", data={"reply": reply})


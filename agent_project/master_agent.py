"""主控调度器：根据 tasks 自动串并行调度。"""

import asyncio
from typing import Any, Dict, List

from agents import (
    AgentResult,
    BalanceAgent,
    ChitChatAgent,
    ProductQAAgent,
    RiskAgent,
    TransferAgent,
)
from config import AppConfig


class MasterAgent:
    """按照依赖关系自动执行任务。"""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self._agent_map = {
            "balance": BalanceAgent(self.config),
            "transfer": TransferAgent(self.config),
            "risk": RiskAgent(self.config),
            "product": ProductQAAgent(),
            "chat": ChitChatAgent(),
        }

    async def run(self, tasks: List[Dict[str, Any]], initial_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context: Dict[str, Any] = {"balance": 1200.0}
        if initial_context:
            context.update(initial_context)

        normalized_tasks = self._ensure_transfer_risk_dependency(tasks)
        pending = {task["id"]: dict(task) for task in normalized_tasks}
        completed: Dict[str, AgentResult] = {}
        execution_logs: List[str] = []

        while pending:
            # 仅挑选“依赖已完成”的任务；这类任务可并行执行。
            ready = [
                task
                for task in pending.values()
                if all(dep in completed and completed[dep].success for dep in task.get("depends_on", []))
            ]

            if not ready:
                # 出现循环依赖或前置失败时，直接终止，避免死循环。
                unresolved = ", ".join(pending.keys())
                execution_logs.append(f"[ERROR] 存在未满足依赖的任务: {unresolved}")
                break

            run_jobs = [self._run_one_task(task, context, execution_logs) for task in ready]
            batch_results = await asyncio.gather(*run_jobs)

            for task_id, result in batch_results:
                completed[task_id] = result
                pending.pop(task_id, None)
                if "balance" in result.data:
                    context["balance"] = result.data["balance"]

        return {
            "results": {task_id: result.__dict__ for task_id, result in completed.items()},
            "context": context,
            "logs": execution_logs,
        }

    def _ensure_transfer_risk_dependency(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保转账任务前置风控，避免模型或配置遗漏风险校验。"""
        normalized = [dict(task) for task in tasks]
        has_transfer = any(task.get("agent") == "transfer" for task in normalized)
        if not has_transfer:
            return normalized

        risk_ids = [str(task.get("id")) for task in normalized if task.get("agent") == "risk"]
        if not risk_ids:
            transfer_amount = 0.0
            for task in normalized:
                if task.get("agent") == "transfer":
                    transfer_amount = self._to_float(task.get("params", {}).get("amount", 0.0))
                    break
            risk_task_id = self._build_unique_task_id(normalized, "auto_risk")
            normalized.insert(
                0,
                {
                    "id": risk_task_id,
                    "agent": "risk",
                    "action": "risk_check",
                    "params": {"amount": transfer_amount},
                    "depends_on": [],
                },
            )
            risk_ids = [risk_task_id]

        first_risk_id = risk_ids[0]
        for task in normalized:
            if task.get("agent") != "transfer":
                continue
            depends_on = task.get("depends_on", [])
            if not isinstance(depends_on, list):
                depends_on = []
            if first_risk_id not in depends_on:
                task["depends_on"] = [first_risk_id, *depends_on]

        return normalized

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _build_unique_task_id(tasks: List[Dict[str, Any]], base_id: str) -> str:
        existing_ids = {str(task.get("id")) for task in tasks}
        if base_id not in existing_ids:
            return base_id

        index = 1
        while f"{base_id}_{index}" in existing_ids:
            index += 1
        return f"{base_id}_{index}"

    async def _run_one_task(
        self, task: Dict[str, Any], context: Dict[str, Any], execution_logs: List[str]
    ) -> tuple[str, AgentResult]:
        task_id = task["id"]
        agent_name = task.get("agent", "chat")
        action = task.get("action", "chitchat")
        execution_logs.append(f"[START] task={task_id}, agent={agent_name}, action={action}")
        await asyncio.sleep(0)

        agent = self._agent_map.get(agent_name)
        if not agent:
            result = AgentResult(success=False, message=f"未知 Agent: {agent_name}", data={})
            execution_logs.append(f"[END] task={task_id}, success={result.success}, message={result.message}")
            return task_id, result

        result = agent.handle(task, context)
        execution_logs.append(f"[END] task={task_id}, success={result.success}, message={result.message}")
        return task_id, result


"""Stable service API for integration with other modules."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any, Callable, Dict, List

import business_clients
import clarification_unit
from config import AppConfig
from intent_classifier import IntentClassifier
from master_agent import MasterAgent
from session_manager import SessionManager


class AgentService:
    """Single entry point for caller modules.

    This class keeps the orchestration details inside agent_project, so callers
    do not need to know how intent classification, session history, and agent
    scheduling are wired together.
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        store_path: str | None = None,
        namer: Callable[[str], str] | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.session_manager = SessionManager(config=self.config, store_path=store_path, namer=namer)
        self.classifier = IntentClassifier()
        self.master = MasterAgent(config=self.config)
        self._pending_workflows: Dict[str, Dict[str, Any]] = {}

    def create_session(self) -> Dict[str, Any]:
        """Create an empty session and return its id."""
        session = self.session_manager.create_session()
        return {
            "success": True,
            "code": "OK",
            "message": "会话已创建",
            "session_id": session.session_id,
            "title": session.title or "新对话",
            "session": self._format_session(session),
        }

    def list_sessions(self, limit: int = 20, grouped: bool = True) -> Dict[str, Any]:
        """Return recent sessions ordered by latest update time."""
        sessions = self.session_manager.list_recent_sessions(limit=limit)
        formatted_sessions = [self._format_session(session) for session in sessions]
        return {
            "success": True,
            "code": "OK",
            "message": "历史会话查询成功",
            "sessions": formatted_sessions,
            "groups": self._group_sessions(formatted_sessions) if grouped else [],
        }

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a session by id."""
        deleted = self.session_manager.delete_session(session_id)
        return {
            "success": deleted,
            "code": "OK" if deleted else "SESSION_NOT_FOUND",
            "message": "会话已删除" if deleted else "会话不存在",
            "session_id": session_id,
        }

    def handle_user_message(self, user_input: str, session_id: str | None = None) -> Dict[str, Any]:
        """Process one user message and return a JSON-serializable result."""
        request_id = str(uuid.uuid4())
        user_input = (user_input or "").strip()
        if not user_input:
            return {
                "success": False,
                "code": "EMPTY_INPUT",
                "message": "请输入有效内容。",
                "request_id": request_id,
                "session_id": session_id,
                "reply": "请输入有效内容。",
                "need_user_input": True,
                "tasks": [],
                "task_summary": [],
                "results": {},
                "context": {},
                "logs": [],
                "recent_context": [],
                "session": None,
            }

        session = self.session_manager.get_session(session_id) if session_id else None
        if session is None:
            session = self.session_manager.create_session()
            session_created = True
        else:
            session_created = False

        workflow_response = self._try_handle_workflow(user_input, session.session_id, session_created, request_id)
        if workflow_response is not None:
            return workflow_response

        recent_context = self.session_manager.get_recent_context_for_classifier(
            session_id=session.session_id,
            max_rounds=self.config.max_context_rounds,
        )
        tasks_payload = self.classifier.classify(user_input=user_input, recent_context=recent_context)
        tasks = tasks_payload.get("tasks", [])
        clarification = clarification_unit.check_clarification(
            user_input=user_input,
            tasks=tasks,
            recent_context=recent_context,
        )
        if clarification.get("need_clarification"):
            reply = str(clarification.get("question", "请补充必要信息。"))
            self.session_manager.add_user_and_assistant_turn(
                session_id=session.session_id,
                user_input=user_input,
                assistant_output=reply,
            )
            updated_session = self.session_manager.get_session(session.session_id)
            updated_context = self.session_manager.get_recent_context_for_classifier(
                session_id=session.session_id,
                max_rounds=self.config.max_context_rounds,
            )
            return {
                "success": True,
                "code": "NEED_MORE_INFO",
                "message": reply,
                "request_id": request_id,
                "session_id": session.session_id,
                "session_created": session_created,
                "session": self._format_session(updated_session) if updated_session else None,
                "reply": reply,
                "need_user_input": True,
                "tasks": tasks,
                "task_summary": self._build_task_summary(tasks, {}),
                "results": {},
                "context": {},
                "logs": [],
                "recent_context": updated_context,
                "pending_workflow": self._pending_workflows.get(session.session_id),
                "clarification": clarification,
                "workflow_completed": False,
            }
        run_result = asyncio.run(self.master.run(tasks=tasks))
        reply = self._build_reply(run_result)

        self.session_manager.add_user_and_assistant_turn(
            session_id=session.session_id,
            user_input=user_input,
            assistant_output=reply,
        )

        updated_context = self.session_manager.get_recent_context_for_classifier(
            session_id=session.session_id,
            max_rounds=self.config.max_context_rounds,
        )
        updated_session = self.session_manager.get_session(session.session_id)
        success = bool(run_result.get("results"))
        return {
            "success": success,
            "code": "OK" if success else "NO_EXECUTABLE_TASK",
            "message": "处理成功" if success else "没有可执行任务",
            "request_id": request_id,
            "session_id": session.session_id,
            "session_created": session_created,
            "session": self._format_session(updated_session) if updated_session else None,
            "reply": reply,
            "need_user_input": False,
            "tasks": tasks,
            "task_summary": self._build_task_summary(tasks, run_result.get("results", {})),
            "results": run_result.get("results", {}),
            "context": run_result.get("context", {}),
            "logs": run_result.get("logs", []),
            "recent_context": updated_context,
            "pending_workflow": self._pending_workflows.get(session.session_id),
        }

    @staticmethod
    def _build_reply(run_result: Dict[str, Any]) -> str:
        results: Dict[str, Dict[str, Any]] = run_result.get("results", {})
        if not results:
            return "本轮没有可执行任务，请换个说法再试。"
        messages: List[str] = [str(item.get("message", "")) for item in results.values()]
        return " | ".join([message for message in messages if message])

    @staticmethod
    def _format_session(session: Any) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "title": session.title or "新对话",
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "turn_count": len(session.turns),
            "last_user_input": session.turns[-1].user_input if session.turns else "",
            "last_assistant_output": session.turns[-1].assistant_output if session.turns else "",
        }

    @staticmethod
    def _build_task_summary(tasks: List[Dict[str, Any]], results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for task in tasks:
            task_id = str(task.get("id", ""))
            result = results.get(task_id, {})
            summary.append(
                {
                    "task_id": task_id,
                    "agent": task.get("agent", ""),
                    "action": task.get("action", ""),
                    "depends_on": task.get("depends_on", []),
                    "executed": task_id in results,
                    "success": result.get("success") if result else None,
                    "message": result.get("message", "") if result else "",
                }
            )

        extra_result_ids = [task_id for task_id in results if task_id not in {str(task.get("id", "")) for task in tasks}]
        for task_id in extra_result_ids:
            result = results[task_id]
            summary.append(
                {
                    "task_id": task_id,
                    "agent": "risk" if str(task_id).startswith("auto_risk") else "",
                    "action": "risk_check" if str(task_id).startswith("auto_risk") else "",
                    "depends_on": [],
                    "executed": True,
                    "success": result.get("success"),
                    "message": result.get("message", ""),
                }
            )
        return summary

    @staticmethod
    def _group_sessions(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets = [
            ("today", "今天", 1),
            ("last_7_days", "近7天", 8),
            ("last_30_days", "近30天", 31),
            ("last_6_months", "近半年", 181),
            ("earlier", "更早", None),
        ]
        grouped: Dict[str, List[Dict[str, Any]]] = {key: [] for key, _, _ in buckets}
        now = time.time()

        for session in sessions:
            age_days = int((now - float(session.get("updated_at", now))) // 86400)
            for key, _, max_age_days in buckets:
                if max_age_days is None or age_days < max_age_days:
                    grouped[key].append(session)
                    break

        return [
            {
                "key": key,
                "label": label,
                "sessions": grouped[key],
            }
            for key, label, _ in buckets
            if grouped[key]
        ]

    def _try_handle_workflow(
        self,
        user_input: str,
        session_id: str,
        session_created: bool,
        request_id: str,
    ) -> Dict[str, Any] | None:
        workflow = self._pending_workflows.get(session_id)
        if workflow is None and self._should_start_product_workflow(user_input):
            workflow = {
                "workflow_id": str(uuid.uuid4()),
                "type": "product_purchase",
                "status": "collecting_requirements",
                "slots": {},
                "selected_product": None,
            }
            self._pending_workflows[session_id] = workflow

        if workflow is None:
            return None

        self._update_product_slots(workflow, user_input)
        if workflow["status"] == "collecting_requirements":
            missing = self._missing_product_slots(workflow)
            if missing:
                reply = self._build_requirement_question(missing)
                return self._build_workflow_response(
                    session_id=session_id,
                    session_created=session_created,
                    request_id=request_id,
                    user_input=user_input,
                    reply=reply,
                    code="NEED_MORE_INFO",
                    need_user_input=True,
                    workflow=workflow,
                )

            workflow["status"] = "waiting_product_selection"
            product_result = business_clients.query_products(workflow["slots"])
            workflow["options"] = product_result.get("products", [])
            workflow["product_query"] = {
                "success": product_result.get("success", False),
                "code": product_result.get("code", ""),
                "message": product_result.get("message", ""),
                "source": product_result.get("source", ""),
            }
            reply = self._format_product_options(workflow["options"])
            return self._build_workflow_response(
                session_id=session_id,
                session_created=session_created,
                request_id=request_id,
                user_input=user_input,
                reply=reply,
                code="NEED_USER_SELECTION",
                need_user_input=True,
                workflow=workflow,
            )

        if workflow["status"] == "waiting_product_selection":
            selected = self._parse_product_selection(user_input, workflow.get("options", []))
            if selected is None:
                reply = "请回复要选择的产品序号，例如：选第1个。"
                return self._build_workflow_response(
                    session_id=session_id,
                    session_created=session_created,
                    request_id=request_id,
                    user_input=user_input,
                    reply=reply,
                    code="NEED_USER_SELECTION",
                    need_user_input=True,
                    workflow=workflow,
                )

            workflow["selected_product"] = selected
            workflow["status"] = "waiting_confirmation"
            amount = workflow["slots"].get("amount", 100.0)
            reply = (
                f"已选择{selected['name']}，金额 {amount:.2f} {self.config.default_currency}。"
                "该操作将进入风控校验和交易提交，请回复“确认”继续，或回复“取消”结束。"
            )
            return self._build_workflow_response(
                session_id=session_id,
                session_created=session_created,
                request_id=request_id,
                user_input=user_input,
                reply=reply,
                code="NEED_CONFIRMATION",
                need_user_input=True,
                workflow=workflow,
            )

        if workflow["status"] == "waiting_confirmation":
            if self._is_cancel(user_input):
                self._pending_workflows.pop(session_id, None)
                return self._build_workflow_response(
                    session_id=session_id,
                    session_created=session_created,
                    request_id=request_id,
                    user_input=user_input,
                    reply="已取消本次产品购买流程。",
                    code="WORKFLOW_CANCELLED",
                    need_user_input=False,
                    workflow=None,
                )
            if not self._is_confirm(user_input):
                reply = "请回复“确认”继续，或回复“取消”结束。"
                return self._build_workflow_response(
                    session_id=session_id,
                    session_created=session_created,
                    request_id=request_id,
                    user_input=user_input,
                    reply=reply,
                    code="NEED_CONFIRMATION",
                    need_user_input=True,
                    workflow=workflow,
                )

            amount = float(workflow["slots"].get("amount", 100.0))
            selected = workflow.get("selected_product") or {}
            tasks = [
                {
                    "id": "t1",
                    "agent": "risk",
                    "action": "risk_check",
                    "params": {"amount": amount, "product_id": selected.get("product_id", "")},
                    "depends_on": [],
                },
                {
                    "id": "t2",
                    "agent": "transfer",
                    "action": "transfer",
                    "params": {"amount": amount, "to_account": selected.get("settlement_account", "PRODUCT-SETTLE")},
                    "depends_on": ["t1"],
                },
            ]
            run_result = asyncio.run(self.master.run(tasks=tasks))
            reply = self._build_reply(run_result)
            self._pending_workflows.pop(session_id, None)
            return self._build_workflow_response(
                session_id=session_id,
                session_created=session_created,
                request_id=request_id,
                user_input=user_input,
                reply=reply,
                code="OK",
                need_user_input=False,
                workflow=None,
                tasks=tasks,
                run_result=run_result,
                workflow_completed=True,
            )

        return None

    def _build_workflow_response(
        self,
        session_id: str,
        session_created: bool,
        request_id: str,
        user_input: str,
        reply: str,
        code: str,
        need_user_input: bool,
        workflow: Dict[str, Any] | None,
        tasks: List[Dict[str, Any]] | None = None,
        run_result: Dict[str, Any] | None = None,
        workflow_completed: bool = False,
    ) -> Dict[str, Any]:
        self.session_manager.add_user_and_assistant_turn(
            session_id=session_id,
            user_input=user_input,
            assistant_output=reply,
        )
        updated_session = self.session_manager.get_session(session_id)
        recent_context = self.session_manager.get_recent_context_for_classifier(
            session_id=session_id,
            max_rounds=self.config.max_context_rounds,
        )
        result_payload = run_result or {"results": {}, "context": {}, "logs": []}
        return {
            "success": code in {"OK", "NEED_MORE_INFO", "NEED_USER_SELECTION", "NEED_CONFIRMATION", "WORKFLOW_CANCELLED"},
            "code": code,
            "message": "处理成功" if code == "OK" else reply,
            "request_id": request_id,
            "session_id": session_id,
            "session_created": session_created,
            "session": self._format_session(updated_session) if updated_session else None,
            "reply": reply,
            "need_user_input": need_user_input,
            "tasks": tasks or [],
            "task_summary": self._build_task_summary(tasks or [], result_payload.get("results", {})),
            "results": result_payload.get("results", {}),
            "context": result_payload.get("context", {}),
            "logs": result_payload.get("logs", []),
            "recent_context": recent_context,
            "pending_workflow": workflow,
            "workflow_completed": workflow_completed,
        }

    @staticmethod
    def _should_start_product_workflow(user_input: str) -> bool:
        has_product_word = any(word in user_input for word in ("理财", "产品", "存款", "大额存单"))
        has_action_word = any(word in user_input for word in ("买", "购买", "申购", "认购", "推荐", "配置"))
        return has_product_word and has_action_word

    @staticmethod
    def _update_product_slots(workflow: Dict[str, Any], user_input: str) -> None:
        slots = workflow.setdefault("slots", {})
        if any(word in user_input for word in ("低风险", "稳健", "保守")):
            slots["risk_level"] = "low"
        elif any(word in user_input for word in ("中风险", "平衡")):
            slots["risk_level"] = "medium"
        elif any(word in user_input for word in ("高风险", "进取")):
            slots["risk_level"] = "high"

        term_match = re.search(r"(\d+)\s*(天|个月|月|年)", user_input)
        if term_match:
            slots["term"] = f"{term_match.group(1)}{term_match.group(2)}"

        amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(万|元|块)?", user_input)
        if amount_match and any(word in user_input for word in ("元", "万", "块", "金额", "买", "投")):
            amount = float(amount_match.group(1))
            unit = amount_match.group(2) or "元"
            slots["amount"] = amount * 10000 if unit == "万" else amount

    @staticmethod
    def _missing_product_slots(workflow: Dict[str, Any]) -> List[str]:
        slots = workflow.get("slots", {})
        required = ["risk_level", "term", "amount"]
        return [item for item in required if item not in slots]

    @staticmethod
    def _build_requirement_question(missing: List[str]) -> str:
        labels = {
            "risk_level": "风险偏好（例如低风险/中风险）",
            "term": "期限（例如3个月/180天）",
            "amount": "金额（例如1000元/10万）",
        }
        items = "、".join(labels[item] for item in missing)
        return f"为了继续筛选产品，请补充：{items}。"

    @staticmethod
    def _format_product_options(options: List[Dict[str, Any]]) -> str:
        if not options:
            return "暂未筛选到符合条件的产品，请调整风险偏好、期限或金额后再试。"
        lines = ["已根据你的条件筛选到以下产品，请回复序号选择："]
        for index, option in enumerate(options, start=1):
            lines.append(
                f"{index}. {option['name']}，期限{option['term']}，参考收益{option['expected_yield']}"
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_product_selection(user_input: str, options: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        match = re.search(r"第?\s*(\d+)\s*个?|选\s*(\d+)", user_input)
        if not match:
            return None
        raw_index = match.group(1) or match.group(2)
        index = int(raw_index) - 1
        if 0 <= index < len(options):
            return options[index]
        return None

    @staticmethod
    def _is_confirm(user_input: str) -> bool:
        return any(word in user_input for word in ("确认", "确定", "继续", "同意", "是"))

    @staticmethod
    def _is_cancel(user_input: str) -> bool:
        return any(word in user_input for word in ("取消", "不买", "算了", "退出"))


def handle_user_message(user_input: str, session_id: str | None = None) -> Dict[str, Any]:
    """Convenience function for simple integrations."""
    service = AgentService()
    return service.handle_user_message(user_input=user_input, session_id=session_id)

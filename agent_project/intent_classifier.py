"""意图识别模块，输出固定 schema 的 JSON tasks。"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from llm_client import call_llm


class IntentClassifier:
    """将用户输入分类为可执行任务。"""

    def __init__(self, rules_path: str | None = None) -> None:
        self._rules_path = Path(rules_path) if rules_path else Path(__file__).with_name("intent_rules.json")
        self._rules = self._load_rules()

    def classify(self, user_input: str, recent_context: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
        """返回结构化 tasks。

        输出 schema:
        {
          "tasks": [
            {
              "id": "t1",
              "agent": "balance|transfer|risk|product|chat",
              "action": "query_balance|transfer|risk_check|product_qa|chitchat",
              "params": {},
              "depends_on": []
            }
          ]
        }
        """
        # 先走本地规则，便于按配置快速调优。
        by_rule = self._classify_by_rules(user_input)
        if by_rule is not None:
            return by_rule

        # 规则未命中时，再走模型兜底。
        context_text = json.dumps(recent_context or [], ensure_ascii=False)
        prompt = (
            "intent_router\n"
            "请根据用户输入和上下文返回 JSON tasks。\n"
            f"用户输入: {user_input}\n"
            f"上下文: {context_text}\n"
        )
        raw = call_llm(prompt)
        return self._validate_and_normalize(raw)

    def _validate_and_normalize(self, raw: str) -> Dict[str, Any]:
        """校验模型返回，失败时降级到闲聊任务。"""
        fallback = {
            "tasks": [
                {
                    "id": "t1",
                    "agent": "chat",
                    "action": "chitchat",
                    "params": {},
                    "depends_on": [],
                }
            ]
        }

        try:
            payload = json.loads(raw)
            tasks = payload.get("tasks")
            if not isinstance(tasks, list) or not tasks:
                return fallback
            normalized = {"tasks": []}
            for idx, task in enumerate(tasks, start=1):
                normalized["tasks"].append(
                    {
                        "id": str(task.get("id", f"t{idx}")),
                        "agent": str(task.get("agent", "chat")),
                        "action": str(task.get("action", "chitchat")),
                        "params": task.get("params", {}) if isinstance(task.get("params"), dict) else {},
                        "depends_on": task.get("depends_on", [])
                        if isinstance(task.get("depends_on"), list)
                        else [],
                    }
                )
            return normalized
        except json.JSONDecodeError:
            return fallback

    def _load_rules(self) -> Dict[str, Any]:
        """加载意图规则配置，读取失败时返回空配置。"""
        if not self._rules_path.exists():
            return {"combo_rules": [], "intents": [], "fallback_task": {}}
        try:
            return json.loads(self._rules_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"combo_rules": [], "intents": [], "fallback_task": {}}

    def _classify_by_rules(self, user_input: str) -> Dict[str, Any] | None:
        """按配置规则识别意图。"""
        text = user_input.strip()
        if not text:
            return {"tasks": [self._build_fallback_task(user_input)]}

        # 复合规则优先，例如“先查余额再转账”。
        for combo in self._rules.get("combo_rules", []):
            required = combo.get("all_keywords", [])
            if isinstance(required, list) and all(keyword in text for keyword in required):
                tasks = combo.get("tasks", [])
                if isinstance(tasks, list) and tasks:
                    return {"tasks": [self._normalize_task(task, idx, user_input) for idx, task in enumerate(tasks, 1)]}

        # 单意图规则按优先级命中。
        intents = self._rules.get("intents", [])
        if isinstance(intents, list):
            sorted_intents = sorted(
                [item for item in intents if isinstance(item, dict)],
                key=lambda item: int(item.get("priority", 0)),
                reverse=True,
            )
            for item in sorted_intents:
                keywords = item.get("keywords", [])
                if isinstance(keywords, list) and any(keyword in text for keyword in keywords):
                    tasks = item.get("tasks")
                    if isinstance(tasks, list) and tasks:
                        return {
                            "tasks": [
                                self._normalize_task(task, idx, user_input)
                                for idx, task in enumerate(tasks, 1)
                            ]
                        }
                    task = item.get("task", {})
                    return {"tasks": [self._normalize_task(task, 1, user_input)]}

        return {"tasks": [self._build_fallback_task(user_input)]}

    def _build_fallback_task(self, user_input: str) -> Dict[str, Any]:
        """生成兜底任务。"""
        fallback = self._rules.get("fallback_task", {})
        return self._normalize_task(fallback, 1, user_input)

    def _normalize_task(self, task: Dict[str, Any], idx: int, user_input: str) -> Dict[str, Any]:
        """将配置模板任务转成执行任务。"""
        raw = deepcopy(task) if isinstance(task, dict) else {}
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        if params.pop("question_from_input", False):
            params["question"] = user_input
        if params.pop("message_from_input", False):
            params["message"] = user_input

        depends_on = raw.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []

        return {
            "id": str(raw.get("id", f"t{idx}")),
            "agent": str(raw.get("agent", "chat")),
            "action": str(raw.get("action", "chitchat")),
            "params": params,
            "depends_on": depends_on,
        }


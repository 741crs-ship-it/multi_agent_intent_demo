"""会话与历史能力（后端规则层，便于迁移到内网）。"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import AppConfig
from llm_client import call_llm


@dataclass
class SessionTurn:
    """一轮问答记录。"""

    user_input: str
    assistant_output: str
    created_at: float


@dataclass
class Session:
    """会话对象。"""

    session_id: str
    title: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: List[SessionTurn] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = time.time()


class SessionManager:
    """管理会话：创建/命名/切换/删除/最近列表/持久化。"""

    def __init__(
        self,
        config: AppConfig | None = None,
        store_path: str | None = None,
        title_max_len: int = 20,
        namer: Callable[[str], str] | None = None,
    ) -> None:
        self._config = config or AppConfig()
        self._store_path = Path(store_path) if store_path else Path(__file__).with_name(self._config.session_store_filename)
        self._title_max_len = title_max_len
        self._namer = namer or self._default_namer
        self._sessions: Dict[str, Session] = {}
        self._load_from_disk()

    def create_session(self) -> Session:
        session = Session(session_id=str(uuid.uuid4()))
        self._sessions[session.session_id] = session
        self._persist_to_disk()
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._persist_to_disk()
            return True
        return False

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_recent_sessions(self, limit: int = 20) -> List[Session]:
        sessions = sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def add_user_and_assistant_turn(
        self,
        session_id: str,
        user_input: str,
        assistant_output: str,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 首轮用户提问时生成会话标题（避免每轮都调用模型）。
        if session.title is None:
            session.title = self._normalize_title(self._namer(user_input))

        session.turns.append(
            SessionTurn(user_input=user_input, assistant_output=assistant_output, created_at=time.time())
        )
        session.touch()
        self._persist_to_disk()

    def get_recent_context_for_classifier(self, session_id: str, max_rounds: int = 5) -> List[Dict[str, str]]:
        """将会话最近 N 轮转成 classifier 需要的结构。"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        recent = session.turns[-max_rounds:]
        return [{"user": t.user_input, "assistant": t.assistant_output} for t in recent]

    def _normalize_title(self, title: str) -> str:
        title = (title or "").strip().replace("\n", " ")
        if not title:
            title = "新对话"
        if len(title) > self._title_max_len:
            title = title[: self._title_max_len] + "..."
        return title

    def _default_namer(self, first_user_input: str) -> str:
        prompt = (
            "你是会话命名器。请用不超过20个中文字符概括用户首次问题的核心内容，"
            "输出纯文本标题，不要包含标点以外的多余解释。\n"
            f"用户首次问题: {first_user_input}\n"
            "标题："
        )
        title = call_llm(prompt)
        if title.startswith("[LLM_ERROR]"):
            return first_user_input
        return title

    def _load_from_disk(self) -> None:
        if not self._store_path.exists():
            return
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
            sessions = payload.get("sessions", [])
            if not isinstance(sessions, list):
                return
            for item in sessions:
                if not isinstance(item, dict):
                    continue
                sid = str(item.get("session_id", ""))
                if not sid:
                    continue
                session = Session(
                    session_id=sid,
                    title=item.get("title"),
                    created_at=float(item.get("created_at", time.time())),
                    updated_at=float(item.get("updated_at", time.time())),
                    turns=[],
                )
                turns = item.get("turns", [])
                if isinstance(turns, list):
                    for t in turns:
                        if not isinstance(t, dict):
                            continue
                        session.turns.append(
                            SessionTurn(
                                user_input=str(t.get("user_input", "")),
                                assistant_output=str(t.get("assistant_output", "")),
                                created_at=float(t.get("created_at", time.time())),
                            )
                        )
                self._sessions[session.session_id] = session
        except Exception:
            # 容错：读取失败不影响主流程
            self._sessions = {}

    def _persist_to_disk(self) -> None:
        payload = {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "turns": [
                        {
                            "user_input": t.user_input,
                            "assistant_output": t.assistant_output,
                            "created_at": t.created_at,
                        }
                        for t in s.turns
                    ],
                }
                for s in self._sessions.values()
            ]
        }
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


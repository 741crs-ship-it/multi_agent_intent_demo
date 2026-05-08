"""轻量上下文管理模块。"""

from dataclasses import dataclass
from typing import List


@dataclass
class ContextTurn:
    """单轮对话记录。"""

    user_input: str
    assistant_output: str


class ContextManager:
    """仅保存最近 N 轮上下文，默认 5 轮。"""

    def __init__(self, max_rounds: int = 5) -> None:
        self._max_rounds = max_rounds
        self._turns: List[ContextTurn] = []

    @property
    def max_rounds(self) -> int:
        """上下文裁剪上限（只读）。"""
        return self._max_rounds

    def append(self, user_input: str, assistant_output: str) -> None:
        """追加一轮对话并裁剪历史长度。"""
        self._turns.append(ContextTurn(user_input=user_input, assistant_output=assistant_output))
        if len(self._turns) > self._max_rounds:
            self._turns = self._turns[-self._max_rounds :]

    def get_recent(self) -> List[ContextTurn]:
        """获取最近上下文。"""
        return list(self._turns)

    def clear(self) -> None:
        """清空上下文。"""
        self._turns.clear()


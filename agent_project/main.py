"""终端多轮对话入口（包含会话与历史切换能力）。"""

import asyncio
from typing import Dict

from config import AppConfig
from context_manager import ContextManager
from intent_classifier import IntentClassifier
from master_agent import MasterAgent
from session_manager import SessionManager


def _format_context_for_classifier(context_manager: ContextManager) -> list[Dict[str, str]]:
    turns = context_manager.get_recent()
    return [{"user": t.user_input, "assistant": t.assistant_output} for t in turns]


async def _process_one_round(
    user_input: str, classifier: IntentClassifier, master: MasterAgent, context_manager: ContextManager
) -> str:
    tasks_payload = classifier.classify(user_input=user_input, recent_context=_format_context_for_classifier(context_manager))
    tasks = tasks_payload.get("tasks", [])
    run_result = await master.run(tasks=tasks)

    if not run_result["results"]:
        reply = "本轮没有可执行任务，请换个说法再试。"
    else:
        messages = [item["message"] for item in run_result["results"].values()]
        reply = " | ".join(messages)

    context_manager.append(user_input=user_input, assistant_output=reply)
    return reply


def _refresh_context_from_session(
    session_manager: SessionManager,
    session_id: str,
    context_manager: ContextManager,
) -> None:
    context_manager.clear()
    recent = session_manager.get_recent_context_for_classifier(session_id=session_id, max_rounds=context_manager.max_rounds)
    for t in recent:
        context_manager.append(user_input=t["user"], assistant_output=t["assistant"])


def main() -> None:
    config = AppConfig()
    session_manager = SessionManager(config=config)
    context_manager = ContextManager(max_rounds=config.max_context_rounds)
    classifier = IntentClassifier()
    master = MasterAgent(config=config)

    current_session = session_manager.create_session()
    _refresh_context_from_session(session_manager, current_session.session_id, context_manager)

    print("智能助手已启动。")
    print("命令：new 创建会话；list 列出最近20条；use <id> 切换；del <id> 删除；exit/quit 退出。")
    while True:
        user_input = input("\n你: ").strip()
        if not user_input:
            print("助手: 请输入有效内容。")
            continue

        lower = user_input.lower()
        if lower in {"exit", "quit"}:
            print("助手: 会话结束，再见。")
            break

        if lower == "new":
            current_session = session_manager.create_session()
            _refresh_context_from_session(session_manager, current_session.session_id, context_manager)
            print(f"助手: 已创建新会话 id={current_session.session_id}")
            continue

        if lower == "list":
            sessions = session_manager.list_recent_sessions(limit=20)
            if not sessions:
                print("助手: 暂无历史会话。输入 new 创建会话。")
                continue
            for s in sessions:
                title = s.title or "新对话"
                print(f"- id={s.session_id} | {title} | updated_at={int(s.updated_at)}")
            continue

        if lower.startswith("use "):
            sid = user_input.split(maxsplit=1)[1].strip()
            s = session_manager.get_session(sid)
            if not s:
                print("助手: 未找到该会话 id。")
                continue
            current_session = s
            _refresh_context_from_session(session_manager, current_session.session_id, context_manager)
            print(f"助手: 已切换会话 id={current_session.session_id}")
            continue

        if lower.startswith("del "):
            sid = user_input.split(maxsplit=1)[1].strip()
            ok = session_manager.delete_session(sid)
            if not ok:
                print("助手: 未找到该会话 id。")
                continue
            # 删除后回到一个新会话
            current_session = session_manager.create_session()
            _refresh_context_from_session(session_manager, current_session.session_id, context_manager)
            print("助手: 已删除会话，并创建新会话继续。")
            continue

        # 普通对话输入：写入会话历史 + 更新上下文
        reply = asyncio.run(_process_one_round(user_input, classifier, master, context_manager))
        session_manager.add_user_and_assistant_turn(
            session_id=current_session.session_id,
            user_input=user_input,
            assistant_output=reply,
        )
        print(f"助手: {reply}")


if __name__ == "__main__":
    main()


"""基础测试用例：覆盖核心业务场景 + 会话历史能力。"""

import asyncio
import http.client
import json
import os
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any, Dict, List

import agents as agents_module
import business_clients
import clarification_unit
from config import AppConfig
from http_server import AgentHttpHandler
import intent_classifier as intent_classifier_module
from intent_classifier import IntentClassifier
from master_agent import MasterAgent
from service_api import AgentService
from session_manager import SessionManager


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _run_case(user_input: str) -> Dict[str, Any]:
    def _mock_call_llm(prompt: str) -> str:
        text = prompt.lower()
        if "intent_router" in text:
            if ("余额" in prompt) and ("转账" in prompt):
                return (
                    '{"tasks":[{"id":"t1","agent":"balance","action":"query_balance","params":{},'
                    '"depends_on":[]},{"id":"t2","agent":"transfer","action":"transfer",'
                    '"params":{"amount":100.0,"to_account":"ACC-20002"},"depends_on":["t1"]}]}'
                )
            if "转账" in prompt:
                return (
                    '{"tasks":[{"id":"t1","agent":"transfer","action":"transfer",'
                    '"params":{"amount":100.0,"to_account":"ACC-20002"},"depends_on":[]}]}'
                )
            if "余额" in prompt:
                return '{"tasks":[{"id":"t1","agent":"balance","action":"query_balance","params":{},"depends_on":[]}]}'
            if ("产品" in prompt) or ("理财" in prompt):
                return (
                    '{"tasks":[{"id":"t1","agent":"product","action":"product_qa",'
                    '"params":{"question":"你们有什么理财产品"},"depends_on":[]}]}'
                )
            return (
                '{"tasks":[{"id":"t1","agent":"chat","action":"chitchat",'
                '"params":{"message":"你好"},"depends_on":[]}]}'
            )
        return f"[MOCK_LLM_REPLY] {prompt[:80]}"

    old_intent_call = intent_classifier_module.call_llm
    old_agent_call = agents_module.call_llm
    intent_classifier_module.call_llm = _mock_call_llm
    agents_module.call_llm = _mock_call_llm
    classifier = IntentClassifier()
    try:
        master = MasterAgent(config=AppConfig())
        tasks_payload = classifier.classify(user_input=user_input, recent_context=[])
        tasks = tasks_payload["tasks"]
        return await master.run(tasks=tasks)
    finally:
        intent_classifier_module.call_llm = old_intent_call
        agents_module.call_llm = old_agent_call


def test_query_balance() -> None:
    result = asyncio.run(_run_case("帮我查一下余额"))
    messages = [item["message"] for item in result["results"].values()]
    _assert(any("余额查询完成" in m for m in messages), "余额查询场景失败")


def test_transfer() -> None:
    result = asyncio.run(_run_case("我要转账 100 元"))
    messages = [item["message"] for item in result["results"].values()]
    _assert(any("转账成功" in m for m in messages), "转账场景失败")


def test_balance_then_transfer() -> None:
    result = asyncio.run(_run_case("先查询余额然后转账"))
    task_ids: List[str] = list(result["results"].keys())
    _assert("auto_risk" in task_ids, "复合转账场景缺少自动风控任务")
    _assert(task_ids.index("auto_risk") < task_ids.index("t2"), "风控应先于转账完成")
    _assert("余额查询完成" in result["results"]["t1"]["message"], "复合场景第一步失败")
    _assert("转账成功" in result["results"]["t2"]["message"], "复合场景第二步失败")


def test_product_qa() -> None:
    result = asyncio.run(_run_case("你们有什么理财产品"))
    messages = [item["message"] for item in result["results"].values()]
    _assert(any("产品问答完成" in m for m in messages), "产品咨询场景失败")


def test_chitchat_fallback() -> None:
    result = asyncio.run(_run_case("今天天气怎么样呀"))
    messages = [item["message"] for item in result["results"].values()]
    _assert(any("闲聊兜底完成" in m for m in messages), "闲聊兜底场景失败")


def test_transfer_insufficient_balance() -> None:
    master = MasterAgent(config=AppConfig())
    tasks = [
        {
            "id": "t1",
            "agent": "transfer",
            "action": "transfer",
            "params": {"amount": 5000.0, "to_account": "ACC-20002"},
            "depends_on": [],
        }
    ]
    result = asyncio.run(master.run(tasks=tasks, initial_context={"balance": 100.0}))
    _assert("t1" in result["results"], "余额不足场景未执行转账任务")
    _assert("余额不足" in result["results"]["t1"]["message"], "余额不足场景断言失败")


def test_transfer_invalid_amount() -> None:
    master = MasterAgent(config=AppConfig())
    tasks = [
        {
            "id": "t1",
            "agent": "transfer",
            "action": "transfer",
            "params": {"amount": -1.0, "to_account": "ACC-20002"},
            "depends_on": [],
        }
    ]
    result = asyncio.run(master.run(tasks=tasks))
    _assert("金额必须大于 0" in result["results"]["t1"]["message"], "非法金额场景断言失败")


def test_risk_block() -> None:
    master = MasterAgent(config=AppConfig(transfer_daily_limit=1000.0))
    tasks = [
        {
            "id": "t1",
            "agent": "risk",
            "action": "risk_check",
            "params": {"amount": 5000.0},
            "depends_on": [],
        }
    ]
    result = asyncio.run(master.run(tasks=tasks))
    _assert(result["results"]["t1"]["success"] is False, "风控拦截场景应失败")
    _assert("超过单日限额" in result["results"]["t1"]["message"], "风控拦截提示不正确")


def test_transfer_auto_risk_block() -> None:
    master = MasterAgent(config=AppConfig(transfer_daily_limit=1000.0))
    tasks = [
        {
            "id": "t1",
            "agent": "transfer",
            "action": "transfer",
            "params": {"amount": 5000.0, "to_account": "ACC-20002"},
            "depends_on": [],
        }
    ]
    result = asyncio.run(master.run(tasks=tasks))
    _assert("auto_risk" in result["results"], "自动风控任务未生成")
    _assert(result["results"]["auto_risk"]["success"] is False, "自动风控应拦截超限转账")
    _assert("t1" not in result["results"], "风控失败后不应继续执行转账")


def test_intent_non_json_fallback() -> None:
    old_call_llm = intent_classifier_module.call_llm
    try:
        intent_classifier_module.call_llm = lambda prompt: "不是 JSON"
        classifier = IntentClassifier()
        payload = classifier.classify(user_input="任意输入", recent_context=[])
        tasks = payload.get("tasks", [])
        _assert(len(tasks) == 1, "非 JSON 回退任务数量不正确")
        _assert(tasks[0]["agent"] == "chat", "非 JSON 应回退到 chat agent")
        _assert(tasks[0]["action"] == "chitchat", "非 JSON 应回退到 chitchat action")
    finally:
        intent_classifier_module.call_llm = old_call_llm


def test_cycle_dependency_guard() -> None:
    master = MasterAgent(config=AppConfig())
    tasks = [
        {"id": "t1", "agent": "balance", "action": "query_balance", "params": {}, "depends_on": ["t2"]},
        {"id": "t2", "agent": "transfer", "action": "transfer", "params": {"amount": 100.0}, "depends_on": ["t1"]},
    ]
    result = asyncio.run(master.run(tasks=tasks))
    _assert("t1" not in result["results"], "循环依赖场景不应执行余额任务")
    _assert("t2" not in result["results"], "循环依赖场景不应执行转账任务")
    _assert(any("未满足依赖" in log for log in result["logs"]), "循环依赖场景缺少错误日志")


def test_session_title_and_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "sessions_store.json")

        sm = SessionManager(config=AppConfig(), store_path=store_path, namer=lambda s: f"标题-{s[:3]}")
        session = sm.create_session()
        sm.add_user_and_assistant_turn(session.session_id, "帮我查一下余额", "余额查询完成")

        reloaded = SessionManager(config=AppConfig(), store_path=store_path, namer=lambda s: "should_not_call")
        s2 = reloaded.get_session(session.session_id)
        _assert(s2 is not None, "会话持久化后未能恢复")
        _assert(s2.title is not None and s2.title.startswith("标题-"), "会话标题未正确生成")
        recent = reloaded.get_recent_context_for_classifier(session.session_id, max_rounds=5)
        _assert(len(recent) == 1, "最近上下文轮数不正确")
        _assert(recent[0]["user"] == "帮我查一下余额", "最近上下文 user_input 不正确")
        _assert(recent[0]["assistant"] == "余额查询完成", "最近上下文 assistant_output 不正确")


def test_session_recent_order_and_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "sessions_store.json")
        sm = SessionManager(config=AppConfig(), store_path=store_path, namer=lambda s: f"T{s[:2]}")

        s1 = sm.create_session()
        sm.add_user_and_assistant_turn(s1.session_id, "查询余额", "余额查询完成")

        # 确保 s2 的 updated_at 更晚
        time.sleep(0.01)
        s2 = sm.create_session()
        sm.add_user_and_assistant_turn(s2.session_id, "我要转账100", "转账成功")

        recent = sm.list_recent_sessions(limit=20)
        _assert(recent and recent[0].session_id == s2.session_id, "最近会话排序不正确")

        deleted = sm.delete_session(s1.session_id)
        _assert(deleted is True, "删除会话返回值不正确")
        _assert(sm.get_session(s1.session_id) is None, "删除后会话仍存在")


def test_service_api_message_and_context() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "sessions_store.json")
        service = AgentService(store_path=store_path, namer=lambda s: f"标题-{s[:4]}")

        first = service.handle_user_message("帮我查一下余额")
        _assert(first["success"] is True, "服务接口首轮调用应成功")
        _assert(first["code"] == "OK", "服务接口成功 code 不正确")
        _assert(first["request_id"], "服务接口应返回 request_id")
        _assert(first["session_id"], "服务接口应返回 session_id")
        _assert(first["session_created"] is True, "首轮调用应自动创建会话")
        _assert("余额查询完成" in first["reply"], "服务接口回复不正确")
        _assert(first["session"]["turn_count"] == 1, "服务接口 session 摘要轮数不正确")
        _assert(first["task_summary"], "服务接口应返回任务摘要")
        _assert(len(first["recent_context"]) == 1, "首轮后上下文应有 1 条")

        second = service.handle_user_message("我要转账100元", session_id=first["session_id"])
        _assert(second["session_id"] == first["session_id"], "服务接口应复用传入会话")
        _assert(second["session_created"] is False, "传入已有会话时不应创建新会话")
        _assert(second["code"] == "NEED_MORE_INFO", "转账信息不全时应追问")
        _assert(second["need_user_input"] is True, "转账信息不全时应等待用户补充")
        _assert("收款人名称" in second["reply"], "转账追问应包含收款人")
        _assert(len(second["recent_context"]) == 2, "第二轮后上下文应有 2 条")

        sessions = service.list_sessions(limit=20)
        _assert(len(sessions["sessions"]) == 1, "历史会话列表数量不正确")
        _assert(sessions["sessions"][0]["turn_count"] == 2, "历史会话轮数不正确")
        _assert(sessions["groups"][0]["key"] == "today", "当天历史会话应归入今天分组")


def test_service_api_empty_message() -> None:
    service = AgentService(namer=lambda s: "不会调用")
    result = service.handle_user_message("   ")
    _assert(result["success"] is False, "空输入应返回失败")
    _assert(result["code"] == "EMPTY_INPUT", "空输入 code 不正确")
    _assert(result["need_user_input"] is True, "空输入应要求用户继续输入")


def test_service_api_session_grouping() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "sessions_store.json")
        service = AgentService(store_path=store_path, namer=lambda s: f"T{s[:2]}")

        now = time.time()
        day_seconds = 86400
        samples = [
            ("今天的问题", now),
            ("近7天的问题", now - 3 * day_seconds),
            ("近30天的问题", now - 20 * day_seconds),
            ("近半年的问题", now - 100 * day_seconds),
            ("更早的问题", now - 220 * day_seconds),
        ]
        for text, updated_at in samples:
            session = service.session_manager.create_session()
            service.session_manager.add_user_and_assistant_turn(session.session_id, text, "回复")
            stored = service.session_manager.get_session(session.session_id)
            if stored:
                stored.updated_at = updated_at

        grouped = service.list_sessions(limit=20)["groups"]
        keys = [group["key"] for group in grouped]
        _assert(keys == ["today", "last_7_days", "last_30_days", "last_6_months", "earlier"], "历史会话分组不正确")


def test_product_purchase_workflow() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "sessions_store.json")
        service = AgentService(store_path=store_path, namer=lambda s: f"T{s[:2]}")

        first = service.handle_user_message("我想买理财")
        _assert(first["code"] == "NEED_MORE_INFO", "产品购买流程应先追问信息")
        _assert(first["need_user_input"] is True, "追问信息时应等待用户输入")
        _assert(first["pending_workflow"]["status"] == "collecting_requirements", "流程状态不正确")

        second = service.handle_user_message("低风险 3个月 1000元", session_id=first["session_id"])
        _assert(second["code"] == "NEED_USER_SELECTION", "信息齐全后应要求选择产品")
        _assert("筛选到以下产品" in second["reply"], "产品候选回复不正确")
        _assert(second["pending_workflow"]["status"] == "waiting_product_selection", "产品选择状态不正确")

        third = service.handle_user_message("选第1个", session_id=first["session_id"])
        _assert(third["code"] == "NEED_CONFIRMATION", "选择产品后应要求确认")
        _assert("请回复“确认”继续" in third["reply"], "确认提示不正确")

        fourth = service.handle_user_message("确认", session_id=first["session_id"])
        _assert(fourth["code"] == "OK", "确认后应执行流程")
        _assert(fourth["workflow_completed"] is True, "确认后流程应完成")
        _assert(fourth["pending_workflow"] is None, "流程完成后不应保留待办流程")
        _assert("风控校验通过" in fourth["reply"], "确认后应执行风控")
        _assert("转账成功" in fourth["reply"], "确认后应执行交易提交")


def test_product_purchase_workflow_cancel() -> None:
    service = AgentService(namer=lambda s: f"T{s[:2]}")
    first = service.handle_user_message("推荐一个理财产品")
    second = service.handle_user_message("低风险 3个月 1000元", session_id=first["session_id"])
    third = service.handle_user_message("选第1个", session_id=first["session_id"])
    _assert(third["code"] == "NEED_CONFIRMATION", "取消测试前应进入确认状态")

    cancelled = service.handle_user_message("取消", session_id=first["session_id"])
    _assert(cancelled["code"] == "WORKFLOW_CANCELLED", "取消流程 code 不正确")
    _assert(cancelled["pending_workflow"] is None, "取消后不应保留待办流程")


def test_business_clients_placeholders() -> None:
    config = AppConfig()
    balance = business_clients.query_balance(config.account_id, context={"balance": 888.0})
    _assert(balance["success"] is True, "余额占位接口应成功")
    _assert(balance["balance"] == 888.0, "余额占位接口返回金额不正确")

    products = business_clients.query_products({"risk_level": "low", "term": "3个月", "amount": 1000.0})
    _assert(products["success"] is True, "产品占位接口应成功")
    _assert(len(products["products"]) >= 1, "产品占位接口应返回候选产品")

    risk = business_clients.run_risk_check({"amount": 100.0}, config)
    _assert(risk["success"] is True, "风控占位接口应通过低金额")

    transfer = business_clients.submit_transfer(
        {"amount": 100.0, "to_account": "ACC-20002"},
        {"balance": 500.0},
        config,
    )
    _assert(transfer["success"] is True, "转账占位接口应成功")
    _assert("transaction_id" in transfer, "转账占位接口应返回 transaction_id")

    purchase = business_clients.submit_product_purchase(
        products["products"][0],
        {"amount": 1000.0},
        config,
    )
    _assert(purchase["success"] is True, "产品购买占位接口应成功")
    _assert("order_id" in purchase, "产品购买占位接口应返回 order_id")


def test_clarification_unit_transfer_missing_fields() -> None:
    tasks = [{"id": "t1", "agent": "transfer", "action": "transfer", "params": {}, "depends_on": []}]
    result = clarification_unit.check_clarification("我要转账100元", tasks)
    _assert(result["need_clarification"] is True, "转账信息不全应触发追问")
    _assert("payee_name" in result["missing_fields"], "追问应识别缺少收款人")
    _assert("to_account" in result["missing_fields"], "追问应识别缺少收款账号")
    _assert("bank_name" in result["missing_fields"], "追问应识别缺少目标银行")


def test_service_api_transfer_full_info() -> None:
    service = AgentService(namer=lambda s: f"T{s[:2]}")
    result = service.handle_user_message("给张三转账100元，工商银行，账号622200001111")
    _assert(result["code"] == "OK", "完整转账信息应继续执行")
    _assert(result["need_user_input"] is False, "完整转账信息不应追问")
    _assert("风控校验通过" in result["reply"], "完整转账应执行风控")
    _assert("转账成功" in result["reply"], "完整转账应执行转账")


def test_http_server_chat_endpoint() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), AgentHttpHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=5)
        body = json.dumps({"user_input": "帮我查一下余额"}, ensure_ascii=False).encode("utf-8")
        conn.request("POST", "/api/chat", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        conn.close()
        _assert(response.status == 200, "HTTP 聊天接口状态码不正确")
        _assert(payload["code"] == "OK", "HTTP 聊天接口 code 不正确")
        _assert("余额查询完成" in payload["reply"], "HTTP 聊天接口回复不正确")
        _assert(payload["session_id"], "HTTP 聊天接口应返回 session_id")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_all_tests() -> None:
    cases = [
        ("查询余额", test_query_balance),
        ("转账", test_transfer),
        ("查询余额并转账", test_balance_then_transfer),
        ("产品咨询", test_product_qa),
        ("闲聊兜底", test_chitchat_fallback),
        ("转账失败-余额不足", test_transfer_insufficient_balance),
        ("转账失败-非法金额", test_transfer_invalid_amount),
        ("风控拦截", test_risk_block),
        ("自动风控阻断转账", test_transfer_auto_risk_block),
        ("意图解析异常回退", test_intent_non_json_fallback),
        ("循环依赖保护", test_cycle_dependency_guard),
        ("会话标题与持久化", test_session_title_and_persistence),
        ("会话最近排序与删除", test_session_recent_order_and_delete),
        ("服务接口消息与上下文", test_service_api_message_and_context),
        ("服务接口空输入", test_service_api_empty_message),
        ("服务接口历史分组", test_service_api_session_grouping),
        ("产品购买复杂编排", test_product_purchase_workflow),
        ("产品购买流程取消", test_product_purchase_workflow_cancel),
        ("业务接口占位层", test_business_clients_placeholders),
        ("追问单元-转账缺字段", test_clarification_unit_transfer_missing_fields),
        ("服务接口-完整转账信息", test_service_api_transfer_full_info),
        ("HTTP接口-聊天入口", test_http_server_chat_endpoint),
    ]
    passed = 0
    failed = 0
    for name, fn in cases:
        try:
            fn()
            passed += 1
            print(f"[PASS] {name}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n测试完成：PASS={passed}, FAIL={failed}")


if __name__ == "__main__":
    run_all_tests()



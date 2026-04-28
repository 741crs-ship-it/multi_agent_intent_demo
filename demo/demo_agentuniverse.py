"""
demo_agentuniverse.py

这是一个使用 agentUniverse 思路组织的“意图分类 + 多 Agent 调度”示例。

说明：
1. 如果本地已经安装 agentUniverse，本文件会优先尝试导入相关基类。
2. 即使没有安装 agentUniverse，本文件也提供了兼容的本地 Agent 基类。
3. 每一步都会用中文 print 说明当前做了什么。

运行方式：
    python demo_agentuniverse.py
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

# 启动即打印一行纯 ASCII（同时写到 stdout/stderr），避免某些终端只显示其一或吞掉 stderr 时误以为“没反应”。
_BOOT = "[demo] script started (correct .py is executing)\n"
sys.stderr.write(_BOOT)
sys.stderr.flush()
sys.stdout.write(_BOOT)
sys.stdout.flush()

print("[demo] 正在加载依赖（agentUniverse 体积较大，第一次可能要等几秒）…", flush=True)


try:
    # 尝试导入 agentUniverse 的 Agent 基类，体现本示例基于 agentUniverse 的 Agent 设计。
    # 不同版本的 agentUniverse 包结构可能略有差异，所以这里仅做可选导入。
    from agentuniverse.agent.agent import Agent as AgentUniverseAgent  # type: ignore
except Exception:
    # 如果没有安装 agentUniverse，就使用本地兼容基类，保证本文件可以直接运行。
    class AgentUniverseAgent:
        """agentUniverse Agent 的简化兼容基类。"""

        pass


VALID_INTENTS = [
    "product_qa",
    "transfer",
    "balance_query",
    "risk_check",
    "chitchat",
]

DEPENDENCY_ORDER = [
    "product_qa",
    "balance_query",
    "risk_check",
    "transfer",
    "chitchat",
]


@dataclass
class AgentResult:
    """保存每个功能 Agent 的执行结果。"""

    intent: str
    message: str


class BaseDemoAgent(AgentUniverseAgent):
    """示例 Agent 基类，统一保存 Agent 名称并定义 run 方法。"""

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "name", name)

    # 声明当前示例 Agent 需要的输入字段，满足 agentUniverse 抽象基类要求。
    def input_keys(self) -> List[str]:
        return ["user_input"]

    # 声明当前示例 Agent 输出的字段，满足 agentUniverse 抽象基类要求。
    def output_keys(self) -> List[str]:
        return ["result"]

    # 解析 agentUniverse 标准输入对象，这里保留原始字典，便于快速理解。
    def parse_input(self, input_object: object, agent_input: dict) -> dict:
        return agent_input

    # 解析 agentUniverse 标准输出对象，这里保留原始结果字典。
    def parse_result(self, agent_result: dict) -> dict:
        return agent_result

    # 执行当前 Agent 的核心逻辑。
    def run(self, user_input: str) -> AgentResult:
        raise NotImplementedError("子类必须实现 run 方法")


class IntentClassifierAgent(BaseDemoAgent):
    """意图分类 Agent：负责把用户输入识别成一个或多个意图。"""

    def __init__(self) -> None:
        super().__init__("intent_classifier_agent")

    # 根据关键词识别用户输入中的意图。
    def classify(self, user_input: str) -> List[str]:
        print(f"[{self.name}] 第一步：接收用户输入，准备识别意图。")
        print(f"[{self.name}] 用户输入：{user_input}")

        text = user_input.lower()
        intents: List[str] = []

        product_keywords = ["产品", "支持", "跨行", "打款", "手续费", "限额", "规则"]
        transfer_keywords = ["转", "转账", "付款", "支付", "打款", "汇款", "招商银行", "万"]
        balance_keywords = ["余额", "查询余额", "还有多少钱", "账户金额"]
        risk_keywords = ["风控", "风险", "校验", "审核", "安全"]

        if self._contains_any(text, product_keywords):
            intents.append("product_qa")
            print(f"[{self.name}] 识别到 product_qa：用户在问产品相关问题。")

        if self._contains_any(text, transfer_keywords):
            intents.append("transfer")
            print(f"[{self.name}] 识别到 transfer：用户有转账或付款需求。")

        if self._contains_any(text, balance_keywords):
            intents.append("balance_query")
            print(f"[{self.name}] 识别到 balance_query：用户想查询余额。")

        if self._contains_any(text, risk_keywords):
            intents.append("risk_check")
            print(f"[{self.name}] 识别到 risk_check：用户提到了风控或安全校验。")

        if "transfer" in intents and "risk_check" not in intents:
            intents.append("risk_check")
            print(f"[{self.name}] 检测到转账任务，自动补充 risk_check，因为转账前必须先风控校验。")

        if not intents:
            intents.append("chitchat")
            print(f"[{self.name}] 未识别到明确业务意图，归类为 chitchat 兜底闲聊。")

        ordered_intents = self._deduplicate(intents)
        print(f"[{self.name}] 意图识别完成：{ordered_intents}")
        return ordered_intents

    # 判断文本中是否包含任意关键词。
    @staticmethod
    def _contains_any(text: str, keywords: Sequence[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    # 对意图列表去重，避免同一个 Agent 被重复调度。
    @staticmethod
    def _deduplicate(intents: Sequence[str]) -> List[str]:
        result: List[str] = []
        for intent in intents:
            if intent not in result:
                result.append(intent)
        return result


class ProductAgent(BaseDemoAgent):
    """产品问答 Agent：模拟回答产品相关问题。"""

    def __init__(self) -> None:
        super().__init__("product_agent")

    # 执行产品问答逻辑。
    def run(self, user_input: str) -> AgentResult:
        print(f"[{self.name}] 第二步：处理产品问答。")
        print(f"[{self.name}] 模拟执行：查询产品说明、跨行打款能力、限额和规则。")
        return AgentResult("product_qa", "产品问答已处理：该产品支持跨行打款，实际限额以风控结果为准。")


class TransferAgent(BaseDemoAgent):
    """转账 Agent：模拟执行转账或付款任务。"""

    def __init__(self) -> None:
        super().__init__("transfer_agent")

    # 执行转账或付款逻辑。
    def run(self, user_input: str) -> AgentResult:
        print(f"[{self.name}] 第四步：处理转账或付款。")
        print(f"[{self.name}] 模拟执行：解析收款银行、转账金额，并发起转账流程。")
        return AgentResult("transfer", "转账任务已提交：已模拟向目标银行发起付款。")


class BalanceAgent(BaseDemoAgent):
    """余额查询 Agent：模拟查询账户余额。"""

    def __init__(self) -> None:
        super().__init__("balance_agent")

    # 执行余额查询逻辑。
    def run(self, user_input: str) -> AgentResult:
        print(f"[{self.name}] 第二步：处理余额查询。")
        print(f"[{self.name}] 模拟执行：查询账户当前可用余额。")
        return AgentResult("balance_query", "余额查询完成：当前可用余额为 1,280,000 元。")


class RiskAgent(BaseDemoAgent):
    """风控 Agent：模拟执行转账前的风险校验。"""

    def __init__(self) -> None:
        super().__init__("risk_agent")

    # 执行风控校验逻辑。
    def run(self, user_input: str) -> AgentResult:
        print(f"[{self.name}] 第三步：处理风控校验。")
        print(f"[{self.name}] 模拟执行：校验账户状态、交易金额、收款方和风险规则。")
        return AgentResult("risk_check", "风控校验通过：允许继续执行后续转账任务。")


class GeneralAgent(BaseDemoAgent):
    """兜底闲聊 Agent：处理无法归类的普通对话。"""

    def __init__(self) -> None:
        super().__init__("general_agent")

    # 执行兜底闲聊逻辑。
    def run(self, user_input: str) -> AgentResult:
        print(f"[{self.name}] 第二步：处理兜底闲聊。")
        print(f"[{self.name}] 模拟执行：生成普通聊天回复。")
        return AgentResult("chitchat", "你好，我可以帮你处理产品问答、转账、余额查询和风控校验。")


class MasterAgent(BaseDemoAgent):
    """总控 Agent：接收用户输入，调用意图分类 Agent，并调度功能 Agent。"""

    def __init__(self) -> None:
        super().__init__("master_agent")
        object.__setattr__(self, "classifier", IntentClassifierAgent())
        object.__setattr__(
            self,
            "agent_map",
            {
                "product_qa": ProductAgent(),
                "transfer": TransferAgent(),
                "balance_query": BalanceAgent(),
                "risk_check": RiskAgent(),
                "chitchat": GeneralAgent(),
            },
        )

    # 总入口：接收用户输入并按指定模式完成调度。
    def handle(self, user_input: str, mode: str = "serial") -> List[AgentResult]:
        print("=" * 80)
        print(f"[{self.name}] 总控 Agent 已收到用户请求。")
        print(f"[{self.name}] 当前调度模式：{mode}")

        intents = self.classifier.classify(user_input)
        scheduled_intents = self._build_schedule(intents, mode)

        print(f"[{self.name}] 调度计划生成完成：{scheduled_intents}")

        if mode == "parallel":
            return self._run_parallel(user_input, scheduled_intents)

        return self._run_serial(user_input, scheduled_intents)

    # 根据串行或并行模式生成调度顺序。
    def _build_schedule(self, intents: Sequence[str], mode: str) -> List[str]:
        if mode not in {"serial", "parallel"}:
            raise ValueError("mode 只能是 serial 或 parallel")

        if mode == "parallel":
            print(f"[{self.name}] 并行模式：不依赖顺序的任务会被视为同时执行。")
            return list(intents)

        print(f"[{self.name}] 串行模式：按依赖顺序执行任务。")
        return [intent for intent in DEPENDENCY_ORDER if intent in intents]

    # 串行执行：按依赖顺序逐个调用功能 Agent。
    def _run_serial(self, user_input: str, scheduled_intents: Sequence[str]) -> List[AgentResult]:
        print(f"[{self.name}] 开始串行调度。")
        results: List[AgentResult] = []

        for intent in scheduled_intents:
            agent = self.agent_map[intent]
            print(f"[{self.name}] 正在调度 {agent.name}，对应意图：{intent}")
            result = agent.run(user_input)
            results.append(result)

        print(f"[{self.name}] 串行调度完成。")
        return results

    # 并行执行：用同步代码模拟同时调度多个不依赖顺序的 Agent。
    def _run_parallel(self, user_input: str, scheduled_intents: Sequence[str]) -> List[AgentResult]:
        print(f"[{self.name}] 开始并行调度。")
        print(f"[{self.name}] 为了演示清晰，这里用同步循环模拟“同时发起多个 Agent”。")

        tasks: List[Callable[[], AgentResult]] = []
        for intent in scheduled_intents:
            agent = self.agent_map[intent]
            print(f"[{self.name}] 已把 {agent.name} 加入并行任务列表，对应意图：{intent}")
            tasks.append(lambda current_agent=agent: current_agent.run(user_input))

        results = [task() for task in tasks]
        print(f"[{self.name}] 并行调度完成。")
        return results


# 打印最终结果，方便直观看到每个 Agent 的输出。
def print_results(results: Sequence[AgentResult]) -> None:
    print("[结果汇总] 以下是各功能 Agent 的执行结果：")
    for item in results:
        print(f"- {item.intent}: {item.message}")
    print("=" * 80)


# 演示固定输入，展示多意图和单意图处理效果。
def run_demo_examples() -> None:
    master_agent = MasterAgent()

    example_1 = "这个产品支持跨行打款吗？帮我向招商银行转100万"
    results_1 = master_agent.handle(example_1, mode="serial")
    print_results(results_1)

    example_2 = "查询余额"
    results_2 = master_agent.handle(example_2, mode="serial")
    print_results(results_2)

    example_3 = "这个产品支持跨行打款吗？帮我向招商银行转100万"
    results_3 = master_agent.handle(example_3, mode="parallel")
    print_results(results_3)


# 程序入口：运行示例，也支持用户自己输入内容测试。
def main() -> None:
    print("这是 agentUniverse 风格的意图分类 + 多 Agent 调度 Demo。", flush=True)
    print("如果直接按回车，会自动运行题目中的示例。", flush=True)

    try:
        user_input = input("请输入你的问题：").strip()
        mode = input("请选择调度模式 serial/parallel，默认 serial：").strip() or "serial"
    except EOFError:
        # 某些运行方式下 stdin 立刻结束（无交互），会导致 input 失败，看起来像“什么都没问就结束了”。
        print(
            "[demo] 无法读取键盘输入（stdin 已结束）。已自动改为运行内置示例。",
            flush=True,
        )
        print(
            '[demo] 若你想指定一句话，可用：python demo_agentuniverse.py -q "查询余额" -m serial',
            flush=True,
        )
        run_demo_examples()
        return

    if user_input:
        master_agent = MasterAgent()
        results = master_agent.handle(user_input, mode=mode)
        print_results(results)
    else:
        run_demo_examples()


# 若正在使用 Windows 商店/别名版 python.exe，很多问题会表现为“没输出或马上退出”。
def warn_if_python_may_be_store_alias() -> None:
    exe = (sys.executable or "").lower().replace("/", "\\")
    if "windowsapps" in exe or exe.endswith("python.app\\python.exe"):
        sys.stderr.write(
            "[demo] 警告：当前 python 更像“应用商店/别名入口”，不一定真的是 Python312。\n"
            "[demo] 建议：在同一目录运行 .\\run_demo.bat，或在终端先执行 "
            'where.exe python 检查路径。\n'
        )
        sys.stderr.flush()


# 解析命令行参数，用来在终端里一键测试（不依赖 input 交互）。
def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="意图分类 + 多 Agent 调度 Demo（可交互，也可命令行一键跑）",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="直接运行内置 3 组示例，不需要输入问题",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default="",
        help='只测一句话，例如："查询余额"',
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["serial", "parallel"],
        default="serial",
        help="调度模式：serial 串行，parallel 并行",
    )
    parser.add_argument(
        "--which-python",
        action="store_true",
        help="打印当前使用的 python.exe 路径后退出，用来排查“没反应”",
    )
    return parser.parse_args(list(argv))


if __name__ == "__main__":
    warn_if_python_may_be_store_alias()
    args = parse_args(sys.argv[1:])
    if args.which_python:
        print(sys.executable, flush=True)
        raise SystemExit(0)
    if args.demo:
        run_demo_examples()
        raise SystemExit(0)
    if args.query:
        master_agent = MasterAgent()
        results = master_agent.handle(args.query, mode=args.mode)
        print_results(results)
        raise SystemExit(0)
    # 未传任何参数时：若 stdin 不是交互终端，input() 往往不可用，直接跑内置示例避免“无任何提示就退出”。
    if not sys.stdin.isatty():
        print(
            "[demo] 检测到非交互 stdin（无法用 input 提问）。自动运行内置示例。",
            flush=True,
        )
        print(
            '[demo] 若你想自行输入，请在 Cursor 的集成终端里运行，或使用：'
            "python demo_agentuniverse.py -q \"查询余额\" -m serial",
            flush=True,
        )
        run_demo_examples()
        raise SystemExit(0)
    main()

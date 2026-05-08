"""Clarification unit before agent dispatch.

This module checks whether a recognized intent has enough information to call
downstream agents. It does not execute business logic and does not own the
underlying specialized agents.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def check_clarification(
    user_input: str,
    tasks: List[Dict[str, Any]],
    recent_context: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Return clarification question when required fields are missing."""
    del recent_context  # Reserved for later context-aware clarification.

    intents = {str(task.get("agent", "")) for task in tasks}
    if "transfer" in intents:
        return _check_transfer(user_input)

    return {
        "need_clarification": False,
        "intent": "",
        "missing_fields": [],
        "question": "",
        "filled_fields": {},
    }


def _check_transfer(user_input: str) -> Dict[str, Any]:
    filled_fields = {
        "amount": _parse_amount(user_input),
        "payee_name": _parse_payee_name(user_input),
        "to_account": _parse_account(user_input),
        "bank_name": _parse_bank_name(user_input),
    }
    required = ["amount", "payee_name", "to_account", "bank_name"]
    missing = [field for field in required if not filled_fields.get(field)]
    if not missing:
        return {
            "need_clarification": False,
            "intent": "transfer",
            "missing_fields": [],
            "question": "",
            "filled_fields": filled_fields,
        }

    labels = {
        "amount": "转账金额",
        "payee_name": "收款人名称",
        "to_account": "收款账号",
        "bank_name": "目标银行",
    }
    return {
        "need_clarification": True,
        "intent": "transfer",
        "missing_fields": missing,
        "question": f"为了继续转账，请补充：{'、'.join(labels[field] for field in missing)}。",
        "filled_fields": {key: value for key, value in filled_fields.items() if value},
    }


def _parse_amount(user_input: str) -> float | None:
    amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(万|元|块)?", user_input)
    if not amount_match:
        return None
    if not any(word in user_input for word in ("元", "万", "块", "金额", "转", "付", "汇", "打")):
        return None
    amount = float(amount_match.group(1))
    unit = amount_match.group(2) or "元"
    return amount * 10000 if unit == "万" else amount


def _parse_bank_name(user_input: str) -> str:
    bank_aliases = [
        ("工商银行", ("工商银行", "工行")),
        ("建设银行", ("建设银行", "建行")),
        ("农业银行", ("农业银行", "农行")),
        ("中国银行", ("中国银行", "中行")),
        ("招商银行", ("招商银行", "招行")),
        ("交通银行", ("交通银行", "交行")),
        ("宁波银行", ("宁波银行",)),
    ]
    for bank_name, aliases in bank_aliases:
        if any(alias in user_input for alias in aliases):
            return bank_name
    return ""


def _parse_account(user_input: str) -> str:
    labelled = re.search(r"(?:账号|账户|卡号)\s*[:：]?\s*([A-Za-z0-9-]{6,})", user_input)
    if labelled:
        return labelled.group(1)
    long_number = re.search(r"\b(\d{8,})\b", user_input)
    return long_number.group(1) if long_number else ""


def _parse_payee_name(user_input: str) -> str:
    patterns = [
        r"给\s*([\u4e00-\u9fa5A-Za-z0-9]{2,20})",
        r"收款人\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z0-9]{2,20})",
    ]
    stop_words = ("转账", "转", "付款", "汇款", "打款", "工商", "建设", "农业", "中国", "招商", "交通", "宁波", "银行", "账号", "账户", "卡号")
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if not match:
            continue
        name = match.group(1)
        for stop_word in stop_words:
            if stop_word in name:
                name = name.split(stop_word, 1)[0]
        name = name.strip()
        if name:
            return name
    return ""

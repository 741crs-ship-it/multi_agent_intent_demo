"""Business system client placeholders.

This module is the boundary between Agent orchestration and real bank systems.
The current implementation uses deterministic mock data and Python standard
library only. During intranet migration, replace function bodies here with real
internal API calls, and keep function signatures stable where possible.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

from config import AppConfig


def query_balance(account_id: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Query account balance.

    In intranet, replace this body with the real account/balance service call.
    """
    context = context or {}
    balance = float(context.get("balance", 1200.0))
    return {
        "success": True,
        "code": "OK",
        "message": "余额查询完成",
        "account_id": account_id,
        "balance": balance,
        "currency": "CNY",
        "source": "mock",
    }


def query_products(requirements: Dict[str, Any]) -> Dict[str, Any]:
    """Query and filter product candidates.

    In intranet, replace this body with the real product search/filter service.
    Expected requirements may include risk_level, term, amount, currency, and
    customer_type.
    """
    risk_level = str(requirements.get("risk_level", "low"))
    risk_label = {"low": "低风险", "medium": "中风险", "high": "高风险"}.get(risk_level, "稳健")
    term = str(requirements.get("term", "3个月"))
    products: List[Dict[str, Any]] = [
        {
            "product_id": "P-001",
            "name": f"{risk_label}{term}现金管理产品A",
            "risk_level": risk_level,
            "term": term,
            "expected_yield": "2.10%",
            "currency": "CNY",
            "min_amount": 100.0,
            "settlement_account": "PRODUCT-SETTLE-001",
        },
        {
            "product_id": "P-002",
            "name": f"{risk_label}{term}稳健理财产品B",
            "risk_level": risk_level,
            "term": term,
            "expected_yield": "2.35%",
            "currency": "CNY",
            "min_amount": 100.0,
            "settlement_account": "PRODUCT-SETTLE-002",
        },
    ]
    return {
        "success": True,
        "code": "OK",
        "message": "产品查询完成",
        "products": products,
        "source": "mock",
    }


def run_risk_check(params: Dict[str, Any], config: AppConfig) -> Dict[str, Any]:
    """Run risk check before transaction-like operations.

    In intranet, replace this body with real risk control service calls.
    """
    amount = _to_float(params.get("amount", 0.0))
    ok = amount <= config.transfer_daily_limit
    return {
        "success": ok,
        "code": "OK" if ok else "LIMIT_EXCEEDED",
        "message": "风控校验通过" if ok else "风控校验失败：超过单日限额",
        "risk_ok": ok,
        "amount": amount,
        "source": "mock",
    }


def submit_transfer(params: Dict[str, Any], context: Dict[str, Any], config: AppConfig) -> Dict[str, Any]:
    """Submit transfer transaction.

    In intranet, replace this body with the real payment/transfer service call.
    """
    amount = _to_float(params.get("amount", 0.0))
    to_account = str(params.get("to_account", "UNKNOWN"))
    balance = _to_float(context.get("balance", 1200.0))

    if amount <= 0:
        return {
            "success": False,
            "code": "INVALID_AMOUNT",
            "message": "转账失败：金额必须大于 0",
            "source": "mock",
        }
    if amount > balance:
        return {
            "success": False,
            "code": "INSUFFICIENT_BALANCE",
            "message": "转账失败：余额不足",
            "balance": balance,
            "source": "mock",
        }

    new_balance = balance - amount
    return {
        "success": True,
        "code": "OK",
        "message": f"转账成功，向 {to_account} 转账 {amount:.2f} {config.default_currency}",
        "transaction_id": f"T-{uuid.uuid4()}",
        "amount": amount,
        "to_account": to_account,
        "balance": new_balance,
        "currency": config.default_currency,
        "submitted_at": time.time(),
        "source": "mock",
    }


def submit_product_purchase(
    product: Dict[str, Any],
    requirements: Dict[str, Any],
    config: AppConfig,
) -> Dict[str, Any]:
    """Submit product purchase.

    Current demo maps purchase settlement to a transaction-like submission. In
    intranet, replace this with the real product purchase/subscription service.
    """
    amount = _to_float(requirements.get("amount", 0.0))
    if amount <= 0:
        return {
            "success": False,
            "code": "INVALID_AMOUNT",
            "message": "产品购买失败：金额必须大于 0",
            "source": "mock",
        }
    return {
        "success": True,
        "code": "OK",
        "message": f"产品购买申请已提交：{product.get('name', '未知产品')}，金额 {amount:.2f} {config.default_currency}",
        "order_id": f"PO-{uuid.uuid4()}",
        "product_id": product.get("product_id", ""),
        "amount": amount,
        "currency": config.default_currency,
        "submitted_at": time.time(),
        "source": "mock",
    }


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

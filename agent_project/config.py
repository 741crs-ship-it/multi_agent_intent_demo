"""项目基础配置。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """应用配置，便于内外网统一管理。"""

    max_context_rounds: int = 5
    default_currency: str = "CNY"
    transfer_daily_limit: float = 50000.0
    account_id: str = "ACC-10001"
    session_store_filename: str = "sessions_store.json"


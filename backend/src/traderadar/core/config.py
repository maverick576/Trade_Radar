"""Configuration management for TradeRadar.

Validates environment variables (.env) and application strategy settings (settings.yaml).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatchlistItem(BaseModel):
    """Symbol specification in the watchlist."""

    symbol: str
    display: str
    asset: Literal["crypto", "gold"]


class GoldSettings(BaseModel):
    sources: list[str] = Field(
        default_factory=lambda: [
            "binance_futures:XAUUSDT",
            "binance_spot:PAXGUSDT",
            "oanda:XAU_USD",
        ]
    )
    prefer_oanda_when_available: bool = False
    switch_after_seconds: int = 120
    orderbook_weight_mult: float = 0.5


class TimeframesSettings(BaseModel):
    entry: str = "M15"
    confirm: str = "H1"
    bias: list[str] = Field(default_factory=lambda: ["H4", "D1"])
    backfill_bars: int = 1000


class VwapSettings(BaseModel):
    reset: str = "00:00"
    z_threshold: float = 0.25
    overextended_z: float = 2.0


class EmaRibbonSettings(BaseModel):
    periods: list[int] = Field(default_factory=lambda: [8, 13, 21, 34, 55])


class SupertrendSettings(BaseModel):
    atr_period: int = 10
    multiplier: float = 3.0
    recent_flip_bars: int = 3


class RsiDivSettings(BaseModel):
    period: int = 14
    pivot_left: int = 5
    pivot_right: int = 3
    min_gap: int = 5
    max_gap: int = 60
    valid_bars: int = 10


class BollingerSettings(BaseModel):
    period: int = 20
    std: float = 2.0
    squeeze_pct: float = 20.0
    squeeze_lookback: int = 120


class CvdObvSettings(BaseModel):
    slope_window: int = 20
    norm_window: int = 100
    threshold: float = 0.5


class FundingOiSettings(BaseModel):
    oi_window_hours: int = 4
    oi_change_pct: float = 1.0
    funding_crowded: float = 0.0005
    funding_negative: float = -0.0003


class OrderbookSettings(BaseModel):
    depth_pct: float = 0.5
    smooth_seconds: int = 60
    threshold: float = 0.15


class LightGbmSettings(BaseModel):
    horizon_bars: int = 16
    barrier_atr: float = 1.5
    p_threshold: float = 0.58
    p_margin: float = 0.15
    min_auc: float = 0.55


class SentimentSettings(BaseModel):
    fng_fear: int = 20
    fng_greed: int = 80
    ls_high: float = 2.5
    ls_low: float = 0.7


class IndicatorsSettings(BaseModel):
    vwap: VwapSettings = Field(default_factory=VwapSettings)
    ema_ribbon: EmaRibbonSettings = Field(default_factory=EmaRibbonSettings)
    supertrend: SupertrendSettings = Field(default_factory=SupertrendSettings)
    rsi_div: RsiDivSettings = Field(default_factory=RsiDivSettings)
    bollinger: BollingerSettings = Field(default_factory=BollingerSettings)
    cvd_obv: CvdObvSettings = Field(default_factory=CvdObvSettings)
    funding_oi: FundingOiSettings = Field(default_factory=FundingOiSettings)
    orderbook: OrderbookSettings = Field(default_factory=OrderbookSettings)
    lightgbm: LightGbmSettings = Field(default_factory=LightGbmSettings)
    sentiment: SentimentSettings = Field(default_factory=SentimentSettings)


class VerdictSettings(BaseModel):
    strong_score: float = 55.0
    watch_score: float = 30.0
    min_categories: int = 3
    min_available_weight_pct: float = 50.0
    cooldown_bars: int = 4
    notify_watch_signals: bool = False


class MacroFilterSettings(BaseModel):
    htf_ema_period: int = 200
    news_blackout_minutes: list[int] = Field(default_factory=lambda: [30, 30])
    news_currencies: list[str] = Field(default_factory=lambda: ["USD"])
    news_impact: list[str] = Field(default_factory=lambda: ["High"])
    atr_percentile_range: list[int] = Field(default_factory=lambda: [10, 95])
    atr_lookback_days: int = 30
    gold_rollover_utc: list[str] = Field(default_factory=lambda: ["20:45", "01:15"])
    max_funding_abs: float = 0.001
    spread_median_multiplier: float = 2.0
    fallback_warmup_minutes: int = 60


class StrategyBTripleEmaSettings(BaseModel):
    enabled: bool = True
    fast: int = 9
    mid: int = 21
    mid_source: Literal["open", "close", "high", "low"] = "open"
    slow: int = 50
    rr_target: float = 1.0
    notify: bool = False


class RiskSettings(BaseModel):
    sl_atr_mult: float = 1.5
    sl_max_atr_mult: float = 2.5
    tp1_r: float = 1.0
    tp1_close_pct: float = 50.0
    tp2_r: float = 2.0


class TicketSettings(BaseModel):
    valid_bars: int = 3
    entry_zone_atr: float = 0.1
    chase_limit_atr: float = 0.5
    calibration_valid_minutes: int = 30


class BrokerSymbolConfig(BaseModel):
    broker_symbol: str
    contract_size: float
    min_lot: float
    lot_step: float


class BrokerProfile(BaseModel):
    name: str
    account_currency: str = "USD"
    balance: float = 1000.0
    risk_pct: float = 1.0
    symbols: dict[str, BrokerSymbolConfig] = Field(default_factory=dict)


class PaperTradingSettings(BaseModel):
    initial_equity_usd: float = 1000.0
    risk_pct: float = 1.0
    time_stop_bars: int = 32
    max_open_positions: int = 3
    max_per_symbol: int = 1
    daily_loss_limit_pct: float = 3.0
    slippage_bps: int = 2
    open_on_watch_signals: bool = False


class ScheduleSettings(BaseModel):
    brief_morning: str = "06:45"
    brief_midday: str | None = None
    daily_recap: str = "22:00"
    news_alert_minutes_before: int = 15
    ml_retrain: str = "SUN 02:00"
    backup: str = "03:00"
    backup_keep_days: int = 14


class TelegramAppConfig(BaseModel):
    send_chart_image: bool = True
    wait_ai_seconds: int = 20


class MLConfig(BaseModel):
    min_train_months: int = 12
    gold_history_source: Literal["dukascopy", "binance"] = "dukascopy"


class AppSettings(BaseModel):
    """Strategy and operational settings loaded from settings.yaml."""

    watchlist: list[WatchlistItem] = Field(default_factory=list)
    gold: GoldSettings = Field(default_factory=GoldSettings)
    timeframes: TimeframesSettings = Field(default_factory=TimeframesSettings)
    indicators: IndicatorsSettings = Field(default_factory=IndicatorsSettings)
    weights_version: str = "v1-default"
    weights: dict[str, float] = Field(default_factory=dict)
    verdict: VerdictSettings = Field(default_factory=VerdictSettings)
    macro_filter: MacroFilterSettings = Field(default_factory=MacroFilterSettings)
    strategy_b_triple_ema: StrategyBTripleEmaSettings = Field(
        default_factory=StrategyBTripleEmaSettings
    )
    risk: RiskSettings = Field(default_factory=RiskSettings)
    ticket: TicketSettings = Field(default_factory=TicketSettings)
    brokers: list[BrokerProfile] = Field(default_factory=list)
    paper: PaperTradingSettings = Field(default_factory=PaperTradingSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    telegram: TelegramAppConfig = Field(default_factory=TelegramAppConfig)
    ml: MLConfig = Field(default_factory=MLConfig)

    @field_validator("watchlist")
    @classmethod
    def validate_watchlist_size(cls, v: list[WatchlistItem]) -> list[WatchlistItem]:
        if len(v) > 5:
            raise ValueError(f"Watchlist maksimum 5 simbol, saat ini {len(v)} simbol.")
        return v


class EnvSettings(BaseSettings):
    """Environment variables from .env or system environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_VERSION: str = "dev"
    APP_PORT: int = 8080
    APP_TIMEZONE: str = "Asia/Jakarta"
    LOG_LEVEL: str = "INFO"
    PUBLIC_URL: str = "http://localhost:8080"
    COOKIE_SECURE: bool = False

    # Security
    SECRET_KEY: str = Field(
        default="ganti-dengan-teks-acak-minimal-32-karakter",
        description="Secret key untuk JWT dan enkripsi sesi",
    )
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = ""

    # Database & Redis
    POSTGRES_USER: str = "traderadar"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "traderadar"
    DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://redis:6379/0"

    # Binance
    BINANCE_FAPI: str = "https://fapi.binance.com"
    BINANCE_FSTREAM: str = "wss://fstream.binance.com"
    BINANCE_SPOT: str = "https://api.binance.com"
    BINANCE_SPOT_FALLBACK: str = "https://data-api.binance.vision"
    BINANCE_SPOT_STREAM: str = "wss://stream.binance.com:9443"
    BINANCE_TAKER_FEE: float = 0.0005

    # OANDA
    OANDA_API_TOKEN: str = ""
    OANDA_ACCOUNT_ID: str = ""
    OANDA_REST: str = "https://api-fxpractice.oanda.com"
    OANDA_STREAM: str = "https://stream-fxpractice.oanda.com"

    # AI
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = ""
    AI_MAX_RPM: int = 5
    AI_MAX_RPD: int = 100
    AI_TIMEOUT_SECONDS: int = 30

    # Telegram
    TELEGRAM_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""

    # Calendar
    NEWS_PRIMARY_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    FINNHUB_API_KEY: str = ""

    @model_validator(mode="after")
    def resolve_database_url(self) -> "EnvSettings":
        if not self.DATABASE_URL:
            # Construct default asyncpg database URL
            pwd = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}{pwd}@db:5432/{self.POSTGRES_DB}"
            )
        return self


class Settings(BaseModel):
    """Composite settings containing environment and YAML strategy configuration."""

    env: EnvSettings
    app: AppSettings


def load_app_settings(config_dir: Path | None = None) -> AppSettings:
    """Load settings.yaml or fallback to settings.example.yaml."""
    search_paths: list[Path] = []
    if config_dir:
        search_paths.extend([config_dir / "settings.yaml", config_dir / "settings.example.yaml"])
    else:
        # Common locations: ./config, /app/config, ../config
        for base in [Path("config"), Path("/app/config"), Path("../config")]:
            search_paths.append(base / "settings.yaml")
            search_paths.append(base / "settings.example.yaml")

    target_file: Path | None = None
    for p in search_paths:
        if p.exists() and p.is_file():
            target_file = p
            break

    if not target_file:
        # Return default AppSettings if no YAML file found
        return AppSettings()

    try:
        with open(target_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return AppSettings.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Gagal memuat konfigurasi dari {target_file}: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get singleton Settings instance."""
    env = EnvSettings()
    app = load_app_settings()
    return Settings(env=env, app=app)


def get_app_settings() -> AppSettings:
    """Convenience getter for AppSettings component."""
    return get_settings().app

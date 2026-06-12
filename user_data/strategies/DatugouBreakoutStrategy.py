from datetime import datetime
import json
import os
from pathlib import Path

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class DatugouBreakoutStrategy(IStrategy):
    """OKX meme spot breakout strategy for sandbox trading."""

    INTERFACE_VERSION = 3

    timeframe = "1h"
    startup_candle_count = 80
    can_short = False

    minimal_roi = {
        "0": 0.30,
        "360": 0.12,
        "1440": 0.04,
        "2160": 0,
    }

    stoploss = -0.07
    trailing_stop = True
    trailing_stop_positive = 0.10
    trailing_stop_positive_offset = 0.30
    trailing_only_offset_is_reached = True

    _default_flow = {
        "min_rows": 80,
        "breakout_lookback": 24,
        "volume_window": 24,
        "momentum_window": 6,
        "min_volume_ratio": 1.6,
        "min_momentum_pct": 2.5,
    }
    _ml_signals_cache: dict | None = None
    _ml_signals_mtime: float | None = None

    def _flow(self) -> dict:
        path = Path("/freqtrade/user_data/datugou_flow.json")
        if not path.exists():
            loaded = {}
        else:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                loaded = {}
        flow = {**self._default_flow, **loaded}
        overlay_path = Path("/freqtrade/user_data/datugou_flow.autopilot.json")
        if not overlay_path.exists():
            return flow
        try:
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        except Exception:
            return flow
        return {**flow, **overlay.get("parameters", {})}

    def _ml_filter_enabled(self) -> bool:
        return os.getenv("ML_SIGNAL_FILTER_ENABLED", "0") == "1"

    def _ml_signals(self) -> dict:
        path = Path(os.getenv("ML_SIGNAL_PATH", "/freqtrade/output/ml_models/latest_signals.json"))
        if not path.exists():
            return {}
        try:
            mtime = path.stat().st_mtime
            if self._ml_signals_cache is not None and self._ml_signals_mtime == mtime:
                return self._ml_signals_cache
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        self._ml_signals_cache = payload
        self._ml_signals_mtime = mtime
        return payload

    def _ml_pair_allowed(self, pair: str) -> bool:
        if not self._ml_filter_enabled():
            return True
        signals = self._ml_signals()
        gate = signals.get("deployment_gate") or {}
        if not gate.get("passed"):
            return False
        candidates = signals.get("research_long_candidates") or signals.get("top_long_candidates") or []
        allowed_pairs = {item.get("pair") for item in candidates if item.get("pred_signal") == "bullish"}
        return pair in allowed_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        flow = self._flow()
        dataframe["breakout_high"] = dataframe["high"].rolling(int(flow["breakout_lookback"])).max().shift(1)
        dataframe["avg_volume"] = dataframe["volume"].rolling(int(flow["volume_window"])).mean().shift(1)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["avg_volume"].replace(0, 1e-12)
        dataframe["momentum_pct"] = dataframe["close"].pct_change(int(flow["momentum_window"])) * 100
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        flow = self._flow()
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["breakout_high"])
                & (dataframe["volume_ratio"] >= float(flow["min_volume_ratio"]))
                & (dataframe["momentum_pct"] >= float(flow["min_momentum_pct"]))
                & (dataframe["volume"] > 0)
                & self._ml_pair_allowed(metadata.get("pair", ""))
            ),
            ["enter_long", "enter_tag"],
        ] = (
            1,
            "datugou_breakout_volume_momentum"
            if not self._ml_filter_enabled()
            else "datugou_breakout_ml_gate",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                ((dataframe["rsi"] >= 82) | (dataframe["momentum_pct"] <= -6.0))
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "datugou_momentum_cooldown")
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        return amount > 0 and rate > 0 and side == "long" and self._ml_pair_allowed(pair)

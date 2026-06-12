"""Runtime patches for the local Freqtrade deployment."""

from __future__ import annotations

import os


def _patch_freqtrade_exchange() -> None:
    try:
        from freqtrade.exchange.exchange import Exchange
    except Exception:
        return

    if getattr(Exchange, "_codex_okx_sandbox_patch", False):
        return

    original_init_ccxt = Exchange._init_ccxt

    def patched_init_ccxt(self, exchange_config, sync, ccxt_kwargs):
        api = original_init_ccxt(self, exchange_config, sync, ccxt_kwargs)
        if (
            os.getenv("OKX_SANDBOX_MODE", "0") == "1"
            and str(exchange_config.get("name", "")).lower() == "okx"
            and hasattr(api, "set_sandbox_mode")
        ):
            api.set_sandbox_mode(True)
        return api

    Exchange._init_ccxt = patched_init_ccxt
    Exchange._codex_okx_sandbox_patch = True


_patch_freqtrade_exchange()

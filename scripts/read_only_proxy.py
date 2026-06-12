#!/usr/bin/env python3
"""Read-only local proxy for the bundled analysis workspace."""

from __future__ import annotations

import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


UI_PORT = int(os.getenv("FREQTRADE_UI_PORT", "8080"))
BACKEND_PORT = int(os.getenv("FREQTRADE_BACKEND_PORT", "18080"))
BACKEND = f"http://127.0.0.1:{BACKEND_PORT}"

ALLOWED_PATHS = {
    "/analysis.html",
    "/assets/analysis.css",
    "/assets/analysis.js",
    "/assets/analysis-data.json",
    "/assets/freqtrade-zh.js",
    "/favicon.ico",
}

BLOCKED_PREFIXES = (
    "/api/",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/login",
    "/dashboard",
    "/balance",
    "/open_trades",
    "/trade_history",
    "/trade",
    "/graph",
    "/logs",
    "/backtest",
    "/settings",
    "/pairlist",
    "/pairlist_config",
    "/download_data",
)


def safety_page() -> bytes:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>交易安全模式</title>
  <style>
    body { margin: 0; background: #0f1720; color: #eef3f7; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 720px; margin: 64px auto; padding: 32px; border: 1px solid #ffb347; border-radius: 8px; background: #1f1a12; line-height: 1.7; }
    h1 { margin: 0 0 16px; font-size: 24px; }
    p { margin: 0 0 16px; color: #ffcf8a; }
    a { display: inline-flex; min-height: 36px; align-items: center; padding: 0 14px; border: 1px solid #45c2ff; border-radius: 6px; color: #dff6ff; text-decoration: none; background: #113140; }
  </style>
</head>
<body>
  <main>
    <h1>交易安全模式</h1>
    <p>当前入口只允许访问本地只读分析工作台。后端 API、OpenAPI 文档、登录页和原生交易控制页面已被代理拦截。</p>
    <a href="/analysis.html">打开分析工作台</a>
  </main>
</body>
</html>
""".encode("utf-8")


def copy_headers(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    excluded = {"connection", "transfer-encoding", "content-encoding", "server", "date"}
    return [(key, value) for key, value in headers if key.lower() not in excluded]


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "FreqtradeReadOnlyProxy/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_HEAD(self) -> None:
        self.handle_request(send_body=False)

    def do_GET(self) -> None:
        self.handle_request(send_body=True)

    def do_POST(self) -> None:
        self.block()

    def do_PUT(self) -> None:
        self.block()

    def do_PATCH(self) -> None:
        self.block()

    def do_DELETE(self) -> None:
        self.block()

    def handle_request(self, send_body: bool) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/analysis.html")
            self.end_headers()
            return

        if path.startswith(BLOCKED_PREFIXES):
            self.block(send_body=send_body)
            return

        if path not in ALLOWED_PATHS:
            self.block(send_body=send_body)
            return

        self.forward(send_body=send_body)

    def block(self, send_body: bool = True) -> None:
        body = safety_page()
        self.send_response(HTTPStatus.FORBIDDEN)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def forward(self, send_body: bool) -> None:
        target = f"{BACKEND}{self.path}"
        request = Request(target, method="GET", headers={"Host": f"127.0.0.1:{BACKEND_PORT}"})
        try:
            with urlopen(request, timeout=8) as response:
                body = response.read()
                self.send_response(response.status)
                for key, value in copy_headers(response.headers.items()):
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if send_body:
                    self.wfile.write(body)
        except HTTPError as error:
            body = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)
        except URLError as error:
            message = f"Backend unavailable: {error.reason}".encode("utf-8")
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            if send_body:
                self.wfile.write(message)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", UI_PORT), ProxyHandler)
    print(f"Read-only proxy listening on http://127.0.0.1:{UI_PORT}, backend {BACKEND}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

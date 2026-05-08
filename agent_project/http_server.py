"""Standard-library HTTP wrapper for AgentService.

This module intentionally avoids third-party web frameworks so it can run in
strict intranet environments where only the Python standard library is allowed.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from service_api import AgentService


SERVICE = AgentService()


class AgentHttpHandler(BaseHTTPRequestHandler):
    server_version = "AiCaixiaoziAgentHTTP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._write_json(200, {"success": True, "code": "OK", "message": "service healthy"})
            return

        if parsed.path == "/api/sessions":
            query = parse_qs(parsed.query)
            limit = _to_int(query.get("limit", ["20"])[0], default=20)
            self._write_json(200, SERVICE.list_sessions(limit=limit))
            return

        self._write_json(404, {"success": False, "code": "NOT_FOUND", "message": "endpoint not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        if payload is None:
            return

        if parsed.path == "/api/chat":
            user_input = str(payload.get("user_input", ""))
            session_id = payload.get("session_id")
            if session_id is not None:
                session_id = str(session_id)
            result = SERVICE.handle_user_message(user_input=user_input, session_id=session_id)
            self._write_json(200, result)
            return

        if parsed.path == "/api/sessions":
            self._write_json(200, SERVICE.create_session())
            return

        self._write_json(404, {"success": False, "code": "NOT_FOUND", "message": "endpoint not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/api/sessions/"
        if parsed.path.startswith(prefix):
            session_id = parsed.path[len(prefix) :].strip()
            if not session_id:
                self._write_json(400, {"success": False, "code": "BAD_REQUEST", "message": "session_id is required"})
                return
            result = SERVICE.delete_session(session_id)
            status = 200 if result.get("success") else 404
            self._write_json(status, result)
            return

        self._write_json(404, {"success": False, "code": "NOT_FOUND", "message": "endpoint not found"})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._write_common_headers()
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} - {format % args}")

    def _read_json(self) -> Dict[str, Any] | None:
        length = _to_int(self.headers.get("Content-Length"), default=0)
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(400, {"success": False, "code": "BAD_JSON", "message": "request body must be JSON"})
            return None
        if not isinstance(payload, dict):
            self._write_json(400, {"success": False, "code": "BAD_JSON", "message": "request body must be a JSON object"})
            return None
        return payload

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._write_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AgentHttpHandler)
    print(f"[http] Agent HTTP server started: http://{host}:{port}")
    print("[http] health: GET /health")
    print("[http] chat:   POST /api/chat")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[http] stopping server...")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Caixiaozi Agent HTTP server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.planning_comm_helper.outlook import OutlookPayloadError, open_outlook_drafts
from tools.planning_comm_helper.whatsapp import WhatsAppPayloadError, open_whatsapp_drafts

HELPER_HEADER = "X-ASF-Planning-Helper"


class HelperRequestError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _require_browser_header(headers: dict[str, object]) -> None:
    if str(headers.get(HELPER_HEADER) or "").strip() != "1":
        raise HelperRequestError(400, "Missing helper authorization header.")


def _require_drafts(payload: dict[str, object]) -> list[dict[str, object]]:
    drafts = payload.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        raise HelperRequestError(422, "At least one draft is required.")
    if not all(isinstance(draft, dict) for draft in drafts):
        raise HelperRequestError(422, "Draft payloads must be objects.")
    return drafts


def handle_json_request(
    *,
    method: str,
    path: str,
    headers: dict[str, object],
    payload: dict[str, object] | None,
) -> dict[str, object]:
    normalized_method = (method or "").upper()
    if normalized_method == "OPTIONS":
        return {"ok": True}
    if normalized_method != "POST":
        raise HelperRequestError(405, "Only POST is supported.")

    _require_browser_header(headers)
    request_payload = payload or {}

    if path == "/health":
        return {"ok": True}

    if path == "/v1/whatsapp/open":
        drafts = _require_drafts(request_payload)
        try:
            opened_count = open_whatsapp_drafts(drafts)
        except WhatsAppPayloadError as exc:
            raise HelperRequestError(422, str(exc)) from exc
        return {"ok": True, "opened_count": opened_count}

    if path == "/v1/outlook/open":
        drafts = _require_drafts(request_payload)
        try:
            opened_count = open_outlook_drafts(drafts)
        except OutlookPayloadError as exc:
            raise HelperRequestError(422, str(exc)) from exc
        return {"ok": True, "opened_count": opened_count}

    raise HelperRequestError(404, "Unsupported helper route.")


class PlanningCommunicationHelperHandler(BaseHTTPRequestHandler):
    server_version = "PlanningCommHelper/1.0"

    def do_OPTIONS(self):  # noqa: N802
        self._send_json_response(200, {"ok": True})

    def do_POST(self):  # noqa: N802
        try:
            content_length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw_body.decode("utf-8") or "{}")
            response_payload = handle_json_request(
                method="POST",
                path=self.path,
                headers=dict(self.headers),
                payload=payload,
            )
            self._send_json_response(200, response_payload)
        except HelperRequestError as exc:
            self._send_json_response(exc.status_code, {"error": exc.message})
        except json.JSONDecodeError:
            self._send_json_response(400, {"error": "Invalid JSON payload."})
        except Exception as exc:  # pragma: no cover - defensive HTTP layer
            self._send_json_response(500, {"error": str(exc)})

    def _send_json_response(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, {HELPER_HEADER}")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 38555) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), PlanningCommunicationHelperHandler)
    server.serve_forever()
    return server


if __name__ == "__main__":  # pragma: no cover
    run_server()

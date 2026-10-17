"""HTTP guards (T2.9): security headers, X-Requested-With on mutating API calls, a general
per-IP request limit, the 256 KB body cap, and the random `cid` cookie used for guest limits.
Pure ASGI so request bodies are never buffered beyond the cap.
"""

from uuid import uuid4

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.errors import AppError, error_response
from app.core.rate_limit import RateLimiter, client_ip, request_rules
from app.domain.schemas import MAX_DOCUMENT_BYTES

MAX_BODY_BYTES = 256 * 1024
# Saved campaigns carry a whole document (512 KB cap, LLD 3) plus a small envelope.
CAMPAIGN_BODY_BYTES = MAX_DOCUMENT_BYTES + 16 * 1024
MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "campaory"
CID_COOKIE = "cid"
CID_MAX_AGE = 365 * 24 * 3600
UNLIMITED_PATHS = frozenset({"/api/health"})
DOCS_PATHS = ("/api/docs", "/api/openapi.json")

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


class GuardMiddleware:
    def __init__(self, app: ASGIApp, *, settings: Settings, limiter: RateLimiter) -> None:
        self.app = app
        self.settings = settings
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        method: str = scope["method"]
        headers = Headers(scope=scope)
        is_api = path == "/api" or path.startswith("/api/")
        send = self._with_headers(send, path, set_cid=is_api and CID_COOKIE not in _cookies(scope))

        try:
            if is_api and method in MUTATING and headers.get(CSRF_HEADER) != CSRF_VALUE:
                raise AppError(403, "forbidden", "Missing X-Requested-With: campaory header.")
            if is_api and path not in UNLIMITED_PATHS:
                ip = client_ip(Request(scope))
                self.limiter.hit(f"ip:{ip}", request_rules(self.settings))
            if method in MUTATING:
                cap = CAMPAIGN_BODY_BYTES if path.startswith("/api/campaigns") else MAX_BODY_BYTES
                receive = await _capped_body(receive, headers, cap)
        except AppError as exc:
            reply = error_response(
                exc.status, exc.code, exc.message, exc.details, exc.retry_after_seconds
            )
            await reply(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _with_headers(self, send: Send, path: str, *, set_cid: bool) -> Send:
        production = self.settings.is_production

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                if not path.startswith(DOCS_PATHS):
                    out.setdefault("Content-Security-Policy", CSP)
                out.setdefault("X-Content-Type-Options", "nosniff")
                out.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                out.setdefault("X-Frame-Options", "DENY")
                out.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                if production:
                    out.setdefault("Strict-Transport-Security", "max-age=31536000")
                if set_cid:
                    cookie = (
                        f"{CID_COOKIE}={uuid4()}; Path=/; Max-Age={CID_MAX_AGE}; "
                        "HttpOnly; SameSite=Lax"
                    )
                    out.append("Set-Cookie", cookie + ("; Secure" if production else ""))
            await send(message)

        return wrapped


def _cookies(scope: Scope) -> set[str]:
    raw = Headers(scope=scope).get("cookie", "")
    return {part.split("=", 1)[0].strip() for part in raw.split(";") if "=" in part}


async def _capped_body(receive: Receive, headers: Headers, cap: int) -> Receive:
    """Read the whole body (at most `cap` bytes) and replay it to the app."""
    too_large = AppError(413, "payload_too_large", f"The request is larger than {cap // 1024} KB.")
    declared = headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cap:
        raise too_large
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        body = message.get("body", b"")
        size += len(body)
        if size > cap:
            raise too_large
        chunks.append(body)
        if not message.get("more_body", False):
            break
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
        return await receive()

    return replay


def install_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(GuardMiddleware, settings=settings, limiter=app.state.limiter)

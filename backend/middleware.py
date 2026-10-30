"""ASGI request limits and response headers without private Request internals."""

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException
from .config import settings
from .constants import REQUEST_BYTES


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Yêu cầu vượt quá giới hạn dung lượng.")


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        api = scope["path"].startswith("/api")
        unsafe = scope["method"] not in ("GET", "HEAD", "OPTIONS")
        started = False

        async def secured_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                out = MutableHeaders(scope=message)
                out["X-Content-Type-Options"] = "nosniff"
                out["Referrer-Policy"] = "same-origin"
                out["X-Frame-Options"] = "DENY"
                out["Cache-Control"] = "no-store" if api else "no-cache"
                if scope["path"] not in ("/docs", "/redoc"):
                    out["Content-Security-Policy"] = (
                        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
                    )
            await send(message)

        if (
            api
            and unsafe
            and headers.get("origin") not in (None, settings().app_origin.rstrip("/"))
        ):
            return await JSONResponse(
                {"detail": "Nguồn yêu cầu không được phép.", "code": "origin_rejected"}, 403
            )(scope, receive, secured_send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > REQUEST_BYTES:
                    raise BodyTooLarge
            return message

        try:
            try:
                length = int(headers.get("content-length", "0") or "0")
            except ValueError:
                return await JSONResponse(
                    {"detail": "Content-Length không hợp lệ.", "code": "invalid_length"}, 400
                )(scope, receive, secured_send)
            if api and unsafe and length > REQUEST_BYTES:
                raise BodyTooLarge
            await self.app(scope, limited_receive if api and unsafe else receive, secured_send)
        except BodyTooLarge:
            if started:
                raise
            await JSONResponse(
                {"detail": "Yêu cầu vượt quá giới hạn dung lượng.", "code": "body_too_large"}, 413
            )(scope, receive, secured_send)

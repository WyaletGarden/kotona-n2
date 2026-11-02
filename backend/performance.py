"""Opt-in request timings; never record SQL text, parameters or account data."""

from contextvars import ContextVar
from dataclasses import dataclass
import logging
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.datastructures import MutableHeaders

from .config import settings


@dataclass
class Measurements:
    queries: int = 0
    sql_ms: float = 0


measurements: ContextVar[Measurements | None] = ContextVar("performance", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def before_query(connection, cursor, statement, parameters, context, executemany):
    current = measurements.get()
    if current is not None:
        current.queries += 1
        context.kotoba_query_started = perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def after_query(connection, cursor, statement, parameters, context, executemany):
    current = measurements.get()
    if current is not None:
        current.sql_ms += (perf_counter() - context.kotoba_query_started) * 1000


@event.listens_for(Engine, "handle_error")
def failed_query(exception_context):
    current = measurements.get()
    context = exception_context.execution_context
    started = getattr(context, "kotoba_query_started", None)
    if current is not None and started is not None:
        current.sql_ms += (perf_counter() - started) * 1000


class PerformanceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or not scope["path"].startswith("/api/")
            or not settings().performance_metrics
        ):
            return await self.app(scope, receive, send)
        current = Measurements()
        token = measurements.set(current)
        started = perf_counter()

        async def timed_send(message):
            if message["type"] == "http.response.start":
                elapsed = (perf_counter() - started) * 1000
                headers = MutableHeaders(scope=message)
                headers["Server-Timing"] = f"app;dur={elapsed:.2f}, db;dur={current.sql_ms:.2f}"
                headers["X-SQL-Queries"] = str(current.queries)
                route = getattr(scope.get("route"), "path", "/api/unknown")
                logging.getLogger("uvicorn.error").info(
                    "%s %s status=%s app_ms=%.2f sql_ms=%.2f queries=%s",
                    scope["method"],
                    route,
                    message["status"],
                    elapsed,
                    current.sql_ms,
                    current.queries,
                )
            await send(message)

        try:
            await self.app(scope, receive, timed_send)
        finally:
            measurements.reset(token)

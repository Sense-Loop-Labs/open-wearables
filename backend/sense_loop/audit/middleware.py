"""Audit middleware for auto-capturing request context."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .context import AuditContext, clear_audit_context, set_audit_context


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to initialize audit context for each request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Create audit context for this request
        ctx = AuditContext()

        # Extract request info
        ctx.set_request_info(
            endpoint=str(request.url.path),
            method=request.method,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        # Set the context for this request
        set_audit_context(ctx)

        try:
            response = await call_next(request)
            return response
        finally:
            # Clear context after request
            clear_audit_context()

    def _get_client_ip(self, request: Request) -> str | None:
        """Extract client IP from request, considering proxies."""
        # Check X-Forwarded-For header (common with reverse proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

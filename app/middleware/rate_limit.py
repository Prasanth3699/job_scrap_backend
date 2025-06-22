from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute=60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = time.time()

        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > now - 60
        ]

        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429, content={"detail": "Too many requests"}
            )

        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response

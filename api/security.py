"""
Security utilities for the API including rate limiting, input validation, and output sanitization.
"""

from __future__ import annotations

import os
import time
import re
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Rate Limiting Configuration and Middleware
# ─────────────────────────────────────────────────────────────────

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    cleanup_interval: int = 300  # 5 minutes


class _InMemoryRateLimiter:
    """Process-local sliding-window limiter (default / fallback)."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()

    def allow(self, client_id: str, now: float) -> bool:
        if now - self.last_cleanup > self.config.cleanup_interval:
            self._cleanup(now)
            self.last_cleanup = now
        reqs = self.request_times[client_id]
        one_hour_ago = now - 3600
        reqs[:] = [t for t in reqs if t > one_hour_ago]
        if len(reqs) >= self.config.requests_per_hour:
            return False
        one_minute_ago = now - 60
        if sum(1 for t in reqs if t > one_minute_ago) >= self.config.requests_per_minute:
            return False
        reqs.append(now)
        return True

    def _cleanup(self, now: float) -> None:
        one_day_ago = now - 86400
        for client_id in list(self.request_times.keys()):
            kept = [t for t in self.request_times[client_id] if t > one_day_ago]
            if kept:
                self.request_times[client_id] = kept
            else:
                del self.request_times[client_id]


class _RedisRateLimiter:
    """
    Redis-backed fixed-window limiter — distributed & restart-persistent.

    Uses atomic INCR + EXPIRE per (client, minute) and (client, hour) window.
    On any Redis hiccup it FAILS OPEN (allows the request) so an infra blip never
    takes the whole API down — availability over strict limiting, logged.
    """

    def __init__(self, client, config: RateLimitConfig):
        self.client = client
        self.config = config

    def allow(self, client_id: str, now: float) -> bool:
        try:
            minute = int(now // 60)
            hour = int(now // 3600)
            mkey = f"rl:{client_id}:m:{minute}"
            hkey = f"rl:{client_id}:h:{hour}"
            pipe = self.client.pipeline()
            pipe.incr(mkey)
            pipe.expire(mkey, 60)
            pipe.incr(hkey)
            pipe.expire(hkey, 3600)
            m_count, _, h_count, _ = pipe.execute()
            if int(m_count) > self.config.requests_per_minute:
                return False
            if int(h_count) > self.config.requests_per_hour:
                return False
            return True
        except Exception as exc:  # Redis blip → fail open (don't block legit traffic)
            _logger.warning("[RateLimit] Redis error, allowing request (fail-open): %s", exc)
            return True


def _build_rate_limiter(config: RateLimitConfig):
    """Redis-backed limiter when REDIS_URL/config is reachable; else in-memory."""
    url = os.environ.get("REDIS_URL")
    if not url:
        try:
            from config.config_loader import get_config
            url = get_config().redis.url
        except Exception:
            url = None
    if url:
        try:
            import redis as _redis
            c = _redis.from_url(url, socket_connect_timeout=2)
            c.ping()
            _logger.info("[RateLimit] Redis-backed limiter active: %s", url)
            return _RedisRateLimiter(c, config)
        except Exception as exc:
            _logger.warning("[RateLimit] Redis unavailable, in-memory fallback: %s", exc)
    return _InMemoryRateLimiter(config)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting per client IP — Redis-backed when available, else in-memory."""

    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.limiter = _build_rate_limiter(self.config)
        # X-Forwarded-For is client-controlled; only trust it behind a known proxy.
        self.trust_proxy = os.environ.get("TRUST_PROXY", "").lower() in ("1", "true", "yes")

    async def dispatch(self, request: Request, call_next):
        client_id = self._get_rate_limit_key(request)
        if not self.limiter.allow(client_id, time.time()):
            return self._rate_limited_response()
        return await call_next(request)

    def _get_rate_limit_key(self, request: Request) -> str:
        # Kullanıcı-bazlı kota: geçerli JWT varsa anahtar `user:{username}` (IP'den bağımsız,
        # NAT/paylaşılan-IP arkasında adil). Token yoksa IP-bazlı (`ip:{ip}`) geri düşer.
        try:
            from api.auth import peek_username
            username = peek_username(request)
            if username:
                return f"user:{username}"
        except Exception:
            pass
        return f"ip:{self._get_client_ip(request)}"

    def _get_client_ip(self, request: Request) -> str:
        # Default: real peer address (spoof-resistant). Only honour XFF when the
        # deployment explicitly opts in via TRUST_PROXY (i.e. behind a trusted LB).
        if self.trust_proxy and "x-forwarded-for" in request.headers:
            return request.headers["x-forwarded-for"].split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    @staticmethod
    def _rate_limited_response() -> JSONResponse:
        # Standard error envelope (consistent with api_error_handler) + Retry-After.
        return JSONResponse(
            status_code=429,
            content={"error": {
                "code": "RATE_LIMITED",
                "message": "Rate limit exceeded. Please slow down and retry shortly.",
                "type": "rate_limit_error",
            }},
            headers={"Retry-After": "60", "X-Error-Code": "RATE_LIMITED"},
        )


# ─────────────────────────────────────────────────────────────────
# Security Headers Middleware
# ─────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # CSP: Allow Swagger UI and other essential external resources
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https:"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


# ─────────────────────────────────────────────────────────────────
# Input Validation
# ─────────────────────────────────────────────────────────────────

DANGEROUS_PATTERNS = {
    'sql_injection': r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|EXEC|EXECUTE|SCRIPT|XSS)\b)",
    'path_traversal': r"(\.\./|\.\.\\|%2e%2e)",
    'command_injection': r"([;|`$\(\)]|\$\([^)]*\))",
    'html_injection': r"(<script|<iframe|<object|<embed|javascript:|on\w+\s*=)",
}


def validate_chat_input(user_input: str, max_length: int = 5000, check_injection: bool = True) -> tuple[bool, Optional[str]]:
    """
    Validate user input for chat requests.
    
    Args:
        user_input: The input string to validate
        max_length: Maximum allowed length of input
        check_injection: Whether to check for injection patterns (default: True)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if not user_input or len(user_input.strip()) == 0:
        return False, "Input cannot be empty"
    
    if len(user_input) > max_length:
        return False, f"Input exceeds maximum length of {max_length} characters"
    
    # Check for dangerous patterns (only if check_injection is True)
    if check_injection:
        for pattern_name, pattern in DANGEROUS_PATTERNS.items():
            if re.search(pattern, user_input, re.IGNORECASE):
                return False, f"Input contains potentially dangerous content (detected: {pattern_name})"
    
    # Check for excessive special characters
    special_char_ratio = sum(1 for c in user_input if not c.isalnum() and c.isascii() and c != ' ') / len(user_input)
    if special_char_ratio > 0.4:
        return False, "Input contains too many special characters"
    
    return True, None


# ─────────────────────────────────────────────────────────────────
# Output Sanitization
# ─────────────────────────────────────────────────────────────────

def sanitize_output(output: str, remove_sensitive: bool = True) -> str:
    """
    Sanitize LLM output to remove potentially harmful content.
    
    Args:
        output: The output string to sanitize
        remove_sensitive: Whether to remove sensitive information patterns
    
    Returns:
        Sanitized output string
    """
    if not output:
        return ""
    
    sanitized = output
    
    # Remove HTML/JavaScript
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'<iframe[^>]*>.*?</iframe>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    # Remove potential SQL injection attempts
    dangerous_sql = r'\b(DROP TABLE|DELETE FROM|TRUNCATE|EXEC|EXECUTE)\b'
    sanitized = re.sub(dangerous_sql, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    # Remove potentially sensitive patterns (if enabled)
    if remove_sensitive:
        # API keys pattern
        sanitized = re.sub(r'(api[_-]?key|password|secret|token)\s*[:=]\s*[^\s]+', '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        # Email pattern (teknik crypto/SSH domain'leri hariç)
        _TECH_DOMAINS = r'openssh\.com|libssh\.org|libgcrypt\.org|gnupg\.org|ietf\.org'
        sanitized = re.sub(
            r'\b[A-Za-z0-9._%+-]+@(?!' + _TECH_DOMAINS + r'\b)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            sanitized
        )
        
        # IP addresses
        sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', sanitized)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    sanitized = re.sub(r' {2,}', ' ', sanitized)
    
    return sanitized.strip()



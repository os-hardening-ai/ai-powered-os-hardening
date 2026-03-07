"""
Security utilities for the API including rate limiting, input validation, and output sanitization.
"""

from __future__ import annotations

import time
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting based on client IP."""
    
    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.request_times: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and apply rate limiting."""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.config.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Check rate limits
        if not self._check_rate_limit(client_ip, current_time):
            return Response("Rate limit exceeded", status_code=429)
        
        # Record this request
        self.request_times[client_ip].append(current_time)
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request headers or connection."""
        if "x-forwarded-for" in request.headers:
            return request.headers["x-forwarded-for"].split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
    def _check_rate_limit(self, client_ip: str, current_time: float) -> bool:
        """Check if client is within rate limits."""
        requests = self.request_times[client_ip]
        
        # Remove requests older than 1 hour
        one_hour_ago = current_time - 3600
        requests[:] = [t for t in requests if t > one_hour_ago]
        
        # Check hourly limit
        if len(requests) >= self.config.requests_per_hour:
            return False
        
        # Check per-minute limit
        one_minute_ago = current_time - 60
        recent_requests = [t for t in requests if t > one_minute_ago]
        if len(recent_requests) >= self.config.requests_per_minute:
            return False
        
        return True
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove old client entries from tracking."""
        one_day_ago = current_time - 86400
        keys_to_remove = []
        
        for client_ip, requests in self.request_times.items():
            self.request_times[client_ip] = [
                t for t in requests if t > one_day_ago
            ]
            if not self.request_times[client_ip]:
                keys_to_remove.append(client_ip)
        
        for key in keys_to_remove:
            del self.request_times[key]


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
        
        # Email pattern
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)
        
        # IP addresses
        sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', sanitized)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    sanitized = re.sub(r' {2,}', ' ', sanitized)
    
    return sanitized.strip()


# ─────────────────────────────────────────────────────────────────
# CORS and Trust Configuration
# ─────────────────────────────────────────────────────────────────

def get_cors_config() -> Dict[str, Any]:
    """Get CORS configuration for the API."""
    return {
        "allow_origins": ["*"],  # In production, restrict this
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "max_age": 600,
    }


def get_trusted_hosts() -> list[str]:
    """Get list of trusted hosts."""
    return [
        "localhost",
        "127.0.0.1",
        "*.localhost",
    ]

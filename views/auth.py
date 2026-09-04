from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Form, Request, Response
from fastapi.responses import RedirectResponse

from auth.login import authenticate_user
from auth.rate_limiter import login_rate_limiter
from auth.token import create_token, get_username_from_token, InvalidToken
from config.templates import templates
from services.audit_logger import audit_logger

router = APIRouter()

TOKEN_COOKIE = "token"


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request, considering proxies."""
    # Check for X-Forwarded-For header (when behind a proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"


@router.get("/")
def login_page(request: Request):
    client_ip = get_client_ip(request)
    
    # Check if already rate limited and show appropriate message
    if login_rate_limiter.is_rate_limited(client_ip):
        retry_after = login_rate_limiter.get_retry_after_seconds(client_ip)
        return templates.TemplateResponse(
            request,
            name="login.jinja",
            context={
                "error": f"登录尝试次数过多，请在 {retry_after} 秒后重试。",
                "rate_limited": True,
                "retry_after": retry_after,
            },
        )
    
    return templates.TemplateResponse(request, name="login.jinja")


@router.post("/")
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    response: Response,
):
    client_ip = get_client_ip(request)
    
    # Check if rate limited before attempting authentication
    if login_rate_limiter.is_rate_limited(client_ip):
        retry_after = login_rate_limiter.get_retry_after_seconds(client_ip)
        return templates.TemplateResponse(
            request,
            name="login.jinja",
            context={
                "error": f"登录尝试次数过多，请在 {retry_after} 秒后重试。",
                "rate_limited": True,
                "retry_after": retry_after,
            },
            status_code=429,
        )
    
    if authenticate_user(username, password):
        # Reset rate limit on successful login
        login_rate_limiter.reset(client_ip)
        token = create_token(username)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(TOKEN_COOKIE, value=token)
        
        # Log successful authentication
        audit_logger.log_auth_success(username=username, ip_address=client_ip)
        
        return response

    # Record failed attempt
    login_rate_limiter.record_failed_attempt(client_ip)
    remaining = login_rate_limiter.get_remaining_attempts(client_ip)
    
    # Log failed authentication attempt
    audit_logger.log_auth_failure(ip_address=client_ip, username=username, reason="invalid_credentials")
    
    # Build error message
    if remaining == 0:
        retry_after = login_rate_limiter.get_retry_after_seconds(client_ip)
        error_msg = f"登录尝试次数过多，请在 {retry_after} 秒后重试。"
        
        # Log rate limit triggered
        audit_logger.log_auth_rate_limited(ip_address=client_ip, retry_after=retry_after)
        
        return templates.TemplateResponse(
            request,
            name="login.jinja",
            context={
                "error": error_msg,
                "rate_limited": True,
                "retry_after": retry_after,
            },
            status_code=429,
        )
    else:
        error_msg = f"用户名或密码错误，还可尝试 {remaining} 次。"
    
    return templates.TemplateResponse(
        request, name="login.jinja", context={"error": error_msg, "remaining_attempts": remaining}
    )


@router.post("/logout")
def logout(
    request: Request,
    token: Optional[str] = Cookie(None),
):
    client_ip = get_client_ip(request)
    
    # Try to get username from token for logging
    username = None
    if token:
        try:
            username = get_username_from_token(token)
        except InvalidToken:
            pass
    
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(TOKEN_COOKIE)
    
    # Log the logout
    if username:
        audit_logger.log_logout(username=username, ip_address=client_ip)
    
    return response

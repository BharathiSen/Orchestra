from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import RateLimitDecision, RateLimiter, get_rate_limiter
from app.core.security import decode_access_token
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = int(subject)
    except (InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def client_ip(request: Request) -> str:
    """Best-effort client address for IP-scoped limits.

    Behind a proxy the socket address is the proxy, so the left-most
    ``X-Forwarded-For`` entry is preferred. That header is client-controlled and
    trivially spoofed, which is why it is only used for the signup limit and
    never for authorization.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _enforce(decision: RateLimitDecision) -> None:
    if decision.allowed:
        return
    # 503 when the limiter itself is down (a server problem the client should
    # retry), 429 when the client genuinely exceeded a limit.
    is_outage = decision.limit > 0 and decision.remaining == 0 and "unavailable" in decision.detail
    raise HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
            if is_outage
            else status.HTTP_429_TOO_MANY_REQUESTS
        ),
        detail=decision.detail,
        headers=decision.headers,
    )


def enforce_signup_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """Throttle account creation per client IP."""
    _enforce(
        limiter.hit(
            scope="signup",
            identity=client_ip(request),
            limit=settings.signup_rate_limit_per_hour,
            window_seconds=3600,
        )
    )


def enforce_chat_rate_limit(
    current_user: User = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> User:
    """Per-minute request cap and daily token budget for the chat endpoint.

    Runs before the handler so an over-budget user is refused without the cost
    of building a pipeline. The concurrency slot is taken inside the handler,
    where it can be released when the stream ends.
    """
    _enforce(
        limiter.hit(
            scope="chat",
            identity=str(current_user.id),
            limit=settings.chat_rate_limit_per_minute,
            window_seconds=60,
        )
    )
    _enforce(
        limiter.check_token_budget(
            user_id=current_user.id,
            budget=settings.chat_daily_token_budget,
        )
    )
    return current_user

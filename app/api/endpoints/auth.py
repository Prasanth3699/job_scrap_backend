from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from fastapi import Header
from ...core.logger import logger
import requests

from ...services.token_service import TokenService
from ...core.auth import get_current_user
from ...models.user import User
from ...db.session import get_db
from ...schemas.auth import (
    AdminUserCreate,
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)
from ...services.auth_service import AuthService
from ...services.event_publisher import get_event_publisher
from ...core.config import get_settings

settings = get_settings()

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate, request: Request, db: Session = Depends(get_db)
):
    user = AuthService.register_user(db, user_data)

    # Publish user registration event
    try:
        event_publisher = get_event_publisher()
        await event_publisher.publish_user_registered(user)
    except Exception as e:
        logger.error(f"Failed to publish user registration event: {str(e)}")

    return user


@router.post("/admin/register", response_model=UserResponse)
async def register_admin(
    admin_data: AdminUserCreate, request: Request, db: Session = Depends(get_db)
):
    return AuthService.register_admin(db, admin_data)


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):

    user = AuthService.authenticate_user(db, user_data)
    is_admin = bool(user.is_admin)

    access_token = AuthService.create_access_token(
        {"sub": str(user.id), "is_admin": is_admin}
    )
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})

    # Publish user login event
    try:
        event_publisher = get_event_publisher()
        login_metadata = {
            "user_agent": request.headers.get("user-agent", "unknown"),
            "ip_address": request.client.host if request.client else "unknown",
            "is_admin": is_admin,
        }
        await event_publisher.publish_user_login(user, login_metadata)
    except Exception as e:
        logger.error(f"Failed to publish user login event: {str(e)}")

    # send refresh token in a secure, http-only cookie
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            is_admin=is_admin,
        ),
    )


@router.post("/logout", status_code=204)
def logout(response: Response):
    """
    Remove the http-only refresh_token cookie.
    The front-end will clear access token + helper cookie.
    """
    response.delete_cookie(
        "refresh_token",
        path="/",
        secure=True,
        samesite="strict",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/ws-token")
async def get_ws_token(current_user: User = Depends(get_current_user)):
    ws_token = TokenService.create_ws_token(current_user.id)
    return {"ws_token": ws_token}


@router.post("/validate-token", response_model=dict)
async def validate_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Validate the provided JWT token

    Returns:
    - User information if token is valid
    - Raises HTTPException if token is invalid
    """
    try:
        # Extract token from Authorization header
        token = credentials.credentials

        # Verify the token
        payload = AuthService.verify_token(token)

        # Extract user ID from token payload
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: No user identifier",
            )

        # Fetch user from database
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
            )

        # Return user information
        return {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin or False,
            "is_active": user.is_active,
        }

    except HTTPException:
        # Re-raise HTTPException to maintain specific error details
        raise
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )


@router.post("/payment-service/validate-token", response_model=dict)
async def payment_service_validate_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    x_internal_secret: str = Header(..., alias="x-internal-secret"),
):
    """
    Validate the provided JWT token

    Returns:
    - User information if token is valid
    - Raises HTTPException if token is invalid
    """
    try:
        # Only allow internal calls with correct secret
        if x_internal_secret != settings.INTER_SERVICE_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Extract token from Authorization header
        token = credentials.credentials

        # Verify the token
        payload = AuthService.verify_token(token)

        # Extract user ID from token payload
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: No user identifier",
            )

        # Fetch user from database
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
            )

        # Return user information
        return {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin or False,
            "is_active": user.is_active,
        }

    except HTTPException:
        # Re-raise HTTPException to maintain specific error details
        raise
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    response: Response,
    refresh_token: str = Cookie(...),
    db: Session = Depends(get_db),
):

    payload = AuthService.verify_refresh_token(refresh_token)
    user_id = int(payload["sub"])

    user: User | None = db.query(User).get(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    new_access = AuthService.create_access_token(
        {"sub": str(user.id), "is_admin": bool(user.is_admin)}
    )
    new_refresh = AuthService.create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )

    return TokenResponse(
        access_token=new_access,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
        ),
    )

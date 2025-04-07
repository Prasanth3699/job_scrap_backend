from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

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

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate, request: Request, db: Session = Depends(get_db)
):
    return AuthService.register_user(db, user_data)


@router.post("/admin/register", response_model=UserResponse)
async def register_admin(
    admin_data: AdminUserCreate, request: Request, db: Session = Depends(get_db)
):
    return AuthService.register_admin(db, admin_data)


@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, user_data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Ensure is_admin is a boolean
    is_admin = user.is_admin if user.is_admin is not None else False

    access_token = AuthService.create_access_token(
        data={"sub": str(user.id), "is_admin": is_admin}
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

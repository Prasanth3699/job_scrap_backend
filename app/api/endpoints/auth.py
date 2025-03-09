from fastapi import APIRouter, Depends, HTTPException, Request, status
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

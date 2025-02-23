from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...schemas.auth import UserCreate, UserLogin, UserResponse, Token
from ...services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate, request: Request, db: Session = Depends(get_db)
):
    return AuthService.register_user(db, user_data)


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, user_data)
    access_token = AuthService.create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)

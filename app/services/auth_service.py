from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from ..models.user import User
from ..core.config import get_settings
from ..schemas.auth import AdminUserCreate, UserCreate, UserLogin
import pytz

settings = get_settings()
IST = pytz.timezone("Asia/Kolkata")


class AuthService:
    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15-minute access token
    REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7-day refresh token
    ADMIN_SECRET_KEY = "123456"

    # ------------------------------------------------------------------
    # internal helper – signs a JWT
    # ------------------------------------------------------------------
    @staticmethod
    def _create_token(data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        to_encode["exp"] = datetime.now(IST) + expires_delta
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------
    @classmethod
    def create_access_token(cls, data: dict) -> str:
        """Return short-lived access token (type='access')."""
        return cls._create_token(
            {**data, "type": "access"},
            timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    @classmethod
    def create_refresh_token(cls, data: dict) -> str:
        """Return long-lived refresh token (type='refresh')."""
        return cls._create_token(
            {**data, "type": "refresh"},
            timedelta(minutes=cls.REFRESH_TOKEN_EXPIRE_MINUTES),
        )

    @staticmethod
    def verify_token(token: str) -> dict:
        try:
            return jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

    @staticmethod
    def verify_refresh_token(token: str) -> dict:
        payload = AuthService.verify_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
        return payload

    # ------------------------------------------------------------------
    # user / auth business logic (unchanged)
    # ------------------------------------------------------------------
    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> User:
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=User.hash_password(user_data.password),
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def register_admin(db: Session, admin_data: AdminUserCreate) -> User:
        if admin_data.admin_secret_key != AuthService.ADMIN_SECRET_KEY:
            raise HTTPException(status_code=403, detail="Invalid admin secret key")
        if db.query(User).filter(User.email == admin_data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        admin = User(
            name=admin_data.name,
            email=admin_data.email,
            password_hash=User.hash_password(admin_data.password),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin

    @staticmethod
    def authenticate_user(db: Session, user_data: UserLogin) -> User:
        user = db.query(User).filter(User.email == user_data.email).first()
        if not user or not user.verify_password(user_data.password):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is inactive")
        return user

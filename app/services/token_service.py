from datetime import datetime, timedelta, timezone
from jose import jwt
from ..core.config import get_settings

settings = get_settings()


class TokenService:
    @staticmethod
    def create_ws_token(user_id: str, expires_delta: timedelta = timedelta(minutes=15)):
        data = {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + expires_delta,
            "type": "ws",
        }
        return jwt.encode(data, settings.WS_SECRET_KEY, algorithm="HS256")

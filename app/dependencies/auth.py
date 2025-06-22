from fastapi import Depends, HTTPException, status
from job_scraper.backend.app.core.auth import get_current_user
from job_scraper.backend.app.models.user import User


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action",
        )
    return current_user

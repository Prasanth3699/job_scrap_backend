"""
Service-to-service authentication module for microservices communication.
Provides secure authentication between internal services.
"""

import os
import time
import jwt
import hashlib
from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Header, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..core.logger import logger

settings = get_settings()


class ServiceAuthConfig:
    """Configuration for service authentication"""
    
    # Service definitions with their allowed scopes
    SERVICES = {
        "ml-service": {
            "scopes": [
                "jobs:read",
                "jobs:bulk_read", 
                "users:read",
                "match_results:write"
            ],
            "description": "Machine Learning Service"
        },
        "llm-service": {
            "scopes": [
                "jobs:read",
                "users:read", 
                "profiles:read",
                "recommendations:write"
            ],
            "description": "Large Language Model Service"
        },
        "core-service": {
            "scopes": [
                "users:write",
                "jobs:write",
                "admin:all"
            ],
            "description": "Core Job Scraper Service"
        }
    }
    
    @classmethod
    def get_service_secret(cls) -> str:
        """Get service secret from environment"""
        secret = os.getenv("INTER_SERVICE_SECRET")
        if not secret:
            raise ValueError("INTER_SERVICE_SECRET environment variable is required")
        if len(secret) < 32:
            raise ValueError("INTER_SERVICE_SECRET must be at least 32 characters long")
        return secret
    
    @classmethod
    def get_service_jwt_secret(cls) -> str:
        """Get JWT secret for service tokens"""
        secret = os.getenv("SERVICE_JWT_SECRET")
        if not secret:
            # Fallback to main service secret with suffix
            return f"{cls.get_service_secret()}_JWT"
        return secret


class ServiceTokenManager:
    """Manages service-to-service JWT tokens"""
    
    TOKEN_EXPIRE_MINUTES = 60  # 1 hour for service tokens
    ALGORITHM = "HS256"
    
    @classmethod
    def create_service_token(
        cls, 
        service_name: str, 
        scopes: List[str],
        expires_in_minutes: Optional[int] = None
    ) -> str:
        """Create a JWT token for service authentication"""
        
        if service_name not in ServiceAuthConfig.SERVICES:
            raise ValueError(f"Unknown service: {service_name}")
        
        allowed_scopes = ServiceAuthConfig.SERVICES[service_name]["scopes"]
        invalid_scopes = set(scopes) - set(allowed_scopes)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes for {service_name}: {invalid_scopes}")
        
        expire_minutes = expires_in_minutes or cls.TOKEN_EXPIRE_MINUTES
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        
        payload = {
            "service": service_name,
            "scopes": scopes,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at,
            "iss": "core-service",
            "aud": "microservices",
            "type": "service_token"
        }
        
        token = jwt.encode(
            payload, 
            ServiceAuthConfig.get_service_jwt_secret(), 
            algorithm=cls.ALGORITHM
        )
        
        logger.info(f"Created service token for {service_name} with scopes: {scopes}")
        return token
    
    @classmethod
    def verify_service_token(cls, token: str) -> Dict:
        """Verify and decode service token"""
        try:
            payload = jwt.decode(
                token,
                ServiceAuthConfig.get_service_jwt_secret(),
                algorithms=[cls.ALGORITHM],
                audience="microservices"
            )
            
            # Validate token type
            if payload.get("type") != "service_token":
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid token type"
                )
            
            # Validate service exists
            service_name = payload.get("service")
            if service_name not in ServiceAuthConfig.SERVICES:
                raise HTTPException(
                    status_code=401, 
                    detail=f"Unknown service: {service_name}"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401, 
                detail="Service token expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=401, 
                detail=f"Invalid service token: {str(e)}"
            )


class ServiceAuth:
    """Service authentication result"""
    
    def __init__(self, service_name: str, scopes: List[str]):
        self.service_name = service_name
        self.scopes = scopes
        self.is_authenticated = True
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if service has required scope"""
        return required_scope in self.scopes
    
    def require_scope(self, required_scope: str):
        """Require specific scope, raise exception if not present"""
        if not self.has_scope(required_scope):
            raise HTTPException(
                status_code=403,
                detail=f"Service {self.service_name} lacks required scope: {required_scope}"
            )


# Dependency functions
security = HTTPBearer()


async def verify_service_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_service_name: str = Header(..., alias="x-service-name"),
    x_service_signature: Optional[str] = Header(None, alias="x-service-signature")
) -> ServiceAuth:
    """
    Verify service authentication using JWT tokens
    
    Headers required:
    - Authorization: Bearer <service_jwt_token>
    - X-Service-Name: <service_name>
    - X-Service-Signature: <optional_request_signature>
    """
    
    try:
        # Verify JWT token
        payload = ServiceTokenManager.verify_service_token(credentials.credentials)
        
        # Verify service name matches token
        token_service = payload.get("service")
        if token_service != x_service_name:
            raise HTTPException(
                status_code=401,
                detail="Service name mismatch between token and header"
            )
        
        # Optional: Verify request signature for extra security
        if x_service_signature:
            await _verify_request_signature(request, x_service_signature)
        
        scopes = payload.get("scopes", [])
        logger.info(f"Service authenticated: {x_service_name} with scopes: {scopes}")
        
        return ServiceAuth(x_service_name, scopes)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service authentication error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal authentication error"
        )


async def _verify_request_signature(request: Request, signature: str):
    """Verify request signature for extra security (optional)"""
    try:
        # Create signature from request body + timestamp + secret
        body = await request.body()
        timestamp = request.headers.get("x-timestamp", "")
        
        expected_signature = hashlib.sha256(
            f"{body.decode()}{timestamp}{ServiceAuthConfig.get_service_secret()}".encode()
        ).hexdigest()
        
        if not signature == expected_signature:
            raise HTTPException(
                status_code=401,
                detail="Invalid request signature"
            )
            
    except Exception as e:
        logger.warning(f"Request signature verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid request signature"
        )


# Scope-specific dependency functions
def require_jobs_read_scope(service_auth: ServiceAuth = Depends(verify_service_auth)):
    """Require jobs:read scope"""
    service_auth.require_scope("jobs:read")
    return service_auth


def require_jobs_write_scope(service_auth: ServiceAuth = Depends(verify_service_auth)):
    """Require jobs:write scope"""
    service_auth.require_scope("jobs:write")
    return service_auth


def require_users_read_scope(service_auth: ServiceAuth = Depends(verify_service_auth)):
    """Require users:read scope"""
    service_auth.require_scope("users:read")
    return service_auth


def require_admin_scope(service_auth: ServiceAuth = Depends(verify_service_auth)):
    """Require admin:all scope"""
    service_auth.require_scope("admin:all")
    return service_auth


# Token generation endpoint (for testing/development)
def generate_service_tokens():
    """Generate tokens for all services (development use only)"""
    tokens = {}
    
    for service_name, config in ServiceAuthConfig.SERVICES.items():
        token = ServiceTokenManager.create_service_token(
            service_name=service_name,
            scopes=config["scopes"],
            expires_in_minutes=1440  # 24 hours for development
        )
        tokens[service_name] = {
            "token": token,
            "scopes": config["scopes"],
            "description": config["description"]
        }
    
    return tokens


# Health check for service auth
async def check_service_auth_health() -> Dict:
    """Check service authentication health"""
    try:
        # Test secret availability
        ServiceAuthConfig.get_service_secret()
        ServiceAuthConfig.get_service_jwt_secret()
        
        return {
            "status": "healthy",
            "services_configured": len(ServiceAuthConfig.SERVICES),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
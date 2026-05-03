"""
auth_utils.py - ShopFlow v1.0.0
JWT + bcrypt authentication utilities
"""
import jwt
import bcrypt
import os
from datetime import datetime, timedelta
from fastapi import HTTPException, Header
from typing import Optional

JWT_SECRET = os.environ.get("JWT_SECRET", "shopflow-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, tenant_id: int, role: str = "admin", email: str = "") -> str:
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No authorization token")
    token = authorization.split(" ", 1)[1]
    return decode_token(token)


def get_tenant_id(authorization: Optional[str] = Header(None)) -> int:
    user = get_current_user(authorization)
    return user["tenant_id"]

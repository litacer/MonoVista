from functools import wraps
from datetime import datetime, timedelta
import os
import jwt
from flask import request, jsonify, g

from backend.models.user import User


def create_token(user_id: int):
    secret = os.getenv("JWT_SECRET", "monovista-dev-secret")
    expire_hours = int(os.getenv("JWT_EXPIRE_HOURS", "72"))
    payload = {
        "sub": str(user_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expire_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str):
    secret = os.getenv("JWT_SECRET", "monovista-dev-secret")
    return jwt.decode(token, secret, algorithms=["HS256"])


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth.replace("Bearer ", "", 1).strip()
        try:
            payload = decode_token(token)
            user = User.query.get(int(payload["sub"]))
            if not user:
                return jsonify({"error": "User not found"}), 401
            g.current_user = user
        except Exception:
            return jsonify({"error": "Token invalid or expired"}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """复用 jwt_required 的管理员权限守卫。"""
    @jwt_required
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user or (user.role or "").lower() != "admin":
            return jsonify({"error": "Forbidden: admin only"}), 403
        return fn(*args, **kwargs)
    return wrapper

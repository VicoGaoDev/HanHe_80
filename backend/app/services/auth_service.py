import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.business_id_service import user_external_id
from app.utils.security import create_access_token, hash_password, verify_password

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _validate_email(email: str) -> str:
    normalized = _normalize_email(email)
    if not normalized or not EMAIL_REGEX.match(normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确")
    if len(normalized) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱长度不能超过255个字符")
    return normalized


def _validate_username(username: str) -> str:
    normalized = (username or "").strip()
    if len(normalized) < 2 or len(normalized) > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名需 2-20 个字符")
    return normalized


def register_user(db: Session, username: str, email: str, password: str) -> tuple[str, User]:
    normalized_username = _validate_username(username)
    normalized_email = _validate_email(email)
    if len(password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少6位")

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")

    user = User(
        username=normalized_username,
        email=normalized_email,
        email_verified=True,
        password_hash=hash_password(password),
        role="user",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_external_id(user), user.role)
    return token, user


def authenticate_user(db: Session, account: str, password: str) -> tuple[str, User]:
    normalized_account = (account or "").strip()
    if not normalized_account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入邮箱或用户名")

    if "@" in normalized_account:
        user = db.query(User).filter(User.email == _normalize_email(normalized_account)).first()
    else:
        matched_users = db.query(User).filter(User.username == normalized_account).all()
        if len(matched_users) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该用户名对应多个账号，请使用邮箱登录",
            )
        user = matched_users[0] if matched_users else None

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱/用户名或密码错误")
    if user.status == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user_external_id(user), user.role)
    return token, user


def change_password(db: Session, user: User, old_password: str, new_password: str):
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if len(new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少6位")

    user.password_hash = hash_password(new_password)
    db.commit()


def update_username(db: Session, user: User, username: str) -> User:
    normalized_username = _validate_username(username)
    if user.username == normalized_username:
        return user
    user.username = normalized_username
    db.commit()
    db.refresh(user)
    return user

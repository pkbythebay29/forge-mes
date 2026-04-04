import hashlib

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_signature(session: Session, username: str, password: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or user.password_hash != hash_password(password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid electronic signature")
    return user

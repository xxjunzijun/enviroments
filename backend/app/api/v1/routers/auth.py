from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if len(data.username) < 2 or len(data.username) > 50:
        raise HTTPException(status_code=400, detail="用户名长度需在 2-50 个字符之间")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少 6 位")

    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
    )


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.id)
    return AuthResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

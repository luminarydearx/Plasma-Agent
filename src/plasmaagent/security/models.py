from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class UserRole(str):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: Optional[str] = Field(None, max_length=255)
    role: str = Field(default=UserRole.USER)
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None


class User(UserBase):
    id: UUID = Field(default_factory=uuid4)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        frozen = True


class UserLogin(BaseModel):
    username: str
    password: str


class UserSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True

    class Config:
        frozen = True


class Permission(BaseModel):
    resource: str
    actions: List[str]

    class Config:
        frozen = True

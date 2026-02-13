"""
Pydantic schemas for authentication API
"""

from typing import Optional
from pydantic import BaseModel, Field


class SignupDto(BaseModel):
    """Request model for user signup"""
    username: str
    first_name: str
    last_name: str
    email: str
    password: str


class LoginDto(BaseModel):
    """Request model for user login"""
    username: str
    password: str


class AuthResponseDto(BaseModel):
    """Response model for authentication"""
    user_id: int
    username: str
    first_name: str = ""
    last_name: str = ""
    message: str = ""

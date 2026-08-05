import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import UserRole


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    if not re.fullmatch(r"1\d{10}", digits):
        raise ValueError("invalid mainland china phone number")
    return digits


class LoginRequest(BaseModel):
    identifier: str | None = Field(default=None, max_length=64)
    username: str | None = Field(default=None, max_length=64)
    password: str = Field(min_length=6, max_length=128)

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        value = (self.identifier or self.username or "").strip()
        if len(value) < 3:
            raise ValueError("identifier is required")
        self.identifier = value
        self.username = value
        return self


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=32)
    display_name: str | None = Field(default=None, max_length=64)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class PhoneCodeRequestIn(BaseModel):
    phone: str = Field(min_length=11, max_length=32)
    purpose: str = Field(default="login", pattern="^(login|reset_password)$")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class PhoneCodeRequestOut(BaseModel):
    sent: bool = True
    phone: str
    purpose: str
    expires_seconds: int
    retry_after_seconds: int
    debug_code: str | None = None


class PhoneCodeVerifyIn(BaseModel):
    phone: str = Field(min_length=11, max_length=32)
    code: str = Field(min_length=4, max_length=8)
    display_name: str | None = Field(default=None, max_length=64)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit():
            raise ValueError("code must be numeric")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int | None = None
    username: str | None = None
    role: UserRole | None = None
    phone: str | None = None
    wechat_openid: str | None = None
    wechat_bound: bool = False
    is_new_user: bool = False
    generated_password: str | None = None


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    display_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    wechat_openid: str | None = None
    wechat_bound: bool = False


class SelfPasswordUpdateIn(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class SelfProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=255)


class WechatMiniCodeIn(BaseModel):
  code: str = Field(min_length=1, max_length=256)
  app_scope: Literal['customer', 'employee'] = 'customer'


class WechatMiniCodeOut(BaseModel):
    openid: str
    unionid: str | None = None
    session_key_present: bool = False


class WechatMiniLoginIn(BaseModel):
  code: str = Field(min_length=1, max_length=256)
  display_name: str | None = Field(default=None, max_length=64)
  app_scope: Literal['customer', 'employee'] = 'customer'


class WechatMiniLoginWithPhoneIn(BaseModel):
  login_code: str = Field(min_length=1, max_length=256)
  phone_code: str = Field(min_length=1, max_length=256)
  display_name: str | None = Field(default=None, max_length=64)
  app_scope: Literal['customer', 'employee'] = 'customer'


class WechatMiniBindPhoneIn(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class WechatMiniBindPhoneOut(BaseModel):
    bound: bool = True
    phone: str

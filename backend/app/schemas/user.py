from pydantic import BaseModel, Field

from app.models.enums import UserRole


class CustomerProfileOut(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    address: str | None = None
    note: str | None = None
    avatar_url: str | None = None
    wechat_bound: bool = False
    wechat_openid: str | None = None
    is_verified_wholesale: bool
    miniapp_notification_enabled: bool = False
    miniapp_notification_event_keys: list[str] = Field(default_factory=list)
    miniapp_notification_updated_at: str | None = None


class UserAdminOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: str
    profile: CustomerProfileOut | None = None


class UserStatusUpdateIn(BaseModel):
    is_active: bool = Field(description="Whether the user can continue to access the system.")


class CustomerCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = Field(default=UserRole.RETAIL)
    display_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)
    is_verified_wholesale: bool = False


class UserRoleAssignIn(BaseModel):
    role: UserRole
    user_id: int | None = None
    phone: str | None = Field(default=None, max_length=32)
    wechat_openid: str | None = Field(default=None, max_length=64)
    is_verified_wholesale: bool | None = None


class CustomerProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=255)
    is_verified_wholesale: bool | None = None
    miniapp_notification_enabled: bool | None = None
    miniapp_notification_event_keys: list[str] | None = None


class CustomerSelfProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=255)


class CustomerSelfPasswordUpdateIn(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class CustomerAddressOut(BaseModel):
    id: int
    recipient: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool


class CustomerAddressCreateIn(BaseModel):
    recipient: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=11, max_length=32)
    province: str = Field(min_length=1, max_length=64)
    city: str = Field(min_length=1, max_length=64)
    district: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class CustomerAddressUpdateIn(BaseModel):
    recipient: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, min_length=11, max_length=32)
    province: str | None = Field(default=None, min_length=1, max_length=64)
    city: str | None = Field(default=None, min_length=1, max_length=64)
    district: str | None = Field(default=None, min_length=1, max_length=64)
    detail: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None


class ShoppingCartItemIn(BaseModel):
    sku_id: int
    unit_code: str = Field(min_length=1, max_length=32)
    quantity: int = Field(ge=1, le=9999)


class ShoppingCartSyncIn(BaseModel):
    items: list[ShoppingCartItemIn]


class ShoppingCartItemOut(BaseModel):
    sku_id: int
    product_id: int
    product_code: str
    product_name: str
    category: str | None = None
    subcategory: str | None = None
    sku_name: str
    sku_code: str
    unit_code: str
    unit_name: str
    quantity: int
    unit_price: str
    image_url: str | None = None
    attrs: dict = Field(default_factory=dict)
    min_wholesale_base_qty: int
    on_hand_base_qty: int
    reserved_base_qty: int
    sellable_stock: int
    conversions: list[dict] = Field(default_factory=list)


class WholesaleApplicationCreateIn(BaseModel):
    company_name: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    reason: str | None = Field(default=None, max_length=255)


class WholesaleApplicationReviewIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=255)


class WholesaleApplicationOut(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    status: str
    company_name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    reason: str | None = None
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: str | None = None
    created_at: str

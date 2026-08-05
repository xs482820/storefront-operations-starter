from pydantic import BaseModel, Field


class SmartEntryItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=128)
    product_code: str = Field(min_length=1, max_length=64)
    sku_code: str = Field(min_length=1, max_length=64)
    sku_name: str = Field(min_length=1, max_length=128)
    brand: str | None = Field(default=None, max_length=64)
    spec: str | None = Field(default=None, max_length=128)
    quantity_base: int = Field(gt=0)


class SmartEntryIn(BaseModel):
    source: str = Field(default="ocr")
    items: list[SmartEntryItemIn]

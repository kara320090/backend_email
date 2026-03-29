from pydantic import BaseModel, EmailStr, Field


class SubscribeRequest(BaseModel):
    email: EmailStr
    region: str = Field(default="ÀüÃ¼", min_length=1, max_length=100)
    min_discount: float = Field(default=0, ge=0, le=100)


class SubscribeResponse(BaseModel):
    ok: bool
    message: str
    subscriber_id: int | None = None


class UnsubscribeRequest(BaseModel):
    email: EmailStr
    region: str | None = None


class UnsubscribeResponse(BaseModel):
    ok: bool
    message: str
    updated: int = 0

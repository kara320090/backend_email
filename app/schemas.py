from pydantic import BaseModel, EmailStr, Field


class SubscribeRequest(BaseModel):
    email: EmailStr
    region: str = Field(default="전체", min_length=1, max_length=100)
    min_discount: float = Field(default=0, ge=0, le=100)


class SubscribeResponse(BaseModel):
    ok: bool
    message: str
    subscriber_id: int | None = None
    confirmation_sent: bool = False
    instant_alert_count: int = 0


class UnsubscribeRequest(BaseModel):
    email: EmailStr
    region: str | None = None
    min_discount: float | None = None


class UnsubscribeResponse(BaseModel):
    ok: bool
    message: str
    updated: int = 0


class SendAlertsResponse(BaseModel):
    ok: bool
    processed_subscribers: int = 0
    emails_sent: int = 0
    listings_logged: int = 0
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import get_supabase
from .schemas import (
    SubscribeRequest,
    SubscribeResponse,
    UnsubscribeRequest,
    UnsubscribeResponse,
)


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_check() -> None:
    settings.validate()
    get_supabase()


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": settings.app_name,
    }


@app.post("/subscribe", response_model=SubscribeResponse)
def subscribe(payload: SubscribeRequest) -> SubscribeResponse:
    supabase = get_supabase()

    email = str(payload.email).strip().lower()
    region = payload.region.strip() if payload.region.strip() else "전체"
    min_discount = float(payload.min_discount)

    try:
        existing = (
            supabase.table("subscribers")
            .select("id,is_active")
            .eq("email", email)
            .eq("region", region)
            .eq("min_discount", min_discount)
            .limit(1)
            .execute()
        )

        rows = existing.data or []

        if rows:
            row = rows[0]
            subscriber_id = int(row["id"])

            (
                supabase.table("subscribers")
                .update({"is_active": True})
                .eq("id", subscriber_id)
                .execute()
            )

            return SubscribeResponse(
                ok=True,
                message="기존 구독을 다시 활성화했습니다.",
                subscriber_id=subscriber_id,
            )

        inserted = (
            supabase.table("subscribers")
            .insert(
                {
                    "email": email,
                    "region": region,
                    "min_discount": min_discount,
                    "is_active": True,
                }
            )
            .execute()
        )

        inserted_rows = inserted.data or []
        subscriber_id = int(inserted_rows[0]["id"]) if inserted_rows else None

        return SubscribeResponse(
            ok=True,
            message="구독이 등록되었습니다.",
            subscriber_id=subscriber_id,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"subscribe failed: {exc}") from exc


@app.post("/unsubscribe", response_model=UnsubscribeResponse)
def unsubscribe(payload: UnsubscribeRequest) -> UnsubscribeResponse:
    supabase = get_supabase()

    email = str(payload.email).strip().lower()

    try:
        query = (
            supabase.table("subscribers")
            .update({"is_active": False})
            .eq("email", email)
        )

        if payload.region and payload.region.strip():
            query = query.eq("region", payload.region.strip())

        result = query.execute()
        updated_rows = result.data or []

        return UnsubscribeResponse(
            ok=True,
            message="구독 해지가 처리되었습니다.",
            updated=len(updated_rows),
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"unsubscribe failed: {exc}") from exc


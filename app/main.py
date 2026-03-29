from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .config import settings
from .db import get_supabase
from .mailer import send_alert_email, send_subscription_email
from .schemas import (
    SendAlertsResponse,
    SubscribeRequest,
    SubscribeResponse,
    UnsubscribeRequest,
    UnsubscribeResponse,
)
from .security import verify_unsubscribe_token

ALL_TEXT = "\uC804\uCCB4"

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


def normalize_region(value: str | None) -> str:
    text = (value or "").strip()
    return text if text else ALL_TEXT


def normalize_discount(value: float | int | str | None) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def listing_sort_key(item: dict) -> tuple:
    return (
        -safe_float(item.get("discount_rate")),
        str(item.get("deal_date") or ""),
        safe_float(item.get("price")),
    )


def build_listing_key(item: dict) -> str:
    listing_id = item.get("id")
    if listing_id is not None:
        return f"id:{listing_id}"

    parts = [
        str(item.get("apt_seq") or ""),
        str(item.get("apt_name") or ""),
        str(item.get("area_size") or ""),
        str(item.get("price") or ""),
        str(item.get("floor") or ""),
        str(item.get("deal_date") or ""),
    ]
    return "row:" + "|".join(parts)


def fetch_matches(region: str, min_discount: float, limit: int = 20) -> list[dict]:
    url = f"{settings.friend_api_base_url}/filter"
    params = {
        "region": region,
        "grade": ALL_TEXT,
        "min_discount": min_discount,
        "page": 1,
        "per_page": max(limit, 20),
    }

    response = httpx.get(url, params=params, timeout=60.0)
    response.raise_for_status()

    payload = response.json()
    items = payload.get("data") or []
    items = sorted(items, key=listing_sort_key)
    return items[:limit]


def get_existing_listing_keys(subscriber_id: int, listing_keys: list[str]) -> set[str]:
    if not listing_keys:
        return set()

    supabase = get_supabase()
    result = (
        supabase.table("alert_logs")
        .select("listing_key")
        .eq("subscriber_id", subscriber_id)
        .in_("listing_key", listing_keys)
        .execute()
    )

    rows = result.data or []
    return {str(row.get("listing_key")) for row in rows}


def insert_alert_logs(subscriber_id: int, listing_keys: list[str]) -> int:
    if not listing_keys:
        return 0

    supabase = get_supabase()
    rows = [{"subscriber_id": subscriber_id, "listing_key": key} for key in listing_keys]
    supabase.table("alert_logs").insert(rows).execute()
    return len(rows)


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
    region = normalize_region(payload.region)
    min_discount = normalize_discount(payload.min_discount)

    try:
        existing = (
            supabase.table("subscribers")
            .select("id,is_active,email,region,min_discount")
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
        else:
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
            subscriber_id = int(inserted_rows[0]["id"])

        confirmation_sent = False
        instant_alert_count = 0
        current_matches = []

        try:
            current_matches = fetch_matches(region=region, min_discount=min_discount, limit=10)
        except Exception as exc:
            print(f"[WARN] fetch_matches failed: {exc}")

        try:
            send_subscription_email(
                to_email=email,
                subscriber_id=subscriber_id,
                region=region,
                min_discount=min_discount,
                listings=current_matches,
            )
            confirmation_sent = True
        except Exception as exc:
            print(f"[WARN] send_subscription_email failed: {exc}")

        try:
            if current_matches:
                current_keys = [build_listing_key(item) for item in current_matches]
                already_sent = get_existing_listing_keys(subscriber_id, current_keys)

                unsent_items = []
                unsent_keys = []

                for item, key in zip(current_matches, current_keys):
                    if key not in already_sent:
                        unsent_items.append(item)
                        unsent_keys.append(key)

                if unsent_items:
                    send_alert_email(
                        to_email=email,
                        subscriber_id=subscriber_id,
                        region=region,
                        min_discount=min_discount,
                        listings=unsent_items,
                        subject="Immediate listing alert",
                    )
                    insert_alert_logs(subscriber_id, unsent_keys)
                    instant_alert_count = len(unsent_items)
        except Exception as exc:
            print(f"[WARN] send instant alert failed: {exc}")

        return SubscribeResponse(
            ok=True,
            message="Subscription saved.",
            subscriber_id=subscriber_id,
            confirmation_sent=confirmation_sent,
            instant_alert_count=instant_alert_count,
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

        if payload.min_discount is not None:
            query = query.eq("min_discount", normalize_discount(payload.min_discount))

        result = query.execute()
        updated_rows = result.data or []

        return UnsubscribeResponse(
            ok=True,
            message="Unsubscribed successfully.",
            updated=len(updated_rows),
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"unsubscribe failed: {exc}") from exc


@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_by_token(token: str = Query(...)) -> HTMLResponse:
    supabase = get_supabase()

    try:
        payload = verify_unsubscribe_token(token)
        subscriber_id = int(payload["subscriber_id"])

        (
            supabase.table("subscribers")
            .update({"is_active": False})
            .eq("id", subscriber_id)
            .execute()
        )

        return HTMLResponse(
            """
            <html>
              <body style="font-family:Arial,sans-serif;padding:40px;">
                <h2>Unsubscribed</h2>
                <p>Your subscription has been cancelled successfully.</p>
              </body>
            </html>
            """
        )
    except Exception as exc:
        return HTMLResponse(
            f"""
            <html>
              <body style="font-family:Arial,sans-serif;padding:40px;">
                <h2>Invalid request</h2>
                <p>{str(exc)}</p>
              </body>
            </html>
            """,
            status_code=400,
        )


@app.post("/send-alerts", response_model=SendAlertsResponse)
def send_alerts(x_cron_secret: str = Header(default="")) -> SendAlertsResponse:
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    supabase = get_supabase()

    try:
        subscribers_result = (
            supabase.table("subscribers")
            .select("id,email,region,min_discount,is_active")
            .eq("is_active", True)
            .execute()
        )
        subscribers = subscribers_result.data or []

        processed_subscribers = 0
        emails_sent = 0
        listings_logged = 0

        for subscriber in subscribers:
            try:
                processed_subscribers += 1

                subscriber_id = int(subscriber["id"])
                email = str(subscriber["email"]).strip().lower()
                region = normalize_region(subscriber.get("region"))
                min_discount = normalize_discount(subscriber.get("min_discount"))

                matches = fetch_matches(region=region, min_discount=min_discount, limit=10)
                if not matches:
                    continue

                keys = [build_listing_key(item) for item in matches]
                existing_keys = get_existing_listing_keys(subscriber_id, keys)

                unsent_items = []
                unsent_keys = []

                for item, key in zip(matches, keys):
                    if key not in existing_keys:
                        unsent_items.append(item)
                        unsent_keys.append(key)

                if not unsent_items:
                    continue

                send_alert_email(
                    to_email=email,
                    subscriber_id=subscriber_id,
                    region=region,
                    min_discount=min_discount,
                    listings=unsent_items,
                    subject="Daily listing alert",
                )
                emails_sent += 1
                listings_logged += insert_alert_logs(subscriber_id, unsent_keys)

            except Exception:
                continue

        return SendAlertsResponse(
            ok=True,
            processed_subscribers=processed_subscribers,
            emails_sent=emails_sent,
            listings_logged=listings_logged,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"send-alerts failed: {exc}") from exc
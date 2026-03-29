from html import escape

import httpx

from .config import settings
from .security import create_unsubscribe_token


def format_money(value) -> str:
    try:
        num = float(value or 0)
    except Exception:
        num = 0
    return f"{num:,.0f}"


def build_unsubscribe_url(subscriber_id: int) -> str:
    token = create_unsubscribe_token(subscriber_id)
    return f"{settings.backend_public_base_url}/unsubscribe?token={token}"


def send_email(to_email: str, subject: str, html_content: str) -> None:
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.mail_from,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        },
        timeout=30.0,
    )
    response.raise_for_status()


def render_listing_rows(listings: list[dict]) -> str:
    rows = []
    for item in listings[:10]:
        apt_name = escape(str(item.get("apt_name") or "-"))
        region_name = escape(str(item.get("region_name") or item.get("dong_name") or "-"))
        area_size = escape(str(item.get("area_size") or "-"))
        deal_date = escape(str(item.get("deal_date") or "-"))
        discount_rate = escape(str(item.get("discount_rate") or "0"))
        price = escape(format_money(item.get("price")))
        market_avg = escape(format_money(item.get("market_avg")))

        rows.append(
            f"""
            <tr>
              <td style="padding:8px;border:1px solid #ddd;">{apt_name}</td>
              <td style="padding:8px;border:1px solid #ddd;">{region_name}</td>
              <td style="padding:8px;border:1px solid #ddd;">{area_size}</td>
              <td style="padding:8px;border:1px solid #ddd;">{price}</td>
              <td style="padding:8px;border:1px solid #ddd;">{market_avg}</td>
              <td style="padding:8px;border:1px solid #ddd;">{discount_rate}%</td>
              <td style="padding:8px;border:1px solid #ddd;">{deal_date}</td>
            </tr>
            """
        )
    return "".join(rows)


def send_subscription_email(
    to_email: str,
    subscriber_id: int,
    region: str,
    min_discount: float,
    listings: list[dict],
) -> None:
    unsubscribe_url = build_unsubscribe_url(subscriber_id)
    rows_html = render_listing_rows(listings)

    current_matches_block = ""
    if listings:
        current_matches_block = f"""
        <h3 style="margin-top:24px;">Current matching listings</h3>
        <table style="border-collapse:collapse;width:100%;font-size:14px;">
          <thead>
            <tr>
              <th style="padding:8px;border:1px solid #ddd;">Apartment</th>
              <th style="padding:8px;border:1px solid #ddd;">Region</th>
              <th style="padding:8px;border:1px solid #ddd;">Area</th>
              <th style="padding:8px;border:1px solid #ddd;">Price</th>
              <th style="padding:8px;border:1px solid #ddd;">12M Avg</th>
              <th style="padding:8px;border:1px solid #ddd;">Discount</th>
              <th style="padding:8px;border:1px solid #ddd;">Deal Date</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        """

    site_link = settings.app_base_url or "#"

    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <h2>Subscription created</h2>
      <p>Your email alert subscription is now active.</p>
      <p><strong>Region:</strong> {escape(region)}</p>
      <p><strong>Minimum discount:</strong> {escape(str(min_discount))}%</p>
      <p>You will receive daily alert emails at 09:00 KST when new matching listings exist.</p>
      {current_matches_block}
      <p style="margin-top:24px;">
        <a href="{site_link}" style="display:inline-block;padding:10px 14px;background:#dc2626;color:#fff;text-decoration:none;border-radius:8px;">
          Open service
        </a>
      </p>
      <p style="margin-top:16px;">
        <a href="{unsubscribe_url}">Unsubscribe</a>
      </p>
    </div>
    """

    send_email(to_email, "Subscription created", html)


def send_alert_email(
    to_email: str,
    subscriber_id: int,
    region: str,
    min_discount: float,
    listings: list[dict],
    subject: str,
) -> None:
    unsubscribe_url = build_unsubscribe_url(subscriber_id)
    rows_html = render_listing_rows(listings)
    site_link = settings.app_base_url or "#"

    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <h2>{escape(subject)}</h2>
      <p>New matching listings were found.</p>
      <p><strong>Region:</strong> {escape(region)}</p>
      <p><strong>Minimum discount:</strong> {escape(str(min_discount))}%</p>

      <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <thead>
          <tr>
            <th style="padding:8px;border:1px solid #ddd;">Apartment</th>
            <th style="padding:8px;border:1px solid #ddd;">Region</th>
            <th style="padding:8px;border:1px solid #ddd;">Area</th>
            <th style="padding:8px;border:1px solid #ddd;">Price</th>
            <th style="padding:8px;border:1px solid #ddd;">12M Avg</th>
            <th style="padding:8px;border:1px solid #ddd;">Discount</th>
            <th style="padding:8px;border:1px solid #ddd;">Deal Date</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>

      <p style="margin-top:24px;">
        <a href="{site_link}" style="display:inline-block;padding:10px 14px;background:#dc2626;color:#fff;text-decoration:none;border-radius:8px;">
          Open service
        </a>
      </p>
      <p style="margin-top:16px;">
        <a href="{unsubscribe_url}">Unsubscribe</a>
      </p>
    </div>
    """

    send_email(to_email, subject, html)
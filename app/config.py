import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Apt Alert Email Backend")
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    friend_api_base_url: str = os.getenv("FRIEND_API_BASE_URL", "").strip().rstrip("/")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "").strip()
    mail_from: str = os.getenv("MAIL_FROM", "").strip()
    app_base_url: str = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    backend_public_base_url: str = os.getenv("BACKEND_PUBLIC_BASE_URL", "").strip().rstrip("/")
    cron_secret: str = os.getenv("CRON_SECRET", "").strip()
    unsubscribe_secret: str = os.getenv("UNSUBSCRIBE_SECRET", "").strip()

    def validate(self) -> None:
        missing = []

        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
            "FRIEND_API_BASE_URL": self.friend_api_base_url,
            "RESEND_API_KEY": self.resend_api_key,
            "MAIL_FROM": self.mail_from,
            "BACKEND_PUBLIC_BASE_URL": self.backend_public_base_url,
            "CRON_SECRET": self.cron_secret,
            "UNSUBSCRIBE_SECRET": self.unsubscribe_secret,
        }

        for key, value in required.items():
            if not value:
                missing.append(key)

        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


settings = Settings()
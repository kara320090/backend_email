from supabase import Client, create_client
from .config import settings

_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client

    if _supabase_client is None:
        settings.validate()
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )

    return _supabase_client


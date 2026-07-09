import os

# Placeholder values so `app.core.config.settings` (instantiated at import time)
# can load during automated tests without a real backend/.env file. Real
# credentials are only required to actually run the server (see Task 8/10).
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

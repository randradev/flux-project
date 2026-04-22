import httpx
print(f"HTTPX Version: {httpx.__version__}")
try:
    from app.infra.supabase import supabase_client
    print("Supabase client imported successfully")
except Exception as e:
    print(f"Supabase import/init failed: {e}")

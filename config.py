from dotenv import load_dotenv
import os

load_dotenv()

# The only config the app needs
# All AI and payment logic lives on the Vercel backend
VERCEL_API_URL = os.getenv("VERCEL_API_URL", "http://localhost:3000")
# Optional fallback for auth when the Vercel backend is unreachable.
# Both values are public Supabase client credentials (safe to ship).
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
APP_VERSION = "1.0.0"

# STT runs locally — no key needed
WHISPER_MODEL = "base"

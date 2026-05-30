from dotenv import load_dotenv
import os

load_dotenv()

# The only config the app needs
# All AI and payment logic lives on the Vercel backend
VERCEL_API_URL = os.getenv("VERCEL_API_URL", "http://localhost:3000")
APP_VERSION = "1.0.0"

# STT runs locally — no key needed
WHISPER_MODEL = "base"

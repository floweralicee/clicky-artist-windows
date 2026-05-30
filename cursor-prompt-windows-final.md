Hi! I have a fork of Bitshank-2338/clicky-windows called clicky-artist-windows.
Read AGENTS.md completely before doing anything. Then follow these steps
one at a time. Tell me what you changed after each step before moving
to the next one.

---

## Step 0 — Read first

Read AGENTS.md fully.
Summarise what this app does and what stack it uses in 3 sentences.
Do not touch any code until I confirm you have understood it.

---

## Step 1 — Read the existing codebase

Read these files and tell me what you find:
- config.py (how are providers currently set up?)
- companion_manager.py (how does it call the AI today?)
- audio/tts/ all files (which TTS providers exist?)
- audio/stt/ all files (which STT providers exist?)
- ui/tray.py (what menu items exist?)
- ui/panel.py (what does the panel currently show?)
- main.py (how does it boot?)

Do not change anything. Just read and report.

---

## Step 2 — Create the folder structure

Create these new files and folders (empty for now, we will fill them
in later steps):

  auth/
    __init__.py
    supabase_auth.py

  api/
    __init__.py
    vercel_client.py

  ui/
    auth_screen.py      (already in ui/ — create if not there)
    paywall_screen.py

  update/
    __init__.py
    updater.py

  backend/
    api/
      chat.ts
      tts.ts
      auth/
        signup.ts
        signin.ts
      status.ts
      webhooks/
        stripe.ts
      version.ts
    lib/
      supabase.ts
      auth.ts
      usage.ts
    package.json
    tsconfig.json
    vercel.json

Tell me the full folder structure after you create these.

---

## Step 3 — Update config.py

Replace the existing config with this minimal version.
Remove all API key loading for Anthropic, OpenAI, Gemini, ElevenLabs,
Deepgram, GitHub Copilot. The app has no secrets.

config.py should only contain:

  import os
  from dotenv import load_dotenv

  load_dotenv()

  # The only config the app needs
  # All AI and payment logic lives on the Vercel backend
  VERCEL_API_URL = os.getenv("VERCEL_API_URL", "http://localhost:3000")
  APP_VERSION = "1.0.0"

  # STT runs locally — no key needed
  WHISPER_MODEL = "base"

Create a .env file at the project root:

  # Clicky for Animators — config
  # This file ships with the app. It contains no secrets.
  VERCEL_API_URL=https://your-project.vercel.app

Tell me what you changed.

---

## Step 4 — Build auth/supabase_auth.py

Build the full Supabase auth module. It needs to:

1. Sign up a new user with email + password
   POST to VERCEL_API_URL/api/auth/signup
   Returns JWT on success

2. Sign in an existing user with email + password
   POST to VERCEL_API_URL/api/auth/signin
   Returns JWT on success

3. Store the JWT in Windows Credential Manager
   Use the `keyring` library:
     keyring.set_password("clicky-animator", "jwt", token)

4. Load the JWT from Windows Credential Manager
     keyring.get_password("clicky-animator", "jwt")

5. Clear the JWT on sign out
     keyring.delete_password("clicky-animator", "jwt")

6. Check if a valid JWT exists on startup
   Returns True/False

Use httpx for async HTTP calls.
Handle errors gracefully — network failures, wrong password, etc.
Return clear error messages the UI can display.

Tell me when done and show me the full file.

---

## Step 5 — Build api/vercel_client.py

Build the async Vercel API client. It needs to:

1. send_chat_request(transcript, screenshot_base64, session_id)
   POST to /api/chat with JWT Bearer token
   Stream the response text back token by token
   Parse remaining_uses from the response headers or body
   If response contains { "error": "paywall" } — raise PaywallError
   If response is 401 — raise AuthError

2. get_tts_audio(text)
   POST to /api/tts with JWT Bearer token
   Returns audio bytes

3. get_status()
   GET /api/status with JWT Bearer token
   Returns { subscription_status, remaining_uses, is_paid }

4. get_version()
   GET /api/version (no auth needed)
   Returns version string

Define these custom exceptions at the top:
  class PaywallError(Exception): pass
  class AuthError(Exception): pass
  class NetworkError(Exception): pass

Use httpx for async streaming.
All methods should be async.
Add the JWT from supabase_auth.py to every request automatically.

Tell me when done and show me the full file.

---

## Step 6 — Update companion_manager.py

Update CompanionManager to use the new Vercel client instead of
calling any AI provider directly.

Changes:
1. Import vercel_client instead of any AI provider
2. Replace the AI call with vercel_client.send_chat_request()
3. Stream the response tokens and update the UI as they arrive
4. After each response, update the usage counter in the panel UI
   by firing a signal: usage_updated = pyqtSignal(int, int)
   (remaining_uses, total_limit)
5. Catch PaywallError → fire signal: paywall_triggered = pyqtSignal()
6. Catch AuthError → fire signal: auth_required = pyqtSignal()

Do NOT change any audio, screen capture, or overlay logic.
Only change the part that calls the AI.

Tell me exactly which lines changed.

---

## Step 7 — Build ui/auth_screen.py

Build the auth screen as a PyQt6 QWidget. It shows three states:

State 1 — Welcome (first launch)
  "welcome to clicky 🎨"
  "made for animators"
  [ get started ] button → switches to State 2

State 2 — Sign up
  "create your account"
  Email input field
  Password input field
  [ create account ] button → calls supabase_auth.signup()
  "already have an account? sign in" link → switches to State 3
  Error message label (hidden until error)

State 3 — Sign in
  "welcome back"
  Email input field
  Password input field
  [ sign in ] button → calls supabase_auth.signin()
  "no account yet? sign up" link → switches to State 2
  Error message label (hidden until error)

On successful auth in either state:
  Emit signal: auth_complete = pyqtSignal()
  CompanionManager listens for this and starts the main app

Design: dark background #0a0a0a, white text, blue accent #4a9eff,
Inter font, lowercase labels, clean and minimal.

Tell me when done.

---

## Step 8 — Build ui/paywall_screen.py

Build the paywall screen as a PyQt6 QWidget. Shows when
CompanionManager fires the paywall_triggered signal.

Content:
  "you've used your 10 free sessions"
  ""
  "clicky for animators"
  "$10 / month"
  ""
  "✓ unlimited sessions"
  "✓ sees your screen in real time"
  "✓ works with maya, ae, blender + more"
  "✓ answers in your voice"
  ""
  [ subscribe — $10/month ] button
    → opens Stripe Checkout URL in browser
    → starts polling vercel_client.get_status() every 5 seconds
    → when status = "active" → emit subscription_activated signal
    → stop polling after 2 minutes if no activation

  "already subscribed? sign in again" link
    → shows sign in screen

Design: same dark theme as auth screen.

Tell me when done.

---

## Step 9 — Update ui/panel.py

Add a usage counter to the panel. It should show:

When user has free uses remaining:
  "7 of 10 free sessions left"
  Small progress bar or dots showing usage

When user is paid:
  Just show nothing (or a small "✓ subscribed" in tiny text)

The panel listens for the usage_updated signal from CompanionManager
and updates this display whenever it fires.

Do not change any other panel logic.

Tell me what you changed.

---

## Step 10 — Update ui/tray.py

Clean up the tray menu to match AGENTS.md.

Keep:
  Show / Hide Panel
  Tutor Mode submenu (Slow Mode, Quiz Mode)
  Account → Sign Out option
  Quit

Remove:
  Any provider switcher
  Any API key input
  HIPAA mode
  GitHub Copilot login
  Any cloud provider toggle

Add:
  Account submenu with:
    email display (greyed out, not clickable)
    Sign Out → clears JWT, shows auth screen

Tell me what you removed and what you kept.

---

## Step 11 — Update main.py

Update the boot sequence:

1. App starts
2. Check for update via updater.py (async, does not block boot)
3. Check if JWT exists via supabase_auth.load_jwt()
4. If NO JWT → show auth_screen
5. If JWT exists → skip auth, go straight to main companion
6. Wire auth_complete signal → dismiss auth screen, start companion
7. Wire paywall_triggered signal → show paywall screen
8. Wire auth_required signal → show sign in screen

Tell me the new boot sequence.

---

## Step 12 — Build the Vercel backend

Build the TypeScript Vercel backend files.

### backend/lib/supabase.ts
  Import createClient from @supabase/supabase-js
  Export supabaseAdmin using SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY

### backend/lib/auth.ts
  Export verifyJWT(req) function
  Verifies the Bearer token in the Authorization header
  Returns { user_id } or throws 401 error

### backend/lib/usage.ts
  Export getUsage(user_id) function
  Counts rows in usage_logs for this user
  Checks subscriptions table for active subscription
  Returns { count, limit: 10, remaining, is_paid }

### backend/api/auth/signup.ts
  POST handler
  Accepts { email, password }
  Creates Supabase user
  Returns { jwt }

### backend/api/auth/signin.ts
  POST handler
  Accepts { email, password }
  Signs in Supabase user
  Returns { jwt }

### backend/api/chat.ts
  POST handler — this is the main one
  1. Verify JWT → get user_id
  2. Get usage for user_id
  3. If not paid AND count >= 10 → return { error: "paywall" }
  4. Call Kimi K2.5 via Vercel AI Gateway:
     model: "moonshotai/kimi-k2.5"
     messages: [{ role: "user", content: [
       { type: "text", text: transcript },
       { type: "image_url", image_url: { url: "data:image/jpeg;base64," + screenshot_base64 }}
     ]}]
     system: the animation mentor prompt (copy from AGENTS.md overview)
     stream: true
  5. Log to usage_logs table
  6. Stream response back with remaining_uses in header

### backend/api/tts.ts
  POST handler
  Accepts { text }
  Verify JWT
  Call ElevenLabs API with ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID
  Return audio buffer

### backend/api/status.ts
  GET handler
  Verify JWT
  Return { subscription_status, remaining_uses, is_paid }

### backend/api/webhooks/stripe.ts
  POST handler — no auth, uses Stripe webhook signature verification
  Handle these events:
    customer.subscription.created → status = "active"
    customer.subscription.updated → update status
    customer.subscription.deleted → status = "cancelled"
    invoice.payment_failed → status = "past_due"
  Update subscriptions table in Supabase for each event

### backend/api/version.ts
  GET handler — no auth needed
  Return { version: "1.0.0" }

### backend/vercel.json
  {
    "rewrites": [{ "source": "/api/(.*)", "destination": "/api/$1" }]
  }

### backend/package.json
  Dependencies needed:
    @supabase/supabase-js
    @vercel/ai
    stripe
    ai

Tell me when all backend files are built.

---

## Step 13 — Build update/updater.py

Simple PyUpdater client:

1. On startup, GET /api/version from Vercel
2. Compare to APP_VERSION in config.py
3. If newer version exists:
   - Download update silently in background
   - Show Windows tray notification:
     "Clicky update ready — restart to apply"
4. If same version — do nothing

Use PyUpdater library if available, or implement manually with
requests + a simple version check.

Tell me when done.

---

## Step 14 — Update requirements.txt

Make sure these are in requirements.txt:
  pyqt6
  httpx
  faster-whisper
  sounddevice
  keyring
  python-dotenv
  pyupdater (or equivalent)
  pyinstaller

Remove any packages only used by providers we removed:
  elevenlabs SDK (we call ElevenLabs through Vercel now)
  anthropic
  openai
  google-generativeai
  deepgram-sdk

Tell me what you added and removed.

---

## Step 15 — Final check

After all steps are done tell me:

1. Every file that was created or changed
2. The exact command to build the .exe
3. What goes in the zip for animators
4. What environment variables need to be set in Vercel dashboard
5. What to test manually before sharing with animators
6. Any known issues

Then update AGENTS.md:
- Update Key Files line counts if any changed by 50+ lines
- Add any new decisions made during this build to Code Style section
- Do not rewrite AGENTS.md from scratch — only update what changed

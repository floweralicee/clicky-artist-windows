# Clicky for Animators (Windows) — Agent Instructions

## Overview

Windows desktop companion app for animation artists. Lives in the Windows
system tray (no taskbar icon, no main window). A blue cursor dot floats
beside the user's real cursor at all times. Hold Ctrl+Alt+Space to
push-to-talk — Clicky captures your screen, transcribes voice locally
via Faster-Whisper, sends the transcript + screenshot to Kimi K2.5 via
Vercel AI Gateway, and speaks the response through ElevenLabs TTS. A
blue dot flies to and points at UI elements Clicky references on screen.

Users get 10 free sessions. After that they pay $10/month via Stripe.
All business logic (usage counting, paywall, auth checking) lives on
the Vercel backend — not in the app. The app is a thin shell that
records, sends, and plays back. This means pricing and features can
be changed server-side without an app update.

Auth: email + password via Supabase. No Google login. No API keys
exposed to users. Auto-update via PyUpdater so animators always have
the latest version without re-downloading.

Landing page: floweralice.me/clicky
Download: floweralice.me/clicky/download/clicky-windows-artists.zip
Target users: US-based animation artists using Maya, After Effects,
Blender, Toon Boom Harmony, Premiere Pro, DaVinci Resolve, Nuke.

## Architecture

* **App type**: System tray app, no taskbar icon, no main window
* **Framework**: Python + PyQt6 with async/await throughout
* **Pattern**: Central CompanionManager state machine, PyQt6 signals
  for all cross-thread UI updates
* **AI**: Kimi K2.5 (moonshotai/kimi-k2.5) via Vercel AI Gateway —
  native multimodal, reads screenshots accurately, streams responses
* **Speech-to-text**: Faster-Whisper (local, free, no key) — base model
* **Text-to-speech**: ElevenLabs API — voice ID stored in Vercel env vars,
  never exposed in the app binary
* **Screen capture**: Multi-monitor JPEG via Qt desktopCapturer,
  physical px + DPI metadata per monitor
* **Voice input**: Push-to-talk via Ctrl+Alt+Space global hotkey.
  Always-on ambient listener with "clicky" wake word as alternative.
* **Element pointing**: Two-stage grid locator. Stage 1 draws a 12×8
  numbered grid on the screenshot, Kimi picks the cell. Stage 2 zooms
  into a 3×3 area around that cell and runs a 6×6 fine-grid pass.
  Bezier arc flight to target with pulsing highlight ring and speech
  bubble label.
* **Auth**: Supabase email + password. JWT stored in Windows Credential
  Manager. Sent as Bearer token with every request to Vercel backend.
* **Usage counting**: Tracked in Supabase usage_logs table server-side.
  App receives remaining count in every API response.
* **Paywall**: Enforced in Vercel backend. App shows paywall screen when
  backend returns { error: "paywall" }.
* **Payment**: Stripe Checkout, $10/month subscription. Stripe webhook
  updates Supabase subscriptions table on payment events.
* **Auto-update**: PyUpdater checks Vercel /version endpoint on startup.
  Downloads and applies updates silently in background.
* **Concurrency**: asyncio with PyQt6 signals for all UI updates from
  async threads. Never call widget methods directly from threads.

### Request Flow

Every push-to-talk request:

  App captures screenshot + transcribes voice (local)
      │
      ▼
  POST /api/chat (Vercel backend)
  Headers: Authorization: Bearer <supabase_jwt>
  Body: { transcript, screenshot_base64, session_id }
      │
      ▼
  Vercel backend:
  1. Verify JWT with Supabase
  2. Count usage_logs for this user
  3a. Under 10 uses AND no subscription → log use, call Kimi, return response
  3b. Active Stripe subscription → log use, call Kimi, return response
  3c. 10 uses used AND no subscription → return { error: "paywall" }
      │
      ▼
  Kimi K2.5 via Vercel AI Gateway (moonshotai/kimi-k2.5)
  Streaming response
      │
      ▼
  Vercel streams text back to app
      │
      ▼
  App sends text to ElevenLabs TTS (via Vercel /api/tts proxy)
      │
      ▼
  App plays audio + flies cursor dot to referenced UI element

### Auth Flow

  First launch → show welcome screen
      │
      ▼
  Sign up (email + password) or Sign in
      │
      ▼
  Supabase returns JWT
      │
      ▼
  Store JWT in Windows Credential Manager
      │
      ▼
  All subsequent requests send JWT as Bearer token
  JWT refreshed automatically before expiry

### Paywall Flow

  Backend returns { error: "paywall", uses: 10, limit: 10 }
      │
      ▼
  App shows paywall screen with Stripe Checkout link
      │
      ▼
  Stripe Checkout opens in browser
      │
      ▼
  Payment → Stripe webhook → POST /api/webhooks/stripe (Vercel)
      │
      ▼
  Vercel updates subscriptions table in Supabase
  status = "active"
      │
      ▼
  App polls /api/status every 5 seconds for up to 2 minutes
  When status = "active" → dismiss paywall → resume normally

### Supabase Schema

  -- Supabase Auth handles users table automatically

  create table usage_logs (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id),
    created_at timestamp default now(),
    request_type text  -- "vision" or "text"
  );

  create table subscriptions (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id),
    stripe_customer_id text,
    stripe_subscription_id text,
    status text,  -- "active", "cancelled", "past_due"
    created_at timestamp default now(),
    updated_at timestamp default now()
  );

### Vercel Backend Routes

  POST /api/chat          — main AI request (auth required)
  POST /api/tts           — ElevenLabs proxy (auth required)
  POST /api/auth/signup   — create Supabase account
  POST /api/auth/signin   — sign in, return JWT
  GET  /api/status        — check subscription + usage status
  POST /api/checkout      — create Stripe Checkout session
  POST /api/webhooks/stripe — Stripe webhook handler
  GET  /api/version       — latest app version for auto-update

### Environment Variables (Vercel, never in app)

  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  AI_GATEWAY_API_KEY        (Vercel AI Gateway key)
  ELEVENLABS_API_KEY
  ELEVENLABS_VOICE_ID
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  STRIPE_PRICE_ID           ($10/month price ID)

## Key Files

### App (Python/PyQt6)

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~120 | Entry point. Boots PyQt6 app, creates CompanionManager, wires all signals, starts event loop. Initialises PyUpdater check on startup. |
| `companion_manager.py` | ~800 | Central async state machine. Owns STT, screen capture, Vercel API calls, ElevenLabs TTS, and overlay management. Tracks voice state and conversation history. Receives usage count from every API response and updates UI. |
| `config.py` | ~60 | Loads .env. Contains only VERCEL_API_URL and APP_VERSION. No API keys. |
| `tutor.py` | ~300 | Query classifier and system prompt builder. Animation-specific prompt. Detects query type (locate, explain, multi-step). Privacy guard skips screenshot for sensitive windows. |
| `hotkey.py` | ~60 | Global Ctrl+Alt+Space hotkey. Publishes press/release events to CompanionManager. Also handles Esc to cancel. |
| `auth/supabase_auth.py` | ~150 | Supabase email+password signup and signin. Stores JWT in Windows Credential Manager. Refreshes JWT before expiry. Returns auth headers for all API calls. |
| `api/vercel_client.py` | ~200 | Async client for all Vercel backend routes. Sends JWT with every request. Handles streaming from /api/chat. Parses { error: "paywall" } and fires paywall signal. Parses remaining_uses from response and fires usage_updated signal. |
| `audio/stt/faster_whisper_stt.py` | ~100 | Local STT via Faster-Whisper. Buffers push-to-talk audio, transcribes on key-up. Model size: base. No API key. |
| `audio/tts/vercel_tts_provider.py` | ~15 | TTS provider shim. Requests audio from the Vercel /api/tts proxy and plays it locally so ElevenLabs keys never ship in the app. |
| `audio/capture.py` | ~80 | PCM audio capture from default microphone via sounddevice. |
| `audio/playback.py` | ~60 | Cancellable audio playback. Uses threading.Event so Esc can stop TTS mid-sentence. |
| `screen/capture.py` | ~90 | Multi-monitor JPEG capture with DPI metadata. Returns one image per monitor with origin coordinates. |
| `ai/element_locator.py` | ~200 | Two-stage grid locator. Draws grids on screenshots, calls Kimi K2.5 to identify cells, converts grid coords to physical screen pixels with DPI correction. |
| `ui/overlay.py` | ~400 | Full-screen transparent click-through PyQt6 window. Hosts the blue cursor dot, bezier arc flight, highlight ring, speech bubble, waveform bars, and spinner. |
| `ui/panel.py` | ~250 | Floating companion panel. Shows status, usage counter ("3 of 10 free sessions left"), and current response. No API key fields. |
| `ui/tray.py` | ~150 | System tray icon and right-click menu. Menu: Show/Hide Panel, Tutor Mode submenu, Account, Quit. |
| `ui/auth_screen.py` | ~200 | Welcome, sign up, and sign in screens. Email + password fields. No Google login. Shows on first launch or when JWT is missing/expired. |
| `ui/paywall_screen.py` | ~150 | Shown when backend returns { error: "paywall" }. Displays $10/month offer, opens Stripe Checkout in browser, polls /api/status until subscription activates. |
| `ui/design.py` | ~60 | Shared colours, fonts, and constants for all UI. |
| `update/updater.py` | ~100 | PyUpdater client. Checks /api/version on startup. Downloads and applies updates silently. Notifies user via tray notification when update is ready. |
| `.env` | ~5 | Contains only VERCEL_API_URL. No secrets. Ships with the app. |
| `clicky.spec` | ~40 | PyInstaller build spec. Produces dist/Clicky/Clicky.exe. |

### Vercel Backend (TypeScript, separate repo or /backend folder)

| File | Lines | Purpose |
|------|-------|---------|
| `api/chat.ts` | ~150 | Main AI endpoint. Verifies JWT, checks usage, calls Kimi K2.5 via Vercel AI Gateway, streams response, logs usage to Supabase. |
| `api/tts.ts` | ~80 | ElevenLabs proxy. Verifies JWT, calls ElevenLabs, returns audio. |
| `api/auth/signup.ts` | ~60 | Creates Supabase account with email + password. |
| `api/auth/signin.ts` | ~60 | Signs in, returns Supabase JWT. |
| `api/status.ts` | ~60 | Returns user's subscription status and remaining free uses. |
| `api/checkout.ts` | ~40 | Creates an authenticated Stripe Checkout session for the $10/month subscription. |
| `api/webhooks/stripe.ts` | ~100 | Handles Stripe webhook events. Updates subscriptions table in Supabase on payment success, cancellation, or failure. |
| `api/version.ts` | ~30 | Returns latest app version string for PyUpdater. |
| `lib/supabase.ts` | ~30 | Supabase admin client initialised with service role key. |
| `lib/auth.ts` | ~50 | JWT verification helper. Used by all protected routes. |
| `lib/usage.ts` | ~60 | Counts usage_logs for a user. Returns { count, limit, remaining, is_paid }. |

## Build & Run

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run app in development (needs VERCEL_API_URL in .env)
python main.py

# Build .exe (run on Windows)
pip install pyinstaller
pyinstaller clicky.spec --clean --noconfirm
# Output: dist/Clicky/Clicky.exe

# Run Vercel backend locally
cd backend
npm install
vercel dev

# Deploy Vercel backend
vercel deploy --prod
```

## What ships to animators

```
clicky-windows-artists.zip   ← upload to floweralice.me/clicky/download/
  Clicky/
    Clicky.exe               ← built by PyInstaller
    _internal/               ← bundled Python + libraries
    .env                     ← contains only VERCEL_API_URL, no secrets
    HOW-TO-USE.txt           ← English setup guide
    HOW-TO-USE-中文.txt      ← Chinese setup guide
```

`build.bat` creates `clicky-windows-artists.zip` automatically after each build.

Upload zip to: floweralice.me/clicky/download/clicky-windows-artists.zip

.env contents (safe to ship, no secrets):
  VERCEL_API_URL=https://your-project.vercel.app

## Code Style & Conventions

### Naming

* Be as clear and specific with variable and method names as possible
* Optimize for clarity over concision — a developer with zero context
  should understand what a variable does just from its name
* No single-character names. No abbreviations unless industry standard.
* Example: use `remainingFreeSessionCount` not `count` or `rem`
* When passing arguments, keep the same name as the original variable

### Code Clarity

* Clear is better than clever. More lines is fine if it aids understanding.
* Every non-obvious block should have a comment explaining WHY not what
* Anyone reading this code should understand it with zero prior context

### Python / PyQt6 Conventions

* All UI updates from async code must go through PyQt6 signals —
  never call widget methods directly from threads or async tasks
* Use async/await for all I/O operations (Vercel API, ElevenLabs, files)
* Type hints on all new functions
* One concern per file — auth, API client, UI, audio each in own files

### Security Rules

* NEVER put API keys in the app binary or .env file that ships with app
* NEVER call Kimi or ElevenLabs directly from the app — always via Vercel
* NEVER log JWTs or auth tokens anywhere
* NEVER trust usage counts from the app — always enforce server-side
* The Vercel backend is the single source of truth for who can use what

### Do NOT

* Do not add any direct AI provider calls from the app (no Kimi, no
  ElevenLabs called directly — always proxied through Vercel)
* Do not add Google login or any OAuth — email + password only
* Do not put any secrets in .env that ships with the app
* Do not add features beyond what was asked
* Do not refactor upstream code that was not asked to change
* Do not add analytics or tracking without explicit request

## Git Workflow

* Branch naming: `feature/description` or `fix/description`
* Commit messages: imperative mood, explain the why not the what
* Do not force-push to main
* Backend and app can be in same repo under /app and /backend folders

## Self-Update Instructions

When you make changes that affect the information in this file,
update this file to reflect those changes. Specifically:

1. **New files**: Add to Key Files table with purpose and line count
2. **Deleted files**: Remove from Key Files table
3. **New routes**: Add to Vercel Backend Routes section
4. **Schema changes**: Update Supabase Schema section
5. **Architecture changes**: Update Architecture section
6. **New env vars**: Add to Environment Variables section
7. **Line count drift**: Update if a file changes by more than 50 lines

Do NOT update this file for minor bug fixes or changes that do not
affect the documented architecture, schema, or conventions.

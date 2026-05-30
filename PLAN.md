# Clicky for Animators — Windows Build Plan

## What this is
A custom fork of Bitshank-2338/clicky-windows built for animation artists.
Runs as a thin Windows tray app: local voice capture and screen capture,
with AI, auth, usage limits, payment, and TTS handled by the Vercel backend.

Landing page: floweralice.me/clicky
Download link: floweralice.me/download/clicky.zip

## Target users
- Animation students and professionals
- Software: Maya, After Effects, Blender, Toon Boom Harmony,
  Premiere Pro, DaVinci Resolve, Nuke
- US-based animation artists — no Google login, email + password only
- Non-technical users — they follow a video, not written instructions
- They should never see API keys, config files, or terminals

## Tech stack
| Layer | Choice |
|-------|--------|
| App | Python + PyQt6 (from upstream Bitshank fork) |
| AI | Vercel AI Gateway + Kimi K2.5 |
| STT | Faster-Whisper — local speech-to-text, free |
| TTS | ElevenLabs through the Vercel backend |
| Auth + usage | Supabase |
| Payments | Stripe Checkout + Stripe webhooks |
| Auto-update | PyUpdater |

---

## Changes from upstream

### CHANGE 1 — Route AI through Vercel AI Gateway + Kimi K2.5
File: config.py

Remove the priority chain: Claude → OpenAI → Copilot → Gemini → Ollama.
Replace with VERCEL_API_URL as the only app-side AI endpoint.

Values to hardcode:
  VERCEL_API_URL = "https://your-project.vercel.app"
  APP_VERSION = "1.0.0"
  WHISPER_MODEL = "base"

The app never stores Kimi or Vercel AI Gateway keys. If the backend is
unreachable, show the error gently in the UI panel.

---

### CHANGE 2 — Route TTS through ElevenLabs on Vercel
File: config.py and audio/tts/ provider chain

Remove direct ElevenLabs and OpenAI TTS calls from the app.
Use the Vercel /api/tts route as the only TTS provider.
The ElevenLabs API key and voice ID live in Vercel env vars only.

Default voice: configured by ELEVENLABS_VOICE_ID in Vercel.

---

### CHANGE 3 — Lock STT to Faster-Whisper only
File: config.py and audio/stt/ provider chain

Remove Deepgram and OpenAI Whisper from the provider list.
Use Faster-Whisper as the only STT provider.
Faster-Whisper runs locally, requires no key.

Model size: "base" — fast enough, small download, works on most machines.

---

### CHANGE 4 — Animation-focused system prompt
File: tutor.py (or wherever the main system prompt is built)

Replace the generic tutor prompt with:

  "You are an animation mentor and teacher. You help professional
  animators and animation students with software including Maya,
  After Effects, Blender, Toon Boom Harmony, Premiere Pro,
  DaVinci Resolve, and Nuke. You can see the animator's screen.
  When they ask about something on screen, describe exactly what
  you see and give clear, step-by-step instructions. Use animation
  industry terminology correctly. Keep answers concise — animators
  are busy and on deadline. When pointing at UI elements, be precise."

---

### CHANGE 5 — Remove API key UI from tray menu
File: ui/tray.py

Remove from tray menu:
- Provider switcher (Claude / OpenAI / Copilot / Gemini options)
- Any item that opens an API key input
- HIPAA mode toggle
- GitHub Copilot login option

Keep in tray menu:
- Show / Hide Panel
- Tutor Mode submenu (Slow Mode and Quiz Mode are useful for animators)
- Account submenu with email display and Sign Out
- Quit

---

### CHANGE 6 — Add Supabase email + password auth
Files: auth/supabase_auth.py, ui/auth_screen.py, main.py

First launch shows a welcome screen, then sign up or sign in.
JWTs are stored in Windows Credential Manager and sent as Bearer tokens
to every protected Vercel backend route.

No Google login. No OAuth. No API keys exposed to users.

---

### CHANGE 7 — Add usage limit and paywall
Files: api/vercel_client.py, ui/paywall_screen.py, ui/panel.py, backend/api/*

Users get 10 free sessions. Usage is counted on the Vercel backend
in Supabase, not trusted from the app.

When the backend returns { error: "paywall" }, show the paywall screen:
  "$10 / month"
  "unlimited sessions"
  "subscribe — $10/month"

Stripe Checkout opens in the browser. Stripe webhooks update Supabase.
The app polls /api/status until the subscription becomes active.

---

### CHANGE 8 — Add Vercel backend
Files: backend/api/* and backend/lib/*

Add these routes:
  POST /api/chat
  POST /api/tts
  POST /api/auth/signup
  POST /api/auth/signin
  GET /api/status
  POST /api/checkout
  POST /api/webhooks/stripe
  GET /api/version

The backend verifies Supabase JWTs, enforces usage limits, calls Kimi
K2.5 through Vercel AI Gateway, proxies ElevenLabs TTS, handles Stripe
webhooks, and exposes the latest app version.

---

### CHANGE 9 — Add auto-update
Files: update/updater.py, main.py

On startup, check /api/version in the background.
If a newer version exists, download it silently and show a tray
notification when the update is ready.

---

### CHANGE 10 — Update branding
Files: ui/tray.py, ui/panel.py, main.py

- App window title: "Clicky for Animators"
- Tray icon tooltip: "Clicky for Animators — hold Ctrl+Alt+Space to ask"
- Panel header text: "clicky 🎨"
- About text: "AI animation mentor · floweralice.me/clicky"

---

### CHANGE 11 — Pre-filled .env file
File: .env (create at project root)

Create this file and include it in the final zip alongside Clicky.exe.
Animators never need to create or edit this.

Contents:
  VERCEL_API_URL=https://your-project.vercel.app
  WHISPER_MODEL=base

---

## How to build the .exe

Run these commands on a Windows machine:

  pip install pyinstaller
  pip install -r requirements.txt
  pyinstaller clicky.spec --clean --noconfirm

Output will be in: dist/Clicky/

Deploy the backend before sharing the zip:

  cd backend
  npm install
  vercel deploy --prod

---

## What to put in the zip for animators

  Clicky-for-Animators/
    Clicky.exe       ← the app
    .env             ← pre-filled config, do not delete
    README.txt       ← two lines only (see below)

README.txt contents:
  1. watch the setup video at floweralice.me/clicky
  2. double-click Clicky.exe

That is all the animator needs to read.

---

## What the setup video should cover

Keep it under 5 minutes. Show each step on screen.

Part 1 — Create an account (1 min)
  - Open Clicky
  - Sign up with email + password
  - No Google login, no API keys

Part 2 — Install Clicky (1 min)
  - Go to floweralice.me/clicky
  - Click download, unzip the folder
  - Double-click Clicky.exe
  - Show the blue dot appearing in the system tray

Part 3 — Use it (3 min)
  - Open Maya or After Effects
  - Hold Ctrl+Alt+Space, ask a question about what's on screen
  - Show Clicky pointing at the thing and explaining it

---

## How to distribute

Host the zip at: floweralice.me/download/clicky.zip
Link from the landing page download button.

Deploy the Vercel backend first, then put its URL in the shipped .env.
Make sure the zip is hosted on your own server or Cloudflare Pages,
not Google Drive.

---

## Version log

| Version | Date | What changed |
|---------|------|-------------|
| v1.0 | TBD | Windows tray companion for animators with local Faster-Whisper STT, Kimi K2.5 via Vercel AI Gateway, ElevenLabs TTS through Vercel, Supabase auth and usage tracking, Stripe paywall, and PyUpdater auto-update |

---

## Known limitations
- Requires internet access for auth, AI, TTS, payment, and update checks
- Intel Macs not supported (this is Windows only)
- First response can be slower if the backend or AI gateway is cold

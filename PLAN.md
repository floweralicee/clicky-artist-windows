# Clicky for Animators — Windows Build Plan

## What this is
A custom fork of Bitshank-2338/clicky-windows built for animation artists.
Runs 100% offline using Ollama. No API keys, no accounts, no internet required
after the one-time model download.

Landing page: floweralice.me/clicky
Download link: floweralice.me/download/clicky.zip

## Target users
- Animation students and professionals
- Software: Maya, After Effects, Blender, Toon Boom Harmony,
  Premiere Pro, DaVinci Resolve, Nuke
- Many users are in China — must work without Google or any cloud service
- Non-technical users — they follow a video, not written instructions
- They should never see API keys, config files, or terminals

## Tech stack
- Python + PyQt6 (from upstream Bitshank fork)
- Ollama — local AI, completely free, no account
- Faster-Whisper — local speech-to-text, free
- Edge TTS — free text-to-speech, 400+ voices, excellent Chinese support

---

## Changes from upstream

### CHANGE 1 — Lock AI provider to Ollama only
File: config.py

Remove the priority chain: Claude → OpenAI → Copilot → Gemini → Ollama
Replace with Ollama hardcoded as the only option.

Values to hardcode:
  CLICKY_ACTIVE_LLM = "ollama"
  OLLAMA_HOST = "http://localhost:11434"
  OLLAMA_VISION_MODEL = "qwen2-vl:7b"
  OLLAMA_TEXT_MODEL = "qwen2.5-coder:7b"

If Ollama is not running, show this message in the UI panel:
  "clicky needs ollama to run.
   visit floweralice.me/clicky for setup instructions."
Do not crash. Do not show a Python error. Show this message gently.

---

### CHANGE 2 — Lock TTS to Edge TTS only
File: config.py and audio/tts/ provider chain

Remove ElevenLabs and OpenAI TTS from the provider list.
Use Edge TTS as the only TTS provider.
Edge TTS is free, requires no key, and has Chinese voices built in.

Default voice: en-US-AvaNeural
Chinese voice (auto-switched when Chinese detected): zh-CN-XiaoxiaoNeural

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
- Quit

---

### CHANGE 6 — Update branding
Files: ui/tray.py, ui/panel.py, main.py

- App window title: "Clicky for Animators"
- Tray icon tooltip: "Clicky for Animators — hold Ctrl+Alt+Space to ask"
- Panel header text: "clicky 🎨"
- About text: "AI animation mentor · floweralice.me/clicky"

---

### CHANGE 7 — Pre-filled .env file
File: .env (create at project root)

Create this file and include it in the final zip alongside Clicky.exe.
Animators never need to create or edit this.

Contents:
  CLICKY_ACTIVE_LLM=ollama
  OLLAMA_HOST=http://localhost:11434
  OLLAMA_VISION_MODEL=qwen2-vl:7b
  OLLAMA_TEXT_MODEL=qwen2.5-coder:7b
  CLICKY_STT=faster_whisper
  WHISPER_MODEL=base

---

## How to build the .exe

Run these commands on a Windows machine:

  pip install pyinstaller
  pip install -r requirements.txt
  pyinstaller clicky.spec --clean --noconfirm

Output will be in: dist/Clicky/

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

Keep it under 10 minutes. Show each step on screen.

Part 1 — Install Ollama (3 min)
  - Go to ollama.com, click Download
  - Run the installer
  - Open cmd, paste: ollama pull qwen2-vl:7b
  - Show it downloading, tell them to wait

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

For China users: make sure the zip is hosted on your own server
or Cloudflare Pages — not Google Drive (blocked in China).

---

## Version log

| Version | Date | What changed |
|---------|------|-------------|
| v1.0 | TBD | Initial animator edition |

---

## Known limitations
- Ollama requires a one-time 5GB model download
- Needs 16GB RAM for best performance (8GB works but slower)
- Intel Macs not supported (this is Windows only)
- First response after launching is slower while model loads into memory
- Does not auto-update — share a new zip when there is a new version

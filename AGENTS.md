# Clicky for Animators (Windows) — Agent Instructions

## Overview

Windows desktop companion app for animation artists. Lives in the Windows
system tray (no taskbar icon, no main window). A blue cursor dot floats
beside the user's real cursor at all times. Hold Ctrl+Alt+Space to push-to-talk
— Clicky captures your screen, transcribes your voice locally via
Faster-Whisper, sends the transcript + screenshot to a local Ollama vision
model, and speaks the response through Edge TTS. A blue dot flies to and
points at UI elements Clicky references on screen.

No API keys. No accounts. No internet required after the one-time model
download. Built for animators using Maya, After Effects, Blender, Toon Boom
Harmony, Premiere Pro, DaVinci Resolve, and Nuke.

This is a fork of Bitshank-2338/clicky-windows, stripped down and
retuned for animation artists. Distribution: floweralice.me/clicky

## Architecture

* **App Type**: System tray app, no taskbar icon, no main window
* **Framework**: Python + PyQt6 with async/await throughout
* **Pattern**: Central CompanionManager state machine, signals for
  all cross-thread UI updates
* **AI**: Ollama (local, free) — vision model for screen-aware queries,
  text model for Code Mode and journal Q&A
* **Speech-to-Text**: Faster-Whisper (local, free, no key) — base model
* **Text-to-Speech**: Edge TTS (free, no key, 400+ voices including
  Chinese) — default en-US-AvaNeural, auto-switches to
  zh-CN-XiaoxiaoNeural when Chinese is detected
* **Screen Capture**: multi-monitor JPEG via Qt desktopCapturer,
  physical px + DPI metadata per monitor
* **Voice Input**: Push-to-talk via Ctrl+Alt+Space global hotkey.
  Always-on ambient listener with "clicky" wake word as alternative.
* **Element Pointing**: Two-stage grid locator. Stage 1 draws a 12×8
  numbered grid on the screenshot, Ollama picks the cell. Stage 2 zooms
  into a 3×3 area around that cell and runs a 6×6 fine-grid pass for
  sub-cell precision. Bezier arc flight to target with pulsing highlight
  ring and speech bubble label.
* **Concurrency**: asyncio with PyQt6 signals for all UI updates from
  async threads. Never call widget methods directly from threads.

### Provider Chain (simplified from upstream)

This fork removes all cloud providers. There is no fallback to Claude,
OpenAI, Gemini, or GitHub Copilot. Ollama is the only LLM provider.

| Component | Provider | Key needed |
|-----------|----------|------------|
| LLM | Ollama (local) | None |
| STT | Faster-Whisper (local) | None |
| TTS | Edge TTS (free cloud) | None |

### Ollama Models

Two model slots are used:

| Slot | Model | Purpose |
|------|-------|---------|
| Vision | qwen2-vl:7b | Screen-aware queries, pointing, "what's on screen?" |
| Text | qwen2.5-coder:7b | Code Mode, journal Q&A |

If Ollama is not running when the app starts, show this message in the
panel UI — do not crash:
  "clicky needs ollama to run. visit floweralice.me/clicky for setup."

### State Flow

  IDLE
    → LISTENING (Ctrl+Alt+Space held)
    → PROCESSING (screenshot captured + sent to Ollama)
    → RESPONDING (Edge TTS playing + optional cursor pointing)
    → IDLE

### Coordinate Pipeline (Pixel-Perfect Pointing)

  Screenshot → JPEG (1280px max width, for Ollama token budget)
                  │
                  ▼
  Two-stage grid locator
  Stage 1: 12×8 grid overlay → Ollama picks cell number
  Stage 2: zoom 3×3 area → 6×6 fine grid → sub-cell (x, y)
                  │
                  ▼
  element_locator.py converts:
    grid coords → physical monitor pixels
               → + monitor origin (multi-monitor offset)
               → ÷ DPI scale (HiDPI correction)
               = logical screen pixels
                  │
                  ▼
  overlay.point_at(logical_x, logical_y) ← correct on any screen/DPI

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~300 | Entry point. Boots PyQt6 app, creates CompanionManager, wires all signals, starts event loop. |
| `companion_manager.py` | ~1110 | Central async state machine. Owns STT, screen capture, Ollama calls, TTS, and overlay management. Coordinates the full push-to-talk → screenshot → Ollama → TTS → pointing pipeline. Tracks voice state and conversation history. Builds animation system prompt via `_build_system_prompt()`. |
| `config.py` | ~115 | Loads .env, hardcodes Ollama / Faster-Whisper / Edge TTS. No cloud providers or API-key detection. |
| `tutor.py` | ~165 | Query classifier and privacy guard. Detects query type (locate, explain, multi-step). System prompt lives in `companion_manager._build_system_prompt()`. |
| `hotkey.py` | ~60 | Global Ctrl+Alt+Space hotkey. Publishes press/release events to CompanionManager. Also handles Esc to cancel. |
| `ai/ollama_provider.py` | ~130 | Ollama LLM client. Sends transcript + screenshot to local Ollama API with streaming. Handles vision and text-only modes. Exposes `OLLAMA_SETUP_MESSAGE` and `health_check()` for friendly offline errors. |
| `ai/element_locator.py` | ~200 | Two-stage grid locator. Draws grids on screenshots, calls Ollama to identify cells, converts grid coords to physical screen pixels with DPI correction. |
| `audio/stt/faster_whisper_stt.py` | ~100 | Local STT via Faster-Whisper. Buffers push-to-talk audio, transcribes on key-up. Model size: base. |
| `audio/tts/edge_tts_provider.py` | ~120 | Edge TTS client. Calls Microsoft Edge TTS (free, no key). Auto-switches voice to match detected language. Default: en-US-AvaNeural. Chinese: zh-CN-XiaoxiaoNeural. |
| `audio/capture.py` | ~80 | PCM audio capture from default microphone via sounddevice. |
| `audio/playback.py` | ~60 | Cancellable audio playback. Uses threading.Event so Esc can stop TTS mid-sentence. |
| `screen/capture.py` | ~90 | Multi-monitor JPEG capture with DPI metadata. Returns one image per monitor with origin coordinates. |
| `ui/overlay.py` | ~400 | Full-screen transparent click-through PyQt6 window. Hosts the blue cursor dot (spring-follows real cursor), bezier arc flight, highlight ring, speech bubble, waveform bars, and spinner. |
| `ui/panel.py` | ~390 | Floating companion panel. Shows Clicky status, push-to-talk instructions, Ollama setup message when server is down, and current model. No API key fields. |
| `ui/tray.py` | ~380 | System tray icon and right-click menu. Menu contains: Show/Hide Panel, Ollama model submenu, Tutor Mode, Journal, Quit. No provider switcher. No API key inputs. |
| `ui/design.py` | ~60 | Shared colours, fonts, and constants for all UI. |
| `tutor_features/journal.py` | ~200 | SQLite Q&A log at %LOCALAPPDATA%\Clicky\journal.db. SM-2 spaced repetition for review reminders. |
| `tutor_features/multilang.py` | ~100 | Language detection via langdetect. Auto-switches Edge TTS voice to match. Supports EN, ZH, JA, KO, FR, DE, ES, PT, RU, AR, HI. |
| `tutor_features/code_mode.py` | ~60 | Detects IDE window titles (VS Code, Cursor, etc.) and injects code-specialist prompt addendum. |
| `skills/__init__.py` | ~50 | Skill loader. Auto-loads .py files from %USERPROFILE%\.clicky\skills\ on startup. |
| `.env` | ~10 | Pre-filled config shipped with the app. Sets Ollama as provider, configures models. Animators never edit this. |
| `clicky.spec` | ~40 | PyInstaller build spec. Produces dist/Clicky/Clicky.exe. |
| `installer.iss` | ~80 | Inno Setup installer script. Produces Setup.exe for one-click install. |

## Build & Run

```
# Install dependencies
pip install -r requirements.txt

# Run in development
python main.py

# Build .exe (run on Windows)
pip install pyinstaller
pyinstaller clicky.spec --clean --noconfirm
# Output: dist/Clicky/Clicky.exe

# Build installer (requires Inno Setup installed on Windows)
# Open installer.iss in Inno Setup and click Build
# Output: Output/ClickySetup.exe
```

**Do NOT** hardcode API keys anywhere in the source. The .env file
ships with the app pre-filled — it contains only Ollama config,
no secrets.

## What to zip for distribution

```
Clicky-for-Animators/
  Clicky.exe      ← built by PyInstaller
  .env            ← pre-filled, ships with app, animators never touch
  README.txt      ← two lines only (watch video → run exe)
```

Upload zip to: floweralice.me/download/clicky.zip

## Code Style & Conventions

### Naming

* Be as clear and specific with variable and method names as possible
* Optimize for clarity over concision — a developer with zero context
  should understand what a variable does just from its name
* Use longer names when they improve clarity. No single-character names.
* Example: use `currentOllamaVisionModelName` not `model`
* When passing arguments, keep the same name as the original variable.
  If you have `capturedScreenshotData`, pass it as
  `capturedScreenshotData`, not `screenshot` or `data`

### Code Clarity

* Clear is better than clever. More lines is fine if it aids understanding.
* Every non-obvious block should have a comment explaining WHY,
  not just what
* Anyone reading this code should understand it with zero prior context

### Python / PyQt6 Conventions

* All UI updates from async code must go through PyQt6 signals —
  never call widget methods directly from threads or async tasks
* Use async/await for all I/O operations (Ollama, Edge TTS, file reads)
* Type hints encouraged on all new functions
* One provider per file in ai/, audio/stt/, audio/tts/
* New tutor features belong in tutor_features/ — one file per feature
* Pre-filled `.env` at project root is committed and shipped with the app —
  animators never create or edit it; `.env.local` is for developer overrides only

### Do NOT

* Do not add any cloud LLM provider (Claude, OpenAI, Gemini, Copilot)
* Do not add any UI that asks for an API key
* Do not add features beyond what was asked
* Do not refactor or rename upstream code that was not asked to change
* Do not add docstrings or comments to code you did not change
* Do not add analytics or tracking without explicit request

## Git Workflow

* Branch naming: `feature/description` or `fix/description`
* Commit messages: imperative mood, explain the why not the what
* Do not force-push to main

## Self-Update Instructions

When you make changes that affect the information in this file,
update this file to reflect those changes. Specifically:

1. **New files**: Add to the Key Files table with purpose and
   approximate line count
2. **Deleted files**: Remove from the Key Files table
3. **Architecture changes**: Update the Architecture section if
   you add new patterns, providers, or structural changes
4. **Build changes**: Update build commands if the process changes
5. **New conventions**: Add any new coding convention the maintainer
   establishes to the Code Style section
6. **Line count drift**: Update line counts if a file changes by
   more than 50 lines

Do NOT update this file for minor bug fixes or changes that do not
affect the documented architecture or conventions.

"""
Clicky for Windows — Entry Point.
Boots Qt, spawns overlay+panel+tray, starts ambient mic listener, binds hotkey.
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from auth import supabase_auth
from ui.tray import TrayManager
from ui.panel import CompanionPanel, AppState
from ui.auth_screen import AuthScreen
from ui.paywall_screen import PaywallScreen
from ui.overlay import (
    CursorOverlay, MODE_IDLE, MODE_LISTENING, MODE_THINKING, MODE_SPEAKING
)
from hotkey import GlobalHotkeyMonitor, StopHotkey
from companion_manager import CompanionManager


STATE_TO_CURSOR_MODE = {
    AppState.IDLE:      MODE_IDLE,
    AppState.LISTENING: MODE_LISTENING,
    AppState.THINKING:  MODE_THINKING,
    AppState.SPEAKING:  MODE_SPEAKING,
}


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Clicky for Animators")
    app.setApplicationDisplayName("Clicky for Animators")

    # ── Core components ───────────────────────────────────────────────────────
    manager = CompanionManager()
    panel   = CompanionPanel()
    overlay = CursorOverlay()
    tray    = TrayManager()
    companion_started = False

    # ── Wire signals ──────────────────────────────────────────────────────────

    # State changes → Panel + Tray + Cursor
    def _on_state(state: AppState):
        panel.set_state(state)
        tray.set_state_icon(state.name.lower())
        overlay.set_mode(STATE_TO_CURSOR_MODE.get(state, MODE_IDLE))

    manager.sig_state_changed.connect(_on_state)

    # Response streaming
    manager.sig_response_chunk.connect(panel.append_response_chunk)
    manager.usage_updated.connect(panel.set_usage)

    # Audio level → cursor waveform (+ panel meter)
    manager.sig_audio_level.connect(panel.set_audio_level)
    manager.sig_audio_level.connect(overlay.set_audio_level)

    # Pointing directives
    manager.sig_point_at.connect(overlay.point_at)
    manager.sig_point_hold.connect(overlay.set_point_hold)
    manager.sig_point_release.connect(overlay.release_point)

    # Whiteboard annotations
    manager.sig_arrow.connect(overlay.add_arrow)
    manager.sig_circle.connect(overlay.add_circle)
    manager.sig_underline.connect(overlay.add_underline)
    manager.sig_label.connect(overlay.add_text)

    # Errors (not Ollama setup — that goes to the panel)
    manager.sig_error.connect(
        lambda e: tray.show_notification("Clicky error", str(e))
    )

    def _on_setup_message(message: str):
        panel.show()
        panel.clear_response()
        panel.update_response(message)

    manager.sig_setup_message.connect(_on_setup_message)

    def _show_auth_screen():
        auth_screen = AuthScreen()

        def _on_auth_complete():
            _start_companion()

        auth_screen.auth_complete.connect(_on_auth_complete)
        auth_screen.show()
        auth_screen.raise_()
        _auth_keepalive[0] = auth_screen

    def _show_paywall_screen():
        paywall = PaywallScreen()

        def _on_subscription_activated():
            panel.show()
            tray.show_notification("Clicky", "Subscription active.")

        def _on_sign_in_requested():
            paywall.close()
            _show_auth_screen()

        paywall.subscription_activated.connect(_on_subscription_activated)
        paywall.sign_in_requested.connect(_on_sign_in_requested)
        paywall.show()
        paywall.raise_()
        _paywall_keepalive[0] = paywall

    manager.paywall_triggered.connect(_show_paywall_screen)
    manager.auth_required.connect(_show_auth_screen)

    # Panel → Manager
    panel.on_model_changed.connect(manager.set_model)

    def _on_doc_dropped(path: str):
        ok = manager.attach_document(path)
        tray.show_notification(
            "Document Attached" if ok else "Attach failed",
            f"{path}\nAsk Clicky about it now." if ok else
            "Couldn't read that file."
        )
    panel.on_document_dropped.connect(_on_doc_dropped)

    # Tray → UI / Manager
    tray.on_show_panel.connect(panel.show)
    tray.on_hide_panel.connect(panel.hide)
    tray.on_toggle_search.connect(manager.set_web_search)
    tray.on_toggle_wake_word.connect(manager.set_wake_word)
    tray.on_toggle_slow_mode.connect(manager.set_slow_mode)
    tray.on_toggle_slow_mode.connect(overlay.set_slow_mode)
    tray.on_toggle_quiz_mode.connect(manager.set_quiz_mode)
    tray.on_toggle_privacy.connect(manager.set_privacy_guard)
    tray.on_toggle_code_mode.connect(manager.set_code_mode_auto)
    tray.on_toggle_multilang.connect(manager.set_multilang)
    tray.on_toggle_journal.connect(manager.set_journal)
    tray.on_toggle_ocr.connect(manager.set_ocr_enabled)
    tray.on_sign_out.connect(
        lambda: (supabase_auth.clear_jwt(), panel.hide(), _show_auth_screen())
    )

    # Lesson recording
    def _record_start():
        out = manager.start_recording()
        tray.show_notification(
            "Lesson Recording",
            f"Recording to:\n{out}" if out else
            "Failed — install imageio[ffmpeg]: pip install imageio imageio-ffmpeg"
        )
    def _record_stop():
        out = manager.stop_recording()
        if out:
            tray.show_notification("Lesson saved", out)
    tray.on_record_start.connect(_record_start)
    tray.on_record_stop.connect(_record_stop)
    manager.sig_recording_state.connect(
        lambda on, _path: tray.set_recording_state(on)
    )

    # Workflow capture
    def _wf_start():
        ok = manager.workflow_start()
        tray.show_notification(
            "Workflow Capture",
            "Recording your clicks + keys. Stop from tray when done."
            if ok else "Install pynput: pip install pynput"
        )
    def _wf_stop():
        summary = manager.workflow_stop()
        if summary:
            tray.show_notification(
                "Workflow Captured",
                "Sent to Clicky as context. Ask: 'what did I just do?'"
            )
            # Stash as an attached doc so the next question sees it
            manager._attached_docs.append(("recorded_workflow.txt", summary))
    tray.on_workflow_start.connect(_wf_start)
    tray.on_workflow_stop.connect(_wf_stop)

    # Journal folder
    def _open_journal():
        import os, subprocess
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "Clicky")
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen(["explorer", path])
    tray.on_journal_open.connect(_open_journal)

    # Attach document (drag-drop alternative — file picker)
    def _attach_doc():
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "Attach a document for Clicky",
            "", "Documents (*.pdf *.docx *.txt *.md *.csv)"
        )
        if path:
            ok = manager.attach_document(path)
            tray.show_notification(
                "Document Attached",
                f"{path}\nAsk Clicky about it now." if ok else
                "Couldn't read that file."
            )
    tray.on_attach_doc.connect(_attach_doc)

    tray.on_stop.connect(manager.stop)

    tray.on_quit.connect(lambda: (manager.shutdown(), app.quit()))

    # ── Global hotkey ─────────────────────────────────────────────────────────
    hotkey = GlobalHotkeyMonitor(
        on_press=manager.on_hotkey_press,
        on_release=manager.on_hotkey_release,
    )
    hotkey.start()

    # Esc = cancel current generation (kills Ollama ramble mid-stream)
    stop_key = StopHotkey(on_stop=manager.stop, key="esc")
    stop_key.start()

    def _start_companion():
        nonlocal companion_started
        if companion_started:
            return
        companion_started = True
        overlay.show()
        manager.start()
        tray.show_notification(
            "Clicky for Animators",
            "Hold Ctrl+Alt+Space to ask  |  Kimi K2.5 + Faster-Whisper",
        )

    def _check_for_updates():
        try:
            from update import updater
            check = getattr(updater, "check_for_updates", None)
            if check:
                manager._submit(check(notify=tray.show_notification))
        except Exception:
            pass

    _check_for_updates()

    # ── Auth gate ─────────────────────────────────────────────────────────────
    if supabase_auth.load_jwt():
        _start_companion()
    else:
        _show_auth_screen()

    sys.exit(app.exec())


# Module-level slots used to keep auth/paywall windows alive while Qt is running.
_auth_keepalive: list = [None]
_paywall_keepalive: list = [None]


if __name__ == "__main__":
    main()

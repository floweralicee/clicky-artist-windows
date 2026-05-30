from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject


def _make_tray_icon(color: QColor) -> QIcon:
    """Generate a simple coloured circle as the tray icon.
    Must be called AFTER QApplication exists (Qt requirement)."""
    px = QPixmap(QSize(22, 22))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(3, 3, 16, 16)
    painter.end()
    return QIcon(px)


class TrayManager(QObject):
    """Windows system tray icon and context menu."""

    on_show_panel         = pyqtSignal()
    on_hide_panel         = pyqtSignal()
    on_quit               = pyqtSignal()
    on_toggle_search      = pyqtSignal(bool)
    on_toggle_wake_word   = pyqtSignal(bool)
    on_toggle_slow_mode   = pyqtSignal(bool)
    on_toggle_quiz_mode   = pyqtSignal(bool)
    on_toggle_privacy     = pyqtSignal(bool)
    on_ollama_set_model   = pyqtSignal(str, str)   # (kind, name): kind = "vision" | "text"
    on_ollama_pull        = pyqtSignal(str)        # model name
    on_ollama_refresh     = pyqtSignal()
    on_stop               = pyqtSignal()
    on_toggle_code_mode   = pyqtSignal(bool)
    on_toggle_multilang   = pyqtSignal(bool)
    on_toggle_journal     = pyqtSignal(bool)
    on_toggle_ocr         = pyqtSignal(bool)
    on_record_start       = pyqtSignal()
    on_record_stop        = pyqtSignal()
    on_workflow_start     = pyqtSignal()
    on_workflow_stop      = pyqtSignal()
    on_journal_open       = pyqtSignal()
    on_attach_doc         = pyqtSignal()
    on_run_setup          = pyqtSignal()
    on_diagnostics        = pyqtSignal()
    on_sign_out           = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._icons = {
            "idle":      _make_tray_icon(QColor(80, 80, 120)),
            "listening": _make_tray_icon(QColor(50, 200, 100)),
            "thinking":  _make_tray_icon(QColor(0, 120, 255)),
            "speaking":  _make_tray_icon(QColor(255, 140, 0)),
        }

        self._tray = QSystemTrayIcon()
        self._tray.setIcon(self._icons["idle"])
        self._tray.setToolTip(
            "Clicky for Animators — hold Ctrl+Alt+Space to ask"
        )
        self._search_enabled = True
        self._wake_enabled = True
        self._slow_enabled = False
        self._quiz_enabled = False
        self._privacy_enabled = True
        self._code_enabled = True
        self._multilang_enabled = True
        self._journal_enabled = True
        self._ocr_enabled = True
        self._is_recording = False
        self._account_email = ""

        self._ollama_installed: dict[str, list[str]] = {"vision": [], "text": []}

        self._build_menu()
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: rgb(22,22,28); border: 1px solid rgb(55,55,70);"
            "border-radius: 8px; color: rgb(220,220,230); font-size: 13px; }"
            "QMenu::item:selected { background: rgb(0,90,200); border-radius: 4px; }"
            "QMenu::separator { height: 1px; background: rgb(55,55,70); margin: 4px 8px; }"
        )

        show_action = menu.addAction("Show Panel")
        show_action.triggered.connect(self.on_show_panel)

        hide_action = menu.addAction("Hide Panel")
        hide_action.triggered.connect(self.on_hide_panel)

        menu.addSeparator()
        tutor_menu = menu.addMenu("Tutor Mode")

        slow_action = tutor_menu.addAction(
            "Slow Mode (teacher pace): ON" if self._slow_enabled
            else "Slow Mode (teacher pace): OFF"
        )
        slow_action.setCheckable(True)
        slow_action.setChecked(self._slow_enabled)
        slow_action.triggered.connect(self._toggle_slow)
        self._slow_action = slow_action

        quiz_action = tutor_menu.addAction(
            "Quiz Mode: ON" if self._quiz_enabled else "Quiz Mode: OFF"
        )
        quiz_action.setCheckable(True)
        quiz_action.setChecked(self._quiz_enabled)
        quiz_action.triggered.connect(self._toggle_quiz)
        self._quiz_action = quiz_action

        menu.addSeparator()
        account_menu = menu.addMenu("Account")
        email_label = self._account_email or "signed in"
        email_action = account_menu.addAction(email_label)
        email_action.setEnabled(False)
        sign_out_action = account_menu.addAction("Sign Out")
        sign_out_action.triggered.connect(self.on_sign_out)

        menu.addSeparator()

        quit_action = menu.addAction("Quit Clicky")
        quit_action.triggered.connect(self.on_quit)

        self._tray.setContextMenu(menu)
        self._menu = menu

    def _build_ollama_submenu(self, parent_menu: QMenu, providers: dict):
        """Vision/Text model pickers + 'Pull recommended' for Ollama."""
        from ai.ollama_models_registry import (
            RECOMMENDED_VISION, RECOMMENDED_TEXT,
        )

        ol_menu = parent_menu.addMenu("Ollama")
        active_vision = providers.get("ollama_vision_model", "")
        active_text   = providers.get("ollama_text_model", "")

        v_menu = ol_menu.addMenu(f"Vision model: {active_vision or '(none)'}")
        installed_vision = self._ollama_installed.get("vision", [])
        if installed_vision:
            for name in installed_vision:
                label = f"● {name}" if name == active_vision else f"  {name}"
                act = v_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("vision", n)
                )
        else:
            empty = v_menu.addAction("(no vision models installed)")
            empty.setEnabled(False)

        t_menu = ol_menu.addMenu(f"Text model: {active_text or '(none)'}")
        installed_text = self._ollama_installed.get("text", [])
        if installed_text:
            for name in installed_text:
                label = f"● {name}" if name == active_text else f"  {name}"
                act = t_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, n=name: self.on_ollama_set_model.emit("text", n)
                )
        else:
            empty = t_menu.addAction("(no text models installed)")
            empty.setEnabled(False)

        ol_menu.addSeparator()

        pull_menu = ol_menu.addMenu("Pull recommended…")
        already = set(installed_vision) | set(installed_text)

        def _add_recs(rec_list, header):
            hdr = pull_menu.addAction(header)
            hdr.setEnabled(False)
            for rec in rec_list:
                installed = any(n == rec.name or n.startswith(rec.name.split(":")[0] + ":") for n in already)
                tag = "✓ " if installed else "  "
                label = f"{tag}{rec.label}  ·  {rec.size}  —  {rec.blurb}"
                act = pull_menu.addAction(label)
                if installed:
                    act.setEnabled(False)
                else:
                    act.triggered.connect(
                        lambda _=False, n=rec.name: self.on_ollama_pull.emit(n)
                    )

        _add_recs(RECOMMENDED_VISION, "── Vision ──")
        pull_menu.addSeparator()
        _add_recs(RECOMMENDED_TEXT, "── Text ──")

        ol_menu.addSeparator()
        refresh_act = ol_menu.addAction("Refresh installed models")
        refresh_act.triggered.connect(self.on_ollama_refresh)

    def set_ollama_models(self, classified: dict):
        """Called by the manager after polling /api/tags. Triggers menu rebuild."""
        self._ollama_installed = {
            "vision": list(classified.get("vision", [])),
            "text":   list(classified.get("text", [])),
        }
        self.rebuild_menu()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.on_show_panel.emit()

    def _toggle_search(self, checked: bool):
        self._search_enabled = checked
        self._search_action.setText(
            "Web Search: ON" if checked else "Web Search: OFF"
        )
        self.on_toggle_search.emit(checked)

    def _toggle_wake(self, checked: bool):
        self._wake_enabled = checked
        self._wake_action.setText(
            "Wake word 'Clicky': ON" if checked else "Wake word 'Clicky': OFF"
        )
        self.on_toggle_wake_word.emit(checked)

    def _toggle_slow(self, checked: bool):
        self._slow_enabled = checked
        self._slow_action.setText(
            "Slow Mode (teacher pace): ON" if checked
            else "Slow Mode (teacher pace): OFF"
        )
        self.on_toggle_slow_mode.emit(checked)

    def _toggle_quiz(self, checked: bool):
        self._quiz_enabled = checked
        self._quiz_action.setText(
            "Quiz Mode: ON" if checked else "Quiz Mode: OFF"
        )
        self.on_toggle_quiz_mode.emit(checked)

    def _toggle_privacy(self, checked: bool):
        self._privacy_enabled = checked
        self._privacy_action.setText(
            "Privacy Guard: ON" if checked else "Privacy Guard: OFF"
        )
        self.on_toggle_privacy.emit(checked)

    def _toggle_code(self, checked: bool):
        self._code_enabled = checked
        self._code_action.setText(
            "Code Mode (auto): ON" if checked else "Code Mode (auto): OFF"
        )
        self.on_toggle_code_mode.emit(checked)

    def _toggle_multilang(self, checked: bool):
        self._multilang_enabled = checked
        self._ml_action.setText(
            "Multilingual: ON" if checked else "Multilingual: OFF"
        )
        self.on_toggle_multilang.emit(checked)

    def _toggle_ocr(self, checked: bool):
        self._ocr_enabled = checked
        self._ocr_action.setText(
            "OCR Fallback: ON" if checked else "OCR Fallback: OFF"
        )
        self.on_toggle_ocr.emit(checked)

    def _toggle_journal(self, checked: bool):
        self._journal_enabled = checked
        self._journal_action.setText(
            "Logging: ON" if checked else "Logging: OFF"
        )
        self.on_toggle_journal.emit(checked)

    def set_recording_state(self, on: bool):
        self._is_recording = on
        self.rebuild_menu()

    def set_account_email(self, email: str):
        self._account_email = email
        self.rebuild_menu()

    def set_state_icon(self, state: str):
        self._tray.setIcon(self._icons.get(state, self._icons["idle"]))

    def rebuild_menu(self):
        self._build_menu()

    def show_notification(self, title: str, message: str):
        self._tray.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information, 3000
        )

    @property
    def search_enabled(self) -> bool:
        return self._search_enabled

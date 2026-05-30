from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auth import supabase_auth
from auth.supabase_auth import AuthResult


class AuthScreen(QWidget):
    auth_complete = pyqtSignal()
    _auth_result = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._mode = "welcome"
        self._is_submitting = False
        self._auth_result.connect(self._handle_auth_result)
        self._setup_window()
        self._render()

    def _setup_window(self) -> None:
        self.setWindowTitle("Clicky for Animators")
        self.setFixedSize(420, 520)
        self.setStyleSheet(
            """
            QWidget {
                background: #0a0a0a;
                color: #ffffff;
                font-family: Inter, Segoe UI, Arial;
            }
            QFrame#card {
                background: #121216;
                border: 1px solid #262638;
                border-radius: 22px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #a6a6b8;
                font-size: 14px;
            }
            QLabel#error {
                color: #ff6767;
                font-size: 12px;
            }
            QLineEdit {
                background: #1b1b24;
                border: 1px solid #303044;
                border-radius: 10px;
                color: #ffffff;
                font-size: 14px;
                padding: 11px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
            }
            QPushButton#primary {
                background: #4a9eff;
                border: none;
                border-radius: 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                padding: 12px 18px;
            }
            QPushButton#primary:hover {
                background: #62abff;
            }
            QPushButton#primary:disabled {
                background: #2e5f99;
                color: #b8c7d8;
            }
            QPushButton#link {
                background: transparent;
                border: none;
                color: #4a9eff;
                font-size: 13px;
                text-align: left;
            }
            """
        )

    def _render(self) -> None:
        root = self.layout()
        if root is None:
            root = QVBoxLayout(self)
            root.setContentsMargins(28, 28, 28, 28)
            root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 34, 32, 34)
        card_layout.setSpacing(16)

        if self._mode == "welcome":
            self._render_welcome(card_layout)
        elif self._mode == "signup":
            self._render_form(
                card_layout=card_layout,
                title="create your account",
                subtitle="10 free sessions to start.",
                button_text="create account",
                link_text="already have an account? sign in",
                link_mode="signin",
                submit_callback=supabase_auth.signup,
            )
        else:
            self._render_form(
                card_layout=card_layout,
                title="welcome back",
                subtitle="sign in to keep using clicky.",
                button_text="sign in",
                link_text="no account yet? sign up",
                link_mode="signup",
                submit_callback=supabase_auth.signin,
            )

        root.addWidget(card)

    def _clear_layout(self) -> None:
        old_layout = self.layout()
        if old_layout is None:
            return
        while old_layout.count():
            item = old_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._clear_layout()
        self._render()

    def _render_welcome(self, layout: QVBoxLayout) -> None:
        title = QLabel("welcome to clicky 🎨")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("made for animators")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(22)

        button = QPushButton("get started")
        button.setObjectName("primary")
        button.clicked.connect(lambda: self._set_mode("signup"))
        layout.addWidget(button)

    def _render_form(
        self,
        card_layout: QVBoxLayout,
        title: str,
        subtitle: str,
        button_text: str,
        link_text: str,
        link_mode: str,
        submit_callback: Callable[[str, str], Awaitable[AuthResult]],
    ) -> None:
        title_label = QLabel(title)
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("subtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle_label)

        card_layout.addSpacing(14)

        email_input = QLineEdit()
        email_input.setPlaceholderText("email")
        email_input.setInputMethodHints(Qt.InputMethodHint.ImhEmailCharactersOnly)
        card_layout.addWidget(email_input)

        password_input = QLineEdit()
        password_input.setPlaceholderText("password")
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        card_layout.addWidget(password_input)

        error_label = QLabel("")
        error_label.setObjectName("error")
        error_label.setWordWrap(True)
        error_label.hide()
        card_layout.addWidget(error_label)

        submit_button = QPushButton(button_text)
        submit_button.setObjectName("primary")
        card_layout.addWidget(submit_button)

        link_row = QHBoxLayout()
        link_row.addStretch()
        link_button = QPushButton(link_text)
        link_button.setObjectName("link")
        link_button.clicked.connect(lambda: self._set_mode(link_mode))
        link_row.addWidget(link_button)
        link_row.addStretch()
        card_layout.addLayout(link_row)

        def submit() -> None:
            if self._is_submitting:
                return
            error_label.hide()
            submit_button.setDisabled(True)
            submit_button.setText("working...")
            self._is_submitting = True
            self._submit_auth(
                submit_callback,
                email_input.text(),
                password_input.text(),
            )

        submit_button.clicked.connect(submit)
        password_input.returnPressed.connect(submit)

        self._error_label = error_label
        self._submit_button = submit_button
        self._submit_button_text = button_text

    def _submit_auth(
        self,
        submit_callback: Callable[[str, str], Awaitable[AuthResult]],
        email: str,
        password: str,
    ) -> None:
        def run() -> None:
            try:
                result = asyncio.run(submit_callback(email, password))
            except Exception:
                result = AuthResult(
                    success=False,
                    error="Clicky could not sign you in right now. Try again.",
                )
            self._auth_result.emit(result)

        threading.Thread(target=run, daemon=True).start()

    def _handle_auth_result(self, result: AuthResult) -> None:
        self._is_submitting = False
        self._submit_button.setDisabled(False)
        self._submit_button.setText(self._submit_button_text)

        if result.success:
            self.auth_complete.emit()
            self.close()
            return

        self._error_label.setText(result.error or "Something went wrong.")
        self._error_label.show()


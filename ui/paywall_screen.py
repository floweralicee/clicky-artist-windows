from __future__ import annotations

import asyncio
import threading
import webbrowser

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from api import vercel_client

class PaywallScreen(QWidget):
    subscription_activated = pyqtSignal()
    sign_in_requested = pyqtSignal()
    _status_checked = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._poll_count = 0
        self._max_poll_count = 24
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._poll_status)
        self._status_checked.connect(self._handle_status_checked)
        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        self.setWindowTitle("Clicky for Animators")
        self.setFixedSize(440, 560)
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
            QLabel#eyebrow {
                color: #8f9bb3;
                font-size: 13px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 25px;
                font-weight: 700;
            }
            QLabel#price {
                color: #4a9eff;
                font-size: 34px;
                font-weight: 800;
            }
            QLabel#feature {
                color: #d8d8e2;
                font-size: 14px;
            }
            QLabel#status {
                color: #a6a6b8;
                font-size: 12px;
            }
            QLabel#error {
                color: #ff6767;
                font-size: 12px;
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
            }
            """
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(16)

        eyebrow = QLabel("you've used your 10 free sessions")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(eyebrow)

        title = QLabel("clicky for animators")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        price = QLabel("$10 / month")
        price.setObjectName("price")
        price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(price)

        layout.addSpacing(8)

        for text in (
            "✓ unlimited sessions",
            "✓ sees your screen in real time",
            "✓ works with maya, ae, blender + more",
            "✓ answers in your voice",
        ):
            feature = QLabel(text)
            feature.setObjectName("feature")
            layout.addWidget(feature)

        layout.addSpacing(12)

        self._subscribe_button = QPushButton("subscribe — $10/month")
        self._subscribe_button.setObjectName("primary")
        self._subscribe_button.clicked.connect(self._start_checkout)
        layout.addWidget(self._subscribe_button)

        self._status_label = QLabel("")
        self._status_label.setObjectName("status")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._error_label = QLabel("")
        self._error_label.setObjectName("error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        link_row = QHBoxLayout()
        link_row.addStretch()
        sign_in_link = QPushButton("already subscribed? sign in again")
        sign_in_link.setObjectName("link")
        sign_in_link.clicked.connect(self.sign_in_requested.emit)
        link_row.addWidget(sign_in_link)
        link_row.addStretch()
        layout.addLayout(link_row)

        root.addWidget(card)

    def _start_checkout(self) -> None:
        self._error_label.hide()
        self._subscribe_button.setDisabled(True)
        self._status_label.setText("Creating Stripe Checkout...")

        def run() -> None:
            try:
                checkout_url = asyncio.run(vercel_client.create_checkout_url())
                webbrowser.open(checkout_url)
                status = {"checkout_started": True}
            except Exception as error:
                status = {"error": str(error)}
            self._status_checked.emit(status)

        threading.Thread(target=run, daemon=True).start()

    def _poll_status(self) -> None:
        self._poll_count += 1
        if self._poll_count > self._max_poll_count:
            self._timer.stop()
            self._subscribe_button.setDisabled(False)
            self._status_label.setText("")
            self._error_label.setText(
                "I couldn't confirm your subscription yet. Try signing in again."
            )
            self._error_label.show()
            return

        self._status_label.setText("Checking subscription status...")

        def run() -> None:
            try:
                status = asyncio.run(vercel_client.get_status())
            except Exception as error:
                status = {"error": str(error)}
            self._status_checked.emit(status)

        threading.Thread(target=run, daemon=True).start()

    def _handle_status_checked(self, status: dict) -> None:
        if status.get("checkout_started"):
            self._poll_count = 0
            self._timer.start()
            self._poll_status()
            return

        if status.get("error"):
            self._subscribe_button.setDisabled(False)
            self._status_label.setText("Still waiting for Stripe...")
            self._error_label.setText(str(status["error"]))
            self._error_label.show()
            return

        if status.get("is_paid") or status.get("subscription_status") == "active":
            self._timer.stop()
            self._status_label.setText("Subscription active.")
            self.subscription_activated.emit()
            self.close()
            return

        self._status_label.setText("Still waiting for Stripe...")


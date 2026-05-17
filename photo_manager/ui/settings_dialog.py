"""Settings dialog covering paths, schedule, upload tuning."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox,
    QVBoxLayout,
)

from ..config import Config


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.resize(420, 400)

        v = QVBoxLayout(self)
        form = QFormLayout()
        v.addLayout(form)

        self.source = QLineEdit(config.source_folder)
        self.library = QLineEdit(config.library_root)
        self.client_secret = QLineEdit(config.oauth_client_secret_path)
        self.hour = QSpinBox(); self.hour.setRange(0, 23); self.hour.setValue(config.upload_hour)
        self.minute = QSpinBox(); self.minute.setRange(0, 59); self.minute.setValue(config.upload_minute)
        self.batch = QSpinBox(); self.batch.setRange(1, 20); self.batch.setValue(config.batch_size)
        self.per_file_to = QSpinBox(); self.per_file_to.setRange(30, 3600); self.per_file_to.setValue(config.per_file_timeout_sec)
        self.batch_to = QSpinBox(); self.batch_to.setRange(60, 7200); self.batch_to.setValue(config.batch_timeout_sec)
        self.max_retries = QSpinBox(); self.max_retries.setRange(0, 20); self.max_retries.setValue(config.max_retries)
        self.net_interval = QSpinBox(); self.net_interval.setRange(5, 600); self.net_interval.setValue(config.network_check_interval_sec)
        self.autostart = QCheckBox(); self.autostart.setChecked(config.autostart)

        form.addRow("Source folder:", self.source)
        form.addRow("Library root:", self.library)
        form.addRow("OAuth client_secret.json:", self.client_secret)
        form.addRow("Upload hour:", self.hour)
        form.addRow("Upload minute:", self.minute)
        form.addRow("Batch size:", self.batch)
        form.addRow("Per-file timeout (s):", self.per_file_to)
        form.addRow("Batch timeout (s):", self.batch_to)
        form.addRow("Max retries:", self.max_retries)
        form.addRow("Network check interval (s):", self.net_interval)
        form.addRow("Autostart on login:", self.autostart)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        btns.accepted.connect(self._apply_and_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _apply_and_accept(self) -> None:
        c = self.config
        c.source_folder = self.source.text().strip()
        c.library_root = self.library.text().strip()
        c.oauth_client_secret_path = self.client_secret.text().strip()
        c.upload_hour = self.hour.value()
        c.upload_minute = self.minute.value()
        c.batch_size = self.batch.value()
        c.per_file_timeout_sec = self.per_file_to.value()
        c.batch_timeout_sec = self.batch_to.value()
        c.max_retries = self.max_retries.value()
        c.network_check_interval_sec = self.net_interval.value()
        c.autostart = self.autostart.isChecked()
        self.accept()

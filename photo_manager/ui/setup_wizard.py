"""First-run wizard: collect source folder, library root, upload time."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWizard, QWizardPage,
)

from ..config import Config


class SetupWizard(QWizard):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Photo Manager — Setup")
        self.addPage(_PathsPage(config))
        self.addPage(_SchedulePage(config))
        self.addPage(_OAuthPage(config))
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)


class _PathsPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setTitle("Folders")
        self.setSubTitle("Choose where new photos arrive and where the library lives.")

        form = QFormLayout(self)
        self.source = _PathPicker(config.source_folder or str(Path.home() / "Downloads" / "Photos"))
        self.library = _PathPicker(config.library_root or str(Path.home() / "Pictures" / "PhotoManager"))
        form.addRow("Source folder:", self.source)
        form.addRow("Library root:", self.library)

    def validatePage(self) -> bool:  # type: ignore[override]
        self.config.source_folder = self.source.value()
        self.config.library_root = self.library.value()
        return bool(self.config.source_folder and self.config.library_root)


class _SchedulePage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setTitle("Schedule")
        self.setSubTitle("When should we run the nightly upload?")
        form = QFormLayout(self)
        self.hour = QSpinBox()
        self.hour.setRange(0, 23)
        self.hour.setValue(config.upload_hour)
        self.minute = QSpinBox()
        self.minute.setRange(0, 59)
        self.minute.setValue(config.upload_minute)
        form.addRow("Hour (0–23):", self.hour)
        form.addRow("Minute:", self.minute)

    def validatePage(self) -> bool:  # type: ignore[override]
        self.config.upload_hour = self.hour.value()
        self.config.upload_minute = self.minute.value()
        return True


class _OAuthPage(QWizardPage):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setTitle("Google OAuth")
        self.setSubTitle(
            "Point us at your OAuth client_secret.json (Desktop app credentials "
            "from Google Cloud Console). You can do this later in Settings."
        )
        form = QFormLayout(self)
        self.path = _PathPicker(config.oauth_client_secret_path, files=True)
        form.addRow("client_secret.json:", self.path)

    def validatePage(self) -> bool:  # type: ignore[override]
        self.config.oauth_client_secret_path = self.path.value()
        return True


class _PathPicker(QHBoxLayout):
    def __init__(self, initial: str, *, files: bool = False):
        super().__init__()
        self._files = files
        self.edit = QLineEdit(initial)
        btn = QPushButton("Browse…")
        btn.clicked.connect(self._pick)
        self.addWidget(self.edit)
        self.addWidget(btn)

    def _pick(self) -> None:
        if self._files:
            path, _ = QFileDialog.getOpenFileName(None, "Select file", self.edit.text(),
                                                    "JSON (*.json)")
        else:
            path = QFileDialog.getExistingDirectory(None, "Select folder", self.edit.text())
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

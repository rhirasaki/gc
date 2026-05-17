"""PyQt6 main window.

Layout:
  - top bar: account email, status pill, "Upload now" / "Retry failed"
  - left: filter sidebar (Today / Yesterday / This Week / Older + Status)
  - center: gallery grid
  - right: metadata panel for the selected photo
  - tray icon: status + quick actions
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
    QSplitter, QStatusBar, QSystemTrayIcon, QToolBar, QVBoxLayout, QWidget,
)

from ..app import AppController
from ..config import Config
from ..models import Photo, PhotoStatus
from .settings_dialog import SettingsDialog
from .setup_wizard import SetupWizard

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    refreshed = pyqtSignal()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.controller = AppController(config)
        self.setWindowTitle("Photo Manager")
        self.resize(1200, 760)

        self._selected_photo_id: Optional[int] = None
        self._build_ui()
        self._build_tray()

        if not (config.library_root and config.source_folder):
            QTimer.singleShot(100, self._run_setup_wizard)
        else:
            self._start_controller()

        # Periodic UI refresh.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(5000)

    # -- ui scaffolding ------------------------------------------------

    def _build_ui(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.upload_action = QAction("Upload now", self)
        self.upload_action.triggered.connect(self._upload_now)
        toolbar.addAction(self.upload_action)

        self.retry_action = QAction("Retry failed", self)
        self.retry_action.triggered.connect(self._retry_failed)
        toolbar.addAction(self.retry_action)

        toolbar.addSeparator()

        self.connect_action = QAction("Connect Google", self)
        self.connect_action.triggered.connect(self._connect_google)
        toolbar.addAction(self.connect_action)

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(self.settings_action)

        # Central split.
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.filter_list = QListWidget()
        for label in ("All", "Inbox", "Pending", "Uploading", "Uploaded",
                      "Failed", "—", "Today", "Yesterday", "This week", "Older"):
            QListWidgetItem(label, self.filter_list)
        self.filter_list.currentItemChanged.connect(lambda *_: self.refresh())
        self.filter_list.setMaximumWidth(180)
        self.filter_list.setCurrentRow(0)
        splitter.addWidget(self.filter_list)

        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setIconSize(self._icon_size())
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setSpacing(8)
        self.gallery.itemSelectionChanged.connect(self._on_selection_change)
        self.gallery.itemDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.gallery)

        self.metadata_panel = MetadataPanel(self._flag_selected, self._delete_selected)
        splitter.addWidget(self.metadata_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([160, 720, 320])

        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar(self))
        self._update_status_bar()

    def _icon_size(self):
        from PyQt6.QtCore import QSize
        return QSize(140, 140)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        icon = self.style().standardIcon(  # type: ignore[union-attr]
            self.style().StandardPixmap.SP_ComputerIcon  # type: ignore[union-attr]
        )
        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        menu.addAction("Open", self.show)
        menu.addAction("Upload now", self._upload_now)
        menu.addSeparator()
        menu.addAction("Quit", self.close)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Photo Manager")
        self.tray.show()

    # -- controller wiring --------------------------------------------

    def _start_controller(self) -> None:
        try:
            self.controller.start()
        except Exception:
            log.exception("controller start failed")
            QMessageBox.critical(self, "Startup failed",
                                  "Could not start the photo manager. See logs.")
            return
        self.refresh()

    def _run_setup_wizard(self) -> None:
        wiz = SetupWizard(self.config, parent=self)
        if wiz.exec():
            self.config.save()
            self._start_controller()

    # -- actions -------------------------------------------------------

    def _upload_now(self) -> None:
        if not self.controller.has_client():
            self._connect_google()
            if not self.controller.has_client():
                return
        try:
            result = self.controller.upload_now()
        except Exception as e:
            QMessageBox.warning(self, "Upload failed", str(e))
            return
        QMessageBox.information(
            self, "Upload complete",
            f"Considered: {result['considered']}\n"
            f"Success: {result['success']}\n"
            f"Failed: {result['failed']}",
        )
        self.refresh()

    def _retry_failed(self) -> None:
        n = self.controller.retry_all_failed()
        QMessageBox.information(self, "Retry queued",
                                  f"{n} failed photo(s) re-queued for upload.")
        self.refresh()

    def _connect_google(self) -> None:
        if not self.config.oauth_client_secret_path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select OAuth client_secret.json", "",
                "JSON files (*.json)",
            )
            if not path:
                return
            self.config.oauth_client_secret_path = path
            self.config.save()
        try:
            email = self.controller.authenticate()
        except Exception as e:
            QMessageBox.critical(self, "Auth failed", str(e))
            return
        QMessageBox.information(self, "Connected",
                                  f"Signed in as {email or '(unknown)'}.")
        self._update_status_bar()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, parent=self)
        if dlg.exec():
            self.config.save()
            # Reschedule if time changed.
            if self.controller._scheduler:
                self.controller._scheduler.reschedule(
                    self.config.upload_hour, self.config.upload_minute,
                )

    def _flag_selected(self) -> None:
        if self._selected_photo_id is None:
            return
        try:
            self.controller.flag_for_upload(self._selected_photo_id)
        except Exception as e:
            QMessageBox.warning(self, "Could not flag", str(e))
        self.refresh()

    def _delete_selected(self) -> None:
        if self._selected_photo_id is None:
            return
        photo = self.controller.db.get_photo(self._selected_photo_id)
        if not photo:
            return
        confirm = QMessageBox.question(
            self, "Delete photo",
            f"Permanently delete {photo.filename}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            p = Path(photo.filepath)
            if p.exists():
                p.unlink()
        except OSError:
            log.exception("file unlink failed")
        self.controller.db.delete_photo(photo.id)
        self.refresh()

    # -- gallery refresh ----------------------------------------------

    def refresh(self) -> None:
        self._populate_gallery()
        self._update_status_bar()

    def _populate_gallery(self) -> None:
        filt = self.filter_list.currentItem().text() if self.filter_list.currentItem() else "All"
        photos = self._filtered_photos(filt)

        self.gallery.clear()
        for p in photos:
            item = QListWidgetItem(p.filename)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            pix = QPixmap(p.filepath) if p.filepath else QPixmap()
            if not pix.isNull():
                pix = pix.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(pix))
            item.setToolTip(
                f"{p.filename}\n{p.status.value} • "
                f"{p.width or '?'}x{p.height or '?'} • "
                f"{(p.file_size or 0) // 1024} KB"
            )
            self.gallery.addItem(item)

    def _filtered_photos(self, filt: str) -> list[Photo]:
        statuses = {s.value: s for s in PhotoStatus}
        if filt in statuses:
            return self.controller.db.photos_by_status(statuses[filt])
        if filt == "All":
            return [p for s in PhotoStatus
                    for p in self.controller.db.photos_by_status(s)
                    if s != PhotoStatus.UPLOADED]
        all_photos = [p for s in PhotoStatus
                      for p in self.controller.db.photos_by_status(s)]
        today = date.today()
        if filt == "Today":
            return [p for p in all_photos if p.date_added.date() == today]
        if filt == "Yesterday":
            yest = today - timedelta(days=1)
            return [p for p in all_photos if p.date_added.date() == yest]
        if filt == "This week":
            start = today - timedelta(days=today.weekday())
            return [p for p in all_photos if p.date_added.date() >= start]
        if filt == "Older":
            cutoff = today - timedelta(days=7)
            return [p for p in all_photos if p.date_added.date() < cutoff]
        return []

    def _update_status_bar(self) -> None:
        counts = self.controller.status_counts()
        text = " | ".join(f"{k}: {v}" for k, v in counts.items())
        net = self.controller._network
        if net is not None:
            text += f"  •  Net: {'online' if net.online else 'offline'}"
        self.statusBar().showMessage(text)

    def _on_selection_change(self) -> None:
        items = self.gallery.selectedItems()
        if not items:
            self._selected_photo_id = None
            self.metadata_panel.clear()
            return
        photo_id = items[0].data(Qt.ItemDataRole.UserRole)
        self._selected_photo_id = photo_id
        photo = self.controller.db.get_photo(photo_id)
        if photo:
            self.metadata_panel.show_photo(photo)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        photo_id = item.data(Qt.ItemDataRole.UserRole)
        photo = self.controller.db.get_photo(photo_id)
        if photo and Path(photo.filepath).exists():
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(photo.filepath))

    # -- lifecycle -----------------------------------------------------

    def closeEvent(self, event):  # type: ignore[override]
        try:
            self.controller.stop()
        except Exception:
            log.exception("controller stop failed")
        super().closeEvent(event)


class MetadataPanel(QWidget):
    def __init__(self, on_flag, on_delete):
        super().__init__()
        self.setMaximumWidth(360)
        v = QVBoxLayout(self)
        self.preview = QLabel()
        self.preview.setFixedHeight(220)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.preview)
        self.info = QLabel("Select a photo")
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.info, 1)

        row = QHBoxLayout()
        self.flag_btn = QPushButton("Flag for upload")
        self.flag_btn.clicked.connect(on_flag)
        row.addWidget(self.flag_btn)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(on_delete)
        row.addWidget(self.del_btn)
        v.addLayout(row)

    def clear(self) -> None:
        self.preview.clear()
        self.info.setText("Select a photo")

    def show_photo(self, photo: Photo) -> None:
        if photo.filepath:
            pix = QPixmap(photo.filepath)
            if not pix.isNull():
                pix = pix.scaled(340, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                self.preview.setPixmap(pix)
            else:
                self.preview.setText("(no preview)")
        lines = [
            f"<b>{photo.filename}</b>",
            f"Status: {photo.status.value}",
            f"Added: {photo.date_added:%Y-%m-%d %H:%M}",
        ]
        if photo.date_taken:
            lines.append(f"Taken: {photo.date_taken:%Y-%m-%d %H:%M}")
        if photo.width and photo.height:
            lines.append(f"Size: {photo.width}×{photo.height}")
        if photo.file_size:
            lines.append(f"Bytes: {photo.file_size:,}")
        if photo.camera_model:
            lines.append(f"Camera: {photo.camera_model}")
        if photo.attempt_count:
            lines.append(f"Attempts: {photo.attempt_count}")
        if photo.error_code:
            lines.append(f"Last error: {photo.error_code} — {photo.error_message or ''}")
        if photo.google_photos_id:
            lines.append(f"Google ID: {photo.google_photos_id[:20]}…")
        self.info.setText("<br>".join(lines))


def run_gui(config: Config) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(config)
    win.show()
    return app.exec()

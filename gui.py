import os
import time
import datetime
import webbrowser
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QPlainTextEdit,
    QFileDialog, QMessageBox, QMenu, QAbstractItemView, QFrame
)
from PySide6.QtGui import QAction, QFont, QCursor

from config import load_config, save_config
from models import Repository
from api import GitHubAPI, GitHubAPIError
import utils

# ----------------- Dark stylesheet -----------------
DARK_STYLESHEET = """
QMainWindow {
    background-color: #121212;
}
QWidget {
    color: #e0e0e0;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}
QFrame#topFrame, QFrame#middleFrame, QFrame#bottomFrame {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
}
QLabel {
    border: none;
    background: transparent;
}
QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 10px;
    color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #1a73e8;
}
QPushButton {
    background-color: #1a73e8;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #155cb0;
}
QPushButton:pressed {
    background-color: #0f437a;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #757575;
}
QPushButton#unstarBtn {
    background-color: #d93838;
}
QPushButton#unstarBtn:hover {
    background-color: #bd2c2c;
}
QPushButton#unstarBtn:pressed {
    background-color: #9c2020;
}
QPushButton#cancelBtn {
    background-color: #555555;
}
QPushButton#cancelBtn:hover {
    background-color: #444444;
}
QCheckBox {
    spacing: 5px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QComboBox {
    background-color: #2a2a2a;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 4px 20px 4px 6px;
    color: #ffffff;
}
QComboBox QAbstractItemView {
    background-color: #202020;
    color: #ECECEC;
    border: 1px solid #343434;
    padding: 4px;
    selection-background-color: #2D6CDF;
    selection-color: white;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}
QTableWidget {
    background-color: #1e1e1e;
    gridline-color: #2d2d2d;
    border: 1px solid #2d2d2d;
    border-radius: 6px;
    color: #e0e0e0;
}
QTableWidget {
    background-color: #1e1e1e;
    alternate-background-color: #252525;
    gridline-color: #2d2d2d;
    border: 1px solid #2d2d2d;
    border-radius: 6px;
    color: #e0e0e0;
}
QTableWidget::item:selected {
    background-color: #2b5c8f;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #161616;
    color: #ffffff;
    padding: 6px;
    border: 1px solid #2d2d2d;
    font-weight: bold;
}
QProgressBar {
    border: 1px solid #2d2d2d;
    border-radius: 4px;
    text-align: center;
    background-color: #1e1e1e;
}
QProgressBar::chunk {
    background-color: #1a73e8;
}
QPlainTextEdit {
    background-color: #0e0e0e;
    border: 1px solid #2d2d2d;
    border-radius: 4px;
    font-family: "Geist Mono", "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: #a9b7c6;
}
"""

# ----------------- Thread Workers -----------------

class VerifyTokenWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, token: str):
        super().__init__()
        self.token = token

    def run(self):
        try:
            api = GitHubAPI(self.token)
            username = api.validate_token()
            self.finished.emit(username)
        except Exception as e:
            self.failed.emit(str(e))


class FetchReposWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, token: str):
        super().__init__()
        self.token = token

    def run(self):
        try:
            api = GitHubAPI(self.token)
            
            def page_cb(page: int, total_so_far: int) -> None:
                self.progress.emit(page, total_so_far)
                
            def log_cb(msg: str) -> None:
                self.log.emit(msg)

            repos = api.fetch_starred_repos(page_callback=page_cb, log_callback=log_cb)
            self.finished.emit(repos)
        except Exception as e:
            self.failed.emit(str(e))


class UnstarWorker(QThread):
    progress = Signal(int, int, str)
    log = Signal(str)
    unstar_success = Signal(int)
    finished = Signal(int)
    cancelled = Signal()

    def __init__(self, token: str, repos: List[Repository]):
        super().__init__()
        self.token = token
        self.repos = repos
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        api = GitHubAPI(self.token)
        total = len(self.repos)
        unstarred_count = 0
        start_time = time.time()
        
        self.log.emit(f"Starting bulk unstar for {total} repositories...")
        
        for idx, repo in enumerate(self.repos):
            if self.is_cancelled:
                self.cancelled.emit()
                return
                
            self.log.emit(f"Deleting star for {repo.owner}/{repo.name}...")
            
            # Est time calculation
            elapsed = time.time() - start_time
            avg_time = elapsed / (idx + 1) if idx > 0 else 0.5
            est_seconds = int(avg_time * (total - idx - 1))
            est_time_str = str(datetime.timedelta(seconds=est_seconds))
            
            self.progress.emit(idx + 1, total, est_time_str)
            
            try:
                success = api.unstar_repo(
                    repo.owner, 
                    repo.name, 
                    log_callback=lambda m: self.log.emit(m)
                )
                if success:
                    unstarred_count += 1
                    self.unstar_success.emit(repo.id)
                    self.log.emit(f"Unstarred successfully: {repo.owner}/{repo.name}")
            except Exception as e:
                self.log.emit(f"Failed: {repo.owner}/{repo.name} - {str(e)}")

        self.finished.emit(unstarred_count)


class RestarWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(list)
    cancelled = Signal()

    def __init__(self, token: str, repos: List[Repository]):
        super().__init__()
        self.token = token
        self.repos = repos
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        api = GitHubAPI(self.token)
        total = len(self.repos)
        self.log.emit(f"Starting re-star process for {total} repos...")
        
        for idx, repo in enumerate(self.repos):
            if self.is_cancelled:
                self.cancelled.emit()
                return
                
            self.log.emit(f"Starring {repo.owner}/{repo.name}...")
            self.progress.emit(idx + 1, total)
            
            try:
                success = api.star_repo(
                    repo.owner, 
                    repo.name, 
                    log_callback=lambda m: self.log.emit(m)
                )
                if success:
                    self.log.emit(f"Successfully starred {repo.owner}/{repo.name}")
            except Exception as e:
                self.log.emit(f"Failed to star {repo.owner}/{repo.name}: {str(e)}")

        # Fetch current lists again
        self.log.emit("Finished re-star. Updating starred list...")
        try:
            new_repos = api.fetch_starred_repos()
            self.finished.emit(new_repos)
        except Exception as e:
            self.finished.emit([])


# ----------------- Main Application Window -----------------

class GitHubStarsApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load configurations
        self.config = load_config()
        
        self.setWindowTitle("GitHub Stars Manager & Remover")
        self.resize(QSize(1000, 700))
        
        # Load window geometry if saved
        size_str = self.config.get("window_size", "1000x700")
        try:
            w, h = map(int, size_str.split("x"))
            self.resize(w, h)
        except Exception:
            pass

        # Data states
        self.api_client: Optional[GitHubAPI] = None
        self.all_repos: List[Repository] = []
        self.filtered_repos: List[Repository] = []
        self.username: str = ""
        self.is_connected: bool = False
        
        # Workers references
        self.verify_worker: Optional[VerifyTokenWorker] = None
        self.fetch_worker: Optional[FetchReposWorker] = None
        self.unstar_worker: Optional[UnstarWorker] = None
        self.restar_worker: Optional[RestarWorker] = None

        self._setup_ui()
        self.setStyleSheet(DARK_STYLESHEET)
        
        # Load saved token
        saved_token = self.config.get("saved_token", "")
        if saved_token:
            self.token_entry.setText(saved_token)
            self.save_token_check.setChecked(True)

        self.log("Application started.")

    def resizeEvent(self, event):
        """Remembers window dimensions on resize."""
        super().resizeEvent(event)
        self.config["window_size"] = f"{self.width()}x{self.height()}"
        save_config(self.config)

    def log(self, message: str) -> None:
        """Appends a timestamped log to the bottom console log."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console_log.appendPlainText(f"[{timestamp}] {message}")

    def _setup_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # ----------------- 1. TOP AUTH PANEL -----------------
        top_frame = QFrame()
        top_frame.setObjectName("topFrame")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(12, 10, 12, 10)
        
        top_layout.addWidget(QLabel("<b>GitHub Token:</b>"))
        
        self.token_entry = QLineEdit()
        self.token_entry.setPlaceholderText("ghp_...")
        self.token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        top_layout.addWidget(self.token_entry)

        self.show_token_btn = QPushButton("👁")
        self.show_token_btn.setFixedWidth(35)
        self.show_token_btn.clicked.connect(self._toggle_token_visibility)
        top_layout.addWidget(self.show_token_btn)

        self.save_token_check = QCheckBox("Save Token")
        top_layout.addWidget(self.save_token_check)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        top_layout.addWidget(self.connect_btn)
        
        main_layout.addWidget(top_frame)

        # ----------------- 2. MIDDLE GRID PANEL -----------------
        middle_frame = QFrame()
        middle_frame.setObjectName("middleFrame")
        middle_layout = QVBoxLayout(middle_frame)
        middle_layout.setContentsMargins(12, 12, 12, 12)

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        filter_layout.addWidget(QLabel("Search:"))
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search repository, owner, desc...")
        self.search_entry.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_entry)

        filter_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("All")
        self.lang_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.lang_combo)

        filter_layout.addWidget(QLabel("Archived:"))
        self.archive_combo = QComboBox()
        self.archive_combo.addItems(["All", "Active Only", "Archived Only"])
        self.archive_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.archive_combo)

        filter_layout.addWidget(QLabel("Fork:"))
        self.fork_combo = QComboBox()
        self.fork_combo.addItems(["All", "Forks Only", "Sources Only"])
        self.fork_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.fork_combo)

        filter_layout.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Updated", "Name", "Owner", "Language"])
        self.sort_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.sort_combo)

        middle_layout.addLayout(filter_layout)

        # Table QTableWidget
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Select", "Repository Name", "Owner", "Language", "Last Updated", "Archived", "Fork"
        ])
        
        # Grid settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_table_double_click)
        self.table.itemClicked.connect(self._on_table_cell_click)
        
        # Header settings
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        middle_layout.addWidget(self.table)

        # Stats label
        self.stats_label = QLabel("Total Starred: 0 | Selected: 0 | Remaining: 0")
        self.stats_label.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        middle_layout.addWidget(self.stats_label)

        main_layout.addWidget(middle_frame)

        # ----------------- 3. BOTTOM PANEL (Action & Console) -----------------
        bottom_frame = QFrame()
        bottom_frame.setObjectName("bottomFrame")
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(12, 12, 12, 12)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(self.refresh_btn)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        self.invert_btn = QPushButton("Invert")
        self.invert_btn.clicked.connect(self._invert_selection)
        btn_layout.addWidget(self.invert_btn)

        self.export_btn = QPushButton("Export List")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import Stars")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(self.import_btn)

        btn_layout.addStretch()

        self.unstar_btn = QPushButton("Unstar Selected")
        self.unstar_btn.setObjectName("unstarBtn")
        self.unstar_btn.setEnabled(False)
        self.unstar_btn.clicked.connect(self._on_unstar_selected)
        btn_layout.addWidget(self.unstar_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        bottom_layout.addLayout(btn_layout)

        # Progress / Status
        progress_layout = QHBoxLayout()
        self.status_label = QLabel("Disconnected. Please enter token and connect.")
        self.status_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(250)
        progress_layout.addWidget(self.progress_bar)

        bottom_layout.addLayout(progress_layout)

        # Log Text Box
        self.console_log = QPlainTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setFixedHeight(100)
        bottom_layout.addWidget(self.console_log)

        main_layout.addWidget(bottom_frame)

    def _toggle_token_visibility(self) -> None:
        if self.token_entry.echoMode() == QLineEdit.EchoMode.Password:
            self.token_entry.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_token_btn.setText("🙈")
        else:
            self.token_entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_token_btn.setText("👁")

    # ----------------- Workers Callbacks -----------------
    def _on_connect(self) -> None:
        token = self.token_entry.text().strip()
        if not token:
            QMessageBox.warning(self, "Token Required", "Please paste your GitHub Personal Access Token.")
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.status_label.setText("Validating token...")

        self.verify_worker = VerifyTokenWorker(token)
        self.verify_worker.finished.connect(self._on_connect_success)
        self.verify_worker.failed.connect(self._on_connect_failed)
        self.verify_worker.start()

    @Slot(str)
    def _on_connect_success(self, username: str) -> None:
        self.username = username
        self.is_connected = True
        self.status_label.setText(f"Connected as {username}")
        self.log(f"Successfully authenticated as: {username}")
        self.connect_btn.setText("Connected")
        self.connect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.import_btn.setEnabled(True)

        if self.save_token_check.isChecked():
            self.config["saved_token"] = self.token_entry.text().strip()
        else:
            self.config["saved_token"] = ""
        save_config(self.config)

        # Trigger automatic list fetching
        self._start_fetch()

    @Slot(str)
    def _on_connect_failed(self, error_msg: str) -> None:
        self.is_connected = False
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.status_label.setText("Invalid Token")
        self.log(f"Authentication failed: {error_msg}")
        QMessageBox.critical(self, "Authentication Error", f"Failed to authenticate token:\n{error_msg}")

    def _on_refresh(self) -> None:
        if self.is_connected:
            self._start_fetch()

    def _start_fetch(self) -> None:
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Fetching starred repositories...")
        self.progress_bar.setValue(0)
        self.all_repos = []
        self._apply_filters()

        self.fetch_worker = FetchReposWorker(self.token_entry.text().strip())
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.log.connect(self.log)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.failed.connect(self._on_fetch_failed)
        self.fetch_worker.start()

    @Slot(int, int)
    def _on_fetch_progress(self, page: int, total_so_far: int) -> None:
        self.log(f"Fetched page {page}... total {total_so_far} repos so far.")
        self.progress_bar.setValue(min(90, int(total_so_far / 10)))  # Soft representation

    @Slot(list)
    def _on_fetch_finished(self, repos: List[Repository]) -> None:
        self.all_repos = repos
        self.log(f"Fetch completed. Total: {len(repos)} repositories loaded.")
        self.status_label.setText(f"Fetch completed: {len(repos)} starred repositories found.")
        self.progress_bar.setValue(100)
        self.refresh_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.unstar_btn.setEnabled(True)

        self._populate_language_dropdown()
        self._apply_filters()

    @Slot(str)
    def _on_fetch_failed(self, error_msg: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("Fetch failed.")
        self.log(f"Repository fetch failed: {error_msg}")
        QMessageBox.critical(self, "Fetch Error", f"Could not fetch starred repositories:\n{error_msg}")

    # ----------------- Filtering & Data Population -----------------
    def _populate_language_dropdown(self) -> None:
        languages = set()
        for repo in self.all_repos:
            if repo.language and repo.language != "None":
                languages.add(repo.language)
        
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        self.lang_combo.addItem("All")
        for lang in sorted(list(languages)):
            self.lang_combo.addItem(lang)
        self.lang_combo.blockSignals(False)

    def _apply_filters(self) -> None:
        query = self.search_entry.text().lower().strip()
        lang_filter = self.lang_combo.currentText()
        archive_filter = self.archive_combo.currentText()
        fork_filter = self.fork_combo.currentText()
        sort_by = self.sort_combo.currentText()

        filtered = []
        for repo in self.all_repos:
            # Live Search
            if query:
                name_match = query in repo.name.lower()
                owner_match = query in repo.owner.lower()
                desc_match = query in repo.description.lower()
                topics_match = any(query in t.lower() for t in repo.topics)
                if not (name_match or owner_match or desc_match or topics_match):
                    continue

            # Language
            if lang_filter != "All" and repo.language != lang_filter:
                continue

            # Archive
            if archive_filter == "Active Only" and repo.archived:
                continue
            if archive_filter == "Archived Only" and not repo.archived:
                continue

            # Fork
            if fork_filter == "Forks Only" and not repo.fork:
                continue
            if fork_filter == "Sources Only" and repo.fork:
                continue

            filtered.append(repo)

        # Sorting
        if sort_by == "Name":
            filtered.sort(key=lambda r: r.name.lower())
        elif sort_by == "Owner":
            filtered.sort(key=lambda r: r.owner.lower())
        elif sort_by == "Language":
            filtered.sort(key=lambda r: (r.language or "").lower())
        elif sort_by == "Updated":
            filtered.sort(key=lambda r: r.updated_at, reverse=True)

        self.filtered_repos = filtered
        self._populate_table()
        self._update_stats()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        self.table.blockSignals(True)
        
        for row_idx, repo in enumerate(self.filtered_repos):
            self.table.insertRow(row_idx)
            
            # Checkbox item
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            check_item.setCheckState(Qt.CheckState.Checked if repo.selected else Qt.CheckState.Unchecked)
            check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 0, check_item)
            
            # Text items
            self.table.setItem(row_idx, 1, QTableWidgetItem(repo.name))
            self.table.setItem(row_idx, 2, QTableWidgetItem(repo.owner))
            self.table.setItem(row_idx, 3, QTableWidgetItem(repo.language or ""))
            
            # Formatted update date
            updated_str = repo.updated_at
            if repo.updated_at:
                try:
                    dt = datetime.datetime.fromisoformat(repo.updated_at.replace("Z", "+00:00"))
                    updated_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            self.table.setItem(row_idx, 4, QTableWidgetItem(updated_str))
            self.table.setItem(row_idx, 5, QTableWidgetItem("Yes" if repo.archived else "No"))
            self.table.setItem(row_idx, 6, QTableWidgetItem("Yes" if repo.fork else "No"))
            
        self.table.blockSignals(False)

    def _update_stats(self) -> None:
        total = len(self.all_repos)
        selected = sum(1 for r in self.all_repos if r.selected)
        remaining = total - selected
        self.stats_label.setText(f"Total Starred: {total} | Selected: {selected} | Remaining: {remaining}")

    # ----------------- Selection Actions -----------------
    def _on_table_cell_click(self, item: QTableWidgetItem) -> None:
        """Handles manual checkbox selection toggle when user clicks the Checkbox item."""
        if item.column() == 0:
            row = item.row()
            if row < len(self.filtered_repos):
                repo = self.filtered_repos[row]
                repo.selected = (item.checkState() == Qt.CheckState.Checked)
                self._update_stats()

    def _select_all(self) -> None:
        for repo in self.filtered_repos:
            repo.selected = True
        self._populate_table()
        self._update_stats()

    def _deselect_all(self) -> None:
        for repo in self.all_repos:
            repo.selected = False
        self._populate_table()
        self._update_stats()

    def _invert_selection(self) -> None:
        for repo in self.filtered_repos:
            repo.selected = not repo.selected
        self._populate_table()
        self._update_stats()

    # ----------------- Right Click Context Menu & Double Click -----------------
    def _show_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self.filtered_repos):
            return

        repo = self.filtered_repos[row]
        menu = QMenu(self)
        
        open_action = QAction("Open Repository", self)
        open_action.triggered.connect(lambda: webbrowser.open(repo.html_url))
        menu.addAction(open_action)

        copy_action = QAction("Copy URL", self)
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(repo.html_url))
        menu.addAction(copy_action)

        owner_action = QAction("Open Owner Profile", self)
        owner_action.triggered.connect(lambda: webbrowser.open(f"https://github.com/{repo.owner}"))
        menu.addAction(owner_action)

        menu.exec(self.table.mapToGlobal(pos))

    def _copy_to_clipboard(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.log(f"Copied URL: {text}")

    def _on_table_double_click(self, model_index) -> None:
        row = model_index.row()
        if row >= 0 and row < len(self.filtered_repos):
            repo = self.filtered_repos[row]
            if repo.html_url:
                webbrowser.open(repo.html_url)

    # ----------------- Unstarring Operations -----------------
    def _on_unstar_selected(self) -> None:
        selected_repos = [r for r in self.all_repos if r.selected]
        if not selected_repos:
            QMessageBox.information(self, "No Selection", "Please select at least one repository checkbox.")
            return

        total = len(selected_repos)
        confirm = QMessageBox.question(
            self, 
            "Confirm Stars Removal",
            f"You are about to remove stars from {total} repositories.\n"
            "This cannot be undone automatically.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._start_unstar(selected_repos)

    def _start_unstar(self, repos: List[Repository]) -> None:
        self.unstar_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Unstarring repositories...")

        self.unstar_worker = UnstarWorker(self.token_entry.text().strip(), repos)
        self.unstar_worker.progress.connect(self._on_unstar_progress)
        self.unstar_worker.unstar_success.connect(self._on_unstar_success)
        self.unstar_worker.log.connect(self.log)
        self.unstar_worker.finished.connect(self._on_unstar_finished)
        self.unstar_worker.cancelled.connect(self._on_operation_cancelled)
        self.unstar_worker.start()

    @Slot(int, int, str)
    def _on_unstar_progress(self, current: int, total: int, est_time: str) -> None:
        self.status_label.setText(f"Removing {current} / {total} (Est: {est_time})")
        self.progress_bar.setValue(int((current / total) * 100))

    @Slot(int)
    def _on_unstar_success(self, repo_id: int) -> None:
        self.all_repos = [r for r in self.all_repos if r.id != repo_id]
        self._apply_filters()

    @Slot(int)
    def _on_unstar_finished(self, total_unstarred: int) -> None:
        self.log(f"Successfully removed stars from {total_unstarred} repositories.")
        self.status_label.setText(f"Unstar complete. Removed {total_unstarred} stars.")
        self.progress_bar.setValue(100)
        self.cancel_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.unstar_btn.setEnabled(True)

    def _on_cancel(self) -> None:
        if self.unstar_worker and self.unstar_worker.isRunning():
            self.unstar_worker.cancel()
        if self.restar_worker and self.restar_worker.isRunning():
            self.restar_worker.cancel()
        self.cancel_btn.setEnabled(False)

    @Slot()
    def _on_operation_cancelled(self) -> None:
        self.log("Operation cancelled by user.")
        self.status_label.setText("Cancelled.")
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.unstar_btn.setEnabled(True)

    # ----------------- Import / Export Operations -----------------
    def _on_export(self) -> None:
        if not self.all_repos:
            return
        
        initial_dir = self.config.get("last_export_folder") or os.path.expanduser("~")
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Starred Repositories",
            initial_dir,
            "JSON File (*.json);;CSV File (*.csv)"
        )
        if not file_path:
            return

        self.config["last_export_folder"] = os.path.dirname(file_path)
        save_config(self.config)

        try:
            if file_path.endswith(".csv"):
                utils.export_to_csv(self.all_repos, file_path)
            else:
                utils.export_to_json(self.all_repos, file_path)
            
            self.log(f"Exported data to {file_path}")
            QMessageBox.information(self, "Export Successful", f"Starred repositories exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred exporting data:\n{e}")

    def _on_import(self) -> None:
        initial_dir = self.config.get("last_export_folder") or os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Starred Repositories",
            initial_dir,
            "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            imported = utils.import_from_json(file_path)
            missing = utils.compare_repositories(imported, self.all_repos)
            self._show_import_comparison_dialog(imported, missing)
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"An error occurred importing data:\n{e}")

    def _show_import_comparison_dialog(self, imported: List[Repository], missing: List[Repository]) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Import Starred Repositories")
        
        info_text = f"Imported: {len(imported)} repositories.\nMissing Stars: {len(missing)} repositories compared to current list.\n\n"
        if missing:
            info_text += "Missing Repositories:\n"
            for idx, r in enumerate(missing[:20], 1):
                info_text += f"- {r.owner}/{r.name} ({r.language})\n"
            if len(missing) > 20:
                info_text += f"... and {len(missing) - 20} more."
        else:
            info_text += "Your starred repositories are fully up to date."

        dialog.setText(info_text)
        
        restar_btn = None
        if missing:
            restar_btn = dialog.addButton("Re-star All Missing", QMessageBox.ButtonRole.ActionRole)
        
        close_btn = dialog.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        
        if dialog.clickedButton() == restar_btn:
            self._start_restar(missing)

    def _start_restar(self, repos: List[Repository]) -> None:
        self.unstar_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Re-starring repositories...")

        self.restar_worker = RestarWorker(self.token_entry.text().strip(), repos)
        self.restar_worker.progress.connect(lambda cur, tot: self.progress_bar.setValue(int((cur / tot) * 100)))
        self.restar_worker.log.connect(self.log)
        self.restar_worker.finished.connect(self._on_restar_finished)
        self.restar_worker.cancelled.connect(self._on_operation_cancelled)
        self.restar_worker.start()

    @Slot(list)
    def _on_restar_finished(self, new_repos: List[Repository]) -> None:
        self.log("Re-star operations finished.")
        self.cancel_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.unstar_btn.setEnabled(True)
        
        if new_repos:
            self.all_repos = new_repos
            self._apply_filters()
            self.status_label.setText(f"Synchronized. {len(self.all_repos)} repositories starred.")
        else:
            self._start_fetch()

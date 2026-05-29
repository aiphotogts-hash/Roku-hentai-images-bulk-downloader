import os
import sys
import re
import time
import subprocess
import urllib.parse
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QLabel, QProgressBar, 
    QScrollArea, QFileDialog, QSlider, QFrame, QCheckBox, QSpinBox,
    QGridLayout, QSizePolicy, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import QColor

# Import local modules
import styles
from downloader import DownloadManager

def format_speed(kb_per_sec):
    if kb_per_sec is None or kb_per_sec < 0:
        return "0.0 KB/s"
    val = float(kb_per_sec)
    if val < 1024.0:
        return f"{val:.1f} KB/s"
    val /= 1024.0
    return f"{val:.1f} MB/s"

def format_time(seconds):
    if seconds is None or seconds < 0:
        return "--:--:--"
    if seconds > 3600 * 24:
        return "24h+"
    
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

class ThreadSlotWidget(QFrame):
    """
    A small widget displaying the status of a single download thread slot.
    """
    def __init__(self, slot_id, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.status = "Idle" # Idle, Active
        self.current_index = ""
        
        self.setObjectName("ThreadSlot")
        self.setProperty("status", self.status)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(4)
        
        self.id_lbl = QLabel(f"Slot {self.slot_id}")
        self.id_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_lbl.setStyleSheet("font-size: 10px; color: #62627a; font-weight: bold;")
        layout.addWidget(self.id_lbl)

        self.idx_lbl = QLabel("Idle")
        self.idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.idx_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #a1a1aa;")
        layout.addWidget(self.idx_lbl)
        
        self.setToolTip(f"Thread Slot {self.slot_id} - Idle")

    def set_active(self, download_index):
        self.status = "Active"
        self.current_index = str(download_index)
        self.idx_lbl.setText(f"#{download_index}")
        self.idx_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #c084fc;")
        
        self.setProperty("status", self.status)
        self.style().unpolish(self)
        self.style().polish(self)
        
        self.setToolTip(f"Thread Slot {self.slot_id} - Downloading Image #{download_index}")

    def set_idle(self):
        self.status = "Idle"
        self.current_index = ""
        self.idx_lbl.setText("Idle")
        self.idx_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #62627a;")
        
        self.setProperty("status", self.status)
        self.style().unpolish(self)
        self.style().polish(self)
        
        self.setToolTip(f"Thread Slot {self.slot_id} - Idle")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sequential Bulk Image Downloader")
        self.setMinimumSize(1100, 800)
        self.setStyleSheet(styles.get_stylesheet())

        # Path configurations
        self.base_download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        self.concurrency = 20 # default
        
        # Queueing System State
        self.queue_items_list = []
        self.active_queue_index = -1
        self.queue_cancel_requested = False
        self.auto_inc_counters = {}
        
        # State Management
        self.manager = DownloadManager()
        self.manager.worker_started.connect(self.on_worker_started)
        self.manager.worker_progress.connect(self.on_worker_progress)
        self.manager.worker_completed.connect(self.on_worker_completed)
        self.manager.worker_failed.connect(self.on_worker_failed)
        self.manager.worker_status.connect(self.on_worker_status)
        self.manager.overall_progress.connect(self.on_overall_progress)
        self.manager.queue_finished.connect(self.on_queue_finished)
        self.manager.log_msg.connect(self.log)

        # Thread slot mapping: slot_id -> ThreadSlotWidget
        self.thread_slots = {}
        self.index_to_slot_map = {}
        
        # Track URL padding and template
        self.url_template = ""
        self.url_padding = 0

        self.init_ui()
        self.log("System", f"Application started. Base output folder: {self.base_download_dir}")

    def init_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ------------------ LEFT COLUMN: Control Panel & Inputs (Scrollable) ------------------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        left_widget = QWidget()
        left_widget.setObjectName("LeftViewport")
        left_widget.setStyleSheet("#LeftViewport { background: transparent; }")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(15)

        # Header Frame
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 12, 15, 12)
        
        title_label = QLabel("BULK IMAGE DOWNLOADER")
        title_label.setObjectName("AppTitle")
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel("CONCURRENT SEQUENTIAL MEDIA HARVESTER")
        subtitle_label.setObjectName("AppSubtitle")
        header_layout.addWidget(subtitle_label)
        left_layout.addWidget(header_frame)

        # Source Config Panel
        source_panel = QFrame()
        source_panel.setObjectName("InputPanel")
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(15, 15, 15, 15)
        source_layout.setSpacing(10)

        source_title = QLabel("Source Config")
        source_title.setObjectName("SectionTitle")
        source_layout.addWidget(source_title)

        # URL Input
        url_label = QLabel("Sequential URL Example:")
        source_layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://rokuhentai.com/_images/pages/r07luu/0.jpg")
        self.url_input.textChanged.connect(self.auto_detect_url_settings)
        source_layout.addWidget(self.url_input)

        help_label = QLabel(
            "💡 Enter any URL containing the image number. The app will replace\n"
            "the last digit sequence to download sequentially.", self
        )
        help_label.setStyleSheet("color: #8888a0; font-size: 11px;")
        source_layout.addWidget(help_label)

        # Sequential Range Config
        range_layout = QHBoxLayout()
        
        start_vbox = QVBoxLayout()
        start_vbox.addWidget(QLabel("Start Index:"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 99999)
        self.start_spin.setValue(0)
        start_vbox.addWidget(self.start_spin)
        range_layout.addLayout(start_vbox)

        end_vbox = QVBoxLayout()
        end_vbox.addWidget(QLabel("End Index:"))
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 99999)
        self.end_spin.setValue(634)
        end_vbox.addWidget(self.end_spin)
        range_layout.addLayout(end_vbox)

        source_layout.addLayout(range_layout)

        # Auto stop checkbox
        self.auto_stop_chk = QCheckBox("Auto-stop on consecutive failures (404)")
        self.auto_stop_chk.setChecked(True)
        self.auto_stop_chk.toggled.connect(self.toggle_auto_stop)
        source_layout.addWidget(self.auto_stop_chk)

        # Add to Queue Button
        self.add_queue_btn = QPushButton("Add to Queue")
        self.add_queue_btn.setObjectName("SuccessBtn")
        self.add_queue_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.add_queue_btn.clicked.connect(self.enqueue_link)
        source_layout.addWidget(self.add_queue_btn)

        left_layout.addWidget(source_panel)

        # Destination Config Panel
        dest_panel = QFrame()
        dest_panel.setObjectName("InputPanel")
        dest_layout = QVBoxLayout(dest_panel)
        dest_layout.setContentsMargins(15, 15, 15, 15)
        dest_layout.setSpacing(10)

        dest_title = QLabel("Destination Config")
        dest_title.setObjectName("SectionTitle")
        dest_layout.addWidget(dest_title)

        # Base Directory Browse
        dest_layout.addWidget(QLabel("Base Download Location:"))
        dir_h_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.base_download_dir)
        self.dir_input.setReadOnly(True)
        dir_h_layout.addWidget(self.dir_input, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("SecondaryBtn")
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self.select_download_dir)
        dir_h_layout.addWidget(browse_btn)
        dest_layout.addLayout(dir_h_layout)

        # Subfolder Name
        subfolder_layout = QHBoxLayout()
        subfolder_layout.addWidget(QLabel("Custom Subfolder Name:"))
        self.subfolder_input = QLineEdit()
        self.subfolder_input.setPlaceholderText("Auto-extracted (e.g. r07luu)")
        subfolder_layout.addWidget(self.subfolder_input)
        dest_layout.addLayout(subfolder_layout)

        # Auto-increment folder number checkbox
        self.auto_inc_chk = QCheckBox("Auto-increment folder number (e.g. Name 1, Name 2...)")
        self.auto_inc_chk.setChecked(False)
        dest_layout.addWidget(self.auto_inc_chk)

        left_layout.addWidget(dest_panel)

        # Concurrency Config Panel
        concurrency_panel = QFrame()
        concurrency_panel.setObjectName("InputPanel")
        concurrency_layout = QVBoxLayout(concurrency_panel)
        concurrency_layout.setContentsMargins(15, 15, 15, 15)
        concurrency_layout.setSpacing(10)

        concurrency_title = QLabel("Concurrency Limits (10 to 100)")
        concurrency_title.setObjectName("SectionTitle")
        concurrency_layout.addWidget(concurrency_title)

        slider_layout = QHBoxLayout()
        self.concurrency_slider = QSlider(Qt.Orientation.Horizontal)
        self.concurrency_slider.setRange(10, 100)
        self.concurrency_slider.setValue(self.concurrency)
        self.concurrency_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.concurrency_slider.setTickInterval(10)
        self.concurrency_slider.valueChanged.connect(self.on_concurrency_changed)
        slider_layout.addWidget(self.concurrency_slider, 1)

        self.concurrency_lbl = QLabel(f"{self.concurrency}")
        self.concurrency_lbl.setFixedWidth(30)
        self.concurrency_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slider_layout.addWidget(self.concurrency_lbl)
        concurrency_layout.addLayout(slider_layout)

        left_layout.addWidget(concurrency_panel)

        # Bypass Headers config (Collapsible/Advanced)
        self.headers_panel = QFrame()
        self.headers_panel.setObjectName("InputPanel")
        headers_layout = QVBoxLayout(self.headers_panel)
        headers_layout.setContentsMargins(15, 15, 15, 15)
        headers_layout.setSpacing(8)

        headers_title = QHBoxLayout()
        headers_lbl = QLabel("Bypass / Headers Configuration")
        headers_lbl.setObjectName("SectionTitle")
        headers_title.addWidget(headers_lbl)
        headers_layout.addLayout(headers_title)

        # Referer
        headers_layout.addWidget(QLabel("Referer Header:"))
        self.referer_input = QLineEdit()
        self.referer_input.setPlaceholderText("https://rokuhentai.com/")
        headers_layout.addWidget(self.referer_input)

        # User-Agent
        headers_layout.addWidget(QLabel("User-Agent Header:"))
        self.ua_input = QLineEdit(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        headers_layout.addWidget(self.ua_input)

        # Cookies
        headers_layout.addWidget(QLabel("Custom Cookies (Optional):"))
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("cf_clearance=...; other_cookie=...")
        headers_layout.addWidget(self.cookie_input)

        left_layout.addWidget(self.headers_panel)
        
        left_scroll.setWidget(left_widget)
        main_layout.addWidget(left_scroll, 38) # Left scroll area takes 38% width

        # ------------------ RIGHT COLUMN: Stats, Queue, Live Grid, Logs ------------------
        right_column = QVBoxLayout()
        right_column.setSpacing(15)

        # Stats Dashboard Panel
        stats_panel = QFrame()
        stats_panel.setObjectName("StatsPanel")
        stats_layout = QHBoxLayout(stats_panel)
        stats_layout.setContentsMargins(15, 12, 15, 12)

        # Saved images
        saved_layout = QVBoxLayout()
        saved_lbl = QLabel("Saved Images")
        saved_lbl.setObjectName("StatLabel")
        saved_layout.addWidget(saved_lbl)
        self.saved_val_lbl = QLabel("0 / 0")
        self.saved_val_lbl.setObjectName("StatValue")
        saved_layout.addWidget(self.saved_val_lbl)
        stats_layout.addLayout(saved_layout)

        stats_layout.addSpacing(15)

        # Download Speed
        speed_layout = QVBoxLayout()
        speed_lbl = QLabel("Download Speed")
        speed_lbl.setObjectName("StatLabel")
        speed_layout.addWidget(speed_lbl)
        self.speed_val_lbl = QLabel("0.0 KB/s")
        self.speed_val_lbl.setObjectName("StatValue")
        speed_layout.addWidget(self.speed_val_lbl)
        stats_layout.addLayout(speed_layout)

        stats_layout.addSpacing(15)

        # Failed downloads
        failed_layout = QVBoxLayout()
        failed_lbl = QLabel("Failed / Missing")
        failed_lbl.setObjectName("StatLabel")
        failed_layout.addWidget(failed_lbl)
        self.failed_val_lbl = QLabel("0")
        self.failed_val_lbl.setObjectName("StatValue")
        failed_layout.addWidget(self.failed_val_lbl)
        stats_layout.addLayout(failed_layout)

        right_column.addWidget(stats_panel)

        # Global progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        right_column.addWidget(self.progress_bar)

        # NEW: DOWNLOAD QUEUE PANEL
        queue_panel = QFrame()
        queue_panel.setObjectName("InputPanel")
        queue_vbox = QVBoxLayout(queue_panel)
        queue_vbox.setContentsMargins(12, 12, 12, 12)
        queue_vbox.setSpacing(6)
        
        queue_header = QHBoxLayout()
        queue_title = QLabel("DOWNLOAD QUEUE")
        queue_title.setObjectName("SectionTitle")
        queue_title.setStyleSheet("font-size: 11px;")
        queue_header.addWidget(queue_title)
        
        self.queue_count_lbl = QLabel("0 Items enqueued")
        self.queue_count_lbl.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 11px;")
        queue_header.addWidget(self.queue_count_lbl)
        queue_header.addStretch(1)
        
        # Queue item modifier buttons
        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("SecondaryBtn")
        remove_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        remove_btn.clicked.connect(self.remove_queue_item)
        queue_header.addWidget(remove_btn)
        
        clear_completed_btn = QPushButton("Clear Done")
        clear_completed_btn.setObjectName("SecondaryBtn")
        clear_completed_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        clear_completed_btn.clicked.connect(self.clear_completed_queue)
        queue_header.addWidget(clear_completed_btn)
        
        queue_vbox.addLayout(queue_header)
        
        # QTableWidget for Queue List
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["Subfolder", "URL", "Range", "Status"])
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setMaximumHeight(130)
        self.queue_table.setStyleSheet("""
            QTableWidget {
                background-color: #11111a;
                border: 1px solid #1f1f2e;
                border-radius: 8px;
                color: #e2e2e9;
                gridline-color: #1f1f2e;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #0d0d14;
                color: #bf8eff;
                font-weight: bold;
                border: 1px solid #1f1f2e;
                padding: 4px;
            }
        """)
        
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        queue_vbox.addWidget(self.queue_table)
        right_column.addWidget(queue_panel)

        # VISUAL THREADS GRID FRAME
        grid_frame = QFrame()
        grid_frame.setObjectName("ThreadGridFrame")
        grid_vbox = QVBoxLayout(grid_frame)
        grid_vbox.setContentsMargins(12, 12, 12, 12)
        grid_vbox.setSpacing(6)
        
        grid_header = QHBoxLayout()
        grid_title = QLabel("CONCURRENT THREAD ACTIVE GRID")
        grid_title.setObjectName("SectionTitle")
        grid_title.setStyleSheet("font-size: 11px;")
        grid_header.addWidget(grid_title)
        
        self.active_threads_lbl = QLabel("0 / 20 Active")
        self.active_threads_lbl.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 11px;")
        grid_header.addWidget(self.active_threads_lbl)
        grid_header.addStretch(1)
        grid_vbox.addLayout(grid_header)

        # Thread Grid Area Scrollable (supporting up to 100 slots in 5 columns)
        grid_scroll = QScrollArea()
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setMaximumHeight(140)
        grid_scroll.setObjectName("QueueScroll")
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(6)
        
        # Initialize 100 thread slots in 5 columns (wider, fully readable slots)
        for i in range(100):
            slot = ThreadSlotWidget(i + 1)
            self.thread_slots[i] = slot
            
            # Place in 5-column grid
            row = i // 5
            col = i % 5
            self.grid_layout.addWidget(slot, row, col)
            
            # Hide slots above current default concurrency initially
            if i >= self.concurrency:
                slot.hide()
            else:
                slot.show()
                
        grid_scroll.setWidget(self.grid_container)
        grid_vbox.addWidget(grid_scroll)
        right_column.addWidget(grid_frame)

        # Actions buttons
        actions_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Queue")
        self.start_btn.setObjectName("SuccessBtn")
        self.start_btn.clicked.connect(self.start_queue_processing)
        actions_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("SecondaryBtn")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_crawling)
        actions_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_crawling)
        actions_layout.addWidget(self.cancel_btn)

        self.open_dir_btn = QPushButton("Open Folder")
        self.open_dir_btn.setObjectName("SecondaryBtn")
        self.open_dir_btn.clicked.connect(self.open_download_folder)
        actions_layout.addWidget(self.open_dir_btn)

        right_column.addLayout(actions_layout)

        # Developer Log Console
        console_layout = QVBoxLayout()
        console_layout.setSpacing(5)
        
        console_title = QLabel("System Log Console")
        console_title.setObjectName("SectionTitle")
        console_layout.addWidget(console_title)
        
        self.log_console = QTextEdit()
        self.log_console.setObjectName("ConsoleLog")
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        console_layout.addWidget(self.log_console)
        
        right_column.addLayout(console_layout)

        main_layout.addLayout(right_column, 62) # Right column takes 62% width

    # ------------------ EVENT LOGGING ------------------
    def log(self, category, message):
        t_str = time.strftime("%H:%M:%S")
        log_text = f"[{t_str}] [{category}] {message}"
        self.log_console.append(log_text)
        
        # Scroll to bottom
        cursor = self.log_console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_console.setTextCursor(cursor)

    # ------------------ INPUT AUTO-DETECTION ------------------
    def auto_detect_url_settings(self, url_text):
        url_text = url_text.strip()
        if not url_text:
            return

        parsed = urllib.parse.urlparse(url_text)
        path = parsed.path
        
        # Find last numeric group
        matches = list(re.finditer(r'\d+', path))
        if matches:
            last_match = matches[-1]
            start, end = last_match.span()
            digit_str = last_match.group(0)
            self.url_padding = len(digit_str)
            
            # Construct template URL
            new_path = path[:start] + "{}" + path[end:]
            new_parsed = parsed._replace(path=new_path)
            self.url_template = urllib.parse.urlunparse(new_parsed)
            
            # Pre-fill Start Index
            start_num = int(digit_str)
            self.start_spin.setValue(start_num)
            
            # Auto-extract and pre-fill subfolder name
            path_parts = path.strip('/').split('/')
            if len(path_parts) >= 2:
                inferred_subfolder = path_parts[-2]
                if not self.subfolder_input.text().strip():
                    self.subfolder_input.setPlaceholderText(inferred_subfolder)
            
            # Auto-prefill referer from host name
            host = parsed.netloc
            scheme = parsed.scheme
            if host:
                inferred_referer = f"{scheme}://{host}/"
                if not self.referer_input.text().strip():
                    self.referer_input.setPlaceholderText(inferred_referer)

    # ------------------ CONCURRENCY ACTIONS ------------------
    def on_concurrency_changed(self, val):
        self.concurrency = val
        self.concurrency_lbl.setText(f"{val}")
        self.active_threads_lbl.setText(f"{len(self.index_to_slot_map)} / {val} Active")
        self.manager.set_concurrency(val)
        
        # Update thread slot visibilities in the grid
        for i in range(100):
            if i < val:
                self.thread_slots[i].show()
            else:
                self.thread_slots[i].hide()

    def toggle_auto_stop(self, checked):
        pass

    # ------------------ DIRECTORY BROWSE ------------------
    def select_download_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Base Download Directory", self.base_download_dir)
        if folder:
            self.base_download_dir = folder
            self.dir_input.setText(folder)
            self.log("Settings", f"Base download folder changed to: {folder}")

    def open_download_folder(self):
        # Open selected queue item folder, or active item folder, or base directory
        selected_row = self.queue_table.currentRow()
        subfolder = ""
        
        if selected_row != -1 and selected_row < len(self.queue_items_list):
            subfolder = self.queue_items_list[selected_row]['subfolder']
        elif self.active_queue_index != -1:
            subfolder = self.queue_items_list[self.active_queue_index]['subfolder']
        else:
            subfolder = self.subfolder_input.text().strip() or self.subfolder_input.placeholderText() or ""

        full_path = os.path.join(self.base_download_dir, subfolder)
        os.makedirs(full_path, exist_ok=True)
        
        if sys.platform == 'win32':
            os.startfile(full_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', full_path])
        else:
            subprocess.Popen(['xdg-open', full_path])
        self.log("System", f"Opened folder in file explorer: {full_path}")

    # ------------------ QUEUE MODIFIER SLOTS ------------------
    def enqueue_link(self):
        url = self.url_input.text().strip()
        if not url:
            self.log("Warning", "Please input a URL to enqueue.")
            return

        # Double check parsing
        self.auto_detect_url_settings(url)
        if not self.url_template:
            self.log("Error", "Could not parse sequential digits from the URL.")
            return

        base_subfolder = self.subfolder_input.text().strip()
        
        # Fallback to placeholder/inferred if empty
        if not base_subfolder:
            inferred = "downloaded_images"
            parsed = urllib.parse.urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 2:
                inferred = path_parts[-2]
            base_subfolder = inferred
            
        if self.auto_inc_chk.isChecked():
            if base_subfolder not in self.auto_inc_counters:
                self.auto_inc_counters[base_subfolder] = 1
            current_num = self.auto_inc_counters[base_subfolder]
            subfolder = f"{base_subfolder} {current_num}"
            self.auto_inc_counters[base_subfolder] += 1
        else:
            subfolder = base_subfolder

        final_download_path = os.path.join(self.base_download_dir, subfolder)
        
        # Prepare headers
        referer = self.referer_input.text().strip() or self.referer_input.placeholderText() or "https://rokuhentai.com/"
        ua = self.ua_input.text().strip()
        cookies_str = self.cookie_input.text().strip()
        
        headers = {
            'User-Agent': ua,
            'Referer': referer,
            'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        if cookies_str:
            headers['Cookie'] = cookies_str

        start_idx = self.start_spin.value()
        end_idx = self.end_spin.value()
        auto_stop = self.auto_stop_chk.isChecked()
        
        if auto_stop and (end_idx <= start_idx):
            end_idx = start_idx + 99999

        # Enqueue item
        queue_item = {
            'url_template': self.url_template,
            'url_padding': self.url_padding,
            'start_idx': start_idx,
            'end_idx': end_idx,
            'save_dir': final_download_path,
            'subfolder': subfolder,
            'headers': headers,
            'auto_stop': auto_stop,
            'status': 'Pending'
        }
        
        self.queue_items_list.append(queue_item)
        
        # Add to UI table
        row_idx = self.queue_table.rowCount()
        self.queue_table.insertRow(row_idx)
        
        self.queue_table.setItem(row_idx, 0, QTableWidgetItem(subfolder))
        self.queue_table.setItem(row_idx, 1, QTableWidgetItem(self.url_template))
        
        rng_text = f"{start_idx} -> Auto" if auto_stop else f"{start_idx} -> {end_idx}"
        self.queue_table.setItem(row_idx, 2, QTableWidgetItem(rng_text))
        
        status_item = QTableWidgetItem("Pending")
        status_item.setForeground(QColor("#9e9eb3"))
        self.queue_table.setItem(row_idx, 3, status_item)

        self.queue_count_lbl.setText(f"{len(self.queue_items_list)} Items enqueued")
        self.log("Queue", f"Enqueued download folder: {subfolder}")

        # Clear inputs for next entry
        self.url_input.clear()
        self.url_template = ""
        self.url_padding = 0
        
        # Only clear subfolder input if auto-increment is OFF
        if not self.auto_inc_chk.isChecked():
            self.subfolder_input.clear()

    def remove_queue_item(self):
        selected_row = self.queue_table.currentRow()
        if selected_row == -1:
            return

        if selected_row == self.active_queue_index:
            self.log("Warning", "Cannot remove the active downloading item. Cancel it first.")
            return

        subfolder = self.queue_items_list[selected_row]['subfolder']
        self.queue_items_list.pop(selected_row)
        self.queue_table.removeRow(selected_row)
        
        # Shift active index if it's after the removed row
        if self.active_queue_index > selected_row:
            self.active_queue_index -= 1

        self.queue_count_lbl.setText(f"{len(self.queue_items_list)} Items enqueued")
        self.log("Queue", f"Removed queue item: {subfolder}")

    def clear_completed_queue(self):
        # Iterate backwards to safely delete indices
        for i in range(len(self.queue_items_list) - 1, -1, -1):
            if self.queue_items_list[i]['status'] in ['Completed', 'Failed', 'Cancelled']:
                self.queue_items_list.pop(i)
                self.queue_table.removeRow(i)
                
                # Shift active index if needed
                if self.active_queue_index > i:
                    self.active_queue_index -= 1
                    
        self.queue_count_lbl.setText(f"{len(self.queue_items_list)} Items enqueued")
        self.log("Queue", "Cleared completed queue items.")

    # ------------------ QUEUE PROCESSOR ------------------
    def start_queue_processing(self):
        if self.active_queue_index != -1:
            # Queue is already running
            return

        self.queue_cancel_requested = False
        self.advance_queue()

    def advance_queue(self):
        if self.queue_cancel_requested:
            self.active_queue_index = -1
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.log("System", "Queue halted.")
            return

        # Find next Pending item
        next_idx = -1
        for i, item in enumerate(self.queue_items_list):
            if item['status'] == 'Pending':
                next_idx = i
                break

        if next_idx == -1:
            self.active_queue_index = -1
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.log("System", "All enqueued downloads processed.")
            return

        # Start downloading next item
        self.active_queue_index = next_idx
        item = self.queue_items_list[next_idx]
        item['status'] = 'Downloading'
        
        # Update Table Status
        status_item = QTableWidgetItem("Downloading")
        status_item.setForeground(QColor("#c084fc")) # Purple downloading status
        self.queue_table.setItem(next_idx, 3, status_item)

        # Configure Manager
        self.manager.url_padding = item['url_padding']
        
        # Reset visual grid and stats
        self.index_to_slot_map.clear()
        for slot in self.thread_slots.values():
            slot.set_idle()
            
        self.progress_bar.setValue(0)
        self.saved_val_lbl.setText("0 / 0")
        self.speed_val_lbl.setText("0.0 KB/s")
        self.failed_val_lbl.setText("0")
        self.active_threads_lbl.setText(f"0 / {self.concurrency} Active")

        # Disable buttons and enable cancel
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

        self.log("System", f"Processing queue item [{next_idx+1}]: {item['subfolder']}")
        
        self.manager.configure(
            url_template=item['url_template'],
            start_idx=item['start_idx'],
            end_idx=item['end_idx'],
            save_dir=item['save_dir'],
            headers=item['headers'],
            concurrency=self.concurrency,
            auto_stop_404=item['auto_stop']
        )
        self.manager.start_download()

    # ------------------ DOWNLOAD CONTROL ACTIONS ------------------
    def pause_crawling(self):
        if self.manager.is_paused:
            self.manager.resume_download()
            self.pause_btn.setText("Pause")
            self.log("Action", "Resumed downloading.")
        else:
            self.manager.pause_download()
            self.pause_btn.setText("Resume")
            self.log("Action", "Paused downloading.")

    def cancel_crawling(self):
        self.queue_cancel_requested = True
        self.manager.cancel_download()
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.log("Action", "Cancel queue requested. Stopping active download...")

    # ------------------ DOWNLOAD MANAGER CALLBACK SLOTS ------------------
    @pyqtSlot(int)
    def on_worker_started(self, index):
        # Assign slot
        assigned_slot_id = -1
        for i in range(self.concurrency):
            slot = self.thread_slots[i]
            if slot.status == "Idle":
                assigned_slot_id = i
                break
                
        if assigned_slot_id != -1:
            self.index_to_slot_map[index] = assigned_slot_id
            self.thread_slots[assigned_slot_id].set_active(index)
            
        self.active_threads_lbl.setText(f"{len(self.index_to_slot_map)} / {self.concurrency} Active")

    @pyqtSlot(int, int, int)
    def on_worker_progress(self, index, downloaded, total):
        pass

    @pyqtSlot(int, str, int)
    def on_worker_completed(self, index, filename, size_bytes):
        if index in self.index_to_slot_map:
            slot_id = self.index_to_slot_map[index]
            self.thread_slots[slot_id].set_idle()
            del self.index_to_slot_map[index]
            
        self.active_threads_lbl.setText(f"{len(self.index_to_slot_map)} / {self.concurrency} Active")

    @pyqtSlot(int, str, int)
    def on_worker_failed(self, index, error_msg, status_code):
        if index in self.index_to_slot_map:
            slot_id = self.index_to_slot_map[index]
            self.thread_slots[slot_id].set_idle()
            del self.index_to_slot_map[index]
            
        self.active_threads_lbl.setText(f"{len(self.index_to_slot_map)} / {self.concurrency} Active")

    @pyqtSlot(int, str)
    def on_worker_status(self, index, status_text):
        if index in self.index_to_slot_map:
            slot_id = self.index_to_slot_map[index]
            self.thread_slots[slot_id].setToolTip(f"Thread Slot {slot_id+1} - #{index} ({status_text})")

    @pyqtSlot(int, int, float, float)
    def on_overall_progress(self, completed, total, speed, eta):
        self.speed_val_lbl.setText(format_speed(speed))
        self.saved_val_lbl.setText(f"{completed} / {total}")
        self.failed_val_lbl.setText(f"{self.manager.failed_count}")
        
        if total > 0:
            pct = int((completed / total) * 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"{pct}% | ETA: {format_time(eta)}")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(f"Downloaded {completed} | ETA: --:--")

    @pyqtSlot(bool)
    def on_queue_finished(self, completed_successfully):
        # UI resets
        self.index_to_slot_map.clear()
        for slot in self.thread_slots.values():
            slot.set_idle()
        self.active_threads_lbl.setText(f"0 / {self.concurrency} Active")

        active_idx = self.active_queue_index
        if active_idx != -1:
            item = self.queue_items_list[active_idx]
            if completed_successfully:
                item['status'] = 'Completed'
                self.log("Queue", f"Completed downloading: {item['subfolder']}")
                
                status_item = QTableWidgetItem("Completed")
                status_item.setForeground(QColor("#10b981")) # Green completed status
                self.queue_table.setItem(active_idx, 3, status_item)
            else:
                item['status'] = 'Cancelled'
                self.log("Queue", f"Cancelled or stopped download: {item['subfolder']}")
                
                status_item = QTableWidgetItem("Cancelled")
                status_item.setForeground(QColor("#ef4444")) # Red status
                self.queue_table.setItem(active_idx, 3, status_item)
        
        # Advance Queue to next pending download
        self.active_queue_index = -1
        self.advance_queue()

    def closeEvent(self, event):
        self.queue_cancel_requested = True
        self.manager.cancel_download()
        time.sleep(0.5)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import get_theme_colors


class QueueWidget(QWidget):
    queue_changed = pyqtSignal()
    expanded_changed = pyqtSignal(bool)
    clear_all_requested = pyqtSignal()

    def __init__(self, queue_manager, parent=None):
        super().__init__(parent)
        self.queue_manager = queue_manager
        self._expanded = False
        self._row_widgets = {}
        self._current_theme = "system"
        self._visible_row_slots = 3
        self._row_slot_height = 40

        self._build_ui()
        self._apply_stylesheet()
        self.refresh()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        self._root_layout = root_layout
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.header_row = QWidget()
        self.header_row.setObjectName("QueueHeaderRow")
        self.header_row.setFixedHeight(52)
        header_layout = QHBoxLayout(self.header_row)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_toggle = QPushButton("▸ Queue (0)")
        self.btn_toggle.setObjectName("QueueHeaderButton")
        self.btn_toggle.setFixedHeight(36)
        self.btn_toggle.setFixedWidth(190)
        self.btn_toggle.clicked.connect(self.toggle_expand)

        self.btn_clear_finished = QPushButton("Clear finished")
        self.btn_clear_finished.setObjectName("QueueHeaderButton")
        self.btn_clear_finished.setFixedHeight(36)
        self.btn_clear_finished.setMinimumWidth(150)
        self.btn_clear_finished.clicked.connect(self._clear_finished)

        self.btn_clear_queue = QPushButton("Clear queue")
        self.btn_clear_queue.setObjectName("QueueHeaderButton")
        self.btn_clear_queue.setFixedHeight(36)
        self.btn_clear_queue.setMinimumWidth(150)
        self.btn_clear_queue.clicked.connect(self._request_clear_all)

        header_layout.addWidget(self.btn_toggle)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_clear_queue)
        header_layout.addWidget(self.btn_clear_finished)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("QueueScrollArea")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.items_container = QWidget()
        self.items_container.setObjectName("QueueItemsContainer")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(6, 6, 6, 6)
        self.items_layout.setSpacing(6)
        self.items_layout.addStretch()

        self.scroll_area.setWidget(self.items_container)

        self.list_frame = QFrame()
        self.list_frame.setObjectName("QueueListFrame")
        list_frame_layout = QVBoxLayout(self.list_frame)
        list_frame_layout.setContentsMargins(1, 1, 1, 1)
        list_frame_layout.setSpacing(0)
        list_frame_layout.addWidget(self.scroll_area)
        self.list_frame.setVisible(False)

        fixed_queue_height = self._get_fixed_queue_height()
        self.list_frame.setFixedHeight(fixed_queue_height)
        self.list_frame.setMaximumHeight(fixed_queue_height)

        root_layout.addWidget(self.header_row)
        root_layout.addWidget(self.list_frame)
        self._update_total_height()

    def _get_fixed_queue_height(self):
        if not hasattr(self, "items_layout"):
            return 150
        margins = self.items_layout.contentsMargins()
        top_bottom = margins.top() + margins.bottom()
        spacing = self.items_layout.spacing()
        return top_bottom + (self._visible_row_slots * self._row_slot_height) + ((self._visible_row_slots - 1) * spacing)

    def _update_total_height(self):
        margins = self._root_layout.contentsMargins()
        spacing = self._root_layout.spacing()
        header_height = self.header_row.height()
        if self._expanded:
            total_height = margins.top() + header_height + spacing + self.list_frame.height() + margins.bottom()
        else:
            total_height = margins.top() + header_height + margins.bottom()
        self.setFixedHeight(total_height)

    def set_theme(self, theme):
        self._current_theme = theme
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        colors = get_theme_colors(self._current_theme, self.palette())
        border_color = colors["border_color"]
        text_color = colors["text_color"]
        input_bg = colors["input_bg"]
        btn_bg = colors["btn_bg"]
        btn_hover = colors["btn_hover"]
        btn_text = colors["btn_text"]
        accent = colors["accent_color"]
        scrollbar_bg = colors["bg_color"]
        scrollbar_handle = colors["border_color"]
        scrollbar_handle_hover = colors["muted_text"]
        if colors["resolved_theme"] == "light":
            panel_header_bg = "#dfe5ec"
            panel_list_bg = "#eceff4"
        else:
            panel_header_bg = "#353b45"
            panel_list_bg = "#1f2329"

        self.setStyleSheet(
            f"""
            QWidget#QueueHeaderRow {{
                background-color: {panel_header_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#QueueListFrame {{
                background-color: {panel_list_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QScrollArea#QueueScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea#QueueScrollArea QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 10px;
                margin: 4px 2px 4px 2px;
                border-radius: 5px;
            }}
            QScrollArea#QueueScrollArea QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 26px;
                border-radius: 5px;
            }}
            QScrollArea#QueueScrollArea QScrollBar::handle:vertical:hover {{
                background: {scrollbar_handle_hover};
            }}
            QScrollArea#QueueScrollArea QScrollBar::add-line:vertical,
            QScrollArea#QueueScrollArea QScrollBar::sub-line:vertical {{
                background: transparent;
                height: 0px;
                border: none;
            }}
            QScrollArea#QueueScrollArea QScrollBar::add-page:vertical,
            QScrollArea#QueueScrollArea QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QWidget#QueueItemsContainer {{
                background-color: {panel_list_bg};
            }}
            QWidget#QueueItemRow {{
                border: 1px solid {border_color};
                border-radius: 6px;
                background-color: {input_bg};
            }}
            QLabel#QueueTitleLabel {{
                color: {text_color};
            }}
            QLabel#QueueSummaryLabel {{
                color: {text_color};
                font-size: 11px;
            }}
            QPushButton#QueueHeaderButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {border_color};
                border-radius: 5px;
                font-weight: 600;
                font-size: 13px;
                padding: 6px 10px;
            }}
            QPushButton#QueueHeaderButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton#QueueRemoveButton {{
                background-color: transparent;
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton#QueueRemoveButton:hover {{
                background-color: {btn_hover};
                border-color: {accent};
            }}
            """
        )

    def _pending_downloading_count(self):
        items = self.queue_manager.get_all()
        return sum(1 for item in items if item["status"] in {"pending", "downloading"})

    def _update_toggle_text(self):
        count = self._pending_downloading_count()
        prefix = "▾" if self._expanded else "▸"
        self.btn_toggle.setText(f"{prefix} Queue ({count})")

    def toggle_expand(self):
        self._expanded = not self._expanded
        self.list_frame.setVisible(self._expanded)
        self._update_total_height()
        self._update_toggle_text()
        self.expanded_changed.emit(self._expanded)

    def add_item(self, url, mode, options=None):
        index = self.queue_manager.add(url, mode, options=options)
        self.refresh()
        self.queue_changed.emit()
        return index

    def _clear_finished(self):
        changed = self.queue_manager.clear_finished()
        if changed:
            self.refresh()
            self.queue_changed.emit()

    def _request_clear_all(self):
        self.clear_all_requested.emit()

    def _remove_item(self, index):
        removed = self.queue_manager.remove(index)
        if removed:
            self.refresh()
            self.queue_changed.emit()

    def _status_icon(self, status):
        return {
            "pending": "⏳",
            "downloading": "⬇️",
            "finished": "✅",
            "error": "❌",
            "cancelled": "⛔",
        }.get(status, "⏳")

    def _set_elided_title(self, label, full_text):
        metrics = QFontMetrics(label.font())
        elided = metrics.elidedText(full_text, Qt.TextElideMode.ElideRight, 430)
        label.setText(elided)
        label.setToolTip(full_text)

    def _build_item_summary(self, item):
        options = item.get("options") or {}
        mode = str(options.get("mode") or item.get("mode") or "Video")
        playlist = bool(options.get("playlist", False))

        if mode.lower() == "audio":
            audio_format = str(options.get("audio_format") or "audio")
            bitrate = options.get("audio_bitrate")
            parts = ["Audio", audio_format.upper()]
            if bitrate:
                parts.append(f"{bitrate}k")
        else:
            quality = options.get("video_quality_text")
            fmt_text = options.get("video_format_text")
            subtitle = options.get("subtitle")

            parts = ["Video"]
            if quality:
                parts.append(str(quality).split("|")[0].strip())
            if fmt_text:
                parts.append(str(fmt_text).split("(")[0].strip())
            if subtitle is not None:
                parts.append("Subs")

        if playlist:
            parts.append("Playlist")

        return " • ".join(part for part in parts if part)

    def _clear_rows(self):
        self._row_widgets = {}
        while self.items_layout.count() > 1:
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self):
        self._clear_rows()
        items = self.queue_manager.get_all()

        for index, item in enumerate(items):
            row = QWidget()
            row.setObjectName("QueueItemRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)

            icon_label = QLabel(self._status_icon(item["status"]))
            icon_label.setFixedWidth(22)

            title_label = QLabel()
            title_label.setObjectName("QueueTitleLabel")
            title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self._set_elided_title(title_label, item.get("title", item["url"]))

            summary_label = QLabel(self._build_item_summary(item))
            summary_label.setObjectName("QueueSummaryLabel")
            summary_label.setFixedWidth(180)
            summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            progress_label = QLabel()
            progress_label.setFixedWidth(40)
            progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if item["status"] == "downloading":
                progress_label.setText(f"{int(item.get('progress', 0))}%")
            else:
                progress_label.setText("")

            remove_button = QPushButton("✕")
            remove_button.setObjectName("QueueRemoveButton")
            remove_button.setFixedSize(20, 20)
            remove_button.clicked.connect(lambda _, i=index: self._remove_item(i))
            remove_button.setEnabled(item["status"] in {"pending", "finished", "error"})

            row_layout.addWidget(icon_label)
            row_layout.addWidget(title_label, 1)
            row_layout.addWidget(summary_label)
            row_layout.addWidget(progress_label)
            row_layout.addWidget(remove_button)

            self.items_layout.insertWidget(self.items_layout.count() - 1, row)
            self._row_widgets[index] = {
                "icon": icon_label,
                "title": title_label,
                "summary": summary_label,
                "progress": progress_label,
                "remove": remove_button,
            }

        self._update_toggle_text()
        self._update_total_height()

    def refresh_item(self, index):
        item_list = self.queue_manager.get_all()
        if index < 0 or index >= len(item_list):
            self.refresh()
            return

        row = self._row_widgets.get(index)
        if not row:
            self.refresh()
            return

        item = item_list[index]
        row["icon"].setText(self._status_icon(item["status"]))
        self._set_elided_title(row["title"], item.get("title", item["url"]))
        row["summary"].setText(self._build_item_summary(item))

        if item["status"] == "downloading":
            row["progress"].setText(f"{int(item.get('progress', 0))}%")
        else:
            row["progress"].setText("")

        row["remove"].setEnabled(item["status"] in {"pending", "finished", "error"})
        self._update_toggle_text()

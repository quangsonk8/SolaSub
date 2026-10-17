"""Hop thoai chon nhung ngon ngu hay dung — chi nhung cai duoc tich moi hien o o chon."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QVBoxLayout)

from ..languages import all_languages
from .theme import STYLE


class LanguageDialog(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cấu hình ngôn ngữ")
        self.setStyleSheet(STYLE)
        self.resize(430, 560)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Tích những ngôn ngữ bạn hay dùng — chỉ chúng hiện ở ô chọn."))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm… (gõ mã như 'th' hoặc tên như 'Thai')")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        pinned, rest = all_languages()
        sel = set(selected or [])
        for code, label in pinned + rest:
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, code)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if code in sel
                             else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)

        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("hint")
        lay.addWidget(self.lbl_count)
        self.list.itemChanged.connect(lambda *_: self._update_count())
        self._update_count()

        row = QHBoxLayout()
        b_all = QPushButton("Chọn tất cả"); b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("Bỏ chọn hết"); b_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(b_all); row.addWidget(b_none); row.addStretch(1)
        b_cancel = QPushButton("Huỷ"); b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("Lưu"); b_ok.setObjectName("primary"); b_ok.clicked.connect(self.accept)
        row.addWidget(b_cancel); row.addWidget(b_ok)
        lay.addLayout(row)

    def _filter(self, text):
        t = (text or "").strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _set_all(self, on):
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden():          # chi tac dong len nhung muc dang thay
                it.setCheckState(state)

    def _update_count(self):
        n = len(self.selected())
        self.lbl_count.setText(f"Đã chọn {n} ngôn ngữ"
                               + ("  — bỏ trống sẽ dùng lại danh sách mặc định" if n == 0 else ""))

    def selected(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

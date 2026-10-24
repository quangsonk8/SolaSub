"""
Canh bao khi chay ma KHONG co van ban goc.

Day khong phai canh bao hinh thuc: thieu van ban goc thi chat luong tut hang,
va nguoi dung can biet ro minh danh doi cai gi truoc khi cho may chay vai phut.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout)

from . import theme

MODELS = [
    ("base", "base — nhanh nhất, chữ sai nhiều (139 MB)"),
    ("small", "small — cân bằng (466 MB)"),
    ("medium", "medium — chữ chuẩn hơn hẳn, chậm ~3× (1,5 GB)"),
    ("large-v3", "large-v3 — tốt nhất, chậm nhất (2,9 GB)"),
]


class NoTextDialog(QDialog):
    """Tra ve (chap_nhan, ten_model)."""

    def __init__(self, current_model="base", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chưa có văn bản gốc")
        # Mau lay tu stylesheet cua QApplication (theme.apply) -> tu doi theo che do sang/toi
        self.setMinimumWidth(580)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        title = QLabel("Bạn chưa chọn văn bản gốc — tool sẽ tự nghe và gõ lại lời thoại.")
        title.setWordWrap(True)
        title.setObjectName("warnTitle")
        lay.addWidget(title)

        body = QLabel(
            "<b>Vẫn tạo được phụ đề</b>, nhưng chất lượng khác hẳn:<br><br>"
            "• <b>Mốc thời gian</b> — vẫn chính xác như thường.<br>"
            "• <b>Chữ</b> — do máy nghe ra, nên <b>sẽ có từ sai</b>. Sai nhiều nhất ở "
            "tên riêng, số, thuật ngữ và chữ Hán. Ví dụ thật: câu "
            "「その仔細を糺さねばならぬ」 bị nghe thành 「その死材をなくさればならね」.<br>"
            "• <b>Bạn sẽ phải tự đọc soát lại toàn bộ</b> thay vì chỉ xem vài chỗ "
            "được khoanh đỏ.<br><br>"
            "Nếu có file kịch bản, hãy chọn nó rồi chạy lại — chữ sẽ đúng 100% "
            "và chỉ còn vài chỗ cần liếc qua."
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(body)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model nhận dạng:"))
        self.cb = QComboBox()
        for code, label in MODELS:
            self.cb.addItem(label, code)
        i = self.cb.findData(current_model)
        self.cb.setCurrentIndex(max(0, i))
        self.cb.setMinimumWidth(330)
        row.addWidget(self.cb, 1)
        lay.addLayout(row)

        hint = QLabel("Chế độ phiên âm phụ thuộc hoàn toàn vào model — "
                      "model lớn hơn cho chữ đúng hơn nhiều. Lần đầu dùng sẽ phải tải về.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QHBoxLayout()
        btns.addStretch(1)
        b_cancel = QPushButton("Để tôi chọn văn bản gốc")
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("Cứ chạy phiên âm")
        b_ok.setObjectName("primary")
        b_ok.clicked.connect(self.accept)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        lay.addLayout(btns)

    def showEvent(self, ev):
        super().showEvent(ev)
        theme.set_title_bar_dark(self, theme.palette()["name"] == "dark")

    def model_name(self):
        return self.cb.currentData() or "base"

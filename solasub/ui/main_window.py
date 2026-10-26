"""
SolaSub — cua so chinh.

Luong lam viec: nap audio + van ban goc -> Chay can chinh -> chi duyet nhung cue
duoc khoanh -> xuat SRT. Chu trong cue LUON la van ban goc, nen khong phai sua chu;
viec duyet chi la kiem THOI GIAN o vai cho may khong chac.

Bo cuc: thanh tren (logo + nut sang/toi) · thanh quy trinh (1 audio, 2 van ban, 3 ngon ngu, chay, xuat)
· 2 the (phu de | van ban goc) · thanh phat · thanh trang thai.
"""
import os

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPixmap, QShortcut, QTextCursor
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QHeaderView, QLabel, QMainWindow,
                             QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSlider,
                             QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit,
                             QVBoxLayout, QWidget)

from .. import settings
from ..languages import all_languages, code_from_label
from ..paths import resource
from ..problems import detect
from ..srt import parse_ts, write_srt, ts
from .. import textio
from . import theme
from .icon import app_icon
from .lang_dialog import LanguageDialog
from .notext_dialog import NoTextDialog
from .worker import AlignWorker

ISSUE_LABEL = {
    "align_hong": "align hỏng",
    "thoi_luong_0": "thời lượng 0",
    "do_tin_cay_thap": "độ tin cậy thấp",
    "ho_lon_truoc_cue": "hở lớn phía trước",
    "doc_qua_nhanh": "đọc quá nhanh",
    "qua_dai": "quá dài",
    "qua_ngan": "quá ngắn",
    "dong_tran": "dòng tràn",
}


CHIP_H = 62     # 3 o buoc (audio, van ban, ngon ngu) cung chieu cao


class ElideLabel(QLabel):
    """
    Nhan tu rut gon chu (giua) theo DUNG do rong cua no. Chinh sach Ignored: layout cap het cho trong cho
    nhan, khong theo do dai chu -> tranh vong lap 'nhan co theo chu da rut gon -> lan sau rut gon con ngan hon'.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = ""
        self._mode = Qt.TextElideMode.ElideMiddle
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, text, mode=Qt.TextElideMode.ElideMiddle):
        self._full = text or ""
        self._mode = mode
        self._update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._update()

    def _update(self):
        super().setText(self.fontMetrics().elidedText(self._full, self._mode, max(20, self.width())))


class FileChip(QFrame):
    """O chon file bam duoc ca o: so buoc · icon · nhan nho + ten file (hoac goi y khi chua chon)."""
    clicked = pyqtSignal()

    def __init__(self, step, caption, placeholder, glyph, parent=None):
        super().__init__(parent)
        self.setObjectName("fileChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(170)          # cua so hep: 2 o file co lai truoc (ten file rut gon giua)
        self.setFixedHeight(CHIP_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.glyph = glyph
        self.placeholder = placeholder

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 14, 8)
        lay.setSpacing(10)
        num = QLabel(str(step)); num.setObjectName("stepNum")
        lay.addWidget(num)
        self.ico = QLabel(); self.ico.setFixedSize(20, 20)
        lay.addWidget(self.ico)
        col = QVBoxLayout(); col.setSpacing(0)
        cap = QLabel(caption.upper()); cap.setObjectName("chipCaption")
        self.value = ElideLabel(); self.value.setObjectName("chipValue")
        col.addWidget(cap); col.addWidget(self.value)
        lay.addLayout(col, 1)
        self.setText(None)

    def setText(self, name):
        """Ten file da chon (None/'' = chua chon). Giu ten ham setText de app.py dung nhu nut cu."""
        filled = bool(name)
        self.full = name or ""
        self.value.setProperty("empty", not filled)
        self.setProperty("filled", filled)
        self.value.setToolTip(self.full)
        for w in (self, self.value):
            w.style().unpolish(w); w.style().polish(w)
        # Ten file: cat GIUA (giu duoi .mp3/.txt). Chu goi y: cat CUOI ("Chon file au…" de doc hon "Chon f…dio…").
        # Goi sau polish de do bang dung font (dam/nhat) cua trang thai moi.
        self.value.set_full_text(self.full or self.placeholder,
                                 Qt.TextElideMode.ElideMiddle if filled else Qt.TextElideMode.ElideRight)

    def set_icon_color(self, color):
        self.ico.setPixmap(theme.glyph_icon(self.glyph, color, 20).pixmap(QSize(20, 20)))

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(ev)


def _card():
    f = QFrame(); f.setObjectName("card")
    lay = QVBoxLayout(f)
    # Chua le 1px + 10px day: bang / o chu ve nen vuong, sat mep se de mat vien va goc bo cua the
    lay.setContentsMargins(1, 0, 1, 10); lay.setSpacing(0)
    return f, lay


def _card_header(title, meta_obj=None):
    h = QWidget()
    lay = QHBoxLayout(h); lay.setContentsMargins(16, 12, 12, 10); lay.setSpacing(8)
    t = QLabel(title); t.setObjectName("cardTitle")
    lay.addWidget(t)
    if meta_obj is not None:
        lay.addWidget(meta_obj)
    lay.addStretch(1)
    return h, lay


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SolaSub — tạo phụ đề từ audio + văn bản gốc")
        self.resize(1320, 820)
        self.setMinimumSize(1060, 640)
        ic = app_icon()
        if ic:
            self.setWindowIcon(ic)

        self.cfg = settings.load()
        self.pal = theme.apply(QApplication.instance(), self.cfg.get("theme", "system"))
        self.audio_path = None
        self.text_path = None
        self.raw_text = ""
        self.cues = []
        self._dirty = False       # co ket qua / chinh sua CHUA xuat SRT -> hoi truoc khi xoa
        self.duration = 0.0
        self.worker = None
        self._stop_at = None
        self._seek_to = 0
        self._armed = True
        self._arm_deadline = 0
        self._icons = []          # (nut, glyph, khoa mau) -> ve lai khi doi sang/toi

        root = QWidget()
        # Phai TU TO nen: de trong suot thi tren cua so that vung quanh 2 the hien DEN
        # (anh chup bang QWidget.grab() van ve nen nen khong thay loi).
        root.setObjectName("root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rl = QVBoxLayout(root); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
        rl.addWidget(self._build_appbar())
        rl.addWidget(self._build_workbar())
        rl.addWidget(self._build_body(), 1)
        rl.addWidget(self._build_player())
        self.setCentralWidget(root)
        self._build_statusbar()
        self._build_shortcuts()
        self._apply_icons()
        self.statusBar().showMessage("Chọn file audio và văn bản gốc để bắt đầu.")

    # ================================================================ dung giao dien
    def _icon_btn(self, btn, glyph, color_key="text2", size=16):
        self._icons.append((btn, glyph, color_key, size))
        return btn

    def _build_appbar(self):
        bar = QFrame(); bar.setObjectName("appbar")
        lay = QHBoxLayout(bar); lay.setContentsMargins(16, 10, 12, 10); lay.setSpacing(10)

        logo = QLabel()
        p = resource("assets", "solasub.png")
        if p:
            dpr = self.devicePixelRatioF() or 1.0
            pm = QPixmap(p).scaled(int(28 * dpr), int(28 * dpr), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            logo.setPixmap(pm)
        lay.addWidget(logo)
        name = QHBoxLayout(); name.setSpacing(0)
        a = QLabel("Sola"); a.setObjectName("brandSola")
        b = QLabel("Sub"); b.setObjectName("brandSub")
        name.addWidget(a); name.addWidget(b)
        lay.addLayout(name)
        tag = QLabel("Tạo phụ đề khớp giờ từ audio + kịch bản gốc"); tag.setObjectName("brandTag")
        lay.addSpacing(8)
        lay.addWidget(tag)
        lay.addStretch(1)

        self.btn_theme = QPushButton(); self.btn_theme.setObjectName("iconBtn")
        self.btn_theme.setIconSize(QSize(16, 16))
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        lay.addWidget(self.btn_theme)
        return bar

    def _build_workbar(self):
        bar = QFrame(); bar.setObjectName("workbar")
        lay = QHBoxLayout(bar); lay.setContentsMargins(16, 14, 16, 4); lay.setSpacing(10)

        # Goi y NGAN: cua so hep van doc tron (giai thich day du nam o tooltip)
        self.btn_audio = FileChip(1, "Audio", "Chọn file audio…", theme.G_AUDIO)
        self.btn_audio.clicked.connect(self.pick_audio)
        self.btn_audio.setToolTip("Chọn file audio hoặc video: mp3, wav, m4a, mp4, mkv (Ctrl+O)")
        lay.addWidget(self.btn_audio, 3)

        self.btn_text = FileChip(2, "Văn bản gốc", "Chọn kịch bản…", theme.G_DOC)
        self.btn_text.clicked.connect(self.pick_text)
        self.btn_text.setToolTip("Chọn file kịch bản gốc: .txt hoặc Word .docx. Nên có: chữ trong phụ đề "
                                 "sẽ đúng 100% (Ctrl+Shift+O)")
        lay.addWidget(self.btn_text, 3)

        # O ngon ngu: cung kieu the voi 2 o file
        lang = QFrame(); lang.setObjectName("fileChip")
        lang.setFixedHeight(CHIP_H)
        # Fixed: luon dung dung do rong can thiet (theo nhan ngon ngu dai nhat). Truoc la Preferred ->
        # cua so hep bi bop, nut banh rang de len o chon va o tran sang nut Chay can chinh.
        lang.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        ll = QHBoxLayout(lang); ll.setContentsMargins(12, 5, 8, 5); ll.setSpacing(10)
        num = QLabel("3"); num.setObjectName("stepNum"); ll.addWidget(num)
        col = QVBoxLayout(); col.setSpacing(1)
        cap = QLabel("NGÔN NGỮ"); cap.setObjectName("chipCaption")
        col.addWidget(cap)
        self.cb_lang = QComboBox()
        self.cb_lang.setObjectName("chipCombo")
        self.cb_lang.setEditable(True)
        self.cb_lang.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cb_lang.setMinimumWidth(200)
        self._fill_languages()
        self.cb_lang.currentIndexChanged.connect(self._remember_lang)
        col.addWidget(self.cb_lang)
        ll.addLayout(col)
        self.btn_lang_cfg = QPushButton(); self.btn_lang_cfg.setObjectName("iconBtn")
        self.btn_lang_cfg.setToolTip("Cấu hình danh sách ngôn ngữ")
        self.btn_lang_cfg.setIconSize(QSize(16, 16))
        self.btn_lang_cfg.clicked.connect(self.configure_languages)
        self._icon_btn(self.btn_lang_cfg, theme.G_SETTINGS)
        ll.addWidget(self.btn_lang_cfg, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lang, 0)

        lay.addSpacing(6)
        self.btn_new = QPushButton("Làm mới")
        self.btn_new.setFixedHeight(CHIP_H - 14)
        self.btn_new.setIconSize(QSize(16, 16))
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setToolTip("Xoá audio, kịch bản và kết quả để làm video tiếp theo (Ctrl+N)")
        self.btn_new.clicked.connect(self.new_session)
        self._icon_btn(self.btn_new, theme.G_NEW)
        lay.addWidget(self.btn_new)

        self.btn_run = QPushButton("Chạy căn chỉnh")
        self.btn_run.setObjectName("primary")
        self.btn_run.setEnabled(False)
        self.btn_run.setFixedHeight(CHIP_H - 14)
        self.btn_run.setIconSize(QSize(16, 16))
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setToolTip("Căn chỉnh văn bản gốc theo audio (Ctrl+Enter)")
        self.btn_run.clicked.connect(self.run_align)
        self._icon_btn(self.btn_run, theme.G_RUN)
        lay.addWidget(self.btn_run)

        self.btn_export = QPushButton("Xuất SRT")
        self.btn_export.setEnabled(False)
        self.btn_export.setFixedHeight(CHIP_H - 14)
        self.btn_export.setIconSize(QSize(16, 16))
        self.btn_export.setToolTip("Lưu file phụ đề .srt (Ctrl+S)")
        self.btn_export.clicked.connect(self.export_srt)
        self._icon_btn(self.btn_export, theme.G_SAVE)
        lay.addWidget(self.btn_export)
        return bar

    def _build_body(self):
        wrap = QWidget()
        wl = QHBoxLayout(wrap); wl.setContentsMargins(16, 10, 16, 14); wl.setSpacing(0)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)          # khe giua 2 the (keo de doi do rong)

        # ---- The phu de ----
        card, cl = _card()
        self.lbl_meta = QLabel("chưa có"); self.lbl_meta.setObjectName("cardMeta")
        head, hl = _card_header("Phụ đề", self.lbl_meta)
        self.chk_issues = QCheckBox("Chỉ hiện chỗ cần xem")
        self.chk_issues.setToolTip("Chỉ hiện những dòng máy không chắc về thời gian")
        self.chk_issues.stateChanged.connect(self.refresh_table)
        hl.addWidget(self.chk_issues)
        cl.addWidget(head)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty())

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "", "Bắt đầu", "Kết thúc", "Dài", "Nội dung"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        h = self.table.horizontalHeader()
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h.setHighlightSections(False)
        for i, w in enumerate([52, 34, 124, 124, 68]):
            self.table.setColumnWidth(i, w)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.table.itemChanged.connect(self.on_edit)
        self.stack.addWidget(self.table)
        cl.addWidget(self.stack, 1)
        split.addWidget(card)

        # ---- The van ban goc ----
        card2, cl2 = _card()
        hint = QLabel("dòng đang chọn được tô sáng"); hint.setObjectName("cardMeta")
        head2, _ = _card_header("Văn bản gốc", hint)
        cl2.addWidget(head2)
        self.text_view = QTextEdit(); self.text_view.setReadOnly(True)
        self.text_view.setFrameShape(QFrame.Shape.NoFrame)
        f = QFont(); f.setFamilies(["Inter", "Yu Gothic UI", "Microsoft YaHei UI", "Malgun Gothic", "Segoe UI"])
        f.setPixelSize(15)
        self.text_view.setFont(f)
        self.text_view.document().setDocumentMargin(14)
        self.text_view.setPlaceholderText("Kịch bản gốc sẽ hiện ở đây.")
        cl2.addWidget(self.text_view, 1)
        split.addWidget(card2)

        split.setSizes([800, 480])
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        wl.addWidget(split)
        return wrap

    def _build_empty(self):
        """Man hinh huong dan khi chua co phu de (thay cho bang den trong)."""
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(40, 30, 40, 40); lay.addStretch(2)
        self.empty_icon = QLabel(); self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty_icon)
        t = QLabel("Bắt đầu tạo phụ đề"); t.setObjectName("emptyTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(8); lay.addWidget(t)
        s = QLabel("Chữ trong phụ đề luôn là kịch bản gốc của bạn — máy chỉ dò mốc thời gian.")
        s.setObjectName("emptyText"); s.setAlignment(Qt.AlignmentFlag.AlignCenter); s.setWordWrap(True)
        lay.addWidget(s)
        lay.addSpacing(18)
        # 3 buoc canh TRAI trong mot khoi dat giua -> so 1-2-3 thang hang
        block = QWidget()
        steps = QVBoxLayout(block); steps.setContentsMargins(0, 0, 0, 0); steps.setSpacing(10)
        for n, txt in ((1, "Chọn file audio hoặc video"),
                       (2, "Chọn kịch bản gốc (.txt hoặc Word .docx) — không có vẫn chạy được ở chế độ phiên âm"),
                       (3, "Chọn ngôn ngữ rồi bấm “Chạy căn chỉnh”")):
            row = QHBoxLayout(); row.setSpacing(10)
            num = QLabel(str(n)); num.setObjectName("stepNum")
            lbl = QLabel(txt); lbl.setObjectName("emptyStep")
            row.addWidget(num); row.addWidget(lbl); row.addStretch(1)
            steps.addLayout(row)
        centre = QHBoxLayout()
        centre.addStretch(1); centre.addWidget(block); centre.addStretch(1)
        lay.addLayout(centre)
        lay.addStretch(3)
        return w

    def _build_player(self):
        bar = QFrame(); bar.setObjectName("playerbar")
        lay = QHBoxLayout(bar); lay.setContentsMargins(16, 10, 16, 10); lay.setSpacing(12)

        self.btn_play = QPushButton(); self.btn_play.setObjectName("playBtn")
        self.btn_play.setEnabled(False)
        self.btn_play.setIconSize(QSize(16, 16))
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setToolTip("Nghe dòng đang chọn (chưa căn chỉnh thì phát/tạm dừng cả file)")
        self.btn_play.clicked.connect(self.play_cue)
        lay.addWidget(self.btn_play)

        tcol = QVBoxLayout(); tcol.setSpacing(0)
        self.lbl_time = QLabel("00:00:00,000"); self.lbl_time.setObjectName("timeNow")
        self.lbl_total = QLabel("/ 00:00:00"); self.lbl_total.setObjectName("timeTotal")
        tcol.addWidget(self.lbl_time); tcol.addWidget(self.lbl_total)
        lay.addLayout(tcol)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.sliderReleased.connect(lambda: self.player.setPosition(self.slider.value()))
        lay.addWidget(self.slider, 1)

        # Chinh moc thoi gian cua dong dang chon: [-0,1s | +0,1s | dat tai day]
        self._nudge_btns = []
        for field, caption in (("start", "Bắt đầu"), ("end", "Kết thúc")):
            lay.addSpacing(4)
            lbl = QLabel(caption); lbl.setObjectName("segLabel")
            lay.addWidget(lbl)
            seg = QFrame(); seg.setObjectName("segment")
            sl = QHBoxLayout(seg); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)
            for k, (txt, d) in enumerate((("−0,1s", -0.1), ("+0,1s", +0.1))):
                b = QPushButton(txt)
                b.setToolTip(f"Dịch mốc {caption.lower()} {txt}")
                b.clicked.connect(lambda _, f=field, dd=d: self.nudge(f, dd))
                sl.addWidget(b); self._nudge_btns.append(b)
                sep = QFrame(); sep.setObjectName("segSep"); sl.addWidget(sep)
            b = QPushButton()
            b.setToolTip(f"Đặt mốc {caption.lower()} = vị trí đang phát")
            b.setIconSize(QSize(14, 14))
            b.clicked.connect(lambda _, f=field: self.grab_position(f))
            self._icon_btn(b, theme.G_PIN, "text2", 14)
            sl.addWidget(b); self._nudge_btns.append(b)
            lay.addWidget(seg)

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.positionChanged.connect(self.on_pos)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(lambda *_: self._update_play_icon())

        self.tick = QTimer(self); self.tick.setInterval(60)
        self.tick.timeout.connect(self._check_stop)
        return bar

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        sb.addPermanentWidget(self.progress)
        ver = QLabel(self._version_text())
        ver.setContentsMargins(0, 0, 8, 0)
        sb.addPermanentWidget(ver)

    @staticmethod
    def _version_text():
        try:
            from .. import __version__
            return f"v{__version__}"
        except Exception:
            return ""

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_session)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.pick_audio)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.pick_text)
        QShortcut(QKeySequence("Ctrl+Return"), self,
                  activated=lambda: self.btn_run.isEnabled() and self.run_align())
        QShortcut(QKeySequence("Ctrl+S"), self,
                  activated=lambda: self.btn_export.isEnabled() and self.export_srt())

    # ================================================================ sang / toi
    def toggle_theme(self):
        mode = "light" if self.pal["name"] == "dark" else "dark"
        self.cfg["theme"] = mode
        settings.save(self.cfg)
        self.pal = theme.apply(QApplication.instance(), mode)
        self._apply_icons()
        theme.set_title_bar_dark(self, self.pal["name"] == "dark")
        self.refresh_table()
        self.statusBar().showMessage("Đã chuyển sang chế độ " + ("sáng." if mode == "light" else "tối."), 3000)

    def _apply_icons(self):
        p = self.pal
        for btn, glyph, key, size in self._icons:
            # Nut chinh (nen dai mau) -> icon trang; nut thuong -> mau theo che do
            color = "#ffffff" if btn.objectName() == "primary" else p.get(key, key)
            btn.setIcon(theme.glyph_icon(glyph, color, size))
        dark = p["name"] == "dark"
        self.btn_theme.setIcon(theme.glyph_icon(theme.G_SUN if dark else theme.G_MOON, p["text2"], 16))
        self.btn_theme.setToolTip("Chuyển sang chế độ sáng" if dark else "Chuyển sang chế độ tối")
        for chip in (self.btn_audio, self.btn_text):
            chip.set_icon_color(p["accent_text"] if dark else p["accent"])
        self.empty_icon.setPixmap(theme.glyph_icon(theme.G_SUBTITLE, p["accent"], 44).pixmap(QSize(44, 44)))
        self._update_play_icon()

    # ================================================================ nut chinh: Chay -> Xuat
    def _emphasize_export(self, on):
        """
        Can chinh xong -> "Xuat SRT" thanh nut chinh (dai mau) + phat sang vai nhip de nguoi dung thay buoc
        tiep theo; "Chay can chinh" lui ve nut thuong. Chay lai -> doi nguoc.
        """
        self.btn_run.setObjectName("" if on else "primary")
        self.btn_export.setObjectName("primary" if on else "")
        for b in (self.btn_run, self.btn_export):
            b.style().unpolish(b); b.style().polish(b)
        self._apply_icons()
        self._stop_pulse()
        if on:
            eff = QGraphicsDropShadowEffect(self.btn_export)
            eff.setOffset(0, 0)
            eff.setColor(QColor(theme.BRAND_VIOLET))
            eff.setBlurRadius(0)
            self.btn_export.setGraphicsEffect(eff)
            an = QPropertyAnimation(eff, b"blurRadius", self)
            an.setDuration(1100)
            an.setLoopCount(4)                    # vai nhip roi tat, khong nhap nhay mai gay kho chiu
            an.setKeyValueAt(0.0, 0.0)
            an.setKeyValueAt(0.5, 34.0)
            an.setKeyValueAt(1.0, 0.0)
            an.setEasingCurve(QEasingCurve.Type.InOutSine)
            an.finished.connect(self._stop_pulse)
            self._pulse_anim = an
            an.start()

    def _stop_pulse(self):
        an = getattr(self, "_pulse_anim", None)
        if an is not None:
            self._pulse_anim = None
            an.stop()
        self.btn_export.setGraphicsEffect(None)

    def _update_play_icon(self):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setIcon(theme.glyph_icon(theme.G_PAUSE if playing else theme.G_PLAY, "#ffffff", 16))

    def showEvent(self, ev):
        # Luc dung widget, stylesheet chua ap nen fontMetrics tra ve phong mac
        # dinh — do luc do la hut. Den khi hien ra moi co phong that.
        super().showEvent(ev)
        theme.set_title_bar_dark(self, self.pal["name"] == "dark")
        self._size_lang_box()

    # ================================================================ ngon ngu
    def _fill_languages(self):
        """Chi do vao o chon nhung ngon ngu nguoi dung da tich — do tat ca 100 cai thi roi mat."""
        codes = list(self.cfg.get("languages") or [])
        cur = self.cfg.get("lang") or "ja"
        if cur not in codes:
            codes.insert(0, cur)      # ngon ngu dang dung luon phai co mat

        pinned, rest = all_languages()
        label_of = dict(pinned + rest)

        self.cb_lang.blockSignals(True)
        self.cb_lang.clear()
        for c in codes:
            self.cb_lang.addItem(label_of.get(c, c), c)
        i = self.cb_lang.findData(cur)
        self.cb_lang.setCurrentIndex(max(0, i))
        self.cb_lang.blockSignals(False)

        self._size_lang_box()

        comp = self.cb_lang.completer()
        if comp:
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def _size_lang_box(self):
        """
        Noi o chon ngon ngu cho vua nhan dai nhat.

        O nay sua duoc nen ben trong la mot QLineEdit: chu dai hon o thi no cuon
        ngang va an mat dau chuoi — "ja — Nhật (Japanese)" hien thanh
        "a — Nhật (Japanese)". Rong co dinh chi vua phong may minh; may khac
        phong/DPI khac la bi cat.
        """
        fm = self.cb_lang.fontMetrics()
        widest = max((fm.horizontalAdvance(self.cb_lang.itemText(k))
                      for k in range(self.cb_lang.count())), default=0)
        # +56: cho mui ten xo xuong va le trai/phai cua QLineEdit
        self.cb_lang.setMinimumWidth(min(widest + 56, 460))
        self._lang_home()

    def _lang_home(self):
        """Keo chu ve dau o — phong xa van bi cat khi nhan qua dai."""
        le = self.cb_lang.lineEdit()
        if le:
            le.setCursorPosition(0)
            le.home(False)

    def _remember_lang(self, *_):
        self._lang_home()
        code = self._lang_code()
        if code and code != self.cfg.get("lang"):
            self.cfg["lang"] = code
            settings.save(self.cfg)

    def configure_languages(self):
        dlg = LanguageDialog(self.cfg.get("languages"), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = dlg.selected() or list(settings.DEFAULTS["languages"])
        self.cfg["languages"] = chosen
        if self.cfg.get("lang") not in chosen:
            self.cfg["lang"] = chosen[0]
        settings.save(self.cfg)
        self._fill_languages()
        self.statusBar().showMessage(
            f"Đã lưu {len(chosen)} ngôn ngữ vào ô chọn.")

    # ================================================================ nap file
    def pick_audio(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Chọn audio", self.cfg.get("last_audio_dir", ""),
            "Audio/Video (*.mp3 *.wav *.m4a *.mp4 *.mkv);;Tất cả (*.*)")
        if not p:
            return
        if not self._confirm_discard("chọn audio mới"):
            return
        self._reset_result()
        self.cfg["last_audio_dir"] = os.path.dirname(p)
        settings.save(self.cfg)
        self.audio_path = p
        self.btn_audio.setText(os.path.basename(p))
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(p)))
        self.btn_play.setEnabled(True)   # nghe thu duoc ngay, khong cho align xong
        self._auto_text_for_audio(p)
        self._update_ready()

    # Kich ban nam CUNG thu muc voi audio thi tu nap. Ly do: nhieu du an dat ten kich ban
    # giong nhau (kich-ban.txt); chon tay tu "thu muc lan truoc" rat de nham sang du an khac
    # -> align hong hang loat (304/370 dong) ma nhin vao khong biet vi sao.
    TEXT_EXT = (".txt", ".docx", ".md")

    def _text_candidates(self, audio):
        d = os.path.dirname(audio)
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith(self.TEXT_EXT) and not f.startswith(("~$", "."))
                     and not any(k in f.lower() for k in ("bilingual", "song-ngu", "ghi-chu", "note", "readme", "prompt", "negative"))]
        except OSError:
            return []
        stem = os.path.splitext(os.path.basename(audio))[0].lower()

        def rank(f):
            n = os.path.splitext(os.path.basename(f))[0].lower()
            return (
                0 if n == stem else 1,                               # cung ten voi audio
                0 if n in ("kich-ban", "kichban", "script") else 1,  # ten kich ban quen dung
                0 if f.lower().endswith((".txt", ".docx")) else 1,   # .md xep sau
                1 if len(n) > 3 and n[-3] == "-" and n[-2:].isdigit() else 0,  # kich-ban-01: ban chia nho, de sau
                -os.path.getsize(f),                                 # ban day du nhat
            )
        return sorted(files, key=rank)

    def _auto_text_for_audio(self, audio):
        d = os.path.normcase(os.path.dirname(os.path.abspath(audio)))
        if self.text_path and os.path.normcase(os.path.dirname(os.path.abspath(self.text_path))) == d:
            return                                       # kich ban da cung thu muc -> giu nguyen
        cands = self._text_candidates(audio)
        if not cands:
            if self.text_path:                           # kich ban cu o thu muc KHAC -> bo, tranh lech
                self._clear_text()
                self.statusBar().showMessage(
                    "Kịch bản cũ nằm ở thư mục khác với audio — đã bỏ. Hãy chọn lại văn bản gốc.")
            return
        if self._load_text(cands[0], quiet=True):
            more = (f" (còn {len(cands) - 1} file khác cùng thư mục — bấm ô Văn bản gốc để đổi)"
                    if len(cands) > 1 else "")
            self.statusBar().showMessage(
                f"Đã tự nạp kịch bản cùng thư mục: {os.path.basename(cands[0])}{more}")

    # ================================================================ lam moi
    def _busy(self):
        return bool(self.worker and self.worker.isRunning())

    def _confirm_discard(self, action):
        """Co ket qua chua xuat SRT -> hoi truoc. Tra False neu nguoi dung huy."""
        if self._busy():
            QMessageBox.information(self, "Đang căn chỉnh",
                                    "Đang chạy căn chỉnh — đợi xong rồi hãy " + action + ".")
            return False
        if not (self.cues and self._dirty):
            return True
        r = QMessageBox.question(
            self, "Kết quả chưa lưu",
            f"Phụ đề hiện tại ({len(self.cues)} dòng) chưa được xuất SRT.\n"
            f"{action[0].upper() + action[1:]} sẽ xoá kết quả này. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return r == QMessageBox.StandardButton.Yes

    def _reset_result(self):
        """Xoa ket qua can chinh + trang thai trinh phat. Giu nguyen audio/kich ban."""
        self.player.stop()
        self._stop_at = None
        self.cues = []
        self.duration = 0.0
        self._dirty = False
        self.btn_run.setText("Chạy căn chỉnh")
        self.btn_export.setEnabled(False)
        self._emphasize_export(False)
        self.slider.setValue(0)
        self.lbl_time.setText(ts(0))
        self.text_view.setExtraSelections([])
        self.refresh_table()

    def new_session(self):
        """Lam video tiep theo: xoa sach audio, kich ban, ket qua."""
        if not self._confirm_discard("làm mới"):
            return
        self._reset_result()
        self.player.setSource(QUrl())
        self.audio_path = None
        self.btn_audio.setText(None)
        self.btn_play.setEnabled(False)
        self._clear_text()
        self.btn_run.setEnabled(False)
        self.statusBar().showMessage("Đã làm mới — chọn audio cho video tiếp theo (Ctrl+O).")

    def _clear_text(self):
        self.raw_text = ""
        self.text_path = None
        self.btn_text.setText(None)                      # về chữ gợi ý ban đầu
        self.text_view.setPlainText("")

    def pick_text(self):
        # Mo hop chon ngay tai thu muc cua audio (neu da co), khong phai thu muc lan truoc
        start = os.path.dirname(self.audio_path) if self.audio_path else self.cfg.get("last_text_dir", "")
        p, _ = QFileDialog.getOpenFileName(self, "Chọn văn bản gốc", start, textio.FILTER)
        if not p:
            return
        if self.cues and not self._confirm_discard("đổi kịch bản"):
            return
        self.cfg["last_text_dir"] = os.path.dirname(p)
        settings.save(self.cfg)
        self._reset_result()                   # cue cu duoc can theo kich ban cu -> bo
        self._load_text(p)
        self._update_ready()

    def _load_text(self, p, quiet=False):
        try:
            text = textio.load_text(p)
        except ValueError as e:
            if not quiet:
                QMessageBox.warning(self, "Không đọc được văn bản gốc", str(e))
            return False
        except OSError as e:
            if not quiet:
                QMessageBox.warning(self, "Không mở được file", f"{os.path.basename(p)}\n\n{e}")
            return False
        if not text.strip():
            if not quiet:
                QMessageBox.warning(self, "Văn bản gốc trống",
                                    f"Không thấy chữ nào trong {os.path.basename(p)}.")
            return False
        self.raw_text = text
        self.text_path = p
        self.btn_text.setText(os.path.basename(p))
        self.btn_text.value.setToolTip(p)                # di chuot vao thay DUONG DAN day du de soat nham thu muc
        self.text_view.setPlainText(self.raw_text)
        return True

    def _update_ready(self):
        # Chi can AUDIO la chay duoc. Khong co van ban goc thi chuyen sang phien am,
        # nhung se hoi lai truoc (xem run_align).
        self.btn_run.setEnabled(bool(self.audio_path))
        if self.audio_path and self.raw_text.strip():
            self.statusBar().showMessage("Sẵn sàng — bấm “Chạy căn chỉnh”.")
        elif self.audio_path:
            self.statusBar().showMessage(
                "Chưa có văn bản gốc — chạy sẽ chuyển sang chế độ phiên âm (chữ do máy nghe).")

    # ================================================================ chay align
    def run_align(self):
        import time
        self._remember_lang()

        model = self.cfg.get("model", "base")
        if not self.raw_text.strip():
            dlg = NoTextDialog(model, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            model = dlg.model_name()        # phien am phu thuoc hoan toan vao model

        self._emphasize_export(False)
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Đang căn chỉnh…")
        self.btn_export.setEnabled(False)
        self.progress.show()

        # stable-ts khong co hook bao tien do -> tu dem gio de nguoi dung biet
        # no dang chay chu khong treo.
        self._t0 = time.time()
        self._stage = "Đang chuẩn bị…"
        self._elapsed = QTimer(self)
        self._elapsed.setInterval(500)
        self._elapsed.timeout.connect(
            lambda: self.statusBar().showMessage(
                f"{self._stage}   ({time.time()-self._t0:.0f}s)"))
        self._elapsed.start()

        self.worker = AlignWorker(self.audio_path, self.raw_text,
                                  self._lang_code(), model)
        self.worker.progress.connect(self._on_stage)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def _lang_code(self):
        """
        Lay ma ngon ngu. O chon cho GO TAY nen khong the chi doc currentData() —
        currentData() van tra ve muc duoc chon truoc do, khong theo chu vua go.
        """
        txt = self.cb_lang.currentText().strip()
        idx = self.cb_lang.currentIndex()

        # Nguoi dung chon tu danh sach (chu khop y nhan cua muc dang chon)
        if idx >= 0 and txt == self.cb_lang.itemText(idx):
            d = self.cb_lang.itemData(idx)
            if d:
                return d

        # Bo trong -> giu lua chon cu
        if not txt:
            return self.cb_lang.itemData(idx) or "ja"

        # Go tay: thu theo ma truoc ('hi'), roi theo ten ('Thai', 'Nhat'…)
        code = code_from_label(txt)
        if self.cb_lang.findData(code) >= 0:
            return code
        i = self.cb_lang.findText(txt, Qt.MatchFlag.MatchContains)
        if i >= 0 and self.cb_lang.itemData(i):
            return self.cb_lang.itemData(i)

        # Khong co trong o chon nhung van la ma hop le cua Whisper -> chap nhan,
        # de nguoi dung go nhanh ma khong phai mo hop thoai cau hinh.
        pinned, rest = all_languages()
        valid = {c for c, _ in pinned + rest}
        if code in valid:
            return code
        low = txt.lower()
        for c, lbl in pinned + rest:
            if low in lbl.lower():
                return c
        return self.cb_lang.itemData(idx) or "ja"

    def closeEvent(self, ev):
        """Luu lua chon truoc khi dong — ke ca khi nguoi dung go tay chu khong chon."""
        if not self._confirm_discard("đóng SolaSub"):
            ev.ignore()
            return
        self.cfg["lang"] = self._lang_code()
        settings.save(self.cfg)
        super().closeEvent(ev)

    def _on_stage(self, msg):
        self._stage = msg

    def _stop_timer(self):
        t = getattr(self, "_elapsed", None)
        if t:
            t.stop()

    def on_done(self, cues, stats, duration):
        self.cues, self.duration = cues, duration
        self._dirty = True
        self._stop_timer()
        self.progress.hide()
        self.btn_run.setText("Chạy lại")
        self.btn_run.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_play.setEnabled(True)
        self._emphasize_export(True)
        self.refresh_table()
        bad = stats.get("_cue_co_van_de", 0)
        tot = stats.get("_tong_cue", 0)
        detail = ", ".join(f"{ISSUE_LABEL.get(k, k)}: {v}"
                           for k, v in sorted(stats.items()) if not k.startswith("_"))
        if stats.get("_che_do") == "phiên âm":
            head = (f"Xong (PHIÊN ÂM — chữ do máy nghe, hãy đọc soát lại toàn bộ) "
                    f"— {tot} cue")
        else:
            head = (f"Xong — {tot} cue, {bad} cần xem "
                    f"({100*bad/max(1,tot):.1f}%). Bấm “Xuất SRT” để lưu.")
        self.statusBar().showMessage(head + (f"  [{detail}]" if detail else ""))

    def on_failed(self, msg):
        self._stop_timer()
        self.progress.hide()
        self.btn_run.setText("Chạy căn chỉnh")
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Căn chỉnh thất bại", msg)
        self.statusBar().showMessage("Thất bại.")

    # ================================================================ bang cue
    def refresh_table(self):
        p = self.pal
        self.stack.setCurrentIndex(1 if self.cues else 0)
        n_issue = sum(1 for c in self.cues if c.get("issues"))
        self.lbl_meta.setText(
            f"{len(self.cues)} dòng · {n_issue} cần xem" if self.cues else "chưa có")

        only = self.chk_issues.isChecked()
        rows = [(i, c) for i, c in enumerate(self.cues)
                if not only or c.get("issues")]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        mono = QFont(); mono.setFamilies(["Cascadia Mono", "Consolas", "Inter"]); mono.setPixelSize(12)
        for r, (i, c) in enumerate(rows):
            issues = c.get("issues") or []
            bad = "align_hong" in issues
            mark = "✕" if bad else ("⚠" if issues else "")
            color = QColor(p["bad"] if bad else p["issue"] if issues else p["ok"])
            tint = QColor(0, 0, 0, 0)
            if issues:
                tint = _rgba(p["bad_bg"] if bad else p["issue_bg"])
            vals = [str(i + 1), mark, ts(c["start"]), ts(c["end"]),
                    f"{c['end']-c['start']:.2f}", c["text"].replace("\n", " ")]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                # Sua duoc: thoi gian (2,3) va noi dung (5). Cot # va Dai chi de xem.
                if col in (0, 1, 4):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col in (0, 4):
                        it.setForeground(QColor(p["dim"]))
                if col in (2, 3, 4):
                    it.setFont(mono)
                if col == 1:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col in (1, 5):
                    it.setForeground(color)
                if col == 1 and issues:
                    it.setToolTip(", ".join(ISSUE_LABEL.get(k, k) for k in issues))
                if issues:
                    it.setBackground(tint)
                it.setData(Qt.ItemDataRole.UserRole, i)
                self.table.setItem(r, col, it)
        self.table.blockSignals(False)

    def _current_index(self):
        it = self.table.currentItem()
        if it is None:
            return None
        return self.table.item(it.row(), 0).data(Qt.ItemDataRole.UserRole)

    def on_select(self):
        i = self._current_index()
        if i is None:
            return
        c = self.cues[i]
        self.player.setPosition(int(c["start"] * 1000))
        self._highlight(c["text"])

    def on_edit(self, item):
        i = item.data(Qt.ItemDataRole.UserRole)
        if i is None:
            return
        col = item.column()
        self._dirty = True
        if col == 5:
            self.cues[i]["text"] = item.text().strip()
        elif col in (2, 3):
            t = parse_ts(item.text())
            if t is None:
                self.statusBar().showMessage("Thời gian sai định dạng — dùng 00:01:23,450")
                self.refresh_table()
                return
            self._set_time(i, "start" if col == 2 else "end", t)
        else:
            return
        detect(self.cues, self.duration)
        self.refresh_table()

    def _set_time(self, i, field, value):
        """Dat moc thoi gian, kep trong gioi han hop le de khong chong lan cue ben canh."""
        self._dirty = True
        c = self.cues[i]
        lo = self.cues[i - 1]["end"] if i > 0 else 0.0
        hi = self.cues[i + 1]["start"] if i < len(self.cues) - 1 else self.duration
        value = max(lo, min(value, hi))
        if field == "start":
            c["start"] = min(value, c["end"] - 0.1)
        else:
            c["end"] = max(value, c["start"] + 0.1)

    def nudge(self, field, delta):
        """Dich moc thoi gian cua cue dang chon."""
        i = self._current_index()
        if i is None:
            return
        self._set_time(i, field, self.cues[i][field] + delta)
        detect(self.cues, self.duration)
        row = self.table.currentRow()
        self.refresh_table()
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)

    def grab_position(self, field):
        """Lay vi tri dang phat lam moc — tien nhat khi dang nghe de do."""
        i = self._current_index()
        if i is None:
            return
        self._set_time(i, field, self.player.position() / 1000.0)
        detect(self.cues, self.duration)
        row = self.table.currentRow()
        self.refresh_table()
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)
        self.statusBar().showMessage(
            f"Đã đặt {'bắt đầu' if field == 'start' else 'kết thúc'} = {ts(self.cues[i][field])}")

    def _highlight(self, snippet):
        """To sang cue dang chon trong khung van ban goc."""
        doc = self.text_view.toPlainText()
        key = snippet.replace("\n", "").strip()
        pos = doc.find(key[:24]) if key else -1
        cur = self.text_view.textCursor()
        cur.setPosition(max(0, pos))
        if pos >= 0:
            cur.setPosition(pos + len(key), QTextCursor.MoveMode.KeepAnchor)
        self.text_view.setTextCursor(cur)
        self.text_view.ensureCursorVisible()

    # ================================================================ phat am thanh
    def play_cue(self):
        if not self.audio_path:
            self.statusBar().showMessage("Chưa chọn file audio.")
            return
        # Chua co cue (chua chay align) -> cho nghe/tam dung ca file nhu may phat thuong
        i = self._current_index()
        if i is None:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            else:
                self._stop_at = None
                self.tick.stop()
                self.player.play()
            return
        c = self.cues[i]
        self._seek_to = int(c["start"] * 1000)
        self._stop_at = int(c["end"] * 1000)
        # Chua duoc phep dung: setPosition cua Qt la BAT DONG BO, position() ngay sau do
        # van la vi tri CU. Neu vi tri cu nam sau _stop_at thi se tam dung tuc thi
        # -> nguoi dung tuong nut hong. Chi bat cong tac dung khi da seek toi noi.
        self._armed = False
        self._arm_deadline = 0
        self.player.setPosition(self._seek_to)
        self.player.play()
        self.tick.start()

    def _check_stop(self):
        if self._stop_at is None:
            return
        pos = self.player.position()

        if not self._armed:
            self._arm_deadline += self.tick.interval()
            # Da nhay toi gan diem bat dau -> tu gio moi tinh chuyen dung
            if abs(pos - self._seek_to) < 1500:
                self._armed = True
            elif self._arm_deadline > 3000:
                # Seek khong an sau 3s (dinh dang la, file dang nap…) -> cu phat tiep,
                # tha nghe dai hon con hon im lang.
                self._armed = True
                self.statusBar().showMessage("Không nhảy đúng vị trí được — đang phát từ chỗ hiện tại.")
            return

        if pos >= self._stop_at:
            self.player.pause()
            self.tick.stop()
            self._stop_at = None

    def on_pos(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.lbl_time.setText(ts(ms / 1000.0))

    def _on_duration(self, d):
        self.slider.setRange(0, d)
        self.lbl_total.setText("/ " + ts(d / 1000.0).split(",")[0])

    # ================================================================ xuat
    def export_srt(self):
        self._stop_pulse()                 # da bam -> thoi nhap nhay (van giu la nut chinh)
        default =(os.path.splitext(self.audio_path)[0] + ".srt") if self.audio_path else "output.srt"
        p, _ = QFileDialog.getSaveFileName(self, "Lưu SRT", default, "SubRip (*.srt)")
        if not p:
            return
        n = write_srt(self.cues, p)
        self._dirty = False
        self.statusBar().showMessage(f"Đã lưu {n} cue vào {p}")


def _rgba(css):
    """'rgba(r,g,b,a)' hoac '#rrggbb' -> QColor."""
    css = css.strip()
    if css.startswith("rgba"):
        r, g, b, a = [x.strip() for x in css[css.index("(") + 1:css.index(")")].split(",")]
        return QColor(int(r), int(g), int(b), int(float(a) * 255))
    return QColor(css)

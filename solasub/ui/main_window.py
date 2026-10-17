"""
SolaSub — cua so chinh.

Luong lam viec: nap audio + van ban goc -> Chay can chinh -> chi duyet nhung cue
duoc khoanh -> xuat SRT. Chu trong cue LUON la van ban goc, nen khong phai sua chu;
viec duyet chi la kiem THOI GIAN o vai cho may khong chac.
"""
import io
import os

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QFont, QTextCursor
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
                             QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                             QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                             QSlider, QSplitter, QTableWidget, QTableWidgetItem,
                             QTextEdit, QToolBar, QVBoxLayout, QWidget)

from .. import settings
from ..languages import all_languages, code_from_label
from ..problems import detect
from ..srt import parse_ts, write_srt, ts
from .icon import app_icon
from .lang_dialog import LanguageDialog
from .notext_dialog import NoTextDialog
from .theme import COLOR_BAD, COLOR_DIM, COLOR_ISSUE, COLOR_OK, STYLE
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SolaSub — tạo phụ đề từ audio + văn bản gốc")
        self.resize(1280, 800)
        self.setStyleSheet(STYLE)
        ic = app_icon()
        if ic:
            self.setWindowIcon(ic)

        self.cfg = settings.load()
        self.audio_path = None
        self.text_path = None
        self.raw_text = ""
        self.cues = []
        self.duration = 0.0
        self.worker = None
        self._stop_at = None
        self._seek_to = 0
        self._armed = True
        self._arm_deadline = 0

        self._build_toolbar()
        self._build_body()
        self._build_player()
        self.statusBar().showMessage("Chọn file audio và văn bản gốc để bắt đầu.")

    # ---------- dung giao dien ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_audio = QPushButton("Chọn audio…")
        self.btn_audio.clicked.connect(self.pick_audio)
        tb.addWidget(self.btn_audio)

        self.btn_text = QPushButton("Chọn văn bản gốc…")
        self.btn_text.clicked.connect(self.pick_text)
        tb.addWidget(self.btn_text)
        tb.addSeparator()

        tb.addWidget(QLabel(" Ngôn ngữ "))
        self.cb_lang = QComboBox()
        self.cb_lang.setEditable(True)
        self.cb_lang.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cb_lang.setMinimumWidth(210)
        self._fill_languages()
        self.cb_lang.currentIndexChanged.connect(self._remember_lang)
        tb.addWidget(self.cb_lang)

        self.btn_lang_cfg = QPushButton("Cấu hình ngôn ngữ…")
        self.btn_lang_cfg.clicked.connect(self.configure_languages)
        tb.addWidget(self.btn_lang_cfg)
        tb.addSeparator()

        self.btn_run = QPushButton("Chạy căn chỉnh")
        self.btn_run.setObjectName("primary")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.run_align)
        tb.addWidget(self.btn_run)

        self.btn_export = QPushButton("Xuất SRT")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_srt)
        tb.addWidget(self.btn_export)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.chk_issues = QCheckBox("Chỉ hiện chỗ cần xem")
        self.chk_issues.stateChanged.connect(self.refresh_table)
        tb.addWidget(self.chk_issues)

    def _build_body(self):
        split = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "", "Bắt đầu", "Kết thúc", "Dài", "Nội dung"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        h = self.table.horizontalHeader()
        for i, w in enumerate([48, 30, 82, 82, 54]):
            self.table.setColumnWidth(i, w)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.table.itemChanged.connect(self.on_edit)
        split.addWidget(self.table)

        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Văn bản gốc — cue đang chọn được tô sáng"))
        self.text_view = QTextEdit(); self.text_view.setReadOnly(True)
        f = QFont("Yu Gothic UI", 12); self.text_view.setFont(f)
        rl.addWidget(self.text_view)
        split.addWidget(right)

        split.setSizes([780, 500])
        self.setCentralWidget(split)

    def _build_player(self):
        bar = QWidget(); lay = QHBoxLayout(bar); lay.setContentsMargins(10, 6, 10, 8)

        self.btn_play = QPushButton("▶  Nghe cue")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.play_cue)
        lay.addWidget(self.btn_play)

        # Chinh moc thoi gian cua cue dang chon
        for field, caption in (("start", "Bắt đầu"), ("end", "Kết thúc")):
            lay.addWidget(QLabel(f"   {caption}"))
            for lbl, d in (("−0,1s", -0.1), ("+0,1s", +0.1)):
                b = QPushButton(lbl)
                b.setObjectName("tiny")
                b.setMinimumWidth(54)
                b.setToolTip(f"Dịch mốc {caption.lower()} {lbl}")
                b.clicked.connect(lambda _, f=field, dd=d: self.nudge(f, dd))
                lay.addWidget(b)
            b = QPushButton("⟲ tại đây")
            b.setObjectName("tiny")
            b.setToolTip(f"Đặt mốc {caption.lower()} = vị trí đang phát")
            b.clicked.connect(lambda _, f=field: self.grab_position(f))
            lay.addWidget(b)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderReleased.connect(
            lambda: self.player.setPosition(self.slider.value()))
        lay.addWidget(self.slider, 1)

        self.lbl_time = QLabel("00:00:00,000")
        self.lbl_time.setMinimumWidth(96)
        lay.addWidget(self.lbl_time)

        self.progress = QProgressBar(); self.progress.setMaximumWidth(150)
        self.progress.setRange(0, 0); self.progress.hide()
        lay.addWidget(self.progress)

        player_bar = QToolBar()
        player_bar.setMovable(False)
        player_bar.addWidget(bar)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, player_bar)

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.positionChanged.connect(self.on_pos)
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, d))

        self.tick = QTimer(self); self.tick.setInterval(60)
        self.tick.timeout.connect(self._check_stop)

    # ---------- ngon ngu ----------
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

    def showEvent(self, ev):
        # Luc dung widget, stylesheet chua ap nen fontMetrics tra ve phong mac
        # dinh — do luc do la hut. Den khi hien ra moi co phong that.
        super().showEvent(ev)
        self._size_lang_box()

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

    # ---------- nap file ----------
    def pick_audio(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Chọn audio", self.cfg.get("last_audio_dir", ""),
            "Audio/Video (*.mp3 *.wav *.m4a *.mp4 *.mkv);;Tất cả (*.*)")
        if not p:
            return
        self.cfg["last_audio_dir"] = os.path.dirname(p)
        settings.save(self.cfg)
        self.audio_path = p
        self.btn_audio.setText(os.path.basename(p))
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(p)))
        self.btn_play.setEnabled(True)   # nghe thu duoc ngay, khong cho align xong
        self._update_ready()

    def pick_text(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Chọn văn bản gốc", self.cfg.get("last_text_dir", ""),
            "Văn bản (*.txt *.md);;Tất cả (*.*)")
        if not p:
            return
        self.cfg["last_text_dir"] = os.path.dirname(p)
        settings.save(self.cfg)
        try:
            self.raw_text = io.open(p, encoding="utf-8-sig").read()
        except UnicodeDecodeError:
            self.raw_text = io.open(p, encoding="shift_jis", errors="replace").read()
        self.text_path = p
        self.btn_text.setText(os.path.basename(p))
        self.text_view.setPlainText(self.raw_text)
        self._update_ready()

    def _update_ready(self):
        # Chi can AUDIO la chay duoc. Khong co van ban goc thi chuyen sang phien am,
        # nhung se hoi lai truoc (xem run_align).
        self.btn_run.setEnabled(bool(self.audio_path))
        if self.audio_path and self.raw_text.strip():
            self.statusBar().showMessage("Sẵn sàng — bấm “Chạy căn chỉnh”.")
        elif self.audio_path:
            self.statusBar().showMessage(
                "Chưa có văn bản gốc — chạy sẽ chuyển sang chế độ phiên âm (chữ do máy nghe).")

    # ---------- chay align ----------
    def run_align(self):
        import time
        self._remember_lang()

        model = self.cfg.get("model", "base")
        if not self.raw_text.strip():
            dlg = NoTextDialog(model, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            model = dlg.model_name()        # phien am phu thuoc hoan toan vao model

        self.btn_run.setEnabled(False)
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
        self._stop_timer()
        self.progress.hide()
        self.btn_run.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_play.setEnabled(True)
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
                    f"({100*bad/max(1,tot):.1f}%).")
        self.statusBar().showMessage(head + (f"  [{detail}]" if detail else ""))

    def on_failed(self, msg):
        self._stop_timer()
        self.progress.hide()
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Căn chỉnh thất bại", msg)
        self.statusBar().showMessage("Thất bại.")

    # ---------- bang cue ----------
    def refresh_table(self):
        only = self.chk_issues.isChecked()
        rows = [(i, c) for i, c in enumerate(self.cues)
                if not only or c.get("issues")]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, (i, c) in enumerate(rows):
            issues = c.get("issues") or []
            mark = "✕" if "align_hong" in issues else ("⚠" if issues else "")
            color = QColor(COLOR_BAD if "align_hong" in issues
                           else COLOR_ISSUE if issues else COLOR_OK)
            vals = [str(i + 1), mark, ts(c["start"]), ts(c["end"]),
                    f"{c['end']-c['start']:.2f}", c["text"].replace("\n", " ")]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                # Sua duoc: thoi gian (2,3) va noi dung (5). Cot # va Dai chi de xem.
                if col in (0, 1, 4):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col in (0, 4):
                        it.setForeground(QColor(COLOR_DIM))
                if col in (1, 5):
                    it.setForeground(color)
                if col == 1 and issues:
                    it.setToolTip(", ".join(ISSUE_LABEL.get(k, k) for k in issues))
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

    # ---------- phat am thanh ----------
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

    # ---------- xuat ----------
    def export_srt(self):
        default = (os.path.splitext(self.audio_path)[0] + ".srt") if self.audio_path else "output.srt"
        p, _ = QFileDialog.getSaveFileName(self, "Lưu SRT", default, "SubRip (*.srt)")
        if not p:
            return
        n = write_srt(self.cues, p)
        self.statusBar().showMessage(f"Đã lưu {n} cue vào {p}")

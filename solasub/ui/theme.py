"""
Giao dien SolaSub: 2 che do SANG / TOI, mau lay theo icon (xanh duong -> cham -> tim).

- Stylesheet dat o muc QApplication -> moi cua so + hop thoai doi theo cung luc.
- Icon dung font bieu tuong co san cua Windows (Segoe Fluent Icons / Segoe MDL2 Assets), to mau theo che do.
- Thanh tieu de Windows cung doi sang/toi (DWM), khong thi app sang ma vien cua so van den.
"""
import os

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

# Mau nhan lay tu icon: xanh duong -> cham -> tim
BRAND_BLUE = "#3b82f6"
BRAND_INDIGO = "#4f46e5"
BRAND_VIOLET = "#7c3aed"

DARK = {
    "name": "dark",
    "bg": "#0e1020",          # nen cua so
    "surface": "#161a2e",     # the
    "surface2": "#1d2239",    # o nhap, nut thuong
    "hover": "#252b47",
    "border": "#262b45",
    "border2": "#323859",
    "text": "#e7e9f7",
    "text2": "#a9aecb",
    "dim": "#6e7394",
    "accent": "#6366f1",
    "accent_text": "#a5b4fc",
    "select": "rgba(99,102,241,0.30)",
    "select_text": "#ffffff",
    "row_alt": "rgba(255,255,255,0.018)",
    "ok": "#e7e9f7",
    "issue": "#fbbf24",
    "bad": "#f87171",
    "issue_bg": "rgba(251,191,36,0.12)",
    "bad_bg": "rgba(248,113,113,0.14)",
    "track": "#2a2f4d",
    "disabled_text": "#5c6182",
}

LIGHT = {
    "name": "light",
    "bg": "#f3f4fa",
    "surface": "#ffffff",
    "surface2": "#f5f6fb",
    "hover": "#eceefa",
    "border": "#e3e5f1",
    "border2": "#d4d7e8",
    "text": "#1a1c2e",
    "text2": "#565b78",
    "dim": "#8d92ad",
    "accent": "#4f46e5",
    "accent_text": "#4338ca",
    "select": "rgba(79,70,229,0.13)",
    "select_text": "#1a1c2e",
    "row_alt": "rgba(30,35,80,0.022)",
    "ok": "#1a1c2e",
    "issue": "#b45309",
    "bad": "#dc2626",
    "issue_bg": "rgba(245,158,11,0.14)",
    "bad_bg": "rgba(220,38,38,0.10)",
    "track": "#e1e3f0",
    "disabled_text": "#a7abc2",
}

_current = DARK


def palette():
    return _current


def system_prefers_dark() -> bool:
    """Doc che do mau cua Windows (Cai dat > Ca nhan hoa > Mau). Khong doc duoc -> toi."""
    if os.name != "nt":
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return True


def resolve(mode: str) -> dict:
    """'dark' | 'light' | 'system' -> bang mau."""
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    return DARK if system_prefers_dark() else LIGHT


def build_style(p: dict) -> str:
    grad = (f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_BLUE}, "
            f"stop:0.55 {BRAND_INDIGO}, stop:1 {BRAND_VIOLET})")
    grad_hover = (f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4b8ff7, "
                  f"stop:0.55 #5b53ea, stop:1 #8a4df0)")
    check = _check_svg()
    chevron = _chevron_svg(p['text2'])
    return f"""
* {{ font-family: 'Inter','Segoe UI',sans-serif; font-size: 12.5px; color: {p['text']}; outline: none; }}
/* THU TU QUAN TRONG: cung do uu tien thi quy tac DUNG SAU thang. 'QWidget' khop ca QMainWindow/QDialog,
   nen phai dat TRUOC; truoc day dat sau -> nen cua so + hop thoai bi xoa thanh trong suot -> hien DEN. */
QWidget {{ background: transparent; }}
QMainWindow, QDialog {{ background: {p['bg']}; }}
QToolTip {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border2']};
            border-radius: 6px; padding: 5px 8px; }}

/* ---- Khung chinh ---- */
QFrame#appbar {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}
QLabel#brandSola {{ color: {p['accent']}; font-size: 17px; font-weight: 700; }}
QLabel#brandSub  {{ color: {p['text']};   font-size: 17px; font-weight: 700; }}
QLabel#brandTag  {{ color: {p['dim']}; font-size: 12px; }}
QFrame#workbar {{ background: {p['bg']}; }}
QWidget#root {{ background: {p['bg']}; }}
QFrame#card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QLabel#cardTitle {{ font-size: 13.5px; font-weight: 600; color: {p['text']}; }}
QLabel#cardMeta  {{ color: {p['dim']}; font-size: 12px; }}
QLabel#hint, QLabel#cardHint {{ color: {p['text2']}; }}
QLabel#stepNum {{ background: {p['select']}; color: {p['accent_text']}; border-radius: 10px;
                  font-size: 11px; font-weight: 700; min-width: 20px; max-width: 20px;
                  min-height: 20px; max-height: 20px; qproperty-alignment: AlignCenter; }}

/* O chon file (bam ca o) */
QFrame#fileChip {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QFrame#fileChip:hover {{ border-color: {p['accent']}; background: {p['hover']}; }}
QFrame#fileChip[filled="true"] {{ border-color: {p['border2']}; }}
QLabel#chipCaption {{ color: {p['dim']}; font-size: 11px; font-weight: 600; }}
QLabel#chipValue {{ color: {p['text']}; font-size: 13px; font-weight: 600; }}
QLabel#chipValue[empty="true"] {{ color: {p['text2']}; font-weight: 500; }}

/* ---- Nut ---- */
QPushButton {{ background: {p['surface2']}; border: 1px solid {p['border2']}; border-radius: 8px;
               padding: 7px 14px; color: {p['text']}; font-weight: 500; }}
QPushButton:hover {{ background: {p['hover']}; }}
QPushButton:pressed {{ background: {p['border']}; }}
QPushButton:disabled {{ color: {p['disabled_text']}; background: {p['surface2']}; border-color: {p['border']}; }}
QPushButton#primary {{ background: {grad}; border: none; color: #ffffff; font-weight: 600; padding: 8px 18px; }}
QPushButton#primary:hover {{ background: {grad_hover}; }}
QPushButton#primary:disabled {{ background: {p['track']}; color: {p['disabled_text']}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; padding: 6px 8px; }}
QPushButton#ghost:hover {{ background: {p['hover']}; border-color: {p['border']}; }}
QPushButton#iconBtn {{ background: transparent; border: 1px solid {p['border']}; border-radius: 8px;
                       padding: 6px; min-width: 20px; }}
QPushButton#iconBtn:hover {{ background: {p['hover']}; border-color: {p['border2']}; }}
QPushButton#iconBtn:checked {{ background: {p['select']}; border-color: {p['accent']}; }}
QPushButton#playBtn {{ background: {grad}; border: none; border-radius: 19px;
                       min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px; padding: 0; }}
QPushButton#playBtn:hover {{ background: {grad_hover}; }}
QPushButton#playBtn:disabled {{ background: {p['track']}; }}
/* Nhom nut dich moc thoi gian: dinh lien nhau nhu mot o */
QFrame#segment {{ background: {p['surface2']}; border: 1px solid {p['border2']}; border-radius: 8px; }}
QFrame#segment QPushButton {{ background: transparent; border: none; border-radius: 0; padding: 6px 9px;
                              font-weight: 600; font-size: 12px; }}
QFrame#segment QPushButton:hover {{ background: {p['hover']}; }}
QFrame#segment QPushButton:disabled {{ color: {p['disabled_text']}; }}
QFrame#segSep {{ background: {p['border2']}; min-width: 1px; max-width: 1px; }}
QLabel#segLabel {{ color: {p['text2']}; font-size: 12px; font-weight: 600; }}

/* ---- O nhap ---- */
QComboBox, QLineEdit {{ background: {p['surface2']}; border: 1px solid {p['border2']}; border-radius: 8px;
                        padding: 6px 10px; min-height: 18px; selection-background-color: {p['accent']};
                        selection-color: #ffffff; }}
QComboBox#chipCombo {{ padding: 3px 8px; min-height: 16px; }}
QComboBox:hover, QLineEdit:hover {{ border-color: {p['accent']}; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBox QAbstractItemView {{ background: {p['surface']}; border: 1px solid {p['border2']};
                               selection-background-color: {p['select']}; selection-color: {p['select_text']};
                               outline: none; padding: 4px; }}

/* ---- Bang phu de ---- */
QTableWidget {{ background: {p['surface']}; border: none; gridline-color: transparent;
                alternate-background-color: {p['row_alt']}; selection-background-color: {p['select']};
                selection-color: {p['select_text']}; }}
QTableWidget::item {{ padding: 4px 8px; border: none; border-bottom: 1px solid {p['border']}; }}
QTableWidget::item:selected {{ background: {p['select']}; color: {p['select_text']};
                               border: none; border-bottom: 1px solid {p['border']}; }}
QTableWidget::item:focus {{ border: none; border-bottom: 1px solid {p['border']}; outline: none; }}
QTableView {{ outline: 0; }}
QHeaderView {{ background: {p['surface']}; }}
QHeaderView::section {{ background: {p['surface']}; border: none; border-bottom: 1px solid {p['border2']};
                        padding: 8px 8px; font-weight: 600; font-size: 11.5px; color: {p['dim']}; }}
QTableCornerButton::section {{ background: {p['surface']}; border: none; }}

QTextEdit, QPlainTextEdit {{ background: {p['surface']}; border: none; padding: 4px 6px;
                             selection-background-color: {p['select']}; selection-color: {p['select_text']}; }}
QListWidget {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ padding: 6px 6px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {p['hover']}; }}

/* ---- Thanh cuon mong ---- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border2']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['dim']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border2']}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- Trinh phat ---- */
QFrame#playerbar {{ background: {p['surface']}; border-top: 1px solid {p['border']}; }}
QLabel#timeNow {{ font-size: 13px; font-weight: 600; color: {p['text']}; }}
QLabel#timeTotal {{ font-size: 12px; color: {p['dim']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {p['track']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {grad}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
                              background: #ffffff; border: 2px solid {p['accent']}; }}

QProgressBar {{ background: {p['track']}; border: none; border-radius: 3px; max-height: 6px; min-width: 140px; }}
QProgressBar::chunk {{ background: {grad}; border-radius: 3px; }}

QStatusBar {{ background: {p['bg']}; border-top: 1px solid {p['border']}; color: {p['text2']};
              padding-left: 10px; min-height: 26px; }}
QStatusBar QLabel {{ color: {p['text2']}; }}
QStatusBar::item {{ border: none; }}

QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;
                        border: 1px solid {p['border2']}; background: {p['surface2']}; }}
QCheckBox::indicator:hover {{ border-color: {p['accent']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: url({check}); }}
QListWidget::indicator {{ width: 16px; height: 16px; border-radius: 4px;
                          border: 1px solid {p['border2']}; background: {p['surface2']}; }}
QListWidget::indicator:hover {{ border-color: {p['accent']}; }}
QListWidget::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: url({check}); }}
QSplitter::handle {{ background: transparent; width: 10px; }}

/* Hop thoai khong co van ban goc */
QLabel#warnTitle {{ font-size: 14px; font-weight: 600; color: {p['issue']}; }}

/* Man hinh trong (chua co phu de) */
QLabel#emptyTitle {{ font-size: 18px; font-weight: 700; color: {p['text']}; }}
QLabel#emptyText {{ color: {p['text2']}; font-size: 13px; }}
QLabel#emptyStep {{ color: {p['text']}; font-size: 13px; }}
"""


def _ui_svg(name: str, path_d: str, color: str, stroke: float) -> str:
    """
    Ghi 1 file SVG nho (1 net ve) cho stylesheet (plugin qsvg co san trong ban dong goi).
    Ten file kem ma mau -> moi che do sang/toi mot file rieng.
    Tra ve duong dan dung dau '/' (stylesheet khong nhan '\\').
    """
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "SolaSub-ui")
    p = os.path.join(d, f"{name}-{color.lstrip('#')}.svg")
    if not os.path.exists(p):
        try:
            os.makedirs(d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">'
                        f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                        'stroke-linecap="round" stroke-linejoin="round"/></svg>')
        except OSError:
            return ""
    return p.replace("\\", "/")


def _check_svg() -> str:
    """
    Dau tick trang cho o duoc chon. Tu tao kieu cho o tick (::indicator) la Qt BO LUON dau tick mac dinh ->
    o da tick chi con o vuong to mau.
    """
    return _ui_svg("check", "M3.6 8.4 6.6 11.3 12.4 4.9", "#ffffff", 2.1)


def _chevron_svg(color: str) -> str:
    """Mui ten combobox. Tu tao kieu cho ::drop-down la Qt BO LUON mui ten mac dinh (giong dau tick o tren)."""
    return _ui_svg("chevron", "M4.5 6.2 8 9.7 11.5 6.2", color, 1.7)


def apply(app, mode: str) -> dict:
    """Dat che do mau cho toan app. Tra ve bang mau dang dung."""
    global _current
    _current = resolve(mode)
    # Fusion: style trung tinh cua Qt, an khop nhat voi stylesheet va GIONG NHAU tren Win10/Win11.
    # Style mac dinh "windows11" (Qt 6.7+) ve thanh danh dau chon len TUNG O -> dong dang chon co vach doc.
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    app.setStyleSheet(build_style(_current))
    return _current


def set_title_bar_dark(widget, dark: bool) -> None:
    """Thanh tieu de Windows 10 (20H1+) / 11 doi sang-toi theo app (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):         # 20: Win10 2004+/Win11; 19: ban Win10 cu hon
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:
        pass


# ---------------------------------------------------------------- icon bang font bieu tuong Windows
G_AUDIO = ""       # Audio
G_DOC = ""         # Document
G_GLOBE = ""       # Globe
G_SETTINGS = ""    # Settings
G_PLAY = ""
G_PAUSE = ""
G_SAVE = ""        # Save
G_RUN = ""         # LightningBolt
G_FILTER = ""
G_SUN = ""         # Brightness
G_MOON = ""        # QuietHours
G_SUBTITLE = ""    # ClosedCaption (Fluent) / CC
G_WARN = ""
G_PIN = ""         # Location (dat tai day)

_icon_family = None


def icon_family() -> str:
    global _icon_family
    if _icon_family is None:
        fams = set(QFontDatabase.families())
        _icon_family = "Segoe Fluent Icons" if "Segoe Fluent Icons" in fams else "Segoe MDL2 Assets"
    return _icon_family


def glyph_icon(glyph: str, color: str, size: int = 16) -> QIcon:
    """Ve 1 ky tu bieu tuong thanh QIcon (2 do phan giai cho man hinh 100% va 200%)."""
    icon = QIcon()
    for scale in (1, 2):
        px = QPixmap(size * scale, size * scale)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        f = QFont(icon_family())
        f.setPixelSize(int(size * scale * 0.82))
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(QRectF(0, 0, size * scale, size * scale), int(Qt.AlignmentFlag.AlignCenter), glyph)
        p.end()
        px.setDevicePixelRatio(scale)
        icon.addPixmap(px)
    return icon

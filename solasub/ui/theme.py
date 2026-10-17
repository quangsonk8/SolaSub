"""Theme toi — lay bang mau tu ban SolaTTS Python de hai cong cu nhin cung mot he."""

STYLE = """
* { font-family: 'Inter','Segoe UI',sans-serif; font-size: 12px; color: #d4d4f0; outline: none; }
QMainWindow, QDialog { background: #0a0a18; }
QWidget { background: transparent; }

QToolBar { background: rgba(6,6,16,0.85); border-bottom: 1px solid rgba(255,255,255,0.05);
           padding: 6px; spacing: 6px; }

QPushButton { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.09);
              border-radius: 6px; padding: 6px 14px; }
QPushButton:hover    { background: rgba(255,255,255,0.11); }
QPushButton:disabled { color: #5a5a72; background: rgba(255,255,255,0.03); }
QPushButton#primary  { background: #4f46e5; border-color: #6366f1; color: #fff; font-weight: 600; }
QPushButton#primary:hover    { background: #6366f1; }
QPushButton#primary:disabled { background: #2a2a44; color: #6b6b85; }

/* Nut nho (dich moc thoi gian): padding mac dinh 14px hai ben se nuot mat chu */
QPushButton#tiny { padding: 5px 6px; font-weight: 600; font-size: 12px; }

QComboBox { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.09);
            border-radius: 6px; padding: 5px 10px; min-width: 90px; }
QComboBox QAbstractItemView { background: #15152a; selection-background-color: #4f46e5;
                              border: 1px solid rgba(255,255,255,0.1); }

QTableWidget { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
               border-radius: 8px; gridline-color: rgba(255,255,255,0.05); }
QTableWidget::item { padding: 5px 6px; border: none; }
QTableWidget::item:selected { background: rgba(79,70,229,0.45); }
QHeaderView::section { background: rgba(255,255,255,0.05); border: none; padding: 7px 6px;
                       border-right: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #a8a8c8; }

QTextEdit, QPlainTextEdit { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
                            border-radius: 8px; padding: 10px; line-height: 170%; }

QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,0.10); border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -5px 0; border-radius: 7px; background: #6366f1; }
QSlider::sub-page:horizontal { background: #4f46e5; border-radius: 2px; }

QProgressBar { background: rgba(255,255,255,0.06); border: none; border-radius: 3px;
               height: 6px; text-align: center; }
QProgressBar::chunk { background: #4f46e5; border-radius: 3px; }

QStatusBar { background: rgba(6,6,16,0.85); border-top: 1px solid rgba(255,255,255,0.05); color: #9a9ab8; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px;
                       border: 1px solid rgba(255,255,255,0.22); background: rgba(255,255,255,0.05); }
QCheckBox::indicator:checked { background: #4f46e5; border-color: #6366f1; }
QSplitter::handle { background: rgba(255,255,255,0.05); width: 3px; }
QLabel#hint { color: #8a8aa8; }
"""

# Mau danh dau trong bang
COLOR_OK = "#d4d4f0"
COLOR_ISSUE = "#fbbf24"      # vang — can xem lai
COLOR_BAD = "#f87171"        # do — align hong
COLOR_DIM = "#7a7a95"

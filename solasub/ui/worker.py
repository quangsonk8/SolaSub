"""Chay align tren luong rieng — 2 tieng audio mat ~35s, khong duoc dong bang giao dien."""
from PyQt6.QtCore import QThread, pyqtSignal

from ..align import load_model, align_words, build_cues, transcribe_words
from ..problems import detect
from ..srt import audio_duration
from ..subtitle import normalize


class AlignWorker(QThread):
    progress = pyqtSignal(str)          # thong bao tien do
    done = pyqtSignal(list, dict, float)  # cues, stats, duration
    failed = pyqtSignal(str)

    # Model giu lai giua cac lan chay — nap lai moi lan rat phi
    _model = None
    _model_name = None
    _device = None

    def __init__(self, audio, text, lang="ja", model="base", device=None):
        super().__init__()
        self.audio, self.raw_text = audio, text
        self.lang, self.model_name, self.device = lang, model, device

    def run(self):
        try:
            text = normalize(self.raw_text)
            # Khong co van ban goc -> chuyen sang che do PHIEN AM (chu do Whisper nghe ra)
            transcribe_mode = not text

            self.progress.emit("Dang do thoi luong audio…")
            dur = audio_duration(self.audio)
            if dur <= 0:
                self.failed.emit("Khong doc duoc audio (ffmpeg loi?)."); return

            cls = AlignWorker
            if cls._model is None or cls._model_name != self.model_name:
                self.progress.emit(f"Dang nap model {self.model_name}…")
                cls._model, cls._device = load_model(self.model_name, self.device)
                cls._model_name = self.model_name

            if transcribe_mode:
                self.progress.emit(
                    f"Đang phiên âm ({dur/60:.0f} phút audio, {cls._device})… "
                    f"chậm hơn căn chỉnh nhiều")
                stream, text = transcribe_words(cls._model, self.audio, self.lang)
                if not text.strip():
                    self.failed.emit("Không nghe được chữ nào từ audio."); return
                text = normalize(text)
            else:
                self.progress.emit(
                    f"Đang căn chỉnh ({dur/60:.0f} phút audio, {cls._device})… "
                    f"khoảng {max(5, int(dur/200))}s")
                stream = align_words(cls._model, self.audio, text, self.lang, status=self.progress.emit)

            self.progress.emit("Đang chia cue và áp luật phụ đề…")
            cues = build_cues(stream, text, dur)
            for c in cues:
                c["transcribed"] = transcribe_mode
            stats = detect(cues, dur)
            stats["_che_do"] = "phiên âm" if transcribe_mode else "căn chỉnh"
            self.done.emit(cues, stats, dur)
        except Exception as e:           # noqa: BLE001 — bao loi len UI thay vi crash
            import traceback
            self.failed.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[-800:]}")

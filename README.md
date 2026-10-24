<div align="center">

<img src="assets/solasub.png" width="120" alt="SolaSub">

# SolaSub

**Tạo phụ đề đúng giờ từ audio + kịch bản gốc của bạn.**

Miễn phí · Không cần tài khoản · Chạy hoàn toàn trên máy bạn

[Tải về](../../releases/latest) · [Cách hoạt động](#cách-hoạt-động) · [Dựng từ mã nguồn](#dựng-từ-mã-nguồn)

</div>

---

## Vấn đề

Bạn có file audio và có sẵn kịch bản. Việc còn lại chỉ là biết **câu nào vang lên ở giây thứ mấy**.

Hai cách làm phổ biến đều hỏng theo cách riêng:

- **Ước lượng theo số ký tự rồi bám khoảng lặng** — nhanh nhưng trôi dần. Trên một file 2 tiếng, cách này lệch trung vị 23 giây, chỗ tệ nhất 39 giây; 98% số dòng sai quá 3 giây. Phụ đề hiện trước hoặc sau lời thoại cả chục giây.
- **Để máy nghe rồi gõ lại (phiên âm)** — đúng giờ, nhưng chữ thì sai. Tên riêng, số, thuật ngữ, chữ Hán sai liên tục. Bạn vẫn phải dò lại từng dòng.

## Cách SolaSub làm

SolaSub dùng **forced alignment**: nạp đúng kịch bản của bạn vào Whisper và chỉ hỏi nó một câu — *từ này nằm ở giây thứ mấy?*

Whisper **không** được phép viết lại chữ. Chữ trong file SRT luôn là bản gốc của bạn, từng ký tự.

Đo trên file thật, cùng một audio:

| | Đúng giờ | Độ trễ trung vị |
|---|---|---|
| Ước lượng theo ký tự | 40% | +0,977 s |
| **SolaSub (forced alignment)** | **93%** | **+0,073 s** |

Vì chữ chắc chắn đúng, SolaSub chỉ khoanh đỏ vài chỗ đáng ngờ để bạn liếc qua, thay vì bắt bạn đọc soát toàn bộ.

## Tính năng

- **Chữ đúng 100%** — lấy thẳng từ kịch bản của bạn, không qua nhận dạng
- **Kịch bản dạng .txt hoặc Word .docx** — với Word, tự bỏ chữ phiên âm furigana, chữ đã xoá khi theo dõi thay đổi và khung văn bản trùng lặp
- **Khung đối chiếu** — bảng phụ đề bên trái, bản gốc bên phải, chọn dòng nào thì bản gốc tô sáng dòng đó
- **Nghe thử từng dòng** — bấm là audio nhảy đúng đoạn và tự dừng ở cuối dòng
- **Nhích thời gian** — nút −0,1s / +0,1s, hoặc gõ thẳng mốc giờ
- **Tự khoanh chỗ cần xem** — độ tin cậy thấp, đọc quá nhanh, hở quá lớn, dòng quá dài/ngắn, tràn dòng
- **Cắt dòng theo chuẩn phụ đề phim** — tối đa 2 dòng, 42 ký tự (CJK 20), CPS ≤ 17 (CJK ≤ 9), 1–7 giây mỗi dòng
- **Hiểu tiếng Nhật/Trung** — áp dụng cấm ngắt dòng (禁則処理), không cắt giữa từ, không bỏ trợ từ lạc sang dòng sau
- **100 ngôn ngữ** — lấy thẳng từ Whisper; tự chọn những thứ tiếng hay dùng để hiện trong ô chọn
- **Không có kịch bản vẫn chạy được** — chuyển sang chế độ phiên âm, kèm cảnh báo rõ chất lượng khác thế nào
- **Chế độ sáng / tối** — lần đầu theo cài đặt Windows, bấm nút góc trên để đổi, app tự nhớ
- **Mở nhanh, có màn hình khởi động** — hiện ngay khi bấm, báo đang nạp gì; bấm thêm lần nữa không mở bản thứ hai

## Tải về

Hai bản ở trang [Releases](../../releases/latest). Cùng một phần mềm, chỉ khác bước cuối:

| Bản | Dung lượng | Dùng khi |
|---|---|---|
| **SolaSub_Setup_CPU.exe** | 330 MB (cài ra ~1,2 GB) | Máy không có card NVIDIA |
| **SolaSub_Setup_GPU.exe** | 330 MB + tải thêm ~2,4 GB | Máy có card NVIDIA |

Bản GPU **không đóng gói sẵn CUDA**. Ở bước cuối của trình cài có một ô tick để tải gói tăng tốc về — tick thì tải, không tick thì vẫn chạy bằng CPU bình thường. Làm vậy để người không có card NVIDIA khỏi phải tải thừa 2,4 GB.

Cài **theo từng người dùng**, không cần quyền quản trị, vào `%LocalAppData%\Programs\SolaSub`.

> **SmartScreen sẽ cảnh báo** "Windows protected your PC" vì bộ cài chưa ký số. Bấm *More info* → *Run anyway*.

### Yêu cầu

- Windows 10 phiên bản 1703 trở lên, hoặc Windows 11 (64-bit)
- 1,2 GB đĩa trống (bản CPU) hoặc 4,7 GB (bản GPU có CUDA)
- **Không** cần cài Python, ffmpeg hay Visual C++ Redistributable — tất cả nằm trong bộ cài

Đã kiểm chứng trên Windows Sandbox sạch hoàn toàn: không Python, không ffmpeg, không VC++ Redist. Cài 49 giây, chạy được ngay.

### Tốc độ

Đo trên file audio 2 phút 18 giây:

| | Nhanh gấp | 2 tiếng audio mất |
|---|---|---|
| CPU (máy để bàn) | 22,8× | ~5 phút |
| CPU (máy yếu / máy ảo) | 8× | ~15 phút |
| GPU (RTX 4060 Ti) | ~10× so với CPU | ~35 giây |

## Cách dùng

1. **Chọn audio** — mp3, wav, m4a, mp4, mkv
2. **Chọn văn bản gốc** — file `.txt` mã UTF-8 đựng kịch bản
3. **Chọn ngôn ngữ**
4. **Chạy căn chỉnh** — lần chạy đầu mất thêm vài giây để nạp mô hình
5. **Soát những dòng được khoanh đỏ** — nghe thử, nhích giờ nếu cần
6. **Xuất SRT**

Không có file kịch bản thì bỏ qua bước 2; tool sẽ hỏi lại và cho chọn mô hình nhận dạng lớn hơn.

## Cách hoạt động

```
audio ──┐
        ├─► Whisper align() ──► từng từ kèm mốc giây
kịch bản ┘                              │
                                        ▼
                      ánh xạ ký tự → thời gian (chính xác tuyệt đối,
                      vì align() giữ nguyên văn bản đầu vào)
                                        ▼
                      cắt câu theo chuẩn phụ đề phim
                      (độ dài dòng · tốc độ đọc · cấm ngắt CJK)
                                        ▼
                      dò chỗ đáng ngờ ──► SRT
```

Điểm mấu chốt: `align()` **giữ nguyên** văn bản bạn nạp vào — đo được 608 ký tự vào, 607 ký tự ra, chênh đúng một dấu cách đầu dòng. Nhờ vậy việc ánh xạ *ký tự thứ N → giây thứ mấy* là chính xác tuyệt đối, không cần khớp mờ, không có chỗ nào để sai lệch chui vào.

Mô hình dùng mặc định là **base** (139 MB, đóng gói sẵn). Mô hình lớn hơn không giúp gì cho việc căn giờ, vì chữ đã có sẵn rồi — chỉ chế độ phiên âm (khi không có kịch bản) mới cần.

## Dựng từ mã nguồn

```bash
git clone https://github.com/quangsonk8/SolaSub.git
cd SolaSub
python -m venv venv-cpu
venv-cpu\Scripts\pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
venv-cpu\Scripts\python app.py
```

Cần Python 3.11 và `ffmpeg` trong PATH (hoặc đặt ở `tools\ffmpeg.exe`).

Chạy bằng dòng lệnh:

```bash
python cli.py --audio story.mp3 --text story.txt --lang ja
```

### Đóng gói

```powershell
.\build\build.ps1              # dung ban di dong vao build\SolaSub\
.\installer\build-installers.ps1   # dung ca hai bo cai vao installer\Output\
```

Bản đóng gói dùng **Python nhúng**, không dùng PyInstaller — vì Python đã đóng băng thì về sau không `pip install` CUDA được nữa, mà đó chính là cách bản GPU hoạt động.

Vài chi tiết đã trả giá mới biết, đều ghi rõ trong `build\build.ps1`:

- Visual C++ Runtime phải nằm **cạnh `pythonw.exe`**. `torch` cần `msvcp140.dll`, mà Windows chỉ tự tìm trong thư mục chứa file `.exe` của tiến trình — không tìm trong thư mục chứa chính DLL đang nạp.
- `python311._pth` phải có dòng `..`, không thì `ModuleNotFoundError: No module named 'solasub'`.
- `ffmpeg` phải được chèn vào `PATH` **trước mọi import**, vì Whisper gọi thẳng chuỗi `"ffmpeg"` qua `subprocess`.
- Chạy bằng `pythonw.exe` thì `sys.stdout` là `None`; thanh tiến độ `tqdm` trong stable-ts sẽ gây `AttributeError`. `app.py` thay bằng bộ ghi rỗng ngay đầu file.
- Python nhúng (chạy theo `._pth`) **không bao giờ tự ghi `.pyc`**, nên mỗi lần mở app phải biên dịch lại hơn 1.000 file. `build.ps1` biên dịch sẵn (`compileall --invalidation-mode unchecked-hash`) và bộ cài giữ lại `__pycache__`. Hệ quả: sửa file `.py` trong bản đã cài sẽ không có tác dụng cho tới khi biên dịch lại.
- Lúc mở app **không được import `whisper`**: nó kéo theo cả PyTorch (vài giây). Danh sách ngôn ngữ vì vậy được chép sẵn vào `solasub/languages.py`; nâng cấp Whisper thì chạy `build\gen_languages.py`.
- `SolaSub.exe` (`build\launcher.cs`) hiện màn hình khởi động trước khi Python chạy, nhận trạng thái qua stdout của `app.py` (`@@STATUS …`, `@@READY`). Biên dịch bằng `csc.exe` của .NET Framework 4 nên chỉ dùng cú pháp C# 5.

Thư mục `build\sandbox\` có sẵn cấu hình Windows Sandbox để thử bộ cài trên một bản Windows sạch — tự cài, thử nạp thư viện, chạy căn chỉnh thật rồi chụp màn hình giao diện.

## Ghi nhận

Dựng trên [OpenAI Whisper](https://github.com/openai/whisper) và [stable-ts](https://github.com/jianfch/stable-ts). Giao diện bằng PyQt6. Xử lý audio bằng [FFmpeg](https://ffmpeg.org/).

// SolaSub.exe — launcher cua ban cai dat.
//
// Truoc day chi goi python\pythonw.exe app.py roi thoat ngay: Python + Qt nap mat 3-20 giay (lan dau sau
// khi bat may, Windows va phan mem diet virus doc ~300 MB thu vien) ma man hinh KHONG hien gi -> nguoi
// dung tuong chua bam, bam them lan nua.
//
// Gio:
//   1. Hien MAN HINH KHOI DONG ngay (WinForms tren .NET Framework co san trong Windows, chua can Python).
//   2. Chay app.py, nhan trang thai qua stdout: "@@STATUS <chu>" -> doi dong trang thai; "@@READY" ->
//      cua so chinh da hien -> mo dan man hinh khoi dong roi thoat.
//   3. Bam them khi dang khoi dong -> chi dua man hinh khoi dong len truoc. Bam khi app da mo -> dua cua
//      so SolaSub len truoc, khong mo ban thu hai.
//   4. Python thoat truoc khi cua so hien -> bao loi kem vai dong cuoi + duong dan nhat ky.
//
// LUU Y: bien dich bang csc.exe cua .NET Framework 4 (C# 5) -> KHONG dung $"", ?., out var, =>.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

static class Launcher
{
    [STAThread]
    static int Main(string[] args)
    {
        Native.MakeDpiAware();
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string py = Path.Combine(root, @"python\pythonw.exe");
        string app = Path.Combine(root, "app.py");

        if (!File.Exists(py) || !File.Exists(app))
        {
            MessageBox.Show("Thiếu tệp của SolaSub:\n\n" + py + "\n" + app + "\n\nHãy cài đặt lại.",
                "SolaSub", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        // Dang khoi dong tu lan bam truoc -> dua man hinh khoi dong len, khong mo them.
        bool created;
        Mutex startup = new Mutex(true, @"Local\SolaSub.Startup", out created);
        if (!created)
        {
            IntPtr h = Native.FindWindow(null, SplashForm.WindowTitle);
            if (h != IntPtr.Zero) Native.SetForegroundWindow(h);
            return 0;
        }
        // App da mo san -> dua cua so len truoc.
        if (ActivateRunningApp(py)) return 0;

        Application.EnableVisualStyles();
        SplashForm splash = new SplashForm(root, py, app, args);
        Application.Run(splash);
        GC.KeepAlive(startup);
        return splash.ExitCode;
    }

    static bool ActivateRunningApp(string py)
    {
        foreach (Process p in Process.GetProcessesByName("pythonw"))
        {
            try
            {
                if (!string.Equals(p.MainModule.FileName, py, StringComparison.OrdinalIgnoreCase)) continue;
                IntPtr h = p.MainWindowHandle;
                if (h == IntPtr.Zero) continue;
                Native.ShowWindow(h, Native.IsIconic(h) ? 9 /*SW_RESTORE*/ : 5 /*SW_SHOW*/);
                Native.SetForegroundWindow(h);
                return true;
            }
            catch { /* tien trinh vua thoat / khong doc duoc -> bo qua */ }
        }
        return false;
    }
}

/// <summary>
/// Man hinh khoi dong kieu FireQuant: the trang bo goc + bong do, icon, ten 2 mau, mo ta, chan the
/// (phien ban · trang thai | Mien phi · chay offline), thanh chay o mep duoi. Ve bang GDI+ vao bitmap 32-bit
/// roi dat len cua so layered (UpdateLayeredWindow) -> bong mo va goc bo that su trong suot.
/// </summary>
sealed class SplashForm : Form
{
    public const string WindowTitle = "SolaSub - đang khởi động";
    public int ExitCode;

    // Kich thuoc o 96 DPI (nhan he so DPI khi ve). Giong ty le Splash.png cua FireQuant: le bong 16px.
    const int W = 632, H = 372, PAD = 16, RADIUS = 14, BAR = 6;
    static readonly Color Accent = Color.FromArgb(79, 70, 229);      // #4f46e5 - mau nut chinh cua SolaSub
    static readonly Color BarFrom = Color.FromArgb(59, 130, 246);    // xanh duong -> tim nhu icon
    static readonly Color BarTo = Color.FromArgb(124, 58, 237);
    static readonly Color Ink = Color.FromArgb(22, 22, 29);
    static readonly Color Sub = Color.FromArgb(85, 85, 95);
    static readonly Color Dim = Color.FromArgb(138, 138, 150);
    static readonly Color Track = Color.FromArgb(236, 235, 250);

    readonly string root, py, app;
    readonly string[] args;
    readonly float scale;
    readonly string version;
    readonly Image icon;
    readonly PrivateFontCollection fonts = new PrivateFontCollection();
    readonly FontFamily famRegular, famBold;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    readonly Stopwatch clock = Stopwatch.StartNew();
    readonly Queue<string> errTail = new Queue<string>();
    readonly StringBuilder log = new StringBuilder();

    Process proc;
    string status = "Đang khởi động…";
    bool ready, failed;
    double readyAt = -1;     // giay; >= 0 la dang mo dan de dong
    byte alpha;

    public SplashForm(string root, string py, string app, string[] args)
    {
        this.root = root; this.py = py; this.app = app; this.args = args;
        scale = Native.ScreenScale();
        version = ReadVersion(root);
        try { string ip = Path.Combine(root, @"assets\solasub.png"); if (File.Exists(ip)) icon = Image.FromFile(ip); } catch { }
        famRegular = LoadFont("Inter-Regular.ttf", "Inter");
        famBold = LoadFont("Inter-Bold.ttf", "Inter");

        Text = WindowTitle;
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = true;                       // co nut tren thanh tac vu -> thay ngay la app dang mo
        StartPosition = FormStartPosition.Manual;
        try { Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location); } catch { }
        Size = new Size(Px(W), Px(H));
        Rectangle wa = Screen.FromPoint(Cursor.Position).WorkingArea;
        Location = new Point(wa.Left + (wa.Width - Width) / 2, wa.Top + (wa.Height - Height) / 2);

        timer.Interval = 16;
        timer.Tick += delegate { Tick(); };
    }

    protected override CreateParams CreateParams
    {
        get { CreateParams cp = base.CreateParams; cp.ExStyle |= 0x80000 /*WS_EX_LAYERED*/; return cp; }
    }

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        Render();
        timer.Start();
        StartPython();
    }

    // Keo the de di chuyen (nhu thanh tieu de).
    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button == MouseButtons.Left) { Native.ReleaseCapture(); Native.SendMessage(Handle, 0xA1, (IntPtr)2, IntPtr.Zero); }
    }

    int Px(float v) { return (int)Math.Round(v * scale); }

    // ---------------------------------------------------------------- Python
    void StartPython()
    {
        StringBuilder a = new StringBuilder("\"" + app + "\"");
        foreach (string s in args) a.Append(" \"").Append(s).Append('"');
        ProcessStartInfo psi = new ProcessStartInfo(py, a.ToString());
        psi.UseShellExecute = false;
        psi.WorkingDirectory = root;
        psi.CreateNoWindow = true;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.StandardOutputEncoding = Encoding.UTF8;
        psi.StandardErrorEncoding = Encoding.UTF8;
        psi.EnvironmentVariables["SOLASUB_SPLASH"] = "1";      // app.py chi bao trang thai khi co bien nay
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        Log("start " + py + " " + psi.Arguments);
        try
        {
            proc = Process.Start(psi);
        }
        catch (Exception ex)
        {
            Fail("Không khởi động được Python:\n\n" + ex.Message);
            return;
        }
        Native.AllowSetForegroundWindow(proc.Id);   // de cua so SolaSub duoc len truoc khi man hinh nay dong
        proc.OutputDataReceived += OnOut;
        proc.ErrorDataReceived += OnErr;
        proc.EnableRaisingEvents = true;
        proc.Exited += delegate { Ui(OnPythonExited); };
        proc.BeginOutputReadLine();
        proc.BeginErrorReadLine();
    }

    void OnOut(object s, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        string line = e.Data;
        if (line.StartsWith("@@STATUS "))
        {
            string st = line.Substring(9).Trim();
            Log("status " + st);
            Ui(delegate { status = st; });
        }
        else if (line.StartsWith("@@READY"))
        {
            Log("ready");
            Ui(MarkReady);
        }
    }

    // Goi tu luong doc pipe / su kien Exited. Man hinh nay co the DA DONG (Python thoat sau khi app da mo)
    // -> BeginInvoke vao form da huy se nem loi tren luong nen va lam sap launcher -> bo qua.
    void Ui(MethodInvoker a)
    {
        try { if (!IsDisposed && IsHandleCreated) BeginInvoke(a); } catch { }
    }

    void OnErr(object s, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        lock (errTail)
        {
            errTail.Enqueue(e.Data);
            while (errTail.Count > 60) errTail.Dequeue();
        }
        Log("err " + e.Data);
    }

    void MarkReady()
    {
        if (ready || failed) return;
        ready = true;
        status = "Sẵn sàng";
        readyAt = clock.Elapsed.TotalSeconds;
    }

    void OnPythonExited()
    {
        if (ready || failed) return;
        int code = -1;
        try { code = proc.ExitCode; } catch { }
        string tail;
        lock (errTail)
        {
            string[] all = errTail.ToArray();
            int from = Math.Max(0, all.Length - 12);
            tail = string.Join("\n", all, from, all.Length - from);
        }
        Fail("SolaSub đóng lại trước khi mở được cửa sổ (mã " + code + ")." +
             (tail.Length > 0 ? "\n\n" + tail : ""));
    }

    void Fail(string message)
    {
        failed = true;
        ExitCode = 1;
        timer.Stop();
        string logPath = SaveLog();
        Hide();
        MessageBox.Show(message + (logPath != null ? "\n\nNhật ký: " + logPath : ""), "SolaSub",
            MessageBoxButtons.OK, MessageBoxIcon.Error);
        Close();
    }

    void Log(string m)
    {
        lock (log) log.AppendFormat("[{0,6:0.00}s] {1}\r\n", clock.Elapsed.TotalSeconds, m);
    }

    string SaveLog()
    {
        try
        {
            string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SolaSub");
            Directory.CreateDirectory(dir);
            string p = Path.Combine(dir, "startup.log");
            lock (log) File.WriteAllText(p, log.ToString(), Encoding.UTF8);
            return p;
        }
        catch { return null; }
    }

    // ---------------------------------------------------------------- vong ve
    void Tick()
    {
        double t = clock.Elapsed.TotalSeconds;
        if (readyAt >= 0)
        {
            double k = (t - readyAt - 0.25) / 0.25;     // thanh chay day 0,25s roi mo dan 0,25s
            if (k >= 1) { timer.Stop(); SaveLog(); Close(); return; }
            alpha = (byte)(255 * (1 - Math.Max(0, k)));
        }
        else
        {
            alpha = (byte)Math.Min(255, t / 0.15 * 255);
            // Phong khi app.py khong bao READY (ban cu): cua so chinh da hien thi coi nhu xong.
            if (proc != null && t > 2 && ((int)(t * 4)) % 2 == 0)
            {
                try { proc.Refresh(); if (proc.MainWindowHandle != IntPtr.Zero) MarkReady(); } catch { }
            }
            if (t > 180) MarkReady();                     // tran an toan: khong treo man hinh nay mai
        }
        Render();
    }

    void Render()
    {
        int w = Px(W), h = Px(H);
        using (Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppPArgb))
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.TextRenderingHint = TextRenderingHint.AntiAlias;   // khong ClearType: hong kenh alpha
            g.ScaleTransform(scale, scale);
            Draw(g);
            Native.PushLayered(this, bmp, alpha);
        }
    }

    void Draw(Graphics g)
    {
        RectangleF card = new RectangleF(PAD, PAD, W - 2 * PAD, H - 2 * PAD);

        // Bong do mem: nhieu lop mo dan ra ngoai, lech xuong 3px
        for (int i = PAD; i >= 1; i--)
        {
            int a = (int)(16 * Math.Pow(1 - (double)i / PAD, 2)) + 1;
            using (GraphicsPath sp = Rounded(new RectangleF(card.X - i + 1, card.Y - i + 4, card.Width + 2 * i - 2, card.Height + 2 * i - 2), RADIUS + i))
            using (SolidBrush sb = new SolidBrush(Color.FromArgb(a, 0, 0, 0)))
                g.FillPath(sb, sp);
        }

        using (GraphicsPath cp = Rounded(card, RADIUS))
        {
            using (SolidBrush white = new SolidBrush(Color.White)) g.FillPath(white, cp);

            // Thanh chay o mep duoi (cat theo goc bo cua the)
            Region old = g.Clip;
            g.SetClip(cp);
            RectangleF bar = new RectangleF(card.X, card.Bottom - BAR, card.Width, BAR);
            using (SolidBrush tb = new SolidBrush(Track)) g.FillRectangle(tb, bar);
            RectangleF seg;
            if (readyAt >= 0) seg = bar;
            else
            {
                double ph = (clock.Elapsed.TotalSeconds % 1.6) / 1.6;
                double e = ph < 0.5 ? 2 * ph * ph : 1 - Math.Pow(-2 * ph + 2, 2) / 2;   // easeInOut
                float sw = bar.Width * 0.32f;
                float sx = bar.X - sw + (float)e * (bar.Width + sw);
                seg = new RectangleF(sx, bar.Y, sw, BAR);
            }
            if (seg.Width > 1)
                using (LinearGradientBrush gb = new LinearGradientBrush(new RectangleF(seg.X - 1, seg.Y, seg.Width + 2, seg.Height), BarFrom, BarTo, LinearGradientMode.Horizontal))
                    g.FillRectangle(gb, seg);
            g.Clip = old;
        }

        // Icon
        if (icon != null) g.DrawImage(icon, new RectangleF(card.X + 40, card.Y + 84, 100, 100));

        // Ten: "Sola" mau nhan + "Sub" mau muc
        StringFormat tf = StringFormat.GenericTypographic;
        float tx = card.X + 160, ty = card.Y + 92;
        using (Font big = new Font(famBold, 44f, FontStyle.Bold, GraphicsUnit.Pixel))
        using (SolidBrush ab = new SolidBrush(Accent))
        using (SolidBrush ib = new SolidBrush(Ink))
        {
            g.DrawString("Sola", big, ab, tx, ty, tf);
            float wSola = g.MeasureString("Sola", big, PointF.Empty, tf).Width;
            g.DrawString("Sub", big, ib, tx + wSola, ty, tf);
        }
        using (Font sub = new Font(famRegular, 15.5f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush sb = new SolidBrush(Sub))
            g.DrawString("Tạo phụ đề khớp giờ từ audio + kịch bản gốc", sub, sb, tx + 2, ty + 62, tf);

        // Chan the
        using (Font small = new Font(famRegular, 12.5f, FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush db = new SolidBrush(Dim))
        {
            float fy = card.Bottom - BAR - 36;
            string right = "Miễn phí · chạy offline";
            float wr = g.MeasureString(right, small, PointF.Empty, tf).Width;
            float rx = card.Right - 48 - wr;
            g.DrawString(right, small, db, rx, fy, tf);

            string left = "Phiên bản " + version + "   ·   " + status;
            float maxW = rx - (card.X + 48) - 24;
            using (StringFormat lf = (StringFormat)StringFormat.GenericTypographic.Clone())
            {
                lf.Trimming = StringTrimming.EllipsisCharacter;
                lf.FormatFlags |= StringFormatFlags.NoWrap;
                g.DrawString(left, small, db, new RectangleF(card.X + 48, fy, maxW, 20), lf);
            }
        }
    }

    static GraphicsPath Rounded(RectangleF r, float rad)
    {
        float d = rad * 2;
        GraphicsPath p = new GraphicsPath();
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    FontFamily LoadFont(string file, string family)
    {
        try
        {
            string p = Path.Combine(root, @"assets\fonts\" + file);
            if (File.Exists(p))
            {
                fonts.AddFontFile(p);
                foreach (FontFamily f in fonts.Families)
                    if (string.Equals(f.Name, family, StringComparison.OrdinalIgnoreCase)) return f;
            }
        }
        catch { }
        return new FontFamily("Segoe UI");   // thieu file font -> van ve duoc
    }

    static string ReadVersion(string root)
    {
        try
        {
            string p = Path.Combine(root, @"solasub\__init__.py");
            Match m = Regex.Match(File.ReadAllText(p), "__version__\\s*=\\s*[\"']([^\"']+)[\"']");
            if (m.Success) return m.Groups[1].Value;
        }
        catch { }
        return "?";
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) { timer.Dispose(); fonts.Dispose(); if (icon != null) icon.Dispose(); }
        base.Dispose(disposing);
    }
}

static class Native
{
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")] public static extern bool AllowSetForegroundWindow(int pid);
    [DllImport("user32.dll")] public static extern bool ReleaseCapture();
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, int msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("shcore.dll")] static extern int SetProcessDpiAwareness(int v);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] static extern int GetDeviceCaps(IntPtr dc, int idx);
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr dc, IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);

    [StructLayout(LayoutKind.Sequential)] struct PT { public int X, Y; public PT(int x, int y) { X = x; Y = y; } }
    [StructLayout(LayoutKind.Sequential)] struct SZ { public int W, H; public SZ(int w, int h) { W = w; H = h; } }
    [StructLayout(LayoutKind.Sequential, Pack = 1)] struct BLEND { public byte Op, Flags, Alpha, Format; }

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool UpdateLayeredWindow(IntPtr hwnd, IntPtr dst, ref PT pos, ref SZ size, IntPtr src, ref PT srcPos, int key, ref BLEND blend, int flags);

    public static void MakeDpiAware()
    {
        // Khong co -> Windows phong to bitmap tren man hinh 125-150% -> chu nhoe.
        try { if (SetProcessDpiAwareness(2) == 0) return; } catch { }
        try { SetProcessDPIAware(); } catch { }
    }

    public static float ScreenScale()
    {
        IntPtr dc = GetDC(IntPtr.Zero);
        try { return Math.Max(1f, GetDeviceCaps(dc, 88 /*LOGPIXELSX*/) / 96f); }
        finally { ReleaseDC(IntPtr.Zero, dc); }
    }

    public static void PushLayered(Form f, Bitmap bmp, byte alpha)
    {
        IntPtr screen = GetDC(IntPtr.Zero);
        IntPtr mem = CreateCompatibleDC(screen);
        IntPtr hbmp = bmp.GetHbitmap(Color.FromArgb(0));
        IntPtr old = SelectObject(mem, hbmp);
        try
        {
            PT pos = new PT(f.Left, f.Top), zero = new PT(0, 0);
            SZ size = new SZ(bmp.Width, bmp.Height);
            BLEND b = new BLEND { Op = 0, Flags = 0, Alpha = alpha, Format = 1 /*AC_SRC_ALPHA*/ };
            UpdateLayeredWindow(f.Handle, screen, ref pos, ref size, mem, ref zero, 0, ref b, 2 /*ULW_ALPHA*/);
        }
        finally
        {
            SelectObject(mem, old);
            DeleteObject(hbmp);
            DeleteDC(mem);
            ReleaseDC(IntPtr.Zero, screen);
        }
    }
}

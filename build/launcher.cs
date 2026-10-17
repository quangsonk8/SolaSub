// SolaSub.exe — chi lam mot viec: goi python\pythonw.exe app.py roi thoat.
// Co de nguoi dung thay mot file .exe co icon dang hoang thay vi phai chay
// pythonw.exe kem tham so.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

static class Launcher
{
    [STAThread]
    static int Main(string[] args)
    {
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string py = Path.Combine(root, @"python\pythonw.exe");
        string app = Path.Combine(root, "app.py");

        if (!File.Exists(py) || !File.Exists(app))
        {
            MessageBox.Show(
                "Thiếu tệp của SolaSub:\n\n" + py + "\n" + app +
                "\n\nHãy cài đặt lại.", "SolaSub",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        var psi = new ProcessStartInfo(py, "\"" + app + "\"")
        {
            UseShellExecute = false,
            WorkingDirectory = root,
        };
        // Noi tham so dong lenh (vd --audio x.mp3) sang cho app.py
        foreach (string a in args) psi.Arguments += " \"" + a + "\"";

        try { Process.Start(psi); }
        catch (Exception ex)
        {
            MessageBox.Show("Không khởi động được SolaSub:\n\n" + ex.Message,
                "SolaSub", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}

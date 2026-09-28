// 持ち運び版の起動用 (GnW改造ツール.exe)。scripts/make_portable.py が Windows 標準の csc.exe でビルドする。
// 自分と同じフォルダの tools\python\pythonw.exe で "python -m gnwtool" を起動するだけ。
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Launcher
{
    [STAThread]
    static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string pyw = Path.Combine(root, @"tools\python\pythonw.exe");
        if (!File.Exists(pyw))
        {
            MessageBox.Show("tools\\python\\pythonw.exe が見つかりません。\nフォルダの中身がすべてコピーされているか確認してください。\n\n" + root,
                            "G&W 改造ツール", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        var psi = new ProcessStartInfo(pyw, "-m gnwtool");
        psi.WorkingDirectory = root;
        psi.UseShellExecute = false;
        // その PC に入っている Python の設定・ユーザー用パッケージを混ぜない
        psi.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        psi.EnvironmentVariables.Remove("PYTHONHOME");
        psi.EnvironmentVariables.Remove("PYTHONPATH");
        try
        {
            Process.Start(psi);
        }
        catch (Exception e)
        {
            MessageBox.Show("起動できませんでした: " + e.Message, "G&W 改造ツール", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}

using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace LocalNetworkAgent
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            Application.SetHighDpiMode(HighDpiMode.SystemAware);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            var minimized = args.Any(a => string.Equals(a, "-minimized", StringComparison.OrdinalIgnoreCase));
            Application.Run(new MainWindow(minimized));
        }
    }
}
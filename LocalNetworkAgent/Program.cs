using System;
using System.Drawing;
using System.Windows.Forms;
using System.Diagnostics;
using System.IO;
using System.Threading;
using Microsoft.VisualBasic;

namespace LocalNetworkAgent;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new NetworkAgentLauncher());
    }
}

public class NetworkAgentLauncher : Form
{
    private Button btnApi = null!, btnWeb = null!, btnVoice = null!, btnScan = null!, btnShell = null!, btnPowerCore0 = null!, btnFiles = null!, btnIntercom = null!, btnSpeak = null!;
    private Label lblStatus = null!, lblToken = null!;
    private TextBox txtLog = null!;
    private Process? apiProcess, voiceProcess;
    private string projectPath = @"C:\Users\Usuario\LocalNetworkAgent";

    public NetworkAgentLauncher()
    {
        this.Text = "Local Network Agent v2.1.0 (PRO)";
        this.Size = new Size(500, 620);
        this.StartPosition = FormStartPosition.CenterScreen;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.BackColor = Color.FromArgb(26, 26, 46);
        this.ForeColor = Color.White;
        this.ShowInTaskbar = true;

        Label title = new Label
        {
            Text = "LOCAL NETWORK AGENT",
            Font = new Font("Segoe UI", 16, FontStyle.Bold),
            ForeColor = Color.FromArgb(0, 217, 255),
            Top = 20,
            Left = 80,
            Width = 340,
            Height = 40
        };

        btnApi = new Button { Text = "INICIAR API", Top = 70, Left = 30, Width = 140, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(15, 52, 96), ForeColor = Color.White };
        btnWeb = new Button { Text = "PANEL WEB", Top = 70, Left = 180, Width = 140, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(15, 52, 96), ForeColor = Color.White, Enabled = false };
        btnScan = new Button { Text = "ESCANEAR", Top = 120, Left = 30, Width = 90, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(0, 217, 255), ForeColor = Color.Black };
        btnFiles = new Button { Text = "ARCHIVOS", Top = 120, Left = 130, Width = 90, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(255, 184, 108), ForeColor = Color.Black };
        btnShell = new Button { Text = "SHELL", Top = 120, Left = 230, Width = 90, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(255, 121, 198), ForeColor = Color.Black };
        btnVoice = new Button { Text = "VOZ LOCAL", Top = 120, Left = 330, Width = 90, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(15, 52, 96), ForeColor = Color.White };
        btnIntercom = new Button { Text = "CHAT CORE0", Top = 170, Left = 30, Width = 190, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(74, 42, 193), ForeColor = Color.White };
        btnSpeak = new Button { Text = "VOZ CORE0", Top = 170, Left = 230, Width = 190, Height = 35, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(255, 87, 34), ForeColor = Color.White };
        btnPowerCore0 = new Button { Text = "ENCENDER CORE0 (WoL)", Top = 220, Left = 30, Width = 390, Height = 40, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(0, 200, 83), ForeColor = Color.White, Font = new Font("Segoe UI", 9, FontStyle.Bold) };
        lblStatus = new Label { Text = "v2.1.0 - Red y Megafonia", Top = 275, Left = 30, Width = 390, ForeColor = Color.Cyan, Font = new Font("Segoe UI", 8) };
        lblToken = new Label { Text = "Token: (inicia servidor)", Top = 295, Left = 30, Width = 390, Font = new Font("Consolas", 8), ForeColor = Color.Silver };
        txtLog = new TextBox { Multiline = true, ReadOnly = true, Top = 320, Left = 30, Width = 390, Height = 200, BackColor = Color.Black, ForeColor = Color.Lime, Font = new Font("Consolas", 8), ScrollBars = ScrollBars.Vertical };

        btnApi.Click += (s, e) => ToggleApi();
        btnWeb.Click += (s, e) => { try { Process.Start(new ProcessStartInfo("http://localhost:8082") { UseShellExecute = true }); } catch { } };
        btnVoice.Click += (s, e) => StartVoice();
        btnScan.Click += (s, e) => {
            var psi = new ProcessStartInfo("powershell", "-ExecutionPolicy Bypass -NoExit -File \"" + Path.Combine(projectPath, "Scan-Network.ps1") + "\"") { 
                WorkingDirectory = projectPath, 
                WindowStyle = ProcessWindowStyle.Normal,
                UseShellExecute = true 
            };
            Process.Start(psi);
        };
        btnFiles.Click += (s, e) => {
            string ip = Interaction.InputBox("IP:", "Archivos", "192.168.1.14");
            if (!string.IsNullOrEmpty(ip)) RunPowerShell("-NoExit -File \"" + Path.Combine(projectPath, "Explorer_Agent.ps1") + "\" -ComputerName " + ip);
        };
        btnShell.Click += (s, e) => {
            string ip = Interaction.InputBox("IP:", "Shell", "192.168.1.14");
            if (!string.IsNullOrEmpty(ip)) {
                string credPath = Path.Combine(projectPath, "core0-cred.xml");
                if (!File.Exists(credPath)) {
                    var result = MessageBox.Show("No hay credenciales guardadas.\n¿Desea configurarlas ahora?", "Credenciales", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                    if (result == DialogResult.Yes) {
                        RunPowerShell("-NoExit -File \"" + Path.Combine(projectPath, "Set-NetworkCredential.ps1") + "\"");
                        return;
                    }
                }
                RunPowerShell("-NoExit -Command \"Import-Module '" + Path.Combine(projectPath, "NetworkUtilsPublic.psm1") + "'; Connect-RemoteComputer -ComputerName " + ip + "\"");
            }
        };
        btnIntercom.Click += (s, e) => {
            string ip = Interaction.InputBox("IP:", "Intercom", "192.168.1.14");
            if (!string.IsNullOrEmpty(ip)) RunPowerShell("-NoExit -File \"" + Path.Combine(projectPath, "Intercom.ps1") + "\" -ComputerName " + ip);
        };
        btnSpeak.Click += (s, e) => {
            string ip = Interaction.InputBox("IP:", "Voz", "192.168.1.10");
            if (!string.IsNullOrEmpty(ip)) RunPowerShell("-NoExit -File \"" + Path.Combine(projectPath, "Speak-Remote.ps1") + "\" -ComputerName " + ip);
        };
        btnPowerCore0.Click += (s, e) => {
            RunPowerShell("-Command \"Import-Module '" + Path.Combine(projectPath, "NetworkUtilsPublic.psm1") + "'; Send-WakeOnLan -MACAddress (Get-Content network-config.json | ConvertFrom-Json).Core0MAC\"");
            MessageBox.Show("Paquete WoL enviado!", "WoL");
        };

        this.Controls.Add(title);
        this.Controls.Add(btnApi);
        this.Controls.Add(btnWeb);
        this.Controls.Add(btnVoice);
        this.Controls.Add(btnScan);
        this.Controls.Add(btnShell);
        this.Controls.Add(btnFiles);
        this.Controls.Add(btnIntercom);
        this.Controls.Add(btnSpeak);
        this.Controls.Add(btnPowerCore0);
        this.Controls.Add(lblStatus);
        this.Controls.Add(lblToken);
        this.Controls.Add(txtLog);
    }

    private void LogLine(string txt) => txtLog.AppendText("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + txt + Environment.NewLine);

    private void ToggleApi()
    {
        if (apiProcess == null)
        {
            apiProcess = new Process();
            apiProcess.StartInfo = new ProcessStartInfo("powershell", "-ExecutionPolicy Bypass -File API-Server.ps1") { WorkingDirectory = projectPath, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true };
            apiProcess.Start();
            btnApi.Text = "DETENER API";
            btnApi.BackColor = Color.FromArgb(233, 69, 96);
            btnWeb.Enabled = true;
            new Thread(() => {
                while (apiProcess != null && !apiProcess.HasExited)
                {
                    try
                    {
                        string? line = apiProcess.StandardOutput.ReadLine();
                        if (line != null)
                        {
                            LogLine(line);
                            if (line.Contains("Token:"))
                            {
                                string token = line.Split(':')[1].Trim();
                                this.Invoke(() => lblToken.Text = "Token: " + token);
                            }
                        }
                    }
                    catch { break; }
                }
            }).Start();
        }
        else
        {
            try { apiProcess.Kill(); } catch { }
            apiProcess = null;
            btnApi.Text = "INICIAR API";
            btnApi.BackColor = Color.FromArgb(15, 52, 96);
            btnWeb.Enabled = false;
        }
    }

    private void StartVoice()
    {
        if (voiceProcess == null)
        {
            voiceProcess = Process.Start(new ProcessStartInfo("powershell", "-ExecutionPolicy Bypass -File VoiceControl.ps1") { WorkingDirectory = projectPath });
            btnVoice.Text = "DETENER VOZ";
        }
        else
        {
            try { voiceProcess.Kill(); } catch { }
            voiceProcess = null;
            btnVoice.Text = "VOZ LOCAL";
        }
    }

    private void RunPowerShell(string args)
    {
        try
        {
            var shell = File.Exists(@"C:\Program Files\PowerShell\7\pwsh.exe") ? "pwsh" : "powershell";
            var psi = new ProcessStartInfo(shell, "-ExecutionPolicy Bypass " + args) { 
                WorkingDirectory = projectPath, 
                WindowStyle = ProcessWindowStyle.Normal,
                UseShellExecute = true 
            };
            Process.Start(psi);
        }
        catch (Exception ex) { MessageBox.Show("Error: " + ex.Message); }
    }
}
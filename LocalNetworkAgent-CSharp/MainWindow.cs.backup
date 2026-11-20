            if (isPhone)
            {
                // Android: usar ADB-Explorer.ps1
                if (!File.Exists(adbPath))
                {
                    MessageBox.Show($"ADB no encontrado en:\n{adbPath}\n\nInstale Android Platform Tools", "ADB no disponible");
                    return;
                }

                string scriptPath = @"C:\Users\Usuario\LocalNetworkAgent\ADB-Explorer.ps1";
                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show($"Script no encontrado:\n{scriptPath}", "Error");
                    return;
                }

                // Resolve actual IP:PORT from adb devices
                string adbIpPort = ResolveAdbDevicePort(ip);
                if (string.IsNullOrEmpty(adbIpPort))
                {
                    MessageBox.Show($"No se encontró {ip} en adb devices.\nAsegúrate de estar conectado a la misma WiFi.", "ADB no encontrado");
                    return;
                }

                Process.Start(new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = $"-WindowStyle Normal -ExecutionPolicy Bypass -File \"{scriptPath}\" -IP \"{adbIpPort}\" -ADB \"{adbPath}\"",
                    UseShellExecute = true
                });
            }
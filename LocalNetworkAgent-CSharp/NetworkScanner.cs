using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Threading.Tasks;
using System.Net.Sockets;
using System.Threading.Tasks;

namespace LocalNetworkAgent
{
    public static class NetworkScanner
    {
        public static async Task<List<DeviceInfo>> ScanAsync(NetworkConfig config, IProgress<string>? progress = null)
        {
            var subnet = config.SubnetPrefix;
            progress?.Report("Ping sweep...");

            await ArpCache.RefreshAsync(subnet);

            var devices = new List<DeviceInfo>();
            var seenIps = new HashSet<string>();

            // Check configured devices
            foreach (var pc in config.Computers)
            {
                progress?.Report($"Comprobando {pc.Name}...");

                string? actualIp = ResolveActualIp(pc, config);
                bool isOnline = await IsOnlineAsync(actualIp, pc.Type == "phone");
                
                if (!isOnline) actualIp = pc.IP;

                devices.Add(new DeviceInfo
                {
                    Host = pc.Name,
                    IP = actualIp,
                    Status = isOnline ? "Conectado" : "Offline",
                    IsPhone = pc.Type == "phone",
                    MAC = pc.MAC,
                    ConfigIP = pc.IP,
                    OS = pc.OS,
                    OpenPorts = pc.OpenPorts
                });
                seenIps.Add(actualIp);
            }

            // Unknown devices from ARP
            var unknownColor = Color.FromArgb(128, 128, 0);
            foreach (var kvp in GetArpEntries(subnet))
            {
                if (seenIps.Contains(kvp.Value)) continue;
                var ip = kvp.Value;
                var mac = kvp.Key;
                
                var isOnline = await IsOnlineAsync(ip, false);
                devices.Add(new DeviceInfo
                {
                    Host = ResolveHostName(ip),
                    IP = ip,
                    Status = isOnline ? "Conectado" : "Offline",
                    IsPhone = false,
                    MAC = mac
                });
            }

            return devices;
        }

        private static string ResolveActualIp(ComputerEntry pc, NetworkConfig config)
        {
            // 1. Local machine
            if (pc.Name == Environment.MachineName)
            {
                var localIp = GetLocalIp(config.SubnetPrefix);
                if (localIp != null) return localIp;
            }

            // 2. MAC -> ARP
            if (!string.IsNullOrEmpty(pc.MAC))
            {
                var ip = ArpCache.ResolveIpByMac(pc.MAC);
                if (ip != null) return ip;
            }

            // 3. CORE0 special handling
            if (pc.Name == "CORE0" && !string.IsNullOrEmpty(config.Core0MAC))
            {
                var ip = ArpCache.ResolveIpByMac(config.Core0MAC);
                if (ip != null) return ip;
            }

            // 4. Known MACs
            if (config.KnownMacs != null)
            {
                foreach (var kvp in config.KnownMacs)
                {
                    if (kvp.Value == pc.Name)
                    {
                        var ip = ArpCache.ResolveIpByMac(kvp.Key);
                        if (ip != null) return ip;
                    }
                }
            }

            return pc.IP;
        }

        private static string? GetLocalIp(string subnetPrefix)
        {
            try
            {
                var addrs = System.Net.Dns.GetHostAddresses(System.Net.Dns.GetHostName())
                    .Where(a => a.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
                    .Select(a => a.ToString())
                    .Where(a => a.StartsWith(subnetPrefix + "."))
                    .FirstOrDefault();
                return addrs;
            }
            catch { return null; }
        }

        private static async Task<bool> IsOnlineAsync(string ip, bool isPhone)
        {
            // Ping
            try
            {
                using var ping = new Ping();
                var reply = await ping.SendPingAsync(ip, 150);
                if (reply.Status == IPStatus.Success) return true;
            }
            catch { }

            // TCP fallback - check both ADB (5555) and WinRM (5985)
            int[] ports = isPhone ? new[] { 5555, 5985 } : new[] { 5985, 5555 };
            foreach (int port in ports)
            {
                try
                {
                    using var tcp = new TcpClient();
                    var connectTask = tcp.ConnectAsync(ip, port);
                    var completed = await Task.WhenAny(connectTask, Task.Delay(300));
                    if (completed == connectTask && tcp.Connected) return true;
                }
                catch { }
            }

            return false;
        }

        private static string ResolveHostName(string ip)
        {
            try { return System.Net.Dns.GetHostEntry(ip).HostName; } 
            catch { return ip; }
        }

        private static IEnumerable<KeyValuePair<string, string>> GetArpEntries(string subnet)
        {
            var results = new List<KeyValuePair<string, string>>();
            try
            {
                using var proc = System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "arp",
                    Arguments = "-a",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                });
                if (proc != null)
                {
                    string output = proc.StandardOutput.ReadToEnd();
                    proc.WaitForExit();
                    foreach (var line in output.Split('\n'))
                    {
                        var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                        if (parts.Length >= 2 && parts[0].StartsWith(subnet + "."))
                        {
                            string ip = parts[0];
                            string mac = parts[1].ToLower().Replace('-', ':');
                            if (mac != "00:00:00:00:00:00" && mac != "ff:ff:ff:ff:ff:ff")
                                results.Add(new KeyValuePair<string, string>(mac, ip));
                        }
                    }
                }
            }
            catch { }
            return results;
        }
    }
}
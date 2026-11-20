using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net.NetworkInformation;

namespace LocalNetworkAgent
{
    public static class ArpCache
    {
        private static Dictionary<string, string> _macToIp = new();
        private static DateTime _lastRefresh = DateTime.MinValue;
        private static readonly object _lock = new();
        private static readonly TimeSpan CacheTtl = TimeSpan.FromSeconds(30);

        public static async Task RefreshAsync(string subnet)
        {
            lock (_lock)
            {
                if (DateTime.Now - _lastRefresh < CacheTtl) return;
            }

            // 1) Ping sweep to refresh ARP
            var tasks = new List<Task>();
            for (int i = 1; i <= 254; i++)
            {
                string ip = $"{subnet}.{i}";
                tasks.Add(Task.Run(async () => 
                {
                    try { await new Ping().SendPingAsync(ip, 50); } catch { }
                }));
            }
            await Task.WhenAll(tasks);

            // 2) Read ARP table
            var newMap = new Dictionary<string, string>();
            try
            {
                using var proc = Process.Start(new ProcessStartInfo
                {
                    FileName = "arp",
                    Arguments = "-a",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                });
                if (proc != null)
                {
                    string output = await proc.StandardOutput.ReadToEndAsync();
                    await proc.WaitForExitAsync();
                    ParseArpOutput(output, subnet, newMap);
                }
            }
            catch { }

            lock (_lock)
            {
                _macToIp = newMap;
                _lastRefresh = DateTime.Now;
            }
        }

        private static void ParseArpOutput(string output, string subnet, Dictionary<string, string> map)
        {
            foreach (var line in output.Split('\n'))
            {
                var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 2 && parts[0].StartsWith(subnet + "."))
                {
                    string ip = parts[0];
                    string mac = parts[1].ToLower().Replace('-', ':');
                    if (mac != "00:00:00:00:00:00" && mac != "ff:ff:ff:ff:ff:ff")
                        map[mac] = ip;
                }
            }
        }

        public static string? ResolveIpByMac(string mac)
        {
            lock (_lock)
            {
                return _macToIp.TryGetValue(mac.ToLower().Replace('-', ':'), out var ip) ? ip : null;
            }
        }
    }
}
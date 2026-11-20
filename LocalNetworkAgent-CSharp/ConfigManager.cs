using System;
using System.IO;
using System.Text.Json;

namespace LocalNetworkAgent
{
    public static class ConfigManager
    {
        private static readonly string ConfigPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            "LocalNetworkAgent", "network-config.json");

        public static NetworkConfig Load()
        {
            if (File.Exists(ConfigPath))
            {
                try
                {
                    var json = File.ReadAllText(ConfigPath);
                    var config = JsonSerializer.Deserialize<NetworkConfig>(json);
                    return config ?? new NetworkConfig();
                }
                catch { }
            }
            return new NetworkConfig();
        }

        public static void Save(NetworkConfig config)
        {
            var dir = Path.GetDirectoryName(ConfigPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            var json = JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(ConfigPath, json);
        }
    }
}
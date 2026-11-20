using System;
using System.Collections.Generic;

namespace LocalNetworkAgent
{
    public class NetworkConfig
    {
        public int Port { get; set; } = 5985;
        public string SubnetPrefix { get; set; } = "192.168.1";
        public List<ComputerEntry> Computers { get; set; } = new();
        public string NtfyTopic { get; set; } = "local-network-agent";
        public List<string> ScheduledTasks { get; set; } = new();
        public string Core0MAC { get; set; } = "";
        public Dictionary<string, string> KnownMacs { get; set; } = new();
    }

    public class ComputerEntry
    {
        public string Name { get; set; } = "";
        public string IP { get; set; } = "";
        public string? OS { get; set; }
        public string? OpenPorts { get; set; }
        public string? MAC { get; set; }
        public string Type { get; set; } = ""; // "phone" for phones
    }

    public class DeviceInfo
    {
        public string Host { get; set; } = "";
        public string IP { get; set; } = "";
        public string Status { get; set; } = "";
        public bool IsPhone { get; set; }
        public string? MAC { get; set; }
        public string? ConfigIP { get; set; }
        public string? ConfigName { get; set; }
        public string? OS { get; set; }
        public string? OpenPorts { get; set; }
    }
}
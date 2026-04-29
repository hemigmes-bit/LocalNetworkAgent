param()

# Function to check if the script is being run from an elevated session
function Test-Elevated {
    $user = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($user)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
}

# Function to check if the script is running on a Windows system
function Test-Windows {
    return [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
}

# Function to check if the script is running as a service
function Test-Service {
    $service = Get-Process -Id $PID | Select-Object -ExpandProperty ProcessName
    return $service -eq "w3wp"  # Change this based on your specific environment
}

# Function to log messages with timestamps
function Write-NetworkLog {
    param (
        [string]$message,
        [string]$level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$level] $message"
}

# Check if the script is being run with elevated permissions
if (-not (Test-Elevated)) {
    Write-NetworkLog "Script must be run as an administrator" "ERROR"
    exit 1
}

# Check if the script is running on a Windows system
if (-not (Test-Windows)) {
    Write-NetworkLog "This script can only run on Windows systems" "ERROR"
    exit 2
}

# Check if the script is running as a service
if (Test-Service) {
    Write-NetworkLog "Script cannot be run as a service" "ERROR"
    exit 3
}

# Function to check WoL status in BIOS/UEFI
function Get-WoLStatusBIOS {
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Power\ACSettings"
    $wolEnabled = (Get-ItemProperty -Path $regPath).AllowWakeFromPulse
    if ($wolEnabled) {
        Write-NetworkLog "WoL is enabled in BIOS/UEFI" "INFO"
    } else {
        Write-NetworkLog "WoL is disabled in BIOS/UEFI" "ERROR"
    }
}

# Function to check WoL status in Windows settings
function Get-WoLStatusWindows {
    $powerSettings = Get-PnpDeviceProperty -KeyName "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Power\State\AC\SubStates\0\DeviceStates\{4D36E972-E325-11CE-BFC1-08002BE10318}\*"
    $wolEnabled = ($powerSettings | Where-Object { $_.KeyName -like "*WakeOnMagicPacket*" }).Data
    if ([System.BitConverter]::ToUInt64($wolEnabled, 0) -eq 1) {
        Write-NetworkLog "WoL is enabled in Windows settings" "INFO"
    } else {
        Write-NetworkLog "WoL is disabled in Windows settings" "ERROR"
    }
}

# Function to check WoL status on network adapter
function Get-WoLStatusAdapter {
    $adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' }
    foreach ($adapter in $adapters) {
        if ([int]$adapter.PnPCapabilities -band 0x1000 -ne 0) {
            Write-NetworkLog "WoL is enabled on adapter: $($adapter.Name)" "INFO"
        } else {
            Write-NetworkLog "WoL is disabled on adapter: $($adapter.Name)" "ERROR"
        }
    }
}

# Main function to run all checks
function Run-Diagnosis {
    Get-WoLStatusBIOS
    Get-WoLStatusWindows
    Get-WoLStatusAdapter
}

# Execute the main function
Run-Diagnosis

exit 0
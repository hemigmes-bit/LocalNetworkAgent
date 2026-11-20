param([int]$Port=9876,[int]$Interval=2000,[float]$Scale=0.5)

$stop=$false
$lastHash=$null

function Capture {
    param([float]$scale)
    try{
        Add-Type -AssemblyName System.Drawing
        Add-Type -AssemblyName System.Windows.Forms
        $sw=[int][System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
        $sh=[int][System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
        if($sw-eq0){$sw=1920;$sh=1080}

        $bmp=New-Object System.Drawing.Bitmap($sw,$sh)
        $g=[System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen(0,0,0,0,(New-Object System.Drawing.Size($sw,$sh)))
        $g.Dispose()

        if($scale -lt 1.0 -and $scale -gt 0){
            $nw=[int]($sw*$scale)
            $nh=[int]($sh*$scale)
            $scaled=New-Object System.Drawing.Bitmap($nw,$nh)
            $sg=[System.Drawing.Graphics]::FromImage($scaled)
            $sg.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::Bilinear
            $sg.DrawImage($bmp,0,0,$nw,$nh)
            $sg.Dispose()
            $bmp.Dispose()
            $bmp=$scaled
        }

        $ms=New-Object System.IO.MemoryStream
        $bmp.Save($ms,[System.Drawing.Imaging.ImageFormat]::Jpeg)
        $bytes=$ms.ToArray()
        $ms.Dispose()
        $bmp.Dispose()
        return $bytes
    }catch{return $null}
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class InputSim {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);
    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT { public uint type; public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT {
        public ushort wVk; public ushort wScan; public uint dwFlags;
        public uint time; public IntPtr dwExtraInfo;
    }
    public const uint INPUT_KEYBOARD = 1;
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public static void SendKey(ushort vk) {
        INPUT[] inputs = new INPUT[2];
        inputs[0] = new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = vk } };
        inputs[1] = new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = vk, dwFlags = KEYEVENTF_KEYUP } };
        SendInput(2, inputs, Marshal.SizeOf(typeof(INPUT)));
    }
}
"@

$html=@"
<html><body style="margin:0;background:black">
<img id="screen" style="max-width:100%;display:block"/>
<script>
function update(){document.getElementById('screen').src='screen.jpg?'+new Date().getTime()}
setInterval(update,$Interval)
</script></body></html>
"@

Write-Host "CaptureServer iniciado en puerto $Port (escala: $Scale)"
Write-Host "Capturando cada $Interval ms"

$listener=New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://+:$Port/")
$listener.Start()

while(-not $stop){
    try{
        $ctx=$listener.GetContext()
        $path=$ctx.Request.Url.LocalPath

        if($path -eq "/" -or $path -eq "/index.html"){
            $ctx.Response.ContentType="text/html"
            $ctx.Response.Headers.Add("Access-Control-Allow-Origin","*")
            $ctx.Response.Headers.Add("Cache-Control","no-cache")
            $b=[byte[]][Text.Encoding]::UTF8.GetBytes($html)
            $ctx.Response.OutputStream.Write($b,0,$b.Length)
        }elseif($path -like "/screen*"){
            $bytes=Capture $Scale
            if($bytes -and $bytes.Length -gt 500){
                $hash=[System.BitConverter]::ToString((New-Object System.Security.Cryptography.SHA1Managed).ComputeHash($bytes))
                if($hash -ne $lastHash){
                    $ctx.Response.ContentType="image/jpeg"
                    $ctx.Response.Headers.Add("Access-Control-Allow-Origin","*")
                    $ctx.Response.Headers.Add("Cache-Control","no-cache, no-store, must-revalidate")
                    $ctx.Response.OutputStream.Write($bytes,0,$bytes.Length)
                    $lastHash=$hash
                }else{
                    $ctx.Response.StatusCode=304
                }
            }else{
                $ctx.Response.StatusCode=204
            }
        }elseif($path -eq "/key" -and $ctx.Request.HttpMethod -eq "POST"){
            $reader=New-Object System.IO.StreamReader($ctx.Request.InputStream)
            $body=$reader.ReadToEnd()
            $reader.Dispose()
            $vk=[uint16]::Parse($body)
            [InputSim]::SendKey($vk)
            $ctx.Response.StatusCode=200
        }elseif($path -eq "/input" -and $ctx.Request.HttpMethod -eq "POST"){
            $reader=New-Object System.IO.StreamReader($ctx.Request.InputStream)
            $body=$reader.ReadToEnd()
            $reader.Dispose()
            try{
                $cmd=$body | ConvertFrom-Json
                if($cmd.type -eq "key"){
                    [InputSim]::SendKey([uint16]::Parse($cmd.code))
                }elseif($cmd.type -eq "text"){
                    [System.Windows.Forms.SendKeys]::SendWait($cmd.data)
                }
                $ctx.Response.StatusCode=200
            }catch{$ctx.Response.StatusCode=400}
        }elseif($path -eq "/stop"){
            $stop=$true
            $ctx.Response.StatusCode=200
        }else{
            $ctx.Response.StatusCode=404
        }
        $ctx.Response.Close()
    }catch{}
}

$listener.Stop()
$listener.Close()
Write-Host "CaptureServer detenido"

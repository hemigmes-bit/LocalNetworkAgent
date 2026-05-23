param([int]$Port=9876,[int]$Interval=2000)
$stop=$false

$imgFile="$env:TEMP\current_screen.jpg"
$htmlFile="$env:TEMP\capture.html"

$html=@"
<html><body style="margin:0;background:black">
<img id="screen" style="max-width:100%;display:block"/>
<script>
function update(){document.getElementById('screen').src='screen.jpg?'+new Date().getTime()}
setInterval(update,$Interval)
</script></body></html>
"@

$html|Set-Content $htmlFile -Force

function capture{
try{
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$w=[int][System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
$h=[int][System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
if($w-eq0){$w=1920;$h=1080}
$b=New-Object System.Drawing.Bitmap($w,$h)
$g=[System.Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0,0,0,0,(New-Object System.Drawing.Size($w,$h)))
$b.Save($imgFile,[System.Drawing.Imaging.ImageFormat]::Jpeg)
$g.Dispose()
$b.Dispose()
}catch{}
}

Write-Host "CaptureServer iniciado en puerto $Port"
Write-Host "Capturando cada $Interval ms"

$listener=New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://+:$Port/")
$listener.Start()

while(-not $stop){
try{
$ctx=$listener.GetContext()
if($ctx.Request.Url.LocalPath -eq "/" -or $ctx.Request.Url.LocalPath -eq "/index.html"){
$ctx.Response.ContentType="text/html"
$ctx.Response.Headers.Add("Access-Control-Allow-Origin","*")
$ctx.Response.Headers.Add("Cache-Control","no-cache")
$ctx.Response.OutputStream.Write([byte[]][Text.Encoding]::UTF8.GetBytes($html),0,$html.Length)
}elseif($ctx.Request.Url.LocalPath -eq "/screen.jpg" -or $ctx.Request.LocalPath -match "screen"){
capture
if(Test-Path $imgFile){
$ctx.Response.ContentType="image/jpeg"
$ctx.Response.Headers.Add("Access-Control-Allow-Origin","*")
$ctx.Response.Headers.Add("Cache-Control","no-cache, no-store, must-revalidate")
$bytes=[IO.File]::ReadAllBytes($imgFile)
$ctx.Response.OutputStream.Write($bytes,0,$bytes.Length)
}
}elseif($ctx.Request.Url.LocalPath -eq "/stop"){
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
Remove-Item $imgFile,$htmlFile -Force -EA SilentlyContinue
Write-Host "CaptureServer detenido"
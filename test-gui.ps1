Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = "TEST GUI"
$form.Size = New-Object System.Drawing.Size(400, 300)
[System.Windows.Forms.Application]::Run($form)
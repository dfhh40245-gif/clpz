$entries = Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*CLPZ*' }
foreach ($e in $entries) {
    $exe = $e.UninstallString.Trim('"')
    if (Test-Path $exe) {
        Write-Output "uninstalling: $exe"
        $p = Start-Process -FilePath $exe -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -PassThru
        $p.WaitForExit(120000) | Out-Null
    } else {
        Write-Output "uninstaller missing, removing stale registry entry"
        Remove-Item -Path $e.PSPath -Recurse -Force
    }
}
$left = (Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*CLPZ*' } | Measure-Object).Count
Write-Output "remaining CLPZ registry entries: $left"

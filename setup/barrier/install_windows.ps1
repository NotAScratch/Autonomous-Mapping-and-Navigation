# Install Barrier on the Windows laptop (the SERVER: its keyboard and mouse are shared).
# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File install_windows.ps1
$ErrorActionPreference = "Stop"
$version = "2.4.0"

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing Barrier $version with winget..."
    winget install --id DebaucheeOpenSourceGroup.Barrier --version $version -e --accept-package-agreements --accept-source-agreements
} else {
    $url = "https://github.com/debauchee/barrier/releases/download/v$version/BarrierSetup-$version-release.exe"
    $exe = Join-Path $env:TEMP "BarrierSetup-$version.exe"
    Write-Host "Downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $exe
    Start-Process -FilePath $exe -Wait
}

# Barrier listens on TCP 24800; allow it on private (home) networks only.
New-NetFirewallRule -DisplayName "Barrier" -Direction Inbound -Protocol TCP -LocalPort 24800 `
    -Action Allow -Profile Private -ErrorAction SilentlyContinue | Out-Null

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -eq "Dhcp" }).IPAddress
Write-Host "`nDone. This laptop's IP address: $ip  (type it into Barrier on the Jetson)"
Write-Host "Next: open Barrier -> Server -> Configure Server -> drag a screen named after the Jetson's hostname -> Start."

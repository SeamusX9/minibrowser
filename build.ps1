$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt -q
python make_icon.py

$main = Join-Path $PSScriptRoot "main.py"
$icon = Join-Path $PSScriptRoot "sea.ico"

python -m PyInstaller --noconfirm --onefile --windowed --name "MiniBrowser" --icon $icon --add-data "$icon;." --collect-all webview --hidden-import=clr_loader $main

Write-Host "Done: dist\MiniBrowser.exe"

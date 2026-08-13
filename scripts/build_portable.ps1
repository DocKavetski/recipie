# Build portable folder for Windows work PC
# Output: dist/Recepty/

$name = "Recepty"
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

python -m pip install -r requirements.txt pyinstaller --quiet

if (Test-Path "dist\$name") { Remove-Item "dist\$name" -Recurse -Force }
if (Test-Path "build\$name") { Remove-Item "build\$name" -Recurse -Force }

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name $name `
  --add-data "web;web" `
  --add-data "data/seed_drugs_from_protocols.json;data" `
  --add-data "data/archived_drugs.json;data" `
  --add-data "VERSION;." `
  --hidden-import bottle `
  --hidden-import bottle_websocket `
  --hidden-import gevent `
  --hidden-import geventwebsocket `
  --hidden-import engineio.async_drivers.gevent `
  main.py

# Keep local runtime data folder (empty-ish) next to exe
New-Item -ItemType Directory -Force -Path "dist\$name\data" | Out-Null
Copy-Item "data\seed_drugs_from_protocols.json" "dist\$name\data\" -Force
Copy-Item "data\archived_drugs.json" "dist\$name\data\" -Force
Copy-Item "VERSION" "dist\$name\" -Force

# Overlay для live-update: backend/web рядом с exe (без перезаписи занятого _internal)
if (Test-Path "dist\$name\backend") { Remove-Item "dist\$name\backend" -Recurse -Force }
if (Test-Path "dist\$name\web") { Remove-Item "dist\$name\web" -Recurse -Force }
Copy-Item "backend" "dist\$name\backend" -Recurse -Force
Copy-Item "web" "dist\$name\web" -Recurse -Force

# Zip for GitHub Release
$zipPath = "dist\Recepty-portable.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\$name\*" -DestinationPath $zipPath -Force

Write-Output "Built: dist\$name\Recepty.exe"
Write-Output "Zip:   $zipPath"

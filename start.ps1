# MonoVista 启动脚本 (Windows PowerShell)
Write-Host ""
Write-Host "  MonoVista - 单目深度估计立体转换工具" -ForegroundColor Cyan
Write-Host ""

try { $pyver = python --version 2>&1; Write-Host "[OK] $pyver" -ForegroundColor Green }
catch { Write-Host "[ERROR] Python 未安装" -ForegroundColor Red; exit 1 }

try { $nodever = node --version; Write-Host "[OK] Node.js $nodever" -ForegroundColor Green }
catch { Write-Host "[ERROR] Node.js 未安装" -ForegroundColor Red; exit 1 }

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "启动 Flask 后端 (port 5000) ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root'; python app.py" -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "启动 Vue 前端 (port 3000) ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\frontend'; if (-not (Test-Path node_modules)) { npm install }; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "启动完成！浏览器访问: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""

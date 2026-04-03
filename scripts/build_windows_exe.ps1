$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

Write-Host "==> 构建前端静态文件"
Push-Location (Join-Path $projectRoot "frontend")
npm exec vite build
Pop-Location

Write-Host "==> 生成 Windows EXE"
Push-Location $projectRoot
python -m PyInstaller .\AIInterviewAssistant.spec --noconfirm --clean
Pop-Location

Write-Host ""
Write-Host "构建完成。"
Write-Host "EXE 路径：$projectRoot\dist\AIInterviewAssistant.exe"

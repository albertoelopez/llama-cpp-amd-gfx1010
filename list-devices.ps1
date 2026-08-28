Write-Host "=== ROCm build ==="
& "D:\AI_Projects\llama-cpp-amd\rocm\llama-cli.exe" --list-devices 2>&1
Write-Host "EXIT=$LASTEXITCODE"
Write-Host ""
Write-Host "=== Vulkan build ==="
& "D:\AI_Projects\llama-cpp-amd\vulkan\llama-cli.exe" --list-devices 2>&1
Write-Host "EXIT=$LASTEXITCODE"

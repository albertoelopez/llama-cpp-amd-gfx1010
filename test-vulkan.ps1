$exe = "D:\AI_Projects\llama-cpp-amd\vulkan\llama-cli.exe"
$model = "D:\AI_Projects\models\Qwen2.5-3B-Instruct-Q4_K_M.gguf"
& $exe -m $model -p "Say hello in exactly one short sentence." -n 32 -ngl 99 --no-warmup 2>&1
Write-Host "EXIT_CODE=$LASTEXITCODE"

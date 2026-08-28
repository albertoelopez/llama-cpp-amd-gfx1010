$exe = "D:\AI_Projects\llama-cpp-amd\vulkan\llama-bench.exe"
$model = "D:\AI_Projects\models\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf"
& $exe -m $model -ncmoe 99 -ngl 99 -p 128 -n 64 -r 3 2>&1
Write-Host "EXIT_CODE=$LASTEXITCODE"

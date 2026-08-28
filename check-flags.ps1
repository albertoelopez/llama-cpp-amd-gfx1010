& "D:\AI_Projects\llama-cpp-amd\vulkan\llama-cli.exe" --help 2>&1 | Select-String -Pattern "moe|n-gpu-layers|ngl" -CaseSensitive:$false

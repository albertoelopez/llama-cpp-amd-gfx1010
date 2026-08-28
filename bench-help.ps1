& "D:\AI_Projects\llama-cpp-amd\vulkan\llama-bench.exe" --help 2>&1 | Select-String -Pattern "moe|ngl|gpu-layers|-p |-n |-r " -CaseSensitive:$false

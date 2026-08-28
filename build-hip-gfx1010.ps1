# Build llama.cpp (tag b10630, same commit as the Vulkan build) with the HIP backend for
# the RX 5700 XT (gfx1010). Run from a plain PowerShell; this script sets up the VS x64
# environment itself.
#
# Prereqs (see NEXT.md in FreeToken): AMD HIP SDK 6.2.4 installed (matches the driver's
# HIP 6.2.4 runtime), with the community gfx1010:xnack- rocBLAS swapped in by
# swap-rocblas-gfx1010.ps1. Ninja comes bundled with VS 2022 Build Tools.
$ErrorActionPreference = "Continue"

$src   = "D:\AI_Projects\llama-cpp-amd\src"
$build = "D:\AI_Projects\llama-cpp-amd\build-hip"
$out   = "D:\AI_Projects\llama-cpp-amd\hip-gfx1010"

$hip = $env:HIP_PATH
if (-not $hip) { $hip = (Get-ChildItem "C:\Program Files\AMD\ROCm" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName }
if (-not (Test-Path "$hip\bin\clang++.exe")) { throw "HIP SDK not found (HIP_PATH=$hip). Install AMD HIP SDK 6.2.4 first." }
Write-Host "HIP_PATH = $hip"

# VS x64 environment (cl.exe/link.exe for host code, Windows SDK headers) + bundled Ninja.
$vsroot = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
$vcvars = "$vsroot\VC\Auxiliary\Build\vcvars64.bat"
cmd /c "`"$vcvars`" >nul 2>&1 && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process") }
}
$env:PATH = "$hip\bin;$vsroot\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;D:\Programs\CMake\bin;$env:PATH"
$env:HIP_PATH = $hip
$env:HIP_PLATFORM = "amd"
# hipconfig is a Perl script; Git for Windows bundles perl. Appended LAST: its usr\bin also has a GNU link.exe.
$env:PATH = "$env:PATH;C:\Program Files\Git\usr\bin"

# GGML_HIP_GRAPHS is on by default; leave it. RDNA1 has no MFMA, so MMQ_MFMA is irrelevant.
cmake -S $src -B $build -G Ninja `
    -DGGML_HIP=ON `
    -DHIP_PLATFORM=amd `
    -DGPU_TARGETS=gfx1010 `
    -DCMAKE_C_COMPILER=clang `
    -DCMAKE_CXX_COMPILER=clang++ `
    -DCMAKE_BUILD_TYPE=Release `
    -DLLAMA_CURL=OFF `
    -DLLAMA_BUILD_TESTS=OFF `
    -DLLAMA_BUILD_EXAMPLES=OFF `
    -DLLAMA_BUILD_TOOLS=ON
if ($LASTEXITCODE) { throw "cmake configure failed" }

cmake --build $build --config Release -j 12
if ($LASTEXITCODE) { throw "build failed" }

# Collect a self-contained runtime folder: our binaries + the HIP/rocBLAS DLLs they load.
New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item "$build\bin\*" $out -Recurse -Force
foreach ($dll in "hipblas.dll", "rocblas.dll", "amd_comgr_2.dll") {
    if (Test-Path "$hip\bin\$dll") { Copy-Item "$hip\bin\$dll" $out -Force }
}
# rocBLAS finds its Tensile kernels at <rocblas.dll dir>\rocblas\library
if (Test-Path "$hip\bin\rocblas\library") { Copy-Item "$hip\bin\rocblas" "$out\rocblas" -Recurse -Force }

Write-Host "`nBUILD OK -> $out"
& "$out\llama-cli.exe" --list-devices

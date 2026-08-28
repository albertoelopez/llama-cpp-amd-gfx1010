# Swap the HIP SDK's stock rocBLAS (no gfx1010 Tensile kernels) for the community build
# that includes gfx1010:xnack- (likelovewant/ROCmLibs v0.6.2.4, for HIP SDK 6.2.4).
# The driver reports this card as 'gfx1010:xnack-' (see hip_arch_probe.py), which is why
# the xnack- variant of the bundle is the right one.
#
# Needs an elevated PowerShell (writes under C:\Program Files\AMD\ROCm\<ver>\bin).
$ErrorActionPreference = "Stop"

$bundle = "D:\AI_Projects\llama-cpp-amd\rocmlibs\extracted\gfx1010-xnack-hip6.2.4"
$hip = $env:HIP_PATH
if (-not $hip) { $hip = (Get-ChildItem "C:\Program Files\AMD\ROCm" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName }
$bin = "$hip\bin"
if (-not (Test-Path "$bin\rocblas.dll")) { throw "stock rocblas.dll not found in $bin -- is the HIP SDK installed?" }
if (-not (Test-Path "$bundle\rocblas.dll")) { throw "community bundle missing at $bundle" }

# Keep the originals so this is reversible.
if (-not (Test-Path "$bin\rocblas.dll.orig")) { Rename-Item "$bin\rocblas.dll" "rocblas.dll.orig" }
if ((Test-Path "$bin\rocblas\library") -and -not (Test-Path "$bin\rocblas\library.orig")) {
    Rename-Item "$bin\rocblas\library" "library.orig"
}

Copy-Item "$bundle\rocblas.dll" "$bin\rocblas.dll" -Force
New-Item -ItemType Directory -Force "$bin\rocblas" | Out-Null
Copy-Item "$bundle\library" "$bin\rocblas\library" -Recurse -Force

$n = (Get-ChildItem "$bin\rocblas\library" -Filter "*gfx1010-xnack-*").Count
Write-Host "rocBLAS swapped in $bin ; gfx1010-xnack- kernel files present: $n"

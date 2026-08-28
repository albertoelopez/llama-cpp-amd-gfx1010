"""Ask the driver-shipped HIP runtime directly whether it can see the GPU.

Bypasses llama.cpp entirely: if hipGetDeviceCount() returns 0 here, no HIP build of
anything will ever see the RX 5700 XT on this driver, regardless of gfx targets.
"""
import ctypes
import os
import sys

override = os.environ.get("HSA_OVERRIDE_GFX_VERSION")
print(f"HSA_OVERRIDE_GFX_VERSION={override!r}")

for name in ("amdhip64_6.dll", "amdhip64.dll"):
    path = os.path.join(r"C:\Windows\System32", name)
    try:
        hip = ctypes.WinDLL(path)
    except OSError as e:
        print(f"{name}: FAILED TO LOAD: {e}")
        continue

    hip.hipGetErrorString.restype = ctypes.c_char_p

    ver = ctypes.c_int()
    rc = hip.hipRuntimeGetVersion(ctypes.byref(ver))
    print(f"{name}: hipRuntimeGetVersion rc={rc} version={ver.value}")

    n = ctypes.c_int(-1)
    rc = hip.hipGetDeviceCount(ctypes.byref(n))
    msg = hip.hipGetErrorString(rc).decode(errors="replace") if rc else "hipSuccess"
    print(f"{name}: hipGetDeviceCount rc={rc} ({msg}) count={n.value}")

    for i in range(max(n.value, 0)):
        buf = ctypes.create_string_buffer(256)
        hip.hipDeviceGetName(buf, 256, i)
        mem = ctypes.c_size_t()
        hip.hipDeviceTotalMem(ctypes.byref(mem), i)
        # hipDeviceAttributeComputeCapabilityMajor/Minor = 4/5 in HIP 6 enum; gcnArch is
        # only in the (version-dependent) props struct, so report name + memory only.
        print(f"  device {i}: {buf.value.decode(errors='replace')}  totalMem={mem.value / 2**30:.2f} GiB")

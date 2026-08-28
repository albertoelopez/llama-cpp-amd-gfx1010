"""Report the exact gcnArchName the driver's HIP runtime uses for device 0.

rocBLAS picks its Tensile library file from this string (TensileLibrary_lazy_<arch>.dat),
so 'gfx1010' vs 'gfx1010:xnack-' decides which community rocBLAS bundle is the right one.
hipGetDeviceProperties' struct layout is version-specific, so rather than declare it we
hand the runtime a large zeroed buffer and scan it for the 'gfx' string.
"""
import ctypes, os, re
hip = ctypes.WinDLL(r"C:\Windows\System32\amdhip64_6.dll")
buf = ctypes.create_string_buffer(64 * 1024)
for sym in ("hipGetDevicePropertiesR0600", "hipGetDeviceProperties"):
    fn = getattr(hip, sym, None)
    if fn is None:
        print(f"{sym}: not exported"); continue
    rc = fn(buf, 0)
    hits = sorted(set(re.findall(rb"gfx[0-9a-f]+(?::[a-z+-]+)?", buf.raw)))
    print(f"{sym}: rc={rc} arch strings found: {[h.decode() for h in hits]}")
    if not rc:
        break

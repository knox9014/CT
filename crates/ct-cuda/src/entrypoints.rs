//! Restricted, explicitly versioned CUDA Driver function address lookup.
use super::*;
use std::ffi::CStr;
use std::ptr::null_mut;

struct Entry {
    name: &'static [u8],
    minimum: i32,
    maximum: i32,
    stream_independent_fallback: bool,
    pointer: *mut c_void,
}

// Version floors/signature transition verified against NVIDIA 12.0.107
// cudaTypedefs.h. This is a lookup ceiling, not a CUDA driver version claim.
fn entries() -> [Entry; 48] {
    macro_rules! e {
        ($name:literal, $function:path, $minimum:literal, $maximum:literal) => {
            Entry {
                name: $name,
                minimum: $minimum,
                maximum: $maximum,
                stream_independent_fallback: false,
                pointer: $function as *const () as *mut c_void,
            }
        };
        ($name:literal, $function:path, $minimum:literal) => {
            e!($name, $function, $minimum, 12000)
        };
    }
    // Only these bootstrap signatures/modes were also audited against 12.9.79
    // cudaTypedefs.h. This grants lookup compatibility, not a Driver version.
    macro_rules! g {
        ($name:literal, $function:path, $minimum:literal, $maximum:literal) => {
            Entry {
                stream_independent_fallback: true,
                ..e!($name, $function, $minimum, $maximum)
            }
        };
    }
    [
        g!(b"cuInit", cuInit, 2000, 12090),
        g!(b"cuDriverGetVersion", cuDriverGetVersion, 2020, 12090),
        g!(b"cuDeviceGetCount", cuDeviceGetCount, 2000, 12090),
        e!(b"cuDeviceGet", cuDeviceGet, 2000),
        e!(b"cuDeviceGetName", cuDeviceGetName, 2000),
        e!(b"cuDeviceTotalMem", cuDeviceTotalMem_v2, 3020),
        e!(b"cuDeviceGetAttribute", cuDeviceGetAttribute, 2000),
        e!(b"cuDevicePrimaryCtxRetain", cuDevicePrimaryCtxRetain, 7000),
        e!(
            b"cuDevicePrimaryCtxSetFlags",
            cuDevicePrimaryCtxSetFlags_v2,
            11000
        ),
        e!(b"cuCtxGetFlags", cuCtxGetFlags, 7000),
        e!(
            b"cuDevicePrimaryCtxReset",
            cuDevicePrimaryCtxReset_v2,
            11000
        ),
        e!(
            b"cuDevicePrimaryCtxGetState",
            cuDevicePrimaryCtxGetState,
            7000
        ),
        e!(
            b"cuDevicePrimaryCtxRelease",
            cuDevicePrimaryCtxRelease_v2,
            11000
        ),
        e!(b"cuCtxCreate", cuCtxCreate_v2, 3020, 11039),
        e!(b"cuCtxDestroy", cuCtxDestroy_v2, 4000),
        e!(b"cuCtxGetCurrent", cuCtxGetCurrent, 4000),
        e!(b"cuCtxSetCurrent", cuCtxSetCurrent, 4000),
        e!(b"cuCtxPushCurrent", cuCtxPushCurrent_v2, 4000),
        e!(b"cuCtxPopCurrent", cuCtxPopCurrent_v2, 4000),
        e!(b"cuCtxGetDevice", cuCtxGetDevice, 2000),
        e!(b"cuCtxSynchronize", cuCtxSynchronize, 2000),
        e!(b"cuMemAlloc", cuMemAlloc_v2, 3020),
        e!(b"cuMemFree", cuMemFree_v2, 3020),
        e!(b"cuMemHostAlloc", cuMemHostAlloc, 2020),
        e!(b"cuEventCreate", cuEventCreate, 2000),
        e!(b"cuEventRecord", cuEventRecord, 2000),
        e!(b"cuEventSynchronize", cuEventSynchronize, 2000),
        e!(b"cuEventDestroy", cuEventDestroy_v2, 4000),
        e!(b"cuEventElapsedTime", cuEventElapsedTime, 2000),
        e!(b"cuMemFreeHost", cuMemFreeHost, 2000),
        e!(b"cuMemGetAddressRange", cuMemGetAddressRange_v2, 3020),
        e!(b"cuPointerGetAttribute", cuPointerGetAttribute, 4000),
        e!(b"cuMemcpyHtoD", cuMemcpyHtoD_v2, 3020),
        e!(b"cuMemcpyDtoH", cuMemcpyDtoH_v2, 3020),
        e!(b"cuMemcpyDtoD", cuMemcpyDtoD_v2, 3020),
        e!(b"cuMemsetD8", cuMemsetD8_v2, 3020),
        e!(b"cuMemsetD16", cuMemsetD16_v2, 3020),
        e!(b"cuMemsetD32", cuMemsetD32_v2, 3020),
        e!(b"cuGetErrorName", cuGetErrorName, 6000),
        e!(b"cuGetErrorString", cuGetErrorString, 6000),
        e!(b"cuModuleLoadData", modules::cuModuleLoadData, 2000),
        e!(b"cuModuleGetGlobal", modules::cuModuleGetGlobal_v2, 3020),
        e!(b"cuModuleGetFunction", modules::cuModuleGetFunction, 2000),
        e!(
            b"cuFuncGetParamInfo",
            modules::cuFuncGetParamInfo,
            12040,
            12090
        ),
        e!(b"cuModuleUnload", modules::cuModuleUnload, 2000),
        e!(b"cuLaunchKernel", modules::cuLaunchKernel, 4000),
        g!(b"cuGetProcAddress", cuGetProcAddress, 11030, 11999),
        g!(b"cuGetProcAddress", cuGetProcAddress_v2, 12000, 12090),
    ]
}

/// # Safety
/// symbol is a valid NUL-terminated string; output is writable pointer storage.
/// Returned functions retain their individual pointer/context preconditions.
#[no_mangle]
pub unsafe extern "system" fn cuGetProcAddress(
    symbol: *const c_char,
    output: *mut *mut c_void,
    version: i32,
    flags: u64,
) -> i32 {
    let result = cuGetProcAddress_v2(symbol, output, version, flags, null_mut());
    if result == 0 && (*output).is_null() {
        500
    } else {
        result
    }
}

/// # Safety
/// symbol is a valid NUL-terminated string; output and optional status are valid,
/// nonoverlapping writable storage. status may be null. No GPU initialization
/// is performed. Successful lookup does not imply support beyond each API's contract.
#[no_mangle]
pub unsafe extern "system" fn cuGetProcAddress_v2(
    symbol: *const c_char,
    output: *mut *mut c_void,
    version: i32,
    flags: u64,
    status: *mut i32,
) -> i32 {
    if !output.is_null() {
        output.write(null_mut());
    }
    if !status.is_null() {
        status.write(1);
    }
    if symbol.is_null() || output.is_null() || version <= 0 || flags > 2 {
        return INVALID;
    }
    let name = CStr::from_ptr(symbol).to_bytes();
    let entries = entries();
    let audited_bootstrap = entries.iter().any(|entry| {
        name == entry.name && entry.stream_independent_fallback && version <= entry.maximum
    });
    let audited_param_info = name == b"cuFuncGetParamInfo"
        && entries
            .iter()
            .any(|entry| name == entry.name && version <= entry.maximum);
    if (flags == 2 && !audited_bootstrap)
        || (version > 12000 && !audited_bootstrap && !audited_param_info)
    {
        return UNSUPPORTED;
    }
    let mut found = false;
    for entry in entries {
        if name == entry.name {
            found = true;
            if (entry.minimum..=entry.maximum).contains(&version) {
                output.write(entry.pointer);
                if !status.is_null() {
                    status.write(0);
                }
                return 0;
            }
        }
    }
    if found && !status.is_null() {
        status.write(2);
    }
    0
}

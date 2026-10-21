//! Restricted, explicitly versioned CUDA Driver function address lookup.
use super::*;
use std::ffi::CStr;
use std::ptr::null_mut;

struct Entry {
    name: &'static [u8],
    minimum: i32,
    maximum: i32,
    pointer: *mut c_void,
}

// Version floors/signature transition verified against NVIDIA 12.0.107
// cudaTypedefs.h. This is a lookup ceiling, not a CUDA driver version claim.
fn entries() -> [Entry; 38] {
    macro_rules! e {
        ($name:literal, $function:path, $minimum:literal, $maximum:literal) => {
            Entry {
                name: $name,
                minimum: $minimum,
                maximum: $maximum,
                pointer: $function as *const () as *mut c_void,
            }
        };
        ($name:literal, $function:path, $minimum:literal) => {
            e!($name, $function, $minimum, 12000)
        };
    }
    [
        e!(b"cuInit", cuInit, 2000),
        e!(b"cuDriverGetVersion", cuDriverGetVersion, 2020),
        e!(b"cuDeviceGetCount", cuDeviceGetCount, 2000),
        e!(b"cuDeviceGet", cuDeviceGet, 2000),
        e!(b"cuDeviceGetName", cuDeviceGetName, 2000),
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
        e!(b"cuModuleGetFunction", modules::cuModuleGetFunction, 2000),
        e!(b"cuModuleUnload", modules::cuModuleUnload, 2000),
        e!(b"cuLaunchKernel", modules::cuLaunchKernel, 4000),
        e!(b"cuGetProcAddress", cuGetProcAddress, 11030, 11999),
        e!(b"cuGetProcAddress", cuGetProcAddress_v2, 12000),
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
    if version > 12000 || flags == 2 {
        return UNSUPPORTED;
    }
    let name = CStr::from_ptr(symbol).to_bytes();
    let mut found = false;
    for entry in entries() {
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

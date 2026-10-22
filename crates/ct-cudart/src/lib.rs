#![allow(non_snake_case)]
#![allow(clippy::missing_safety_doc)]
#![allow(dead_code)] // Intermediate ABI skeleton; stateful wiring follows.
use std::ffi::{c_char, c_void};
mod device;
mod driver;
mod errors;
mod platform;
mod state;
use driver::DriverBridge;
use state::Runtime;
static BRIDGE: std::sync::OnceLock<Result<Runtime<DriverBridge>, i32>> = std::sync::OnceLock::new();
fn bridge() -> Result<&'static Runtime<DriverBridge>, i32> {
    BRIDGE
        .get_or_init(|| DriverBridge::open().map(Runtime::new))
        .as_ref()
        .map_err(|&code| code)
}
#[cfg(test)]
mod state_tests;
fn boundary(f: impl FnOnce() -> i32) -> i32 {
    errors::record(std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).unwrap_or(999))
}
unsafe fn scalar(out: *mut i32) -> i32 {
    if out.is_null() {
        return 1;
    }
    unsafe {
        *out = 0;
    }
    801
}
#[no_mangle]
pub unsafe extern "system" fn cudaGetDeviceCount(out: *mut i32) -> i32 {
    boundary(|| unsafe { device::scalar(out, true) })
}
#[no_mangle]
pub unsafe extern "system" fn cudaGetDevice(out: *mut i32) -> i32 {
    boundary(|| unsafe { device::scalar(out, false) })
}
#[no_mangle]
pub extern "system" fn cudaSetDevice(ordinal: i32) -> i32 {
    boundary(|| device::set_device(ordinal))
}
#[no_mangle]
pub extern "system" fn cudaDeviceSynchronize() -> i32 {
    boundary(device::synchronize)
}
#[no_mangle]
pub unsafe extern "system" fn cudaMalloc(out: *mut *mut c_void, _: usize) -> i32 {
    boundary(|| {
        if out.is_null() {
            1
        } else {
            unsafe {
                *out = std::ptr::null_mut();
            }
            801
        }
    })
}
#[no_mangle]
pub extern "system" fn cudaFree(_: *mut c_void) -> i32 {
    boundary(|| 801)
}
#[no_mangle]
pub unsafe extern "system" fn cudaMemcpy(
    _: *mut c_void,
    _: *const c_void,
    _: usize,
    _: i32,
) -> i32 {
    boundary(|| 801)
}
#[no_mangle]
pub extern "system" fn cudaMemset(_: *mut c_void, _: i32, _: usize) -> i32 {
    boundary(|| 801)
}
#[no_mangle]
pub extern "system" fn cudaGetLastError() -> i32 {
    errors::take()
}
#[no_mangle]
pub extern "system" fn cudaPeekAtLastError() -> i32 {
    errors::peek()
}
#[no_mangle]
pub extern "system" fn cudaGetErrorName(code: i32) -> *const c_char {
    errors::text(code, false)
}
#[no_mangle]
pub extern "system" fn cudaGetErrorString(code: i32) -> *const c_char {
    errors::text(code, true)
}
#[no_mangle]
pub unsafe extern "system" fn cudaDriverGetVersion(out: *mut i32) -> i32 {
    boundary(|| unsafe { scalar(out) })
}
#[no_mangle]
pub unsafe extern "system" fn cudaRuntimeGetVersion(out: *mut i32) -> i32 {
    boundary(|| unsafe { scalar(out) })
}
#[cfg(test)]
mod tests;

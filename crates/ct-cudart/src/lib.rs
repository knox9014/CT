#![allow(non_snake_case)]
#![allow(clippy::missing_safety_doc)]
use std::ffi::{c_char, c_void};
#[allow(dead_code)] // Export wiring follows native ABI proof.
mod configuration;
#[cfg(test)]
mod configuration_tests;
mod device;
mod driver;
mod errors;
mod memory;
#[cfg(test)]
mod memory_tests;
mod platform;
#[allow(dead_code)] // Wired into ABI exports after the independent native ABI gate.
mod registration;
#[cfg(test)]
mod registration_tests;
mod state;
use driver::DriverBridge;
use state::Runtime;
static BRIDGE: std::sync::OnceLock<Result<Runtime<DriverBridge>, i32>> = std::sync::OnceLock::new();
fn cached<T>(
    cache: &std::sync::OnceLock<Result<T, i32>>,
    load: impl FnOnce() -> Result<T, i32>,
) -> Result<&T, i32> {
    cache.get_or_init(load).as_ref().map_err(|&code| code)
}
fn bridge() -> Result<&'static Runtime<DriverBridge>, i32> {
    cached(&BRIDGE, || DriverBridge::open().map(Runtime::new))
}
#[cfg(test)]
mod state_tests;
fn boundary(f: impl FnOnce() -> i32) -> i32 {
    errors::record(std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).unwrap_or(999))
}
#[allow(dead_code)]
fn callback_boundary<T>(
    registry: &registration::Registry,
    token: Option<registration::Token>,
    f: impl FnOnce() -> Result<T, i32>,
) -> Result<T, i32> {
    let result = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        Ok(result) => result,
        Err(_) => {
            if let Some(token) = token {
                registry.fail(token, 999);
            }
            Err(999)
        }
    };
    if let Err(code) = result.as_ref() {
        errors::record(*code);
    }
    result
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
pub unsafe extern "system" fn cudaMalloc(out: *mut *mut c_void, size: usize) -> i32 {
    boundary(|| {
        if out.is_null() {
            1
        } else {
            unsafe {
                *out = std::ptr::null_mut();
            }
            if size == 0 {
                return 801;
            }
            match bridge() {
                Ok(rt) => unsafe { memory::allocate(rt, out, size) },
                Err(code) => code,
            }
        }
    })
}
#[no_mangle]
pub extern "system" fn cudaFree(ptr: *mut c_void) -> i32 {
    boundary(|| match bridge() {
        Ok(rt) => memory::free(rt, ptr),
        Err(code) => code,
    })
}
#[no_mangle]
pub unsafe extern "system" fn cudaMemcpy(
    dst: *mut c_void,
    src: *const c_void,
    size: usize,
    kind: i32,
) -> i32 {
    boundary(|| {
        if let Some(code) = unsafe { memory::copy_preflight(dst, src, size, kind) } {
            return code;
        }
        match bridge() {
            Ok(rt) => unsafe { memory::copy_device(rt, dst, src, size, kind) },
            Err(code) => code,
        }
    })
}
#[no_mangle]
pub extern "system" fn cudaMemset(ptr: *mut c_void, value: i32, size: usize) -> i32 {
    boundary(|| {
        if size == 0 {
            return 0;
        }
        if ptr.is_null() {
            return 1;
        }
        match bridge() {
            Ok(rt) => memory::fill(rt, ptr, value, size),
            Err(code) => code,
        }
    })
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

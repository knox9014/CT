#![allow(non_snake_case)]
#![allow(clippy::missing_safety_doc)]
use std::ffi::{c_char, c_void};
mod configuration;
#[cfg(test)]
mod configuration_tests;
mod device;
mod driver;
mod errors;
mod kernel_driver;
#[cfg(test)]
mod kernel_tests;
mod kernels;
mod memory;
#[cfg(test)]
mod memory_tests;
mod platform;
mod registration;
#[cfg(test)]
mod registration_image_tests;
mod registration_images;
#[cfg(test)]
mod registration_tests;
#[cfg(test)]
mod registration_variable_tests;
mod registration_variables;
mod state;
use driver::DriverBridge;
use state::Runtime;
static BRIDGE: std::sync::OnceLock<Result<Runtime<DriverBridge>, i32>> = std::sync::OnceLock::new();
static KERNELS: std::sync::OnceLock<kernels::KernelRuntime> = std::sync::OnceLock::new();
fn kernel_runtime() -> &'static kernels::KernelRuntime {
    KERNELS.get_or_init(kernels::KernelRuntime::new)
}
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

#[no_mangle]
pub unsafe extern "system" fn __cudaRegisterFatBinary(wrapper: *mut c_void) -> *mut *mut c_void {
    let registry = &kernel_runtime().registry;
    callback_boundary(registry, None, || unsafe { registry.register(wrapper) })
        .map(|token| token as *mut *mut c_void)
        .unwrap_or(std::ptr::null_mut())
}
#[no_mangle]
pub extern "system" fn __cudaRegisterFatBinaryEnd(token: *mut *mut c_void) {
    let registry = &kernel_runtime().registry;
    let _ = callback_boundary(registry, Some(token as usize), || {
        registry.end(token as usize)
    });
}
#[no_mangle]
pub extern "system" fn __cudaUnregisterFatBinary(token: *mut *mut c_void) {
    let registry = &kernel_runtime().registry;
    let _ = callback_boundary(registry, Some(token as usize), || {
        registry.retire(token as usize)
    });
}
#[no_mangle]
pub unsafe extern "system" fn __cudaRegisterFunction(
    token: *mut *mut c_void,
    host: *const c_char,
    device: *mut c_char,
    name: *const c_char,
    thread_limit: i32,
    tid: *mut configuration::Dim3,
    bid: *mut configuration::Dim3,
    block: *mut configuration::Dim3,
    grid: *mut configuration::Dim3,
    warp: *mut i32,
) {
    let registry = &kernel_runtime().registry;
    let _ = callback_boundary(registry, Some(token as usize), || {
        registry.function_state(token as usize)?;
        let names = (|| unsafe {
            let a = registration::copy_name(device.cast(), 1024)?;
            let b = registration::copy_name(name.cast(), 1024)?;
            if a != b {
                return Err(801);
            }
            Ok(())
        })();
        if let Err(code) = names {
            return Err(registry.fail_mapping(token as usize, host as usize, code));
        }
        unsafe {
            registry.function(
                token as usize,
                host as usize,
                device.cast(),
                registration::FunctionMetadata {
                    thread_limit,
                    optional: [
                        tid as usize,
                        bid as usize,
                        block as usize,
                        grid as usize,
                        warp as usize,
                    ],
                },
            )
        }
    });
}
#[no_mangle]
pub extern "system" fn __cudaPushCallConfiguration(
    grid: configuration::Dim3,
    block: configuration::Dim3,
    shared: usize,
    stream: *mut c_void,
) -> u32 {
    boundary(|| {
        configuration::push(configuration::Config {
            grid,
            block,
            shared,
            stream: stream as usize,
        })
    }) as u32
}
#[no_mangle]
pub unsafe extern "system" fn __cudaPopCallConfiguration(
    grid: *mut configuration::Dim3,
    block: *mut configuration::Dim3,
    shared: *mut usize,
    stream: *mut c_void,
) -> i32 {
    boundary(|| unsafe { configuration::pop(grid, block, shared, stream) })
}
#[no_mangle]
pub unsafe extern "system" fn cudaLaunchKernel(
    host: *const c_void,
    grid: configuration::Dim3,
    block: configuration::Dim3,
    args: *mut *mut c_void,
    shared: usize,
    stream: *mut c_void,
) -> i32 {
    boundary(|| {
        let kernel = kernel_runtime();
        match kernel.registry.lease(host as usize) {
            Ok(lease) => {
                if let Err(code) = lease.image() {
                    return code;
                }
            }
            Err(code) => return code,
        }
        let config = configuration::Config {
            grid,
            block,
            shared,
            stream: stream as usize,
        };
        let code = configuration::preflight(config);
        if code != 0 {
            return code;
        }
        match bridge() {
            Ok(rt) => unsafe {
                kernel.launch(
                    rt,
                    host as usize,
                    configuration::Config {
                        grid,
                        block,
                        shared,
                        stream: stream as usize,
                    },
                    args,
                )
            },
            Err(code) => code,
        }
    })
}

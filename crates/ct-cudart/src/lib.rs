#![allow(non_snake_case)]
#![allow(clippy::missing_safety_doc)]
use std::ffi::{c_char, c_void};
mod async_copy;
mod configuration;
#[cfg(test)]
mod configuration_tests;
mod device;
mod driver;
mod errors;
#[cfg(test)]
mod event_tests;
mod events;
mod host;
mod host_ownership;
#[cfg(test)]
mod host_ownership_tests;
mod kernel_driver;
#[cfg(test)]
mod kernel_tests;
mod kernels;
mod memory;
#[cfg(test)]
mod memory_tests;
mod platform;
mod profiler;
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
#[cfg(test)]
mod stream_tests;
mod streams;
mod submission;
#[cfg(test)]
mod submission_tests;
mod symbols;
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
pub unsafe extern "system" fn cudaDeviceGetAttribute(
    out: *mut i32,
    attribute: i32,
    device: i32,
) -> i32 {
    boundary(|| unsafe { device::attribute(out, attribute, device) })
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
pub unsafe extern "system" fn cudaStreamCreateWithFlags(out: *mut *mut c_void, flags: u32) -> i32 {
    boundary(|| unsafe { streams::create(out.cast(), flags) })
}
#[no_mangle]
pub extern "system" fn cudaStreamDestroy(stream: *mut c_void) -> i32 {
    boundary(|| streams::destroy(stream as usize))
}
#[no_mangle]
pub extern "system" fn cudaStreamSynchronize(stream: *mut c_void) -> i32 {
    boundary(|| device::synchronize_stream(stream as usize))
}
#[no_mangle]
pub unsafe extern "system" fn cudaHostAlloc(out: *mut *mut c_void, size: usize, flags: u32) -> i32 {
    boundary(|| {
        if let Some(code) = host::preflight(out.cast(), size, flags) {
            return code;
        }
        match bridge() {
            Ok(rt) => unsafe { host::allocate(rt, out.cast(), size, flags) },
            Err(code) => code,
        }
    })
}
#[no_mangle]
pub extern "system" fn cudaFreeHost(pointer: *mut c_void) -> i32 {
    boundary(|| {
        if pointer.is_null() {
            return 1;
        }
        match bridge() {
            Ok(rt) => host::free(rt, pointer as usize),
            Err(code) => code,
        }
    })
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
pub unsafe extern "system" fn cudaMemcpyAsync(
    dst: *mut c_void,
    src: *const c_void,
    bytes: usize,
    kind: i32,
    stream: *mut c_void,
) -> i32 {
    boundary(|| {
        let copy = async_copy::Copy {
            dst: dst as usize,
            src: src as usize,
            bytes,
            kind,
            stream: stream as usize,
        };
        if let Some(code) = async_copy::preflight(streams::registry(), copy) {
            return code;
        }
        match bridge() {
            Ok(rt) => async_copy::enqueue(
                rt,
                submission::scheduler(),
                host_ownership::registry(),
                streams::registry(),
                copy,
            ),
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
#[no_mangle]
pub unsafe extern "system" fn cudaGetSymbolAddress(
    out: *mut *mut c_void,
    symbol: *const c_void,
) -> i32 {
    boundary(|| unsafe {
        symbols::query(kernel_runtime(), bridge, symbol as usize, out, |p, _| {
            p as *mut c_void
        })
    })
}
#[no_mangle]
pub unsafe extern "system" fn cudaGetSymbolSize(out: *mut usize, symbol: *const c_void) -> i32 {
    boundary(|| unsafe { symbols::query(kernel_runtime(), bridge, symbol as usize, out, |_, n| n) })
}
#[no_mangle]
pub unsafe extern "system" fn cudaMemcpyToSymbol(
    symbol: *const c_void,
    src: *const c_void,
    count: usize,
    offset: usize,
    kind: i32,
) -> i32 {
    boundary(|| unsafe {
        symbols::copy(
            kernel_runtime(),
            bridge,
            symbol as usize,
            symbols::Transfer {
                data: src.cast_mut(),
                count,
                offset,
                kind,
                to: true,
            },
        )
    })
}
#[no_mangle]
pub unsafe extern "system" fn cudaMemcpyFromSymbol(
    dst: *mut c_void,
    symbol: *const c_void,
    count: usize,
    offset: usize,
    kind: i32,
) -> i32 {
    boundary(|| unsafe {
        symbols::copy(
            kernel_runtime(),
            bridge,
            symbol as usize,
            symbols::Transfer {
                data: dst,
                count,
                offset,
                kind,
                to: false,
            },
        )
    })
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

#[no_mangle]
pub unsafe extern "system" fn __cudaRegisterVar(
    token: *mut *mut c_void,
    host: *mut c_char,
    address: *mut c_char,
    name: *const c_char,
    external: i32,
    size: usize,
    constant: i32,
    global: i32,
) {
    let registry = &kernel_runtime().registry;
    let _ = callback_boundary(registry, Some(token as usize), || unsafe {
        registry.variable(
            token as usize,
            host as usize,
            address.cast(),
            name.cast(),
            registration_variables::VariableMetadata {
                external,
                size,
                constant,
                global,
            },
        )
    });
}

#[no_mangle]
pub unsafe extern "system" fn cudaEventCreate(out: *mut *mut c_void) -> i32 {
    boundary(|| {
        if out.is_null() {
            return 1;
        }
        let result = bridge().and_then(events::create);
        match result {
            Ok(token) => {
                unsafe {
                    out.write(token as *mut c_void);
                }
                0
            }
            Err(code) => code,
        }
    })
}
#[no_mangle]
pub extern "system" fn cudaEventRecord(event: *mut c_void, stream: *mut c_void) -> i32 {
    boundary(|| {
        if let Err(c) = events::registry().preflight(event as usize) {
            return c;
        }
        if let Err(c) = streams::registry().preflight(stream as usize) {
            return c;
        }
        bridge()
            .and_then(|rt| events::record(rt, event as usize, stream as usize))
            .err()
            .unwrap_or(0)
    })
}
#[no_mangle]
pub extern "system" fn cudaEventSynchronize(event: *mut c_void) -> i32 {
    boundary(|| {
        if let Err(c) = events::registry().preflight(event as usize) {
            return c;
        }
        bridge()
            .and_then(|rt| events::synchronize(rt, event as usize))
            .err()
            .unwrap_or(0)
    })
}
#[no_mangle]
pub extern "system" fn cudaEventDestroy(event: *mut c_void) -> i32 {
    boundary(|| {
        if let Err(c) = events::registry().preflight(event as usize) {
            return c;
        }
        bridge()
            .and_then(|rt| events::destroy(rt, event as usize))
            .err()
            .unwrap_or(0)
    })
}
#[no_mangle]
pub unsafe extern "system" fn cudaEventElapsedTime(
    out: *mut f32,
    start: *mut c_void,
    end: *mut c_void,
) -> i32 {
    boundary(|| {
        if out.is_null() {
            return 1;
        }
        for token in [start, end] {
            if let Err(c) = events::registry().preflight(token as usize) {
                return c;
            }
        }
        match bridge().and_then(|rt| events::elapsed(rt, start as usize, end as usize)) {
            Ok(value) => {
                unsafe {
                    out.write(value);
                }
                0
            }
            Err(code) => code,
        }
    })
}

#[no_mangle]
pub extern "system" fn cudaProfilerStart() -> i32 {
    boundary(|| match bridge() {
        Ok(rt) => profiler::no_collector(rt, submission::scheduler()),
        Err(code) => code,
    })
}
#[no_mangle]
pub extern "system" fn cudaProfilerStop() -> i32 {
    boundary(|| match bridge() {
        Ok(rt) => profiler::no_collector(rt, submission::scheduler()),
        Err(code) => code,
    })
}

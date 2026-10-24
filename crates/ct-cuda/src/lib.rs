//! Experimental CUDA Driver ABI subset. C caller pointers must be valid for the
//! specified access. Arbitrary invalid non-null host pointers cannot be validated.
#![cfg(all(windows, target_pointer_width = "64"))]
#![allow(non_snake_case)]
use ct_backend_intel::{Backend, Context, Module};
use ct_core::AllocationRanges;
use ct_ptx::ParamKind;
use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::ffi::{c_char, c_void};
use std::sync::{Mutex, OnceLock};

type CudaResult = Result<(), i32>;
const INVALID: i32 = 1;
const NOT_INITIALIZED: i32 = 3;
const INVALID_DEVICE: i32 = 101;
const INVALID_CONTEXT: i32 = 201;
const UNSUPPORTED: i32 = 801;
const UNKNOWN: i32 = 999;
struct OwnedContext {
    native: Context,
    allocations: AllocationRanges,
    modules: BTreeMap<usize, OwnedModule>,
    functions: BTreeMap<usize, OwnedFunction>,
}
struct OwnedModule {
    native: Module,
    entries: Vec<ct_codegen_spirv::CompiledEntry>,
    globals: std::sync::Arc<[ct_ptx::Global]>,
}
struct OwnedFunction {
    module: usize,
    entry: usize,
}
mod context_stack;
mod device_ranges;
use device_ranges::DeviceRanges;
mod entrypoints;
mod images;
mod memory;
mod memory_queries;
pub use memory_queries::{cuMemGetAddressRange_v2, cuPointerGetAttribute};
mod modules;
pub use memory::{cuMemcpyDtoD_v2, cuMemsetD16_v2, cuMemsetD32_v2, cuMemsetD8_v2};
pub use modules::cuModuleGetGlobal_v2;
mod primary;
mod primary_state;
pub use entrypoints::{cuGetProcAddress, cuGetProcAddress_v2};
pub use primary::{
    cuCtxGetFlags, cuDevicePrimaryCtxGetState, cuDevicePrimaryCtxRelease_v2,
    cuDevicePrimaryCtxReset_v2, cuDevicePrimaryCtxRetain, cuDevicePrimaryCtxSetFlags_v2,
};
#[derive(Default)]
struct Runtime {
    backend: Option<Backend>,
    contexts: BTreeMap<usize, OwnedContext>,
    next: usize,
    retired: Vec<OwnedContext>,
    primary: primary_state::PrimaryContexts,
    destroyed: BTreeSet<usize>,
}
static RUNTIME: OnceLock<Mutex<Runtime>> = OnceLock::new();
thread_local! {static CURRENT:RefCell<Vec<usize>>=const{RefCell::new(Vec::new())};}
fn current() -> Option<usize> {
    CURRENT.with(|s| s.borrow().last().copied())
}
fn native_error(code: u32) -> i32 {
    match code {
        0x70000002 | 0x70000003 => 2,
        0x78000003 => UNSUPPORTED,
        0x70000004 => 218,
        _ => UNKNOWN,
    }
}
fn backend(r: &Runtime) -> Result<&Backend, i32> {
    r.backend.as_ref().ok_or(NOT_INITIALIZED)
}
fn context_id(r: &Runtime) -> Result<usize, i32> {
    backend(r)?;
    let id = current().ok_or(INVALID_CONTEXT)?;
    validate_context(r, id)?;
    Ok(id)
}
fn validate_context(r: &Runtime, id: usize) -> CudaResult {
    if r.contexts.contains_key(&id) {
        Ok(())
    } else if r.primary.retired(id) || r.destroyed.contains(&id) {
        Err(709)
    } else {
        Err(INVALID_CONTEXT)
    }
}

fn create_owned_context(
    b: &mut Backend,
    contexts: &mut BTreeMap<usize, OwnedContext>,
    next: &mut usize,
    device: i32,
) -> Result<usize, i32> {
    let id = next.checked_add(1).ok_or(UNKNOWN)?;
    let native = b.create_context(device as usize).map_err(native_error)?;
    *next = id;
    contexts.insert(
        id,
        OwnedContext {
            native,
            allocations: AllocationRanges::default(),
            modules: BTreeMap::new(),
            functions: BTreeMap::new(),
        },
    );
    Ok(id)
}

// Removing the public handle precedes cleanup. An uncertain native cleanup is
// quarantined, and this helper deliberately never touches any thread's stack.
fn retire_context(r: &mut Runtime, id: usize) -> CudaResult {
    let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
    retire_owned(&mut r.contexts, &mut r.retired, id, |c| {
        cleanup_context(b, c)
    })
}

fn cleanup_context(b: &Backend, c: &mut OwnedContext) -> CudaResult {
    for module in c.modules.values_mut() {
        b.unload_module(&mut c.native, &mut module.native)
            .map_err(native_error)?;
    }
    b.destroy_context(&mut c.native, &c.allocations.bases())
        .map_err(native_error)
}

fn retire_owned<T>(
    contexts: &mut BTreeMap<usize, T>,
    retired: &mut Vec<T>,
    id: usize,
    cleanup: impl FnOnce(&mut T) -> CudaResult,
) -> CudaResult {
    let mut owned = contexts.remove(&id).ok_or(INVALID_CONTEXT)?;
    let result = cleanup(&mut owned);
    if result.is_err() {
        retired.push(owned);
    }
    result
}
fn invoke(f: impl FnOnce(&mut Runtime) -> CudaResult) -> i32 {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let mut runtime = RUNTIME
            .get_or_init(|| Mutex::new(Runtime::default()))
            .lock()
            .map_err(|_| UNKNOWN)?;
        f(&mut runtime)
    }))
    .unwrap_or(Err(UNKNOWN))
    .err()
    .unwrap_or(0)
}

/// Initialize CT's native device layer. Flags other than zero are unsupported.
#[no_mangle]
pub extern "system" fn cuInit(flags: u32) -> i32 {
    invoke(|r| {
        if flags != 0 {
            return Err(INVALID);
        }
        if r.backend.is_none() {
            let b = Backend::open().map_err(native_error)?;
            if b.devices.is_empty() {
                return Err(100);
            }
            r.backend = Some(b);
        }
        Ok(())
    })
}

/// # Safety
/// version must be valid writable memory for one C int.
#[no_mangle]
pub unsafe extern "system" fn cuDriverGetVersion(version: *mut i32) -> i32 {
    if version.is_null() {
        return INVALID;
    }
    version.write(0);
    UNSUPPORTED
}
/// # Safety
/// count must be writable for one C int.
#[no_mangle]
pub unsafe extern "system" fn cuDeviceGetCount(count: *mut i32) -> i32 {
    invoke(|r| {
        let b = backend(r)?;
        if count.is_null() {
            return Err(INVALID);
        }
        count.write(b.devices.len() as i32);
        Ok(())
    })
}
/// # Safety
/// device must be writable for one C int.
#[no_mangle]
pub unsafe extern "system" fn cuDeviceGet(device: *mut i32, ordinal: i32) -> i32 {
    invoke(|r| {
        let b = backend(r)?;
        if device.is_null() {
            return Err(INVALID);
        }
        if ordinal < 0 || ordinal as usize >= b.devices.len() {
            return Err(INVALID_DEVICE);
        }
        device.write(ordinal);
        Ok(())
    })
}
/// # Safety
/// name must be writable for length bytes; length must be positive.
#[no_mangle]
pub unsafe extern "system" fn cuDeviceGetName(name: *mut c_char, length: i32, device: i32) -> i32 {
    invoke(|r| {
        let b = backend(r)?;
        if name.is_null() || length <= 0 {
            return Err(INVALID);
        }
        let d = b.devices.get(device as usize).ok_or(INVALID_DEVICE)?;
        let bytes = d.name.as_bytes();
        let n = bytes.len().min(length as usize - 1);
        std::ptr::copy_nonoverlapping(bytes.as_ptr(), name.cast(), n);
        name.add(n).write(0);
        Ok(())
    })
}
/// # Safety
/// value must be writable for one C int. Group/grid limits and compute mode exist.
#[no_mangle]
pub unsafe extern "system" fn cuDeviceGetAttribute(
    value: *mut i32,
    attribute: i32,
    device: i32,
) -> i32 {
    invoke(|r| {
        let b = backend(r)?;
        if value.is_null() {
            return Err(INVALID);
        }
        value.write(0);
        let d = b.devices.get(device as usize).ok_or(INVALID_DEVICE)?;
        // CT has no exclusive/prohibited compute-mode mechanism. Its contexts
        // use ordinary shared device access (CUDA CU_COMPUTEMODE_DEFAULT).
        if attribute == 20 {
            return Ok(());
        }
        let x = match attribute {
            1..=4 => d.max_group[attribute as usize - 1],
            5..=7 => d.max_groups[attribute as usize - 5],
            _ => return Err(UNSUPPORTED),
        };
        if x > i32::MAX as u32 {
            return Err(UNSUPPORTED);
        }
        value.write(x as i32);
        Ok(())
    })
}
/// # Safety
/// output must be writable for one context handle. Only flags=0 is supported.
#[no_mangle]
pub unsafe extern "system" fn cuCtxCreate_v2(
    output: *mut *mut c_void,
    flags: u32,
    device: i32,
) -> i32 {
    invoke(|r| {
        backend(r)?;
        if output.is_null() {
            return Err(INVALID);
        }
        output.write(std::ptr::null_mut());
        if flags != 0 {
            return Err(INVALID);
        }
        let b = r.backend.as_mut().ok_or(NOT_INITIALIZED)?;
        if device < 0 || device as usize >= b.devices.len() {
            return Err(INVALID_DEVICE);
        }
        let next = create_owned_context(b, &mut r.contexts, &mut r.next, device)?;
        CURRENT.with(|s| s.borrow_mut().push(next));
        output.write(next as *mut c_void);
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuCtxDestroy_v2(context: *mut c_void) -> i32 {
    invoke(|r| {
        backend(r)?;
        let id = context as usize;
        validate_context(r, id)?;
        if r.primary.owns(id) {
            return Err(INVALID_CONTEXT);
        }
        r.destroyed.insert(id);
        CURRENT.with(|s| context_stack::pop_destroyed_current(&mut s.borrow_mut(), id));
        retire_context(r, id)
    })
}
/// # Safety
/// context must be writable for one handle. A stale current handle is an error.
#[no_mangle]
pub unsafe extern "system" fn cuCtxGetCurrent(context: *mut *mut c_void) -> i32 {
    invoke(|r| {
        backend(r)?;
        if context.is_null() {
            return Err(INVALID);
        }
        context.write(std::ptr::null_mut());
        if let Some(id) = current() {
            validate_context(r, id)?;
            context.write(id as *mut c_void);
        }
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuCtxSetCurrent(context: *mut c_void) -> i32 {
    invoke(|r| {
        backend(r)?;
        let id = context as usize;
        if id != 0 {
            validate_context(r, id)?;
        }
        CURRENT.with(|s| {
            let mut v = s.borrow_mut();
            v.pop();
            if id != 0 {
                v.push(id);
            }
        });
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuCtxPushCurrent_v2(context: *mut c_void) -> i32 {
    invoke(|r| {
        backend(r)?;
        let id = context as usize;
        validate_context(r, id)?;
        CURRENT.with(|s| s.borrow_mut().push(id));
        Ok(())
    })
}
/// # Safety
/// context must be writable for one handle.
#[no_mangle]
pub unsafe extern "system" fn cuCtxPopCurrent_v2(context: *mut *mut c_void) -> i32 {
    invoke(|r| {
        backend(r)?;
        if context.is_null() {
            return Err(INVALID);
        }
        context.write(std::ptr::null_mut());
        let id = context_id(r)?;
        CURRENT.with(|s| s.borrow_mut().pop());
        context.write(id as *mut c_void);
        Ok(())
    })
}
/// # Safety
/// device must be writable for one C int.
#[no_mangle]
pub unsafe extern "system" fn cuCtxGetDevice(device: *mut i32) -> i32 {
    invoke(|r| {
        if device.is_null() {
            return Err(INVALID);
        }
        let id = context_id(r)?;
        device.write(r.contexts[&id].native.device as i32);
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuCtxSynchronize() -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        b.synchronize(&mut c.native).map_err(native_error)
    })
}
/// # Safety
/// output must be writable for one 64-bit device address.
#[no_mangle]
pub unsafe extern "system" fn cuMemAlloc_v2(output: *mut u64, size: usize) -> i32 {
    invoke(|r| {
        if output.is_null() {
            return Err(INVALID);
        }
        output.write(0);
        let id = context_id(r)?;
        if size == 0 {
            return Err(INVALID);
        }
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        let p = b.allocate(&mut c.native, size).map_err(native_error)?;
        if !c.allocations.insert(p, size) {
            let _ = b.free(&mut c.native, p);
            return Err(UNKNOWN);
        }
        output.write(p);
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuMemFree_v2(pointer: u64) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if !c.allocations.bases().contains(&pointer) {
            return Err(INVALID);
        }
        b.free(&mut c.native, pointer).map_err(native_error)?;
        c.allocations.remove(pointer);
        Ok(())
    })
}
unsafe fn transfer(device: u64, host: *mut c_void, size: usize, to_device: bool) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        if size > 0 && host.is_null() {
            return Err(INVALID);
        }
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if !c.contains_device(device, size) {
            return Err(INVALID);
        }
        b.copy(&mut c.native, device, host, size, to_device)
            .map_err(native_error)
    })
}
/// # Safety
/// source must be readable for size bytes and must not alias the staging memory.
#[no_mangle]
pub unsafe extern "system" fn cuMemcpyHtoD_v2(
    destination: u64,
    source: *const c_void,
    size: usize,
) -> i32 {
    transfer(destination, source.cast_mut(), size, true)
}
/// # Safety
/// destination must be writable for size bytes.
#[no_mangle]
pub unsafe extern "system" fn cuMemcpyDtoH_v2(
    destination: *mut c_void,
    source: u64,
    size: usize,
) -> i32 {
    transfer(source, destination, size, false)
}

fn error_text(code: i32) -> Option<(&'static std::ffi::CStr, &'static std::ffi::CStr)> {
    Some(match code {
        0 => (c"CUDA_SUCCESS", c"success"),
        1 => (
            c"CUDA_ERROR_INVALID_VALUE",
            c"invalid argument or allocation range",
        ),
        2 => (
            c"CUDA_ERROR_OUT_OF_MEMORY",
            c"native memory allocation failed",
        ),
        3 => (c"CUDA_ERROR_NOT_INITIALIZED", c"call cuInit first"),
        100 => (c"CUDA_ERROR_NO_DEVICE", c"no supported device"),
        101 => (c"CUDA_ERROR_INVALID_DEVICE", c"invalid device ordinal"),
        201 => (
            c"CUDA_ERROR_INVALID_CONTEXT",
            c"no valid current context or stale context",
        ),
        218 => (
            c"CUDA_ERROR_INVALID_PTX",
            c"invalid PTX in the implemented profile",
        ),
        400 => (
            c"CUDA_ERROR_INVALID_HANDLE",
            c"invalid, stale or foreign module/function handle",
        ),
        500 => (c"CUDA_ERROR_NOT_FOUND", c"entry point not found in module"),
        709 => (
            c"CUDA_ERROR_CONTEXT_IS_DESTROYED",
            c"context has been destroyed or primary context released",
        ),
        801 => (
            c"CUDA_ERROR_NOT_SUPPORTED",
            c"not implemented by this experimental CT subset",
        ),
        999 => (c"CUDA_ERROR_UNKNOWN", c"native backend or runtime failure"),
        _ => return None,
    })
}
/// # Safety
/// output must be writable for one pointer. Returned static string is read-only.
#[no_mangle]
pub unsafe extern "system" fn cuGetErrorName(code: i32, output: *mut *const c_char) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    output.write(std::ptr::null());
    if let Some((name, _)) = error_text(code) {
        output.write(name.as_ptr());
        0
    } else {
        INVALID
    }
}
/// # Safety
/// output must be writable for one pointer. Returned static string is read-only.
#[no_mangle]
pub unsafe extern "system" fn cuGetErrorString(code: i32, output: *mut *const c_char) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    output.write(std::ptr::null());
    if let Some((_, message)) = error_text(code) {
        output.write(message.as_ptr());
        0
    } else {
        INVALID
    }
}

#[cfg(test)]
mod failure_mapping_tests {
    use super::*;
    #[test]
    fn ordinary_destroyed_handles_stay_distinct_from_unknown_handles() {
        let mut runtime = Runtime::default();
        runtime.destroyed.insert(42);
        assert_eq!(validate_context(&runtime, 42), Err(709));
        assert_eq!(validate_context(&runtime, 43), Err(201));
        assert_eq!(validate_context(&runtime, 0), Err(201));
    }
    #[test]
    fn failed_cleanup_quarantines_once_and_never_retries_removed_resources() {
        let mut contexts = BTreeMap::from([(7, 42)]);
        let mut retired = Vec::new();
        let mut calls = 0;
        assert_eq!(
            retire_owned(&mut contexts, &mut retired, 7, |resource| {
                calls += 1;
                *resource = 43;
                Err(999)
            }),
            Err(999)
        );
        assert!(contexts.is_empty());
        assert_eq!(retired, vec![43]);
        assert_eq!(
            retire_owned(&mut contexts, &mut retired, 7, |_| {
                calls += 1;
                Ok(())
            }),
            Err(201)
        );
        assert_eq!(calls, 1);
    }
    #[test]
    fn native_failures_never_map_to_success_and_oom_keeps_its_cuda_category() {
        for (native, cuda) in [
            (0x70000002, 2),
            (0x70000003, 2),
            (0x70000001, 999),
            (0x70000006, 999),
            (1, 999),
            (0x7ffffffe, 999),
        ] {
            assert_eq!(native_error(native), cuda);
            assert!(error_text(cuda).is_some());
        }
    }
}

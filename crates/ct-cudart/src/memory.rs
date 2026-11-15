use crate::driver::DriverCalls;
use crate::errors::from_driver;
use crate::state::Runtime;
use std::ffi::c_void;
pub unsafe fn copy_host(dst: *mut u8, src: *const u8, size: usize) -> i32 {
    if size == 0 {
        return 0;
    }
    if dst.is_null() || src.is_null() || size > isize::MAX as usize {
        return 1;
    }
    let Some(de) = (dst as usize).checked_add(size) else {
        return 1;
    };
    let Some(se) = (src as usize).checked_add(size) else {
        return 1;
    };
    if (dst as usize) < se && (src as usize) < de {
        return 1;
    }
    // Readable/writable host storage is a caller precondition, as in the C ABI.
    unsafe {
        std::ptr::copy_nonoverlapping(src, dst, size);
    }
    0
}
pub unsafe fn copy_preflight(
    dst: *mut c_void,
    src: *const c_void,
    size: usize,
    kind: i32,
) -> Option<i32> {
    match kind {
        4 => return Some(801),
        0..=3 => {}
        _ => return Some(21),
    }
    if size == 0 {
        return Some(0);
    }
    if dst.is_null() || src.is_null() {
        return Some(1);
    }
    if kind == 0 {
        return Some(unsafe { copy_host(dst.cast(), src.cast(), size) });
    }
    None
}
pub unsafe fn copy_device<D: DriverCalls>(
    rt: &Runtime<D>,
    dst: *mut c_void,
    src: *const c_void,
    size: usize,
    kind: i32,
) -> i32 {
    if let Some(code) = unsafe { copy_preflight(dst, src, size, kind) } {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    crate::submission::scheduler()
        .barrier(context, false, || {
            let code = from_driver(match kind {
                1 => unsafe { rt.driver.copy_htod(dst as u64, src.cast(), size) },
                2 => unsafe { rt.driver.copy_dtoh(dst.cast(), src as u64, size) },
                3 => rt.driver.copy_dtod(dst as u64, src as u64, size),
                _ => unreachable!(),
            });
            if code == 0 {
                Ok(())
            } else {
                Err(code)
            }
        })
        .err()
        .unwrap_or(0)
}

pub unsafe fn allocate<D: DriverCalls>(rt: &Runtime<D>, out: *mut *mut c_void, size: usize) -> i32 {
    if out.is_null() {
        return 1;
    }
    unsafe {
        *out = std::ptr::null_mut();
    }
    if size == 0 {
        return 801;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    match crate::submission::scheduler().barrier(context, false, || {
        rt.driver.allocate(size).map_err(from_driver)
    }) {
        Ok(pointer) => {
            unsafe {
                *out = pointer as *mut c_void;
            }
            0
        }
        Err(code) => code,
    }
}

pub fn free<D: DriverCalls>(rt: &Runtime<D>, ptr: *mut c_void) -> i32 {
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    crate::submission::scheduler()
        .barrier(context, true, || {
            let code = if ptr.is_null() {
                0
            } else {
                from_driver(rt.driver.free(ptr as u64))
            };
            if code == 0 {
                Ok(())
            } else {
                Err(code)
            }
        })
        .err()
        .unwrap_or(0)
}

pub fn fill<D: DriverCalls>(rt: &Runtime<D>, ptr: *mut c_void, value: i32, size: usize) -> i32 {
    if size == 0 {
        return 0;
    }
    if ptr.is_null() {
        return 1;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    crate::submission::scheduler()
        .barrier(context, false, || {
            match from_driver(rt.driver.fill8(ptr as u64, value as u8, size)) {
                0 => Ok(()),
                code => Err(code),
            }
        })
        .err()
        .unwrap_or(0)
}

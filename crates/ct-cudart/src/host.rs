//! Synchronous native host storage; async acquire-use/free exclusion is separate.
use crate::{driver::DriverCalls, errors::from_driver, state::Runtime};
pub fn preflight(out: *mut usize, size: usize, flags: u32) -> Option<i32> {
    if out.is_null() || size == 0 || flags & !7 != 0 {
        Some(1)
    } else if flags != 0 {
        Some(801)
    } else {
        None
    }
}
pub unsafe fn allocate<D: DriverCalls>(
    rt: &Runtime<D>,
    out: *mut usize,
    size: usize,
    flags: u32,
) -> i32 {
    if let Some(code) = preflight(out, size, flags) {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    if let Err(code) = rt.driver.prepare_host() {
        return code;
    }
    match crate::submission::scheduler().barrier(context, false, || {
        crate::host_ownership::registry().allocate(context, size, || {
            rt.driver.allocate_host(size).map_err(from_driver)
        })
    }) {
        Ok(pointer) => {
            unsafe {
                *out = pointer;
            }
            0
        }
        Err(code) => code,
    }
}

pub fn free<D: DriverCalls>(rt: &Runtime<D>, pointer: usize) -> i32 {
    if pointer == 0 {
        return 1;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    if let Err(code) = rt.driver.prepare_host() {
        return code;
    }
    crate::submission::scheduler()
        .barrier(context, true, || {
            crate::host_ownership::registry().free(context, pointer, || {
                match from_driver(rt.driver.free_host(pointer)) {
                    0 => Ok(()),
                    code => Err(code),
                }
            })
        })
        .err()
        .unwrap_or(0)
}

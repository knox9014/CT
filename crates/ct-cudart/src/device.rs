use crate::{bridge, errors};
pub unsafe fn scalar(out: *mut i32, count: bool) -> i32 {
    if out.is_null() {
        return 1;
    }
    unsafe {
        *out = 0;
    }
    let runtime = match bridge() {
        Ok(runtime) => runtime,
        Err(code) => return code,
    };
    let result = if count {
        runtime.get_count()
    } else {
        runtime.get_device()
    };
    match result {
        Ok(value) => {
            unsafe {
                *out = value;
            }
            0
        }
        Err(code) => errors::from_driver(code),
    }
}
pub fn set_device(ordinal: i32) -> i32 {
    match bridge() {
        Ok(rt) => errors::from_driver(rt.set_device(ordinal)),
        Err(code) => code,
    }
}
pub fn synchronize() -> i32 {
    let rt = match bridge() {
        Ok(rt) => rt,
        Err(code) => return code,
    };
    match rt.ensure_current() {
        Ok(context) => match crate::kernel_runtime().drain(&rt.driver, context) {
            Ok(()) => errors::from_driver(crate::driver::DriverCalls::synchronize(&rt.driver)),
            Err(code) => code,
        },
        Err(code) => errors::from_driver(code),
    }
}

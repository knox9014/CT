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
pub fn synchronization_query<D: crate::driver::DriverCalls>(
    rt: &crate::state::Runtime<D>,
    stream: usize,
    drain: impl FnOnce(&D, crate::driver::Context) -> Result<(), i32>,
) -> i32 {
    if let Err(code) = crate::streams::registry().preflight(stream) {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(context) => context,
        Err(code) => return errors::from_driver(code),
    };
    let action = || {
        crate::submission::scheduler().barrier(context, false, || {
            match drain(&rt.driver, context) {
                Ok(()) => match errors::from_driver(rt.driver.synchronize()) {
                    0 => Ok(()),
                    code => Err(code),
                },
                Err(code) => Err(code),
            }
        })
    };
    if stream != 0 {
        return crate::streams::registry()
            .run(context, stream, action)
            .err()
            .unwrap_or(0);
    }
    action().err().unwrap_or(0)
}
pub fn synchronize_stream(stream: usize) -> i32 {
    // Reject unsupported/stale handles before resolving the process-local Driver.
    if let Err(code) = crate::streams::registry().preflight(stream) {
        return code;
    }
    let rt = match bridge() {
        Ok(rt) => rt,
        Err(code) => return code,
    };
    synchronization_query(rt, stream, |driver, context| {
        crate::kernel_runtime().drain(driver, context)
    })
}
pub fn synchronize() -> i32 {
    synchronize_stream(0)
}

// CT's bounded attribute subset; unsupported combinations have explicit preflight precedence.
pub fn attribute_preflight(out: *mut i32, attribute: i32, ordinal: i32) -> Option<i32> {
    if out.is_null() {
        Some(1)
    } else if ordinal < 0 {
        Some(101)
    } else if !matches!(attribute, 1..=8 | 15 | 16 | 20 | 40 | 75 | 76) {
        Some(801)
    } else {
        None
    }
}
pub unsafe fn attribute_query<D: crate::driver::DriverCalls>(
    rt: &crate::state::Runtime<D>,
    out: *mut i32,
    attribute: i32,
    ordinal: i32,
) -> i32 {
    if let Some(code) = attribute_preflight(out, attribute, ordinal) {
        return code;
    }
    let initialized = rt.initialize();
    if initialized != 0 {
        return errors::from_driver(initialized);
    }
    let device = match rt.driver.device(ordinal) {
        Ok(device) => device,
        Err(code) => return errors::from_driver(code),
    };
    // Preparation errors are Runtime-domain (35); raw Driver errors are mapped below.
    if let Err(code) = rt.driver.prepare_device_attribute() {
        return code;
    }
    match rt.driver.device_attribute(attribute, device) {
        Ok(value) => {
            unsafe {
                *out = value;
            }
            0
        }
        Err(code) => errors::from_driver(code),
    }
}
pub unsafe fn attribute(out: *mut i32, attribute: i32, ordinal: i32) -> i32 {
    if let Some(code) = attribute_preflight(out, attribute, ordinal) {
        return code;
    }
    match bridge() {
        Ok(rt) => unsafe { attribute_query(rt, out, attribute, ordinal) },
        Err(code) => code,
    }
}

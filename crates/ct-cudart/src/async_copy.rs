//! Owned asynchronous copy commands; no borrowed caller argument stack.
use crate::{driver::DriverCalls, errors::from_driver, state::Runtime};
#[derive(Clone, Copy)]
pub struct Copy {
    pub dst: usize,
    pub src: usize,
    pub bytes: usize,
    pub kind: i32,
    pub stream: usize,
}
pub fn preflight(streams: &crate::streams::Registry, copy: Copy) -> Option<i32> {
    match copy.kind {
        0 | 4 => return Some(801),
        1..=3 => {}
        _ => return Some(21),
    }
    if let Err(code) = streams.preflight(copy.stream) {
        return Some(code);
    }
    if copy.bytes == 0 {
        return Some(0);
    }
    if copy.dst == 0 || copy.src == 0 || copy.bytes > isize::MAX as usize {
        return Some(1);
    }
    let (Some(de), Some(se)) = (
        copy.dst.checked_add(copy.bytes),
        copy.src.checked_add(copy.bytes),
    ) else {
        return Some(1);
    };
    if copy.kind == 3 && copy.dst < se && copy.src < de {
        return Some(1);
    }
    None
}
pub fn enqueue<D: DriverCalls + 'static>(
    rt: &'static Runtime<D>,
    queue: &crate::submission::Scheduler,
    hosts: &crate::host_ownership::Registry,
    streams: &crate::streams::Registry,
    copy: Copy,
) -> i32 {
    if let Some(code) = preflight(streams, copy) {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    let submit = || {
        queue.submit(context, || {
            let held = match copy.kind {
                1 => Some(hosts.acquire(context, copy.src, copy.bytes)?),
                2 => Some(hosts.acquire(context, copy.dst, copy.bytes)?),
                _ => None,
            };
            Ok(Box::new(move || {
                let _keep_alive = held;
                let selected = from_driver(rt.driver.set_current(context));
                if selected != 0 {
                    return selected;
                }
                from_driver(match copy.kind {
                    1 => unsafe {
                        rt.driver
                            .copy_htod(copy.dst as u64, copy.src as *const u8, copy.bytes)
                    },
                    2 => unsafe {
                        rt.driver
                            .copy_dtoh(copy.dst as *mut u8, copy.src as u64, copy.bytes)
                    },
                    3 => rt
                        .driver
                        .copy_dtod(copy.dst as u64, copy.src as u64, copy.bytes),
                    _ => unreachable!(),
                })
            }))
        })
    };
    let result = if copy.stream == 0 {
        submit()
    } else {
        streams.run(context, copy.stream, submit)
    };
    result.err().unwrap_or(0)
}

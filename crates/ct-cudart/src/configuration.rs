//! CPU-only per-thread compiler launch configuration.
use std::cell::RefCell;
use std::ffi::c_void;
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Dim3 {
    pub x: u32,
    pub y: u32,
    pub z: u32,
}
impl Dim3 {
    pub fn axes(self) -> [u32; 3] {
        [self.x, self.y, self.z]
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Config {
    pub grid: Dim3,
    pub block: Dim3,
    pub shared: usize,
    pub stream: usize,
}
thread_local! { static STACK:RefCell<Vec<Config>> = const {RefCell::new(Vec::new())}; }
#[cfg(test)]
thread_local! { pub static FAIL_RESERVATION:std::cell::Cell<bool> = const {std::cell::Cell::new(false)}; }
pub fn preflight(c: Config) -> i32 {
    if c.grid.axes().contains(&0) || c.block.axes().contains(&0) {
        9
    } else if c.shared != 0 || c.stream != 0 {
        801
    } else {
        0
    }
}
pub fn push(c: Config) -> i32 {
    let code = preflight(c);
    if code != 0 {
        return code;
    }
    STACK.with(|stack| {
        let Ok(mut stack) = stack.try_borrow_mut() else {
            return 999;
        };
        if stack.len() >= 64 {
            return 801;
        }
        #[cfg(test)]
        if FAIL_RESERVATION.get() {
            return 2;
        }
        if stack.try_reserve_exact(1).is_err() {
            return 2;
        }
        stack.push(c);
        0
    })
}
pub unsafe fn pop(
    grid: *mut Dim3,
    block: *mut Dim3,
    shared: *mut usize,
    stream: *mut c_void,
) -> i32 {
    if grid.is_null() || block.is_null() || shared.is_null() || stream.is_null() {
        return 1;
    }
    STACK.with(|stack| {
        let Ok(mut stack) = stack.try_borrow_mut() else {
            return 999;
        };
        let Some(c) = stack.pop() else {
            return 9;
        };
        unsafe {
            grid.write(c.grid);
            block.write(c.block);
            shared.write(c.shared);
            stream.cast::<*mut c_void>().write(c.stream as *mut c_void);
        }
        0
    })
}

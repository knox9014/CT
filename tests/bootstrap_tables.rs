// TEST ONLY: typed deny callbacks, never exposed to CUDA Runtime.
#![allow(non_snake_case)]
#[cfg(not(all(target_os = "windows", target_pointer_width = "64")))]
compile_error!("This fixture is reviewed only for Windows x64");
use std::ffi::c_void;
use std::ptr::{null, null_mut};
use std::sync::atomic::{AtomicU64, Ordering};

#[repr(C)]
pub struct CudartTable {
    pub byte_size: usize,
    pub module: unsafe extern "system" fn(*mut *mut c_void, *const c_void) -> i32,
    pub context: unsafe extern "system" fn(*mut *mut c_void, i32) -> i32,
    pub hole3: usize,
    pub primary: unsafe extern "system" fn(i32, u32) -> i32,
    pub hole5: usize,
    pub module_ext1: unsafe extern "system" fn(
        *mut *mut c_void,
        *const c_void,
        *mut c_void,
        *mut c_void,
        u32,
    ) -> i32,
    pub opaque_void: unsafe extern "system" fn(usize),
    pub module_ext2: unsafe extern "system" fn(
        *const c_void,
        *mut *mut c_void,
        *mut c_void,
        *mut c_void,
        u32,
    ) -> i32,
    pub hole9: usize,
    pub hole10: usize,
    pub hole11: usize,
    pub compiler: unsafe extern "system" fn() -> i32,
}

#[repr(C)]
pub struct HooksTable {
    pub byte_size: usize,
    pub hole1: usize,
    pub first: unsafe extern "system" fn(*mut *mut c_void, *mut usize),
    pub hole3: usize,
    pub hole4: usize,
    pub hole5: usize,
    pub second: unsafe extern "system" fn(*mut *mut c_void, *mut usize),
}

#[repr(C)]
pub struct TableState {
    pub mask: u64,
    pub stopped: u32,
    pub reserved: u32,
}

static HITS: AtomicU64 = AtomicU64::new(0);
fn hit(bit: u32) {
    HITS.fetch_or(1u64 << bit, Ordering::SeqCst);
}
unsafe fn clear_status(output: *mut *mut c_void) -> i32 {
    if output.is_null() {
        return 1;
    }
    output.write(null_mut());
    801
}
unsafe extern "system" fn module(output: *mut *mut c_void, _: *const c_void) -> i32 {
    hit(0);
    clear_status(output)
}
unsafe extern "system" fn context(output: *mut *mut c_void, _: i32) -> i32 {
    hit(1);
    clear_status(output)
}
unsafe extern "system" fn primary(_: i32, _: u32) -> i32 {
    hit(2);
    801
}
unsafe extern "system" fn ext1(
    output: *mut *mut c_void,
    _: *const c_void,
    _: *mut c_void,
    _: *mut c_void,
    _: u32,
) -> i32 {
    hit(3);
    clear_status(output)
}
unsafe extern "system" fn opaque_void(_: usize) {
    hit(4);
}
unsafe extern "system" fn ext2(
    _: *const c_void,
    output: *mut *mut c_void,
    _: *mut c_void,
    _: *mut c_void,
    _: u32,
) -> i32 {
    hit(5);
    clear_status(output)
}
unsafe extern "system" fn compiler() -> i32 {
    hit(6);
    801
}
unsafe fn clear_hook(output: *mut *mut c_void, count: *mut usize) {
    if !output.is_null() {
        output.write(null_mut());
    }
    if !count.is_null() {
        count.write(0);
    }
}
unsafe extern "system" fn first(output: *mut *mut c_void, count: *mut usize) {
    hit(7);
    clear_hook(output, count);
}
unsafe extern "system" fn second(output: *mut *mut c_void, count: *mut usize) {
    hit(8);
    clear_hook(output, count);
}

pub static CUDART: CudartTable = CudartTable {
    byte_size: 104,
    module,
    context,
    hole3: 0,
    primary,
    hole5: 0,
    module_ext1: ext1,
    opaque_void,
    module_ext2: ext2,
    hole9: 0,
    hole10: 0,
    hole11: 0,
    compiler,
};
pub static HOOKS: HooksTable = HooksTable {
    byte_size: 56,
    hole1: 0,
    first,
    hole3: 0,
    hole4: 0,
    hole5: 0,
    second,
};

// Valid output storage or null is required; these are fixture-only exports.
#[no_mangle]
pub unsafe extern "system" fn ctTableGet(kind: u32, output: *mut *const c_void) -> i32 {
    if output.is_null() {
        return 1;
    }
    output.write(null());
    let value = match kind {
        0 => (&CUDART as *const CudartTable).cast(),
        1 => (&HOOKS as *const HooksTable).cast(),
        _ => return 1,
    };
    output.write(value);
    0
}

#[no_mangle]
pub unsafe extern "system" fn ctTableState(output: *mut TableState) -> i32 {
    if output.is_null() {
        return 1;
    }
    let mask = HITS.load(Ordering::SeqCst);
    output.write(TableState {
        mask,
        stopped: u32::from(mask != 0),
        reserved: 0,
    });
    0
}

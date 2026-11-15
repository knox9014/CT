// TEST ONLY: all CUDA entry points and private context use one linked Runtime.
extern crate ct_cuda;
#[path = "bootstrap_tables.rs"]
mod tables;
use std::ffi::c_void;
use std::sync::atomic::{AtomicI32, AtomicU32, AtomicU64, Ordering};

static CALLS: AtomicU64 = AtomicU64::new(0);
static RESULT: AtomicI32 = AtomicI32::new(0);
static NONNULL: AtomicU32 = AtomicU32::new(0);

#[repr(C)]
pub struct PrimaryState {
    calls: u64,
    result: i32,
    nonnull: u32,
}
const _: [(); 16] = [(); std::mem::size_of::<PrimaryState>()];

unsafe extern "system" fn context(output: *mut *mut c_void, device: i32) -> i32 {
    if !output.is_null() {
        output.write(std::ptr::null_mut());
    }
    let mut deny = tables::TableState {
        mask: 0,
        stopped: 0,
        reserved: 0,
    };
    tables::ctTableState(&mut deny);
    let previous = CALLS.fetch_add(1, Ordering::SeqCst);
    let result = if previous != 0 || deny.mask != 0 {
        801
    } else {
        ct_cuda::cudart_primary_context(output, device)
    };
    RESULT.store(result, Ordering::SeqCst);
    NONNULL.store(
        u32::from(!output.is_null() && !output.read().is_null()),
        Ordering::SeqCst,
    );
    result
}

static NATIVE_CUDART: tables::CudartTable = tables::CudartTable {
    byte_size: 104,
    module: tables::CUDART.module,
    context,
    hole3: 0,
    primary: tables::CUDART.primary,
    hole5: 0,
    module_ext1: tables::CUDART.module_ext1,
    opaque_void: tables::CUDART.opaque_void,
    module_ext2: tables::CUDART.module_ext2,
    hole9: 0,
    hole10: 0,
    hole11: 0,
    compiler: tables::CUDART.compiler,
};

#[no_mangle]
pub unsafe extern "system" fn ctPrimaryTableGet(output: *mut *const c_void) -> i32 {
    if output.is_null() {
        return 1;
    }
    output.write((&NATIVE_CUDART as *const tables::CudartTable).cast());
    0
}

#[no_mangle]
pub unsafe extern "system" fn ctPrimaryState(output: *mut PrimaryState) -> i32 {
    if output.is_null() {
        return 1;
    }
    output.write(PrimaryState {
        calls: CALLS.load(Ordering::SeqCst),
        result: RESULT.load(Ordering::SeqCst),
        nonnull: NONNULL.load(Ordering::SeqCst),
    });
    0
}

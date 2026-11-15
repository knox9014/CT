#[path = "bootstrap_tables.rs"]
mod fixture;
use fixture::*;
use std::ffi::c_void;
use std::mem::{align_of, offset_of, size_of};
use std::ptr::{null, null_mut};

#[test]
fn exact_layout_and_stable_owned_tables() {
    assert_eq!(
        (size_of::<CudartTable>(), align_of::<CudartTable>()),
        (104, 8)
    );
    assert_eq!((size_of::<HooksTable>(), align_of::<HooksTable>()), (56, 8));
    assert_eq!(size_of::<TableState>(), 16);
    assert_eq!(
        [
            offset_of!(CudartTable, module),
            offset_of!(CudartTable, context),
            offset_of!(CudartTable, primary),
            offset_of!(CudartTable, module_ext1),
            offset_of!(CudartTable, opaque_void),
            offset_of!(CudartTable, module_ext2),
            offset_of!(CudartTable, compiler)
        ],
        [8, 16, 32, 48, 56, 64, 96]
    );
    assert_eq!(
        [
            offset_of!(HooksTable, first),
            offset_of!(HooksTable, second)
        ],
        [16, 48]
    );
    assert_eq!((CUDART.byte_size, HOOKS.byte_size), (104, 56));
    assert_eq!(
        [
            CUDART.hole3,
            CUDART.hole5,
            CUDART.hole9,
            CUDART.hole10,
            CUDART.hole11
        ],
        [0; 5]
    );
    assert_eq!([HOOKS.hole1, HOOKS.hole3, HOOKS.hole4, HOOKS.hole5], [0; 4]);
    unsafe {
        let mut first = null();
        let mut again = null();
        assert_eq!(ctTableGet(0, &mut first), 0);
        assert_eq!(ctTableGet(0, &mut again), 0);
        assert_eq!(first, again);
        assert_eq!(first, (&CUDART as *const CudartTable).cast());
        assert_eq!(ctTableGet(1, &mut first), 0);
        assert_eq!(first, (&HOOKS as *const HooksTable).cast());
        assert_eq!(ctTableGet(2, &mut first), 1);
        assert!(first.is_null());
        assert_eq!(ctTableGet(0, null_mut()), 1);
        assert_eq!(ctTableState(null_mut()), 1);
    }
}

#[test]
fn every_typed_deny_clears_outputs_and_latches() {
    unsafe {
        let bad = 0xBAD0usize as *const c_void;
        let mut output = 0xDEADusize as *mut c_void;
        assert_eq!((CUDART.module)(&mut output, bad), 801);
        assert!(output.is_null());
        assert_eq!((CUDART.module)(null_mut(), bad), 1);
        output = 0xDEADusize as *mut c_void;
        assert_eq!((CUDART.context)(&mut output, -1), 801);
        assert!(output.is_null());
        assert_eq!((CUDART.context)(null_mut(), 0), 1);
        assert_eq!((CUDART.primary)(-1, u32::MAX), 801);
        output = 0xDEADusize as *mut c_void;
        assert_eq!(
            (CUDART.module_ext1)(&mut output, bad, bad.cast_mut(), bad.cast_mut(), u32::MAX),
            801
        );
        assert!(output.is_null());
        assert_eq!(
            (CUDART.module_ext1)(null_mut(), bad, null_mut(), null_mut(), 0),
            1
        );
        (CUDART.opaque_void)(usize::MAX);
        output = 0xDEADusize as *mut c_void;
        assert_eq!(
            (CUDART.module_ext2)(bad, &mut output, bad.cast_mut(), bad.cast_mut(), u32::MAX),
            801
        );
        assert!(output.is_null());
        assert_eq!(
            (CUDART.module_ext2)(bad, null_mut(), null_mut(), null_mut(), 0),
            1
        );
        assert_eq!((CUDART.compiler)(), 801);
        for callback in [HOOKS.first, HOOKS.second] {
            output = 0xDEADusize as *mut c_void;
            let mut count = usize::MAX;
            callback(&mut output, &mut count);
            assert!(output.is_null());
            assert_eq!(count, 0);
            count = usize::MAX;
            callback(null_mut(), &mut count);
            assert_eq!(count, 0);
            output = 0xDEADusize as *mut c_void;
            callback(&mut output, null_mut());
            assert!(output.is_null());
            callback(null_mut(), null_mut());
        }
        let mut state = TableState {
            mask: 0,
            stopped: 0,
            reserved: 99,
        };
        assert_eq!(ctTableState(&mut state), 0);
        assert_eq!((state.mask, state.stopped, state.reserved), (511, 1, 0));
    }
}

#[test]
fn concurrent_denials_never_clear_latch_or_move_storage() {
    std::thread::scope(|scope| {
        for _ in 0..8 {
            scope.spawn(|| {
                for _ in 0..64 {
                    unsafe {
                        (CUDART.opaque_void)(0);
                        let mut output = 0xDEADusize as *mut c_void;
                        let mut count = usize::MAX;
                        (HOOKS.first)(&mut output, &mut count);
                        assert!(output.is_null());
                        assert_eq!(count, 0);
                        output = 0xDEADusize as *mut c_void;
                        assert_eq!((CUDART.context)(&mut output, 0), 801);
                        assert!(output.is_null());
                    }
                }
            });
        }
    });
    unsafe {
        let mut state = TableState {
            mask: 0,
            stopped: 0,
            reserved: 0,
        };
        assert_eq!(ctTableState(&mut state), 0);
        assert_ne!(state.mask & 16, 0);
        assert_eq!(state.stopped, 1);
    }
}

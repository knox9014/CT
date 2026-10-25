#![cfg(all(windows, target_pointer_width = "64"))]
use ct_cuda::cuModuleGetGlobal_v2;
use std::ptr::{null, null_mut};
#[test]
fn global_query_resets_outputs_before_uninitialized_error() {
    let mut address = u64::MAX;
    let mut size = usize::MAX;
    unsafe {
        assert_eq!(
            cuModuleGetGlobal_v2(&mut address, &mut size, null_mut(), null()),
            3
        );
        assert_eq!((address, size), (0, 0));
        assert_eq!(
            cuModuleGetGlobal_v2(null_mut(), null_mut(), null_mut(), null()),
            3
        );
    }
}

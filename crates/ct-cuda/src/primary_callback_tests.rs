use super::*;

type Callback = unsafe extern "system" fn(*mut *mut c_void, i32) -> i32;

#[test]
fn typed_primary_callback_rejects_null_without_initialization() {
    let callback: Callback = cudart_primary_context;
    assert_eq!(unsafe { callback(std::ptr::null_mut(), 0) }, 1);
}

#[test]
#[ignore = "requires Intel GPU and exact fresh-process execution"]
fn native_global_primary_callback_matches_public_lifecycle() {
    let callback: Callback = cudart_primary_context;
    unsafe {
        let mut handle = std::ptr::dangling_mut();
        assert_eq!(callback(&mut handle, 0), 3);
        assert!(handle.is_null());
        assert_eq!(callback(std::ptr::null_mut(), 0), 1);
        assert_eq!(cuInit(0), 0);
        let mut name = [0i8; 256];
        assert_eq!(cuDeviceGetName(name.as_mut_ptr(), name.len() as i32, 0), 0);
        let name = std::ffi::CStr::from_ptr(name.as_ptr())
            .to_str()
            .unwrap()
            .to_owned();
        assert!(name.contains("Intel"));
        let mut current_handle = std::ptr::null_mut();
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert!(current_handle.is_null());
        let mut flags = u32::MAX;
        let mut active = -1;
        assert_eq!(cuDevicePrimaryCtxGetState(0, &mut flags, &mut active), 0);
        assert_eq!((flags, active), (0, 0));
        assert_eq!(callback(&mut handle, -1), 101);
        assert!(handle.is_null());
        assert_eq!(callback(&mut handle, 0), 0);
        let first = handle;
        assert!(!first.is_null());
        assert_eq!(cuDevicePrimaryCtxGetState(0, &mut flags, &mut active), 0);
        assert_eq!((flags, active), (0, 0));
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert!(current_handle.is_null());
        let mut ordinary = std::ptr::null_mut();
        assert_eq!(cuCtxCreate_v2(&mut ordinary, 0, 0), 0);
        assert_eq!(callback(&mut handle, 0), 0);
        assert_eq!(handle, first);
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert_eq!(current_handle, ordinary);
        assert_eq!(cuDevicePrimaryCtxRelease_v2(0), 201);
        assert_eq!(cuDevicePrimaryCtxRetain(&mut handle, 0), 0);
        assert_eq!(handle, first);
        assert_eq!(cuDevicePrimaryCtxGetState(0, &mut flags, &mut active), 0);
        assert_eq!((flags, active), (0, 1));
        assert_eq!(callback(&mut handle, 0), 0);
        assert_eq!(handle, first);
        assert_eq!(cuDevicePrimaryCtxRelease_v2(0), 0);
        assert_eq!(cuDevicePrimaryCtxGetState(0, &mut flags, &mut active), 0);
        assert_eq!((flags, active), (0, 0));
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert_eq!(current_handle, ordinary);
        assert_eq!(callback(&mut handle, 0), 0);
        assert_ne!(handle, first);
        assert_eq!(cuDevicePrimaryCtxReset_v2(0), 0);
        assert_eq!(cuDevicePrimaryCtxRetain(&mut handle, 0), 0);
        assert_eq!(cuDevicePrimaryCtxReset_v2(0), 0);
        assert_eq!(callback(&mut handle, 0), 801);
        assert!(handle.is_null());
        assert_eq!(cuDevicePrimaryCtxRelease_v2(0), 0);
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert_eq!(current_handle, ordinary);
        assert_eq!(cuCtxDestroy_v2(ordinary), 0);
        assert_eq!(cuCtxGetCurrent(&mut current_handle), 0);
        assert!(current_handle.is_null());
        assert_eq!(
            invoke(|r| {
                assert!(r.contexts.is_empty() && r.retired.is_empty());
                assert!(!r.primary.active(0));
                Ok(())
            }),
            0
        );
        println!("global primary callback passed: device={name}; TLS empty; owned/quarantined contexts=0");
    }
}

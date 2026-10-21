#![cfg(all(windows, target_pointer_width = "64"))]
use ct_cuda::{cuGetProcAddress, cuGetProcAddress_v2};
use std::ffi::{c_char, c_void, CString};
use std::ptr::{dangling_mut, null, null_mut};

unsafe fn query(name: &str, version: i32, flags: u64) -> (i32, *mut c_void, i32) {
    let name = CString::new(name).unwrap();
    let mut pointer = dangling_mut();
    let mut status = -1;
    let code = cuGetProcAddress_v2(name.as_ptr(), &mut pointer, version, flags, &mut status);
    (code, pointer, status)
}

#[test]
fn canonical_entries_obey_verified_abi_boundaries() {
    let entries = [
        ("cuInit", 2000),
        ("cuDriverGetVersion", 2020),
        ("cuDeviceGetCount", 2000),
        ("cuDeviceGet", 2000),
        ("cuDeviceGetName", 2000),
        ("cuDeviceGetAttribute", 2000),
        ("cuDevicePrimaryCtxRetain", 7000),
        ("cuDevicePrimaryCtxGetState", 7000),
        ("cuDevicePrimaryCtxRelease", 11000),
        ("cuDevicePrimaryCtxReset", 11000),
        ("cuDevicePrimaryCtxSetFlags", 11000),
        ("cuCtxGetFlags", 7000),
        ("cuCtxCreate", 3020),
        ("cuCtxDestroy", 4000),
        ("cuCtxGetCurrent", 4000),
        ("cuCtxSetCurrent", 4000),
        ("cuCtxPushCurrent", 4000),
        ("cuCtxPopCurrent", 4000),
        ("cuCtxGetDevice", 2000),
        ("cuCtxSynchronize", 2000),
        ("cuMemAlloc", 3020),
        ("cuMemFree", 3020),
        ("cuMemGetAddressRange", 3020),
        ("cuPointerGetAttribute", 4000),
        ("cuMemcpyHtoD", 3020),
        ("cuMemcpyDtoH", 3020),
        ("cuMemcpyDtoD", 3020),
        ("cuMemsetD8", 3020),
        ("cuMemsetD16", 3020),
        ("cuMemsetD32", 3020),
        ("cuGetErrorName", 6000),
        ("cuGetErrorString", 6000),
        ("cuModuleLoadData", 2000),
        ("cuModuleGetFunction", 2000),
        ("cuModuleUnload", 2000),
        ("cuLaunchKernel", 4000),
        ("cuGetProcAddress", 11030),
    ];
    unsafe {
        for (name, minimum) in entries {
            let (code, pointer, status) = query(name, minimum - 1, 0);
            assert_eq!((code, pointer, status), (0, null_mut(), 2), "{name}");
            for flags in [0, 1] {
                let (code, pointer, status) = query(name, minimum, flags);
                assert_eq!((code, status), (0, 0), "{name}");
                assert!(!pointer.is_null(), "{name}");
            }
        }
        assert!(!query("cuCtxCreate", 11039, 0).1.is_null());
        assert_eq!(query("cuCtxCreate", 11040, 0), (0, null_mut(), 2));
        assert_eq!(query("cuCtxCreate", 12000, 0), (0, null_mut(), 2));
    }
}

#[test]
fn rejection_initializes_outputs_and_preserves_distinct_resolver_contracts() {
    unsafe {
        for name in [
            "missing",
            "cuDevicePrimaryCtxRelease_v2",
            "cuDevicePrimaryCtxReset_v2",
            "cuDevicePrimaryCtxSetFlags_v2",
            "cuMemAlloc_v2",
            "cuMemGetAddressRange_v2",
            "cuPointerGetAttributes",
            "cuMemcpyDtoD_v2",
            "cuMemsetD8_v2",
            "cuMemsetD16_v2",
            "cuMemsetD32_v2",
            "cuCtxCreate_v3",
            "cuGetProcAddress_v2",
            "",
        ] {
            assert_eq!(query(name, 12000, 0), (0, null_mut(), 1));
            let name = CString::new(name).unwrap();
            let mut p = dangling_mut();
            assert_eq!(cuGetProcAddress(name.as_ptr(), &mut p, 12000, 0), 500);
            assert!(p.is_null());
        }
        for (version, flags, expected) in [
            (0, 0, 1),
            (-1, 0, 1),
            (12001, 0, 801),
            (2000, 2, 801),
            (2000, 3, 1),
            (2000, 4, 1),
        ] {
            let (code, p, status) = query("cuInit", version, flags);
            assert_eq!((code, p, status), (expected, null_mut(), 1));
        }
        let mut p = dangling_mut();
        let mut status = -1;
        assert_eq!(cuGetProcAddress_v2(null(), &mut p, 2000, 0, &mut status), 1);
        assert_eq!((p, status), (null_mut(), 1));
        assert_eq!(
            cuGetProcAddress_v2(c"cuInit".as_ptr(), null_mut(), 2000, 0, &mut status),
            1
        );
        assert_eq!(
            cuGetProcAddress_v2(c"cuInit".as_ptr(), &mut p, 2000, 0, null_mut()),
            0
        );
        let f: unsafe extern "system" fn(u32) -> i32 = std::mem::transmute(p);
        assert_eq!(f(1), 1); // Calls the actual implementation, not a fabricated success stub.
    }
}

#[test]
fn resolver_self_selection_uses_distinct_function_signatures() {
    unsafe {
        let old = query("cuGetProcAddress", 11999, 0).1;
        let new = query("cuGetProcAddress", 12000, 0).1;
        assert_ne!(old, new);
        let old: unsafe extern "system" fn(*const c_char, *mut *mut c_void, i32, u64) -> i32 =
            std::mem::transmute(old);
        let new: unsafe extern "system" fn(
            *const c_char,
            *mut *mut c_void,
            i32,
            u64,
            *mut i32,
        ) -> i32 = std::mem::transmute(new);
        let mut p = null_mut();
        let mut status = -1;
        assert_eq!(old(c"cuInit".as_ptr(), &mut p, 2000, 0), 0);
        let first = p;
        assert_eq!(new(c"cuInit".as_ptr(), &mut p, 2000, 0, &mut status), 0);
        assert_eq!((p, status), (first, 0));
    }
    let threads: Vec<_> = (0..4)
        .map(|_| {
            std::thread::spawn(|| {
                for _ in 0..100 {
                    unsafe {
                        assert_eq!(query("cuLaunchKernel", 4000, 0).2, 0);
                    }
                }
            })
        })
        .collect();
    for thread in threads {
        thread.join().unwrap();
    }
}

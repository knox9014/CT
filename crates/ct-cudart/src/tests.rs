use crate::errors::*;

#[test]
fn bootstrap_checks_identity_and_pins_before_publish() {
    use crate::platform::*;
    use std::cell::RefCell;
    struct Fake {
        wrong: bool,
        missing: bool,
        pin_error: bool,
        trace: RefCell<Vec<&'static str>>,
    }
    impl Platform for Fake {
        type Owned = ();
        fn load_owned(&self) -> Result<(), i32> {
            self.trace.borrow_mut().push("load");
            Ok(())
        }
        fn check_identity(&self, _: &()) -> Result<(), i32> {
            self.trace.borrow_mut().push("identity");
            if self.wrong {
                Err(35)
            } else {
                Ok(())
            }
        }
        fn resolve(&self, _: &(), _: &[u8]) -> Result<usize, i32> {
            self.trace.borrow_mut().push("resolve");
            if self.missing {
                Err(35)
            } else {
                Ok(1)
            }
        }
        fn pin(&self, _: &()) -> Result<(), i32> {
            self.trace.borrow_mut().push("pin");
            if self.pin_error {
                Err(35)
            } else {
                Ok(())
            }
        }
    }
    let good = Fake {
        wrong: false,
        missing: false,
        pin_error: false,
        trace: RefCell::new(vec![]),
    };
    let (_, table) = bootstrap(&good).unwrap();
    assert_eq!(table, [1; 15]);
    let trace = good.trace.borrow();
    assert_eq!(&trace[..2], &["load", "identity"]);
    assert_eq!(trace.len(), 18);
    assert_eq!(trace[17], "pin");
    for (wrong, missing, pin_error, want) in [
        (true, false, false, 2),
        (false, true, false, 3),
        (false, false, true, 18),
    ] {
        let bad = Fake {
            wrong,
            missing,
            pin_error,
            trace: RefCell::new(vec![]),
        };
        let cache = std::sync::OnceLock::new();
        assert_eq!(*cache.get_or_init(|| bootstrap(&bad)), Err(35));
        assert_eq!(*cache.get_or_init(|| bootstrap(&bad)), Err(35));
        assert_eq!(bad.trace.borrow().len(), want);
    }
}

#[test]
fn export_signatures_and_pure_error_paths() {
    use crate::*;
    let _: unsafe extern "system" fn(*mut i32) -> i32 = cudaGetDeviceCount;
    let _: unsafe extern "system" fn(*mut i32) -> i32 = cudaGetDevice;
    let _: extern "system" fn(i32) -> i32 = cudaSetDevice;
    let _: extern "system" fn() -> i32 = cudaDeviceSynchronize;
    let _: unsafe extern "system" fn(*mut *mut c_void, usize) -> i32 = cudaMalloc;
    let _: extern "system" fn(*mut c_void) -> i32 = cudaFree;
    let _: unsafe extern "system" fn(*mut c_void, *const c_void, usize, i32) -> i32 = cudaMemcpy;
    let _: extern "system" fn(*mut c_void, i32, usize) -> i32 = cudaMemset;
    let _: extern "system" fn() -> i32 = cudaGetLastError;
    let _: extern "system" fn() -> i32 = cudaPeekAtLastError;
    let _: extern "system" fn(i32) -> *const c_char = cudaGetErrorName;
    let _: extern "system" fn(i32) -> *const c_char = cudaGetErrorString;
    let _: unsafe extern "system" fn(*mut i32) -> i32 = cudaDriverGetVersion;
    let _: unsafe extern "system" fn(*mut i32) -> i32 = cudaRuntimeGetVersion;
    unsafe {
        let mut version = -1;
        assert_eq!(cudaRuntimeGetVersion(&mut version), 801);
        assert_eq!(version, 0);
        assert_eq!(cudaDriverGetVersion(std::ptr::null_mut()), 1);
        assert_eq!(cudaPeekAtLastError(), 1);
        assert_eq!(
            std::ffi::CStr::from_ptr(cudaGetErrorName(49)).to_bytes(),
            b"cudaErrorIncompatibleDriverContext"
        );
        assert_eq!(
            std::ffi::CStr::from_ptr(cudaGetErrorString(-123)).to_bytes(),
            b"unrecognized error code"
        );
        assert_eq!(cudaGetLastError(), 1);
        assert_eq!(cudaGetLastError(), 0);
    }
}

#[test]
fn runtime_error_mapping_is_explicit() {
    for (driver, runtime) in [
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 3),
        (100, 100),
        (101, 101),
        (201, 49),
        (709, 709),
        (801, 801),
        (999, 999),
        (218, 999),
        (400, 999),
        (500, 999),
        (-1, 999),
    ] {
        assert_eq!(from_driver(driver), runtime, "driver {driver}");
    }
}

#[test]
fn last_error_is_thread_local_and_success_does_not_clear() {
    take();
    assert_eq!(record(21), 21);
    assert_eq!(record(0), 0);
    std::thread::spawn(|| {
        assert_eq!(peek(), 0);
        record(801);
        assert_eq!(take(), 801);
        assert_eq!(take(), 0);
    })
    .join()
    .unwrap();
    assert_eq!(peek(), 21);
    assert_eq!(take(), 21);
    assert_eq!(take(), 0);
}

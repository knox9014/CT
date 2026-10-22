use crate::{driver::*, memory::*, state::Runtime};
use std::ffi::c_void;
use std::ptr::{null, null_mut};
use std::sync::Mutex;
#[derive(Default)]
struct Spy {
    calls: Mutex<Vec<(u8, u64, u64, usize)>>,
    error: i32,
}
impl Spy {
    fn push(&self, kind: u8, d: u64, s: u64, n: usize) -> i32 {
        self.calls.lock().unwrap().push((kind, d, s, n));
        self.error
    }
}
impl DriverCalls for Spy {
    fn init(&self) -> i32 {
        self.calls.lock().unwrap().push((10, 0, 0, 0));
        0
    }
    fn count(&self) -> DriverResult<i32> {
        Ok(1)
    }
    fn device(&self, d: i32) -> DriverResult<i32> {
        Ok(d)
    }
    fn current(&self) -> DriverResult<Option<usize>> {
        Ok(Some(77))
    }
    fn context_device(&self) -> DriverResult<i32> {
        Ok(0)
    }
    fn retain(&self, _: i32) -> DriverResult<usize> {
        panic!("ordinary context must survive")
    }
    fn release(&self, _: i32) -> i32 {
        panic!("must not release")
    }
    fn set_current(&self, _: usize) -> i32 {
        panic!("must not select")
    }
    fn synchronize(&self) -> i32 {
        self.push(11, 0, 0, 0)
    }
    fn allocate(&self, n: usize) -> DriverResult<u64> {
        let e = self.push(12, 0, 0, n);
        if e == 0 {
            Ok(4096)
        } else {
            Err(e)
        }
    }
    fn free(&self, p: u64) -> i32 {
        self.push(13, p, 0, 0)
    }
    unsafe fn copy_htod(&self, d: u64, s: *const u8, n: usize) -> i32 {
        self.push(1, d, s as u64, n)
    }
    unsafe fn copy_dtoh(&self, d: *mut u8, s: u64, n: usize) -> i32 {
        self.push(2, d as u64, s, n)
    }
    fn copy_dtod(&self, d: u64, s: u64, n: usize) -> i32 {
        self.push(3, d, s, n)
    }
    fn fill8(&self, d: u64, v: u8, n: usize) -> i32 {
        self.push(4, d, v as u64, n)
    }
}
#[test]
fn unsupported_kind_is_not_hidden_by_zero_size() {
    let rt = Runtime::new(Spy::default());
    unsafe {
        for (kind, want) in [(-1, 21), (0, 0), (1, 0), (2, 0), (3, 0), (4, 801), (5, 21)] {
            assert_eq!(copy_device(&rt, null_mut(), null(), 0, kind), want);
        }
        let mut out = std::ptr::dangling_mut::<c_void>();
        assert_eq!(allocate(&rt, &mut out, 0), 801);
        assert!(out.is_null());
        assert_eq!(allocate(&rt, null_mut(), 8), 1);
    }
    assert_eq!(fill(&rt, null_mut(), 5, 0), 0);
    assert!(rt.driver.calls.lock().unwrap().is_empty());
}
#[test]
fn memory_dispatch_preserves_direction_and_byte_value() {
    let rt = Runtime::new(Spy::default());
    let d = 4096usize as *mut c_void;
    let s = 8192usize as *const c_void;
    unsafe {
        for kind in 1..=3 {
            assert_eq!(copy_device(&rt, d, s, 17, kind), 0);
        }
    }
    for v in [-1, 256, 0x1234] {
        assert_eq!(fill(&rt, d, v, 19), 0);
    }
    let calls = rt.driver.calls.lock().unwrap();
    assert_eq!(
        &*calls,
        &[
            (10, 0, 0, 0),
            (1, 4096, 8192, 17),
            (2, 4096, 8192, 17),
            (3, 4096, 8192, 17),
            (4, 4096, 255, 19),
            (4, 4096, 0, 19),
            (4, 4096, 52, 19)
        ]
    );
}
#[test]
fn host_copy_checks_extents_overlap_and_guards() {
    let rt = Runtime::new(Spy::default());
    let src = [3u8, 9, 17, 42, 51];
    let mut dst = [0xcdu8; 9];
    unsafe {
        assert_eq!(
            copy_device(
                &rt,
                dst.as_mut_ptr().add(2).cast(),
                src.as_ptr().cast(),
                5,
                0
            ),
            0
        );
        assert_eq!(dst, [205, 205, 3, 9, 17, 42, 51, 205, 205]);
        assert_eq!(copy_host(dst.as_mut_ptr().add(1), dst.as_ptr(), 5), 1);
        assert_eq!(copy_host(null_mut(), src.as_ptr(), 1), 1);
        assert_eq!(copy_host(usize::MAX as *mut u8, src.as_ptr(), 2), 1);
        assert_eq!(copy_host(dst.as_mut_ptr(), usize::MAX as *const u8, 2), 1);
    }
    assert!(rt.driver.calls.lock().unwrap().is_empty());
}
#[test]
fn null_device_arguments_are_rejected_before_init_and_free_null_prepares() {
    let rt = Runtime::new(Spy::default());
    unsafe {
        for kind in 1..=3 {
            assert_eq!(copy_device(&rt, null_mut(), null(), 5, kind), 1);
        }
    }
    assert_eq!(fill(&rt, null_mut(), 0, 1), 1);
    assert!(rt.driver.calls.lock().unwrap().is_empty());
    assert_eq!(free(&rt, null_mut()), 0);
    assert_eq!(&*rt.driver.calls.lock().unwrap(), &[(10, 0, 0, 0)]);
}
#[test]
fn memory_driver_errors_translate_once_and_preserve_null_output() {
    for (code, want) in [
        (1, 1),
        (2, 2),
        (201, 49),
        (709, 709),
        (801, 801),
        (999, 999),
    ] {
        let rt = Runtime::new(Spy {
            error: code,
            ..Spy::default()
        });
        let mut out = std::ptr::dangling_mut::<c_void>();
        unsafe {
            assert_eq!(allocate(&rt, &mut out, 8), want);
        }
        assert!(out.is_null());
        assert_eq!(fill(&rt, 4096usize as *mut c_void, 1, 8), want);
        assert_eq!(
            &*rt.driver.calls.lock().unwrap(),
            &[(10, 0, 0, 0), (12, 0, 0, 8), (4, 4096, 1, 8)]
        );
    }
}

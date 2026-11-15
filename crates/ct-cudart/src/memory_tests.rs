use crate::{driver::*, memory::*, state::Runtime};
use std::ffi::c_void;
use std::ptr::{null, null_mut};
use std::sync::Mutex;
#[derive(Default)]
struct Spy {
    calls: Mutex<Vec<(u8, u64, u64, usize)>>,
    error: i32,
    host_prepare_error: i32,
    worker: bool,
    context: usize,
    host_pointer: usize,
    select_error: i32,
    entered: Option<std::sync::Arc<std::sync::Barrier>>,
    release: Option<std::sync::Arc<std::sync::Barrier>>,
}
impl Spy {
    fn push(&self, kind: u8, d: u64, s: u64, n: usize) -> i32 {
        self.calls.lock().unwrap().push((kind, d, s, n));
        self.error
    }
}
impl DriverCalls for Spy {
    fn prepare_host(&self) -> Result<(), i32> {
        self.push(15, 0, 0, 0);
        if self.host_prepare_error == 0 {
            Ok(())
        } else {
            Err(self.host_prepare_error)
        }
    }
    fn allocate_host(&self, size: usize) -> DriverResult<usize> {
        let code = self.push(14, 0, 0, size);
        if code == 0 {
            Ok(if self.host_pointer == 0 {
                0x4000
            } else {
                self.host_pointer
            })
        } else {
            Err(code)
        }
    }
    fn free_host(&self, pointer: usize) -> i32 {
        self.push(16, pointer as u64, 0, 0)
    }

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
        Ok(Some(if self.context == 0 { 77 } else { self.context }))
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
    fn set_current(&self, context: usize) -> i32 {
        assert!(self.worker, "must not select");
        self.calls.lock().unwrap().push((17, context as u64, 0, 0));
        self.select_error
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
        if let Some(entered) = &self.entered {
            entered.wait();
        }
        if let Some(release) = &self.release {
            release.wait();
        }
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

#[test]
fn host_allocation_preflight_is_gpu_free_and_preserves_output() {
    let rt = Runtime::new(Spy::default());
    let mut output = 123usize;
    for (size, flags, want) in [
        (0, 0, 1),
        (4, 1, 801),
        (4, 7, 801),
        (4, 8, 1),
        (4, u32::MAX, 1),
    ] {
        assert_eq!(
            unsafe { crate::host::allocate(&rt, &mut output, size, flags) },
            want
        );
        assert_eq!(output, 123);
    }
    assert_eq!(
        unsafe { crate::host::allocate(&rt, std::ptr::null_mut(), 4, 0) },
        1
    );
    assert_eq!(crate::host::free(&rt, 0), 1);
    assert!(rt.driver.calls.lock().unwrap().is_empty());
    let mut pointer = 123usize as *mut c_void;
    assert_eq!(unsafe { crate::cudaHostAlloc(&mut pointer, 4, 1) }, 801);
    assert_eq!(crate::cudaGetLastError(), 801);
    assert_eq!(pointer as usize, 123);
    assert_eq!(crate::cudaFreeHost(std::ptr::null_mut()), 1);
    assert_eq!(crate::cudaGetLastError(), 1);
}
#[test]
fn host_allocation_and_free_preserve_error_domains() {
    for (prepare, driver, want) in [(35, 0, 35), (0, 201, 49), (0, 709, 709), (0, 777, 999)] {
        let rt = Runtime::new(Spy {
            host_prepare_error: prepare,
            error: driver,
            ..Spy::default()
        });
        let mut output = 123;
        assert_eq!(
            unsafe { crate::host::allocate(&rt, &mut output, 4, 0) },
            want
        );
        assert_eq!(output, 123);
        if prepare != 0 {
            assert!(!rt.driver.calls.lock().unwrap().iter().any(|c| c.0 == 14));
        }
        assert_eq!(crate::host::free(&rt, 0x4000), want);
    }
    let rt = Runtime::new(Spy::default());
    let mut output = 0;
    assert_eq!(unsafe { crate::host::allocate(&rt, &mut output, 4, 0) }, 0);
    assert_eq!(output, 0x4000);
    assert_eq!(crate::host::free(&rt, output), 0);
    assert_eq!(
        rt.driver
            .calls
            .lock()
            .unwrap()
            .iter()
            .filter(|c| c.0 == 14 || c.0 == 16)
            .count(),
        2
    );
}

#[test]
fn async_copy_preflight_preserves_kind_stream_and_pointer_errors() {
    use crate::async_copy::{preflight, Copy};
    for (kind, stream, bytes, dst, src, want) in [
        (-1, 0, 0, 0, 0, Some(21)),
        (0, 0, 0, 0, 0, Some(801)),
        (4, 0, 0, 0, 0, Some(801)),
        (1, 1, 0, 0, 0, Some(801)),
        (1, 0, 0, 0, 0, Some(0)),
        (1, 0, 4, 0, 16, Some(1)),
        (3, 0, 4, 16, 16, Some(1)),
        (3, 0, 4, usize::MAX - 1, 16, Some(1)),
    ] {
        assert_eq!(
            preflight(
                crate::streams::registry(),
                Copy {
                    kind,
                    stream,
                    bytes,
                    dst,
                    src
                }
            ),
            want
        );
        assert_eq!(
            unsafe {
                crate::cudaMemcpyAsync(
                    dst as *mut c_void,
                    src as *const c_void,
                    bytes,
                    kind,
                    stream as *mut c_void,
                )
            },
            want.unwrap()
        );
    }
    crate::cudaGetLastError();
}
#[test]
fn async_copy_worker_selects_context_and_maps_driver_errors_once() {
    for (select, error, want) in [(201, 0, 49), (0, 201, 49), (0, 709, 709), (0, 777, 999)] {
        let rt = Box::leak(Box::new(Runtime::new(Spy {
            worker: true,
            context: 0xab123,
            select_error: select,
            error,
            ..Spy::default()
        })));
        let q = crate::submission::Scheduler::new();
        let hosts = crate::host_ownership::Registry::new();
        let streams = crate::streams::Registry::new();
        hosts.allocate(0xab123, 16, || Ok(0x4000)).unwrap();
        let copy = crate::async_copy::Copy {
            dst: 0x8000,
            src: 0x4000,
            bytes: 16,
            kind: 1,
            stream: 0,
        };
        assert_eq!(
            crate::async_copy::enqueue(rt, &q, &hosts, &streams, copy),
            0
        );
        assert_eq!(q.barrier(0xab123, false, || Ok(())), Err(want));
        if select != 0 {
            assert!(!rt.driver.calls.lock().unwrap().iter().any(|c| c.0 == 1));
        }
        assert_eq!(
            q.barrier(0xab123, true, || hosts.free(0xab123, 0x4000, || Ok(()))),
            Err(want)
        );
        assert_eq!(hosts.acquire(0xab123, 0x4000, 1).err(), Some(801));
    }
}
#[test]
fn async_host_free_waits_for_the_accepted_copy() {
    use std::sync::{mpsc, Arc, Barrier};
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let rt = Box::leak(Box::new(Runtime::new(Spy {
        worker: true,
        context: 0xab777,
        host_pointer: 0x7000,
        entered: Some(entered.clone()),
        release: Some(release.clone()),
        ..Spy::default()
    })));
    let mut pointer = 0;
    assert_eq!(unsafe { crate::host::allocate(rt, &mut pointer, 16, 0) }, 0);
    let copy = crate::async_copy::Copy {
        dst: 0x8000,
        src: pointer,
        bytes: 16,
        kind: 1,
        stream: 0,
    };
    assert_eq!(
        crate::async_copy::enqueue(
            rt,
            crate::submission::scheduler(),
            crate::host_ownership::registry(),
            crate::streams::registry(),
            copy
        ),
        0
    );
    entered.wait();
    let (started_tx, started_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    let shared: &'static Runtime<Spy> = rt;
    let free = std::thread::spawn(move || {
        started_tx.send(()).unwrap();
        let code = crate::host::free(shared, pointer);
        done_tx.send(code).unwrap();
    });
    started_rx.recv().unwrap();
    assert_eq!(
        done_rx.recv_timeout(std::time::Duration::from_millis(100)),
        Err(mpsc::RecvTimeoutError::Timeout)
    );
    assert!(!rt.driver.calls.lock().unwrap().iter().any(|c| c.0 == 16));
    release.wait();
    assert_eq!(done_rx.recv().unwrap(), 0);
    free.join().unwrap();
    assert!(rt.driver.calls.lock().unwrap().iter().any(|c| c.0 == 16));
}

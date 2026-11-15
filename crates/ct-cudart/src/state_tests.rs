use crate::driver::*;
use crate::state::Runtime;
use std::collections::HashMap;
use std::sync::atomic::{AtomicI32, AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct Inner {
    attribute_calls: Mutex<Vec<(i32, i32)>>,
    attribute_prepares: AtomicUsize,
    attribute_prepare_error: AtomicI32,
    attribute_error: AtomicI32,
    device_handle_offset: AtomicI32,
    current_calls: AtomicUsize,
    sync_calls: AtomicUsize,
    sync_error: AtomicI32,
    currents: Mutex<HashMap<std::thread::ThreadId, usize>>,
    retains: AtomicUsize,
    releases: AtomicUsize,
    sets: AtomicUsize,
    inits: AtomicUsize,
    init_error: AtomicI32,
    select_error: AtomicI32,
    release_error: AtomicI32,
    current_error: AtomicI32,
}
#[derive(Clone, Default)]
pub struct Fake(Arc<Inner>);
impl Fake {
    fn current_value(&self) -> usize {
        *self
            .0
            .currents
            .lock()
            .unwrap()
            .get(&std::thread::current().id())
            .unwrap_or(&0)
    }
    fn inject_current(&self, id: usize) {
        self.0
            .currents
            .lock()
            .unwrap()
            .insert(std::thread::current().id(), id);
    }
}
impl DriverCalls for Fake {
    fn prepare_device_attribute(&self) -> Result<(), i32> {
        self.0.attribute_prepares.fetch_add(1, SeqCst);
        match self.0.attribute_prepare_error.load(SeqCst) {
            0 => Ok(()),
            code => Err(code),
        }
    }
    fn device_attribute(&self, attribute: i32, device: i32) -> DriverResult<i32> {
        self.0
            .attribute_calls
            .lock()
            .unwrap()
            .push((attribute, device));
        match self.0.attribute_error.load(SeqCst) {
            0 => Ok(attribute * 100 + device),
            code => Err(code),
        }
    }

    fn init(&self) -> i32 {
        self.0.inits.fetch_add(1, SeqCst);
        self.0.init_error.load(SeqCst)
    }
    fn count(&self) -> DriverResult<i32> {
        Ok(2)
    }
    fn device(&self, d: i32) -> DriverResult<i32> {
        if (0..2).contains(&d) {
            Ok(d + self.0.device_handle_offset.load(SeqCst))
        } else {
            Err(101)
        }
    }
    fn current(&self) -> DriverResult<Option<usize>> {
        self.0.current_calls.fetch_add(1, SeqCst);
        let error = self.0.current_error.load(SeqCst);
        if error != 0 {
            Err(error)
        } else {
            Ok((self.current_value() != 0).then(|| self.current_value()))
        }
    }
    fn context_device(&self) -> DriverResult<i32> {
        Ok(if self.current_value() == 77 { 1 } else { 0 })
    }
    fn retain(&self, d: i32) -> DriverResult<usize> {
        self.0.retains.fetch_add(1, SeqCst);
        Ok(100 + d as usize)
    }
    fn release(&self, _: i32) -> i32 {
        self.0.releases.fetch_add(1, SeqCst);
        self.0.release_error.load(SeqCst)
    }
    fn set_current(&self, c: usize) -> i32 {
        self.0.sets.fetch_add(1, SeqCst);
        let error = self.0.select_error.load(SeqCst);
        if error == 0 {
            self.inject_current(c)
        }
        error
    }
    fn synchronize(&self) -> i32 {
        self.0.sync_calls.fetch_add(1, SeqCst);
        self.0.sync_error.load(SeqCst)
    }
    fn allocate(&self, _: usize) -> DriverResult<u64> {
        Ok(4096)
    }
    fn free(&self, _: u64) -> i32 {
        0
    }
    unsafe fn copy_htod(&self, _: u64, _: *const u8, _: usize) -> i32 {
        0
    }
    unsafe fn copy_dtoh(&self, _: *mut u8, _: u64, _: usize) -> i32 {
        0
    }
    fn copy_dtod(&self, _: u64, _: u64, _: usize) -> i32 {
        0
    }
    fn fill8(&self, _: u64, _: u8, _: usize) -> i32 {
        0
    }
}

#[test]
fn set_device_is_eager_and_retains_once() {
    let fake = Fake::default();
    let rt = Arc::new(Runtime::new(fake.clone()));
    assert_eq!(rt.get_count(), Ok(2));
    assert_eq!(rt.get_device(), Ok(0));
    assert_eq!(fake.0.retains.load(SeqCst), 0);
    let worker = rt.clone();
    let f = fake.clone();
    let thread = std::thread::spawn(move || {
        for _ in 0..100 {
            assert_eq!(worker.set_device(0), 0);
            assert_eq!(f.current_value(), 100);
        }
    });
    for _ in 0..100 {
        assert_eq!(rt.set_device(0), 0);
        assert_eq!(fake.current_value(), 100);
    }
    thread.join().unwrap();
    assert_eq!(fake.0.retains.load(SeqCst), 1);
    assert_eq!(fake.0.sets.load(SeqCst), 200);
    assert_eq!(fake.0.inits.load(SeqCst), 1);
    assert_eq!(rt.set_device(2), 101);
}

#[test]
fn ordinary_current_is_preserved() {
    let fake = Fake::default();
    fake.inject_current(77);
    let rt = Runtime::new(fake.clone());
    assert_eq!(rt.ensure_current(), Ok(77));
    assert_eq!(rt.get_device(), Ok(1));
    assert_eq!(fake.0.retains.load(SeqCst), 0);
    assert_eq!(fake.0.sets.load(SeqCst), 0);
    fake.0.current_error.store(709, SeqCst);
    assert_eq!(rt.ensure_current(), Err(709));
}

#[test]
fn failed_selection_rolls_back_or_faults_slot() {
    for release in [0, 999] {
        let fake = Fake::default();
        fake.inject_current(77);
        fake.0.select_error.store(201, SeqCst);
        fake.0.release_error.store(release, SeqCst);
        let rt = Runtime::new(fake.clone());
        assert_eq!(rt.set_device(0), if release == 0 { 201 } else { 999 });
        assert_eq!(fake.current_value(), 77);
        fake.0.select_error.store(0, SeqCst);
        fake.0.release_error.store(0, SeqCst);
        if release == 0 {
            assert_eq!(rt.set_device(0), 0);
            assert_eq!(fake.0.retains.load(SeqCst), 2);
        } else {
            for _ in 0..2 {
                assert_eq!(rt.set_device(0), 999);
            }
            assert_eq!(fake.0.retains.load(SeqCst), 1);
            assert_eq!(fake.0.releases.load(SeqCst), 1);
            assert_eq!(rt.ensure_current(), Ok(77));
        }
    }
}

#[test]
fn ready_failure_does_not_release_and_stale_is_sticky() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    assert_eq!(rt.set_device(0), 0);
    fake.0.select_error.store(201, SeqCst);
    assert_eq!(rt.set_device(0), 201);
    assert_eq!(fake.0.releases.load(SeqCst), 0);
    fake.0.select_error.store(709, SeqCst);
    assert_eq!(rt.set_device(0), 709);
    fake.0.select_error.store(0, SeqCst);
    assert_eq!(rt.set_device(0), 709);
    assert_eq!(fake.0.retains.load(SeqCst), 1);
}

#[test]
fn initialization_failure_is_sticky() {
    for error in [3, 100, 999] {
        let fake = Fake::default();
        fake.0.init_error.store(error, SeqCst);
        let rt = Runtime::new(fake.clone());
        assert_eq!(rt.initialize(), error);
        fake.0.init_error.store(0, SeqCst);
        assert_eq!(rt.get_count(), Err(error));
        assert_eq!(rt.get_device(), Err(error));
        assert_eq!(rt.set_device(0), error);
        assert_eq!(rt.ensure_current(), Err(error));
        assert_eq!(fake.0.inits.load(SeqCst), 1);
        assert_eq!(fake.0.retains.load(SeqCst), 0);
    }
}

#[test]
fn attribute_preflight_is_driver_free() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    let mut out = 123;
    for (pointer, attr, ordinal, expected) in [
        (std::ptr::null_mut(), 75, -1, 1),
        (&mut out, 75, -1, 101),
        (&mut out, 0, 0, 801),
        (&mut out, 9, 0, 801),
        (&mut out, 10, 0, 801),
        (&mut out, 11, 0, 801),
        (&mut out, 999, 999, 801),
    ] {
        assert_eq!(
            unsafe { crate::device::attribute_query(&rt, pointer, attr, ordinal) },
            expected
        );
        assert_eq!(out, 123);
    }
    assert_eq!(fake.0.inits.load(SeqCst), 0);
    assert_eq!(fake.0.attribute_prepares.load(SeqCst), 0);
    assert!(fake.0.attribute_calls.lock().unwrap().is_empty());
}

#[test]
fn attribute_uses_device_handle_without_context() {
    let fake = Fake::default();
    fake.inject_current(77);
    fake.0.device_handle_offset.store(40, SeqCst);
    let rt = Runtime::new(fake.clone());
    for attr in [1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 20, 40, 75, 76] {
        let mut out = -1;
        assert_eq!(
            unsafe { crate::device::attribute_query(&rt, &mut out, attr, 1) },
            0
        );
        assert_eq!(out, attr * 100 + 41);
    }
    assert_eq!(fake.0.inits.load(SeqCst), 1);
    assert_eq!(fake.0.attribute_prepares.load(SeqCst), 14);
    assert_eq!(
        *fake.0.attribute_calls.lock().unwrap(),
        [1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 20, 40, 75, 76].map(|a| (a, 41))
    );
    assert_eq!(fake.0.current_calls.load(SeqCst), 0);
    assert_eq!(fake.0.retains.load(SeqCst), 0);
    assert_eq!(fake.0.sets.load(SeqCst), 0);
    assert_eq!(fake.current_value(), 77);
}

#[test]
fn attribute_error_domains_and_output_preservation() {
    for (init, ordinal, prepare, query, expected) in [
        (201, 0, 0, 0, 49),
        (0, 2, 0, 0, 101),
        (0, 0, 35, 0, 35),
        (0, 0, 0, 201, 49),
        (0, 0, 0, 709, 709),
        (0, 0, 0, 801, 801),
        (0, 0, 0, 777, 999),
    ] {
        let fake = Fake::default();
        fake.0.init_error.store(init, SeqCst);
        fake.0.attribute_prepare_error.store(prepare, SeqCst);
        fake.0.attribute_error.store(query, SeqCst);
        let rt = Runtime::new(fake.clone());
        let mut out = 123;
        for attribute in [1, 16] {
            assert_eq!(
                unsafe { crate::device::attribute_query(&rt, &mut out, attribute, ordinal) },
                expected
            );
        }
        assert_eq!(out, 123);
        if init != 0 || ordinal == 2 {
            assert_eq!(fake.0.attribute_prepares.load(SeqCst), 0);
        }
        if init != 0 || ordinal == 2 || prepare != 0 {
            assert!(fake.0.attribute_calls.lock().unwrap().is_empty());
        }
    }
}

#[test]
fn attribute_export_preflight_and_tls() {
    unsafe {
        crate::cudaGetLastError();
        let mut out = 123;
        assert_eq!(crate::cudaDeviceGetAttribute(&mut out, 9, 0), 801);
        assert_eq!(crate::cudaPeekAtLastError(), 801);
        assert_eq!(
            crate::cudaDeviceGetAttribute(std::ptr::null_mut(), 75, -1),
            1
        );
        assert_eq!(crate::cudaGetLastError(), 1);
        assert_eq!(crate::cudaDeviceGetAttribute(&mut out, 1, -1), 101);
        assert_eq!(crate::cudaGetLastError(), 101);
        assert_eq!(out, 123);
    }
    crate::errors::record(709);
    let fake = Fake::default();
    let rt = Runtime::new(fake);
    let mut out = 0;
    assert_eq!(
        crate::boundary(|| unsafe { crate::device::attribute_query(&rt, &mut out, 1, 0) }),
        0
    );
    assert_eq!(crate::cudaGetLastError(), 709);
}

#[test]
fn stream_sync_rejects_nonnull_before_context_or_drain() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    for stream in [1, 2, 77, usize::MAX] {
        assert_eq!(
            crate::device::synchronization_query(&rt, stream, |_, _| panic!("no drain")),
            801
        );
        assert_eq!(
            crate::cudaStreamSynchronize(stream as *mut std::ffi::c_void),
            801
        );
        assert_eq!(crate::cudaGetLastError(), 801);
    }
    assert_eq!(fake.0.inits.load(SeqCst), 0);
    assert_eq!(fake.0.current_calls.load(SeqCst), 0);
    assert_eq!(fake.0.sync_calls.load(SeqCst), 0);
}

#[test]
fn stream_sync_orders_context_drain_and_sync() {
    let fake = Fake::default();
    fake.inject_current(77);
    let rt = Runtime::new(fake.clone());
    crate::errors::record(801);
    assert_eq!(
        crate::boundary(
            || crate::device::synchronization_query(&rt, 0, |driver, ctx| {
                assert_eq!(ctx, 77);
                assert_eq!(driver.0.inits.load(SeqCst), 1);
                assert_eq!(driver.0.current_calls.load(SeqCst), 1);
                assert_eq!(driver.0.sync_calls.load(SeqCst), 0);
                Ok(())
            })
        ),
        0
    );
    assert_eq!(crate::cudaGetLastError(), 801);
    assert_eq!(fake.0.sync_calls.load(SeqCst), 1);
    assert_eq!(fake.current_value(), 77);
    assert_eq!(fake.0.retains.load(SeqCst), 0);
    assert_eq!(fake.0.sets.load(SeqCst), 0);
}

#[test]
fn stream_sync_creates_default_context_when_needed() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    assert_eq!(
        crate::device::synchronization_query(&rt, 0, |_, ctx| {
            assert_eq!(ctx, 100);
            Ok(())
        }),
        0
    );
    assert_eq!(fake.0.retains.load(SeqCst), 1);
    assert_eq!(fake.0.sets.load(SeqCst), 1);
    assert_eq!(fake.0.sync_calls.load(SeqCst), 1);
}

#[test]
fn stream_sync_preserves_error_domains_and_short_circuits() {
    for (init, current, drain, sync, expected) in [
        (201, 0, 0, 0, 49),
        (0, 201, 0, 0, 49),
        (0, 709, 0, 0, 709),
        (0, 0, 35, 0, 35),
        (0, 0, 801, 0, 801),
        (0, 0, 201, 0, 201),
        (0, 0, 0, 201, 49),
        (0, 0, 0, 709, 709),
        (0, 0, 0, 777, 999),
    ] {
        let fake = Fake::default();
        fake.inject_current(77);
        fake.0.init_error.store(init, SeqCst);
        fake.0.current_error.store(current, SeqCst);
        fake.0.sync_error.store(sync, SeqCst);
        let rt = Runtime::new(fake.clone());
        let mut drained = false;
        assert_eq!(
            crate::device::synchronization_query(&rt, 0, |_, ctx| {
                assert_eq!(ctx, 77);
                drained = true;
                if drain == 0 {
                    Ok(())
                } else {
                    Err(drain)
                }
            }),
            expected
        );
        assert_eq!(drained, init == 0 && current == 0);
        assert_eq!(
            fake.0.sync_calls.load(SeqCst),
            usize::from(init == 0 && current == 0 && drain == 0)
        );
        assert_eq!(fake.current_value(), 77);
    }
}

#[test]
fn stream_sync_selection_failure_skips_drain_and_sync() {
    let fake = Fake::default();
    fake.0.select_error.store(201, SeqCst);
    let rt = Runtime::new(fake.clone());
    assert_eq!(
        crate::device::synchronization_query(&rt, 0, |_, _| panic!("selection failed")),
        49
    );
    assert_eq!(fake.0.sync_calls.load(SeqCst), 0);
    assert_eq!(fake.0.releases.load(SeqCst), 1);
    assert_eq!(fake.current_value(), 0);
}

#[test]
fn stream_create_preflight_and_errors_preserve_output() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    let registry = crate::streams::Registry::new();
    let mut out = 123usize;
    assert_eq!(
        unsafe { crate::streams::create_query(&registry, &rt, std::ptr::null_mut(), 0) },
        1
    );
    assert_eq!(
        unsafe { crate::streams::create_query(&registry, &rt, &mut out, 2) },
        1
    );
    assert_eq!(out, 123);
    assert_eq!(fake.0.inits.load(SeqCst), 0);
    fake.0.init_error.store(201, SeqCst);
    assert_eq!(
        unsafe { crate::streams::create_query(&registry, &rt, &mut out, 0) },
        49
    );
    assert_eq!(out, 123);
    let mut token = 123usize as *mut std::ffi::c_void;
    assert_eq!(
        unsafe { crate::cudaStreamCreateWithFlags(&mut token, 2) },
        1
    );
    assert_eq!(crate::cudaGetLastError(), 1);
    assert_eq!(token as usize, 123);
    assert_eq!(crate::cudaStreamDestroy(std::ptr::null_mut()), 400);
    assert_eq!(crate::cudaGetLastError(), 400);
}

#[test]
fn created_stream_sync_context_and_configuration() {
    let fake = Fake::default();
    fake.inject_current(77);
    let rt = Runtime::new(fake.clone());
    let registry = crate::streams::registry();
    let mut token = 0;
    assert_eq!(
        unsafe { crate::streams::create_query(registry, &rt, &mut token, 1) },
        0
    );
    let config = crate::configuration::Config {
        grid: crate::configuration::Dim3 { x: 1, y: 1, z: 1 },
        block: crate::configuration::Dim3 { x: 1, y: 1, z: 1 },
        shared: 0,
        stream: token,
    };
    assert_eq!(crate::configuration::preflight(config), 0);
    assert_eq!(
        crate::device::synchronization_query(&rt, token, |_, ctx| {
            assert_eq!(ctx, 77);
            Ok(())
        }),
        0
    );
    assert_eq!(fake.0.sync_calls.load(SeqCst), 1);
    fake.inject_current(88);
    assert_eq!(
        crate::device::synchronization_query(&rt, token, |_, _| panic!("wrong context")),
        400
    );
    assert_eq!(fake.0.sync_calls.load(SeqCst), 1);
    registry.close(77, token, || Ok(())).unwrap();
    assert_eq!(crate::configuration::preflight(config), 400);
}

#[test]
fn failed_stream_destroy_reclaims_live_slot_and_keeps_finish_error() {
    let fake = Fake::default();
    fake.inject_current(77);
    let rt = Runtime::new(fake.clone());
    let r = crate::streams::Registry::with_limits(1, 4);
    let token = r.create(77, 1).unwrap();
    assert_eq!(r.run(77, token, || Err::<(), _>(709)), Err(709));
    assert_eq!(
        crate::streams::destroy_query(&r, &rt, token, |_, ctx| {
            assert_eq!(ctx, 77);
            Err(709)
        }),
        709
    );
    assert_eq!(r.preflight(token), Err(400));
    assert!(r.create(77, 0).is_ok());
    assert_eq!(
        crate::streams::destroy_query(&r, &rt, token, |_, _| panic!("closed")),
        400
    );
}

#[test]
fn profiler_no_collector_initializes_but_never_syncs_or_reserves_queue_nodes() {
    let fake = Fake::default();
    let rt = Runtime::new(fake.clone());
    let q = crate::submission::Scheduler::with_limits(0, 1);
    for _ in 0..10 {
        assert_eq!(crate::profiler::no_collector(&rt, &q), 0);
    }
    assert_eq!(fake.0.inits.load(SeqCst), 1);
    assert_eq!(fake.0.sync_calls.load(SeqCst), 0);
    let _: extern "system" fn() -> i32 = crate::cudaProfilerStart;
    let _: extern "system" fn() -> i32 = crate::cudaProfilerStop;
}
#[test]
fn profiler_propagates_init_context_and_completed_async_errors_once() {
    let q = crate::submission::Scheduler::new();
    let fake = Fake::default();
    fake.0.init_error.store(3, SeqCst);
    assert_eq!(crate::profiler::no_collector(&Runtime::new(fake), &q), 3);
    let fake = Fake::default();
    fake.0.current_error.store(201, SeqCst);
    assert_eq!(crate::profiler::no_collector(&Runtime::new(fake), &q), 49);
    let fake = Fake::default();
    let rt = Runtime::new(fake);
    let ctx = rt.ensure_current().unwrap();
    q.submit(ctx, || Ok(Box::new(|| 1))).unwrap();
    assert_eq!(q.barrier(ctx, true, || Ok(())), Err(1));
    assert_eq!(crate::profiler::no_collector(&rt, &q), 1);
    let other = crate::submission::Scheduler::new();
    other.submit(ctx, || Ok(Box::new(|| 49))).unwrap();
    assert_eq!(other.barrier(ctx, true, || Ok(())), Err(49));
    assert_eq!(crate::profiler::no_collector(&rt, &other), 49);
}
#[test]
fn profiler_does_not_wait_for_pending_work_or_erase_its_later_error() {
    let fake = Fake::default();
    let rt = Arc::new(Runtime::new(fake));
    let ctx = rt.ensure_current().unwrap();
    let q = Arc::new(crate::submission::Scheduler::new());
    let (entered_tx, entered_rx) = std::sync::mpsc::channel();
    let (release_tx, release_rx) = std::sync::mpsc::channel();
    q.submit(ctx, || {
        Ok(Box::new(move || {
            entered_tx.send(()).unwrap();
            release_rx.recv().unwrap();
            1
        }))
    })
    .unwrap();
    entered_rx.recv().unwrap();
    let (tx, rx) = std::sync::mpsc::channel();
    let r = rt.clone();
    let queue = q.clone();
    let join = std::thread::spawn(move || {
        tx.send(crate::profiler::no_collector(&r, &queue)).unwrap();
    });
    let observed = rx.recv_timeout(std::time::Duration::from_secs(2));
    release_tx.send(()).unwrap();
    join.join().unwrap();
    assert_eq!(observed.unwrap(), 0);
    assert_eq!(q.barrier(ctx, true, || Ok(())), Err(1));
    assert_eq!(crate::profiler::no_collector(&rt, &q), 1);
}

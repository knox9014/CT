use crate::driver::*;
use crate::state::Runtime;
use std::collections::HashMap;
use std::sync::atomic::{AtomicI32, AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct Inner {
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
    fn init(&self) -> i32 {
        self.0.inits.fetch_add(1, SeqCst);
        self.0.init_error.load(SeqCst)
    }
    fn count(&self) -> DriverResult<i32> {
        Ok(2)
    }
    fn device(&self, d: i32) -> DriverResult<i32> {
        if (0..2).contains(&d) {
            Ok(d)
        } else {
            Err(101)
        }
    }
    fn current(&self) -> DriverResult<Option<usize>> {
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
        0
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

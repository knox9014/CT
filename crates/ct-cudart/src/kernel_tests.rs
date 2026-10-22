use crate::configuration::{Config, Dim3};
use crate::driver::{DriverCalls, DriverResult};
use crate::kernel_driver::{Function, KernelDriver, Module};
use crate::kernels::KernelRuntime;
use crate::registration_tests::{image, metadata, register};
use crate::state::Runtime;
use std::collections::HashMap;
use std::ffi::c_void;
use std::sync::atomic::{AtomicI32, AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Barrier, Mutex};
#[derive(Default)]
struct Inner {
    currents: Mutex<HashMap<std::thread::ThreadId, usize>>,
    loads: AtomicUsize,
    lookups: AtomicUsize,
    launches: AtomicUsize,
    unloads: AtomicUsize,
    load_error: AtomicI32,
    lookup_error: AtomicI32,
    launch_error: AtomicI32,
    unload_error: AtomicI32,
    prepare_error: AtomicI32,
    current_error: AtomicI32,
    bad_cap: AtomicI32,
    barrier: Mutex<Option<(Arc<Barrier>, Arc<Barrier>)>>,
}
#[derive(Clone, Default)]
struct Fake(Arc<Inner>);
impl DriverCalls for Fake {
    fn init(&self) -> i32 {
        0
    }
    fn count(&self) -> DriverResult<i32> {
        Ok(1)
    }
    fn device(&self, _: i32) -> DriverResult<i32> {
        Ok(0)
    }
    fn current(&self) -> DriverResult<Option<usize>> {
        let error = self.0.current_error.load(SeqCst);
        if error != 0 {
            return Err(error);
        }
        Ok(Some(
            *self
                .0
                .currents
                .lock()
                .unwrap()
                .get(&std::thread::current().id())
                .unwrap_or(&77),
        ))
    }
    fn context_device(&self) -> DriverResult<i32> {
        Ok(0)
    }
    fn retain(&self, _: i32) -> DriverResult<usize> {
        panic!("must preserve ordinary context")
    }
    fn release(&self, _: i32) -> i32 {
        panic!("unexpected release")
    }
    fn set_current(&self, c: usize) -> i32 {
        self.0
            .currents
            .lock()
            .unwrap()
            .insert(std::thread::current().id(), c);
        0
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
impl KernelDriver for Fake {
    fn prepare_kernel(&self) -> Result<(), i32> {
        let c = self.0.prepare_error.load(SeqCst);
        if c == 0 {
            Ok(())
        } else {
            Err(c)
        }
    }
    fn attribute(&self, a: i32, _: i32) -> DriverResult<i32> {
        if self.0.bad_cap.load(SeqCst) != 0 {
            return Ok(0);
        }
        Ok(match a {
            1..=4 => 256,
            _ => i32::MAX,
        })
    }
    fn load(&self, _: &[u8]) -> DriverResult<Module> {
        let id = self.0.loads.fetch_add(1, SeqCst) + 1;
        let barrier = self.0.barrier.lock().unwrap().clone();
        if let Some((start, end)) = barrier {
            start.wait();
            end.wait();
        }
        let c = self.0.load_error.load(SeqCst);
        if c != 0 {
            Err(c)
        } else {
            Ok(id)
        }
    }
    fn function(&self, m: Module, _: &[u8]) -> DriverResult<Function> {
        self.0.lookups.fetch_add(1, SeqCst);
        let c = self.0.lookup_error.load(SeqCst);
        if c != 0 {
            Err(c)
        } else {
            Ok(m * 100)
        }
    }
    fn unload(&self, _: Module) -> i32 {
        self.0.unloads.fetch_add(1, SeqCst);
        self.0.unload_error.load(SeqCst)
    }
    unsafe fn launch(&self, _: Function, _: Config, _: *mut *mut c_void) -> i32 {
        self.0.launches.fetch_add(1, SeqCst);
        self.0.launch_error.load(SeqCst)
    }
}
fn config() -> Config {
    Config {
        grid: Dim3 { x: 2, y: 1, z: 1 },
        block: Dim3 { x: 16, y: 1, z: 1 },
        shared: 0,
        stream: 0,
    }
}
fn ready(k: &KernelRuntime) -> usize {
    let t = unsafe { register(&k.registry, &image()) };
    unsafe {
        k.registry
            .function(t, 11, c"one".as_ptr().cast(), metadata())
            .unwrap();
        k.registry
            .function(t, 12, c"two".as_ptr().cast(), metadata())
            .unwrap();
    }
    k.registry.end(t).unwrap();
    t
}
unsafe fn launch(k: &KernelRuntime, rt: &Runtime<Fake>) -> i32 {
    k.launch(rt, 11, config(), std::ptr::null_mut())
}

#[test]
fn same_symbol_two_contexts_isolated() {
    let k = KernelRuntime::new();
    ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    f.set_current(88);
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    assert_eq!(f.0.loads.load(SeqCst), 2);
    assert_eq!(f.0.lookups.load(SeqCst), 2);
    assert_eq!(f.current(), Ok(Some(88)));
}
#[test]
fn first_use_loads_once() {
    let k = Arc::new(KernelRuntime::new());
    ready(&k);
    let f = Fake::default();
    let rt = Arc::new(Runtime::new(f.clone()));
    let gate = Arc::new(Barrier::new(8));
    let mut threads = Vec::new();
    for _ in 0..8 {
        let k = k.clone();
        let rt = rt.clone();
        let gate = gate.clone();
        threads.push(std::thread::spawn(move || {
            gate.wait();
            assert_eq!(unsafe { launch(&k, &rt) }, 0);
        }));
    }
    for t in threads {
        t.join().unwrap();
    }
    assert_eq!(f.0.loads.load(SeqCst), 1);
    assert_eq!(f.0.lookups.load(SeqCst), 1);
    assert_eq!(f.0.launches.load(SeqCst), 8);
}
#[test]
fn unregister_during_load_owns_late_handle() {
    let k = Arc::new(KernelRuntime::new());
    let token = ready(&k);
    let f = Fake::default();
    let rt = Arc::new(Runtime::new(f.clone()));
    let start = Arc::new(Barrier::new(2));
    let end = Arc::new(Barrier::new(2));
    *f.0.barrier.lock().unwrap() = Some((start.clone(), end.clone()));
    let worker = k.clone();
    let runtime = rt.clone();
    let thread = std::thread::spawn(move || unsafe { launch(&worker, &runtime) });
    start.wait();
    k.registry.retire(token).unwrap();
    assert_eq!(k.drain(&f, 77), Ok(()));
    assert_eq!(f.0.unloads.load(SeqCst), 0);
    end.wait();
    assert_eq!(thread.join().unwrap(), 0);
    assert_eq!(unsafe { launch(&k, &rt) }, 98);
    assert_eq!(k.drain(&f, 88), Ok(()));
    assert_eq!(f.0.unloads.load(SeqCst), 0);
    assert_eq!(k.drain(&f, 77), Ok(()));
    assert_eq!(f.0.unloads.load(SeqCst), 1);
}
#[test]
fn lookup_failure_retains_module_and_is_scoped_to_symbol() {
    let k = KernelRuntime::new();
    let t = ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    f.0.lookup_error.store(500, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 98);
    f.0.lookup_error.store(0, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 98);
    assert_eq!(
        unsafe { k.launch(&rt, 12, config(), std::ptr::null_mut()) },
        0
    );
    assert_eq!(f.0.loads.load(SeqCst), 1);
    assert_eq!(f.0.lookups.load(SeqCst), 2);
    k.registry.retire(t).unwrap();
    k.drain(&f, 77).unwrap();
    assert_eq!(f.0.unloads.load(SeqCst), 1);
}
#[test]
fn retirement_at_capacity_and_cleanup_failure_never_retries() {
    let k = KernelRuntime::with_capacity(1);
    let t = ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    f.set_current(88);
    assert_eq!(unsafe { launch(&k, &rt) }, 801);
    k.registry.retire(t).unwrap();
    f.set_current(77);
    f.0.unload_error.store(400, SeqCst);
    assert_eq!(k.drain(&f, 77), Err(400));
    assert_eq!(k.drain(&f, 77), Err(400));
    assert_eq!(f.0.unloads.load(SeqCst), 1);
}
#[test]
fn stale_context_never_resurrects() {
    let k = KernelRuntime::new();
    ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    f.0.launch_error.store(709, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 709);
    f.0.launch_error.store(0, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 709);
    assert_eq!(f.0.loads.load(SeqCst), 1);
    assert_eq!(f.0.launches.load(SeqCst), 2);
}
#[test]
fn shape_and_argument_errors_differ_and_prepare35_is_preserved() {
    let k = KernelRuntime::new();
    ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    let mut c = config();
    c.block.x = 257;
    assert_eq!(unsafe { k.launch(&rt, 11, c, std::ptr::null_mut()) }, 9);
    c = config();
    c.grid.x = i32::MAX as u32;
    c.block.x = 3;
    assert_eq!(unsafe { k.launch(&rt, 11, c, std::ptr::null_mut()) }, 9);
    c = config();
    c.block.y = 32;
    assert_eq!(unsafe { k.launch(&rt, 11, c, std::ptr::null_mut()) }, 9);
    c = config();
    c.grid.z = 0;
    assert_eq!(unsafe { k.launch(&rt, 11, c, std::ptr::null_mut()) }, 9);
    assert_eq!(f.0.loads.load(SeqCst), 0);
    f.0.prepare_error.store(35, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 35);
    assert_eq!(f.allocate(8), Ok(4096));
    f.0.prepare_error.store(0, SeqCst);
    f.0.bad_cap.store(1, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 999);
    f.0.bad_cap.store(0, SeqCst);
    f.0.launch_error.store(1, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 1);
}

#[test]
fn cache_reservation_precedes_load_and_failed_load_is_sticky() {
    let k = KernelRuntime::with_capacity(1);
    let token = ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    crate::kernels::FAIL_RESERVATION.set(true);
    let code = unsafe { launch(&k, &rt) };
    crate::kernels::FAIL_RESERVATION.set(false);
    assert_eq!(code, 2);
    assert_eq!(f.0.loads.load(SeqCst), 0);
    f.0.load_error.store(218, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 218);
    f.0.load_error.store(0, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 218);
    assert_eq!(f.0.loads.load(SeqCst), 1);
    k.registry.retire(token).unwrap();
    k.drain(&f, 77).unwrap();
    assert_eq!(f.0.unloads.load(SeqCst), 0);
    ready(&k);
    assert_eq!(unsafe { launch(&k, &rt) }, 0);
    assert_eq!(f.0.loads.load(SeqCst), 2);
}

#[test]
fn uncertain_load_failure_retains_capacity_after_retirement() {
    let k = KernelRuntime::with_capacity(1);
    let token = ready(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    f.0.load_error.store(999, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 999);
    k.registry.retire(token).unwrap();
    k.drain(&f, 77).unwrap();
    ready(&k);
    f.0.load_error.store(0, SeqCst);
    assert_eq!(unsafe { launch(&k, &rt) }, 801);
    assert_eq!(f.0.loads.load(SeqCst), 1);
}

use crate::{events::Registry, submission::Scheduler};
use std::sync::{Arc, Barrier};
#[test]
fn generation_is_pending_then_done_and_old_snapshot_survives_rerecord_destroy() {
    let events = Registry::new();
    let q = Scheduler::new();
    let e = events.create(7, || Ok(11)).unwrap();
    assert_eq!(events.synchronize(7, e), Ok(()));
    assert_eq!(
        events.elapsed(&q, 7, e, e, |_, _| panic!("unrecorded native read")),
        Err(400)
    );
    let gate = Arc::new(Barrier::new(2));
    let r = gate.clone();
    events
        .record(&q, 7, e, move |_| {
            r.wait();
            0
        })
        .unwrap();
    let first = events.snapshot(7, e).unwrap().unwrap();
    assert_eq!(first.poll(), Err(600));
    assert_eq!(
        events.elapsed(&q, 7, e, e, |_, _| panic!("pending native read")),
        Err(600)
    );
    gate.wait();
    first.wait().unwrap();
    let gate = Arc::new(Barrier::new(2));
    let r = gate.clone();
    events
        .record(&q, 7, e, move |_| {
            r.wait();
            0
        })
        .unwrap();
    assert_eq!(first.wait(), Ok(()));
    let second = events.snapshot(7, e).unwrap().unwrap();
    assert_eq!(second.poll(), Err(600));
    events.destroy(&q, 7, e, |_| 0).unwrap();
    assert_eq!(events.synchronize(7, e), Err(400));
    gate.wait();
    assert_eq!(second.wait(), Ok(()));
    q.barrier(7, false, || Ok(())).unwrap();
}
#[test]
fn failed_enqueue_preserves_generation_and_open_event() {
    let events = Registry::new();
    let q = Scheduler::new();
    let e = events.create(7, || Ok(11)).unwrap();
    events.record(&q, 7, e, |_| 0).unwrap();
    let old = events.snapshot(7, e).unwrap().unwrap();
    old.wait().unwrap();
    q.fail_send_once();
    assert_eq!(events.record(&q, 7, e, |_| 0), Err(2));
    assert!(Arc::ptr_eq(&old, &events.snapshot(7, e).unwrap().unwrap()));
    q.fail_send_once();
    assert_eq!(events.destroy(&q, 7, e, |_| 0), Err(2));
    assert_eq!(events.synchronize(7, e), Ok(()));
    events.destroy(&q, 7, e, |_| 0).unwrap();
}
#[test]
fn event_context_tombstones_and_limits_are_checked_before_native() {
    let events = Registry::with_limits(1, 2);
    let q = Scheduler::new();
    let e = events.create(7, || Ok(11)).unwrap();
    assert_eq!(events.create(7, || panic!("live budget")), Err(801));
    assert_eq!(
        events.record(&q, 8, e, |_| panic!("foreign record")),
        Err(400)
    );
    assert_eq!(
        events.destroy(&q, 8, e, |_| panic!("foreign destroy")),
        Err(400)
    );
    assert_eq!(events.snapshot(7, 123).err(), Some(400));
    events.destroy(&q, 7, e, |_| 0).unwrap();
    q.barrier(7, false, || Ok(())).unwrap();
    let next = events.create(7, || Ok(12)).unwrap();
    assert_ne!(next, e);
    events.destroy(&q, 7, next, |_| 0).unwrap();
    assert_eq!(events.create(7, || panic!("lifetime budget")), Err(801));
}
#[test]
fn async_error_and_panic_finish_events_and_cleanup_runs() {
    for code in [1, 999] {
        let events = Registry::new();
        let q = Scheduler::new();
        let e = events.create(7, || Ok(11)).unwrap();
        events
            .record(&q, 7, e, move |_| {
                if code == 999 {
                    panic!("native panic")
                }
                code
            })
            .unwrap();
        assert_eq!(events.synchronize(7, e), Err(code));
        let (tx, rx) = std::sync::mpsc::channel();
        events
            .destroy(&q, 7, e, move |_| {
                tx.send(()).unwrap();
                0
            })
            .unwrap();
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap();
        assert_eq!(q.barrier(7, true, || Ok(())), Err(code));
    }
}
#[test]
fn elapsed_same_and_reverse_argument_calls_serialize_without_deadlock() {
    let events = Arc::new(Registry::new());
    let q = Arc::new(Scheduler::new());
    let a = events.create(7, || Ok(11)).unwrap();
    let b = events.create(7, || Ok(12)).unwrap();
    events.record(&q, 7, a, |_| 0).unwrap();
    events.record(&q, 7, b, |_| 0).unwrap();
    q.barrier(7, false, || Ok(())).unwrap();
    assert_eq!(
        events.elapsed(&q, 7, a, a, |x, y| {
            assert_eq!(x, y);
            Ok(0.0)
        }),
        Ok(0.0)
    );
    let joins: Vec<_> = [(a, b), (b, a)]
        .into_iter()
        .map(|(a, b)| {
            let e = events.clone();
            let q = q.clone();
            std::thread::spawn(move || {
                for _ in 0..100 {
                    assert_eq!(e.elapsed(&q, 7, a, b, |_, _| Ok(1.0)), Ok(1.0));
                }
            })
        })
        .collect();
    for j in joins {
        j.join().unwrap();
    }
}

#[test]
fn public_event_preflight_is_gpu_free_and_preserves_outputs() {
    use crate::*;
    let mut out: *mut std::ffi::c_void = std::ptr::dangling_mut();
    let before = out;
    let mut ms = 987.5;
    assert_eq!(unsafe { cudaEventCreate(std::ptr::null_mut()) }, 1);
    assert_eq!(
        cudaEventRecord(std::ptr::null_mut(), std::ptr::null_mut()),
        400
    );
    assert_eq!(cudaEventSynchronize(std::ptr::dangling_mut()), 400);
    assert_eq!(cudaEventDestroy(std::ptr::dangling_mut()), 400);
    assert_eq!(
        unsafe { cudaEventElapsedTime(&mut ms, std::ptr::null_mut(), std::ptr::null_mut()) },
        400
    );
    assert_eq!(ms, 987.5);
    assert_eq!(
        unsafe {
            cudaEventElapsedTime(
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        },
        1
    );
    // Function signatures are checked independently of Driver/GPU initialization.
    let _: unsafe extern "system" fn(*mut *mut std::ffi::c_void) -> i32 = cudaEventCreate;
    let _ = (&mut out, before);
    assert_eq!(crate::events::driver_error(400), 400);
    assert_eq!(crate::events::driver_error(600), 600);
    assert_eq!(crate::events::driver_error(201), 49);
    assert_eq!(crate::events::driver_error(49), 999);
}
#[test]
fn event_extension_is_optional_complete_owned_and_cached() {
    use crate::platform::*;
    use std::cell::Cell;
    struct Fake {
        calls: Cell<usize>,
        missing: usize,
    }
    impl Platform for Fake {
        type Owned = usize;
        fn load_owned(&self) -> Result<usize, i32> {
            panic!("no new DLL")
        }
        fn check_identity(&self, _: &usize) -> Result<(), i32> {
            panic!("already owned")
        }
        fn pin(&self, _: &usize) -> Result<(), i32> {
            panic!("already pinned")
        }
        fn resolve(&self, owned: &usize, name: &[u8]) -> Result<usize, i32> {
            assert_eq!(*owned, 77);
            let n = EVENT_SYMBOLS.iter().position(|s| *s == name).unwrap() + 1;
            self.calls.set(self.calls.get() + 1);
            if n == self.missing {
                Err(35)
            } else {
                Ok(n)
            }
        }
    }
    for missing in 0..=5 {
        let fake = Fake {
            calls: Cell::new(0),
            missing,
        };
        let cache = std::sync::OnceLock::new();
        for _ in 0..3 {
            assert_eq!(
                crate::cached(&cache, || resolve_events(&fake, &77)).copied(),
                if missing == 0 {
                    Ok([1, 2, 3, 4, 5])
                } else {
                    Err(35)
                }
            );
        }
        assert_eq!(fake.calls.get(), if missing == 0 { 5 } else { missing });
    }
}

#[test]
fn skipped_event_gets_prior_error_and_cleanup_is_not_skipped() {
    let e = Registry::new();
    let q = Scheduler::new();
    let token = e.create(7, || Ok(11)).unwrap();
    let gate = Arc::new(Barrier::new(2));
    let r = gate.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            r.wait();
            1
        }))
    })
    .unwrap();
    e.record(&q, 7, token, |_| panic!("failed-context event executed"))
        .unwrap();
    gate.wait();
    assert_eq!(e.synchronize(7, token), Err(1));
    assert_eq!(
        e.elapsed(&q, 7, token, token, |_, _| panic!(
            "failed event elapsed called native"
        )),
        Err(1)
    );
    let (tx, rx) = std::sync::mpsc::channel();
    e.destroy(&q, 7, token, move |_| {
        tx.send(()).unwrap();
        0
    })
    .unwrap();
    rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap();
    assert_eq!(q.barrier(7, true, || Ok(())), Err(1));
}

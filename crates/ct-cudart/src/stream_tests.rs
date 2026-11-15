use crate::streams::Registry;
use std::sync::{Arc, Barrier, Mutex};

#[test]
fn stream_registry_context_flags_stale_and_budgets() {
    let registry = Registry::with_limits(2, 4);
    assert_eq!(registry.create(7, 2), Err(1));
    assert_eq!(registry.create(0, 0), Err(49));
    let a = registry.create(7, 0).unwrap();
    let b = registry.create(8, 1).unwrap();
    assert!(a > 2 && b > a);
    assert_eq!(registry.create(7, 0), Err(801));
    assert_eq!(registry.run(8, a, || Ok(1)), Err(400));
    assert_eq!(registry.run(7, a, || Ok(11)), Ok(11));
    assert_eq!(registry.close(7, a, || Ok(())), Ok(()));
    assert_eq!(registry.preflight(a), Err(400));
    assert_eq!(registry.run(7, a, || panic!("stale")), Err::<(), _>(400));
    let c = registry.create(7, 1).unwrap();
    assert!(c > b);
    registry.close(7, c, || Ok(())).unwrap();
    let d = registry.create(7, 0).unwrap();
    registry.close(7, d, || Ok(())).unwrap();
    assert_eq!(registry.create(7, 0), Err(801));
    for token in [1, 2, 99, usize::MAX] {
        assert_eq!(registry.preflight(token), Err(801));
    }
    assert_eq!(registry.close(7, 0, || panic!("null")), Err(400));
}

#[test]
fn stream_close_waits_for_active_use_without_blocking_other_entries() {
    let registry = Arc::new(Registry::with_limits(3, 8));
    let a = registry.create(7, 1).unwrap();
    let b = registry.create(7, 0).unwrap();
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let events = Arc::new(Mutex::new(Vec::new()));
    let r = registry.clone();
    let e = entered.clone();
    let q = release.clone();
    let trace = events.clone();
    let active = std::thread::spawn(move || {
        r.run(7, a, || {
            trace.lock().unwrap().push("active");
            e.wait();
            q.wait();
            trace.lock().unwrap().push("finished");
            Ok(())
        })
    });
    entered.wait();
    let r = registry.clone();
    let trace = events.clone();
    let (tx, rx) = std::sync::mpsc::channel();
    let close = std::thread::spawn(move || {
        tx.send(()).unwrap();
        r.close(7, a, || {
            trace.lock().unwrap().push("closed");
            Ok(())
        })
    });
    rx.recv().unwrap();
    assert_eq!(registry.run(7, b, || Ok(5)), Ok(5));
    assert!(registry.create(7, 1).is_ok());
    release.wait();
    assert_eq!(active.join().unwrap(), Ok(()));
    assert_eq!(close.join().unwrap(), Ok(()));
    assert_eq!(*events.lock().unwrap(), ["active", "finished", "closed"]);
    assert_eq!(registry.run(7, a, || panic!("closed")), Err::<(), _>(400));
}

#[test]
fn stream_two_closes_and_delayed_lease_fail_closed() {
    let registry = Arc::new(Registry::with_limits(2, 8));
    let token = registry.create(7, 0).unwrap();
    let lease = registry.lease(token).unwrap();
    let barrier = Arc::new(Barrier::new(3));
    let mut workers = Vec::new();
    for _ in 0..2 {
        let r = registry.clone();
        let b = barrier.clone();
        workers.push(std::thread::spawn(move || {
            b.wait();
            r.close(7, token, || Ok(()))
        }));
    }
    barrier.wait();
    let mut results = workers
        .into_iter()
        .map(|w| w.join().unwrap())
        .collect::<Vec<_>>();
    results.sort();
    assert_eq!(results, [Ok(()), Err(400)]);
    assert_eq!(
        lease.run(7, || panic!("delayed stale lease")),
        Err::<(), _>(400)
    );
}

#[test]
fn stream_failure_and_panic_policy() {
    let r = Registry::with_limits(4, 8);
    let a = r.create(7, 0).unwrap();
    assert_eq!(r.run(7, a, || Err::<(), _>(1)), Err(1));
    assert_eq!(r.run(7, a, || Ok(9)), Ok(9));
    assert_eq!(r.run(7, a, || Err::<(), _>(709)), Err(709));
    assert_eq!(r.run(7, a, || panic!("failed context")), Err::<(), _>(709));
    assert_eq!(r.close(7, a, || Ok(())), Ok(()));
    let b = r.create(7, 1).unwrap();
    assert!(std::panic::catch_unwind(|| r.run::<()>(7, b, || panic!("injected"))).is_err());
    assert_eq!(r.run(7, b, || Ok(1)), Err(999));
    let c = r.create(7, 0).unwrap();
    assert_eq!(r.close(7, c, || Err(35)), Err(35));
    assert_eq!(r.run(7, c, || Ok(1)), Err(400));
}

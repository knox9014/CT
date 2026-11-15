use crate::host_ownership::Registry;
use std::sync::{Arc, Barrier};
#[test]
fn host_lease_checks_extents_context_and_exact_free() {
    let r = Registry::with_limit(2);
    assert_eq!(r.allocate(7, 16, || Ok(0x1000)), Ok(0x1000));
    let lease = r.acquire(7, 0x1004, 12).unwrap();
    assert_eq!(r.acquire(7, 0x1004, 13).err(), Some(1));
    assert_eq!(r.acquire(8, 0x1000, 1).err(), Some(1));
    assert_eq!(r.acquire(7, 0x2000, 1).err(), Some(801));
    assert_eq!(r.acquire(7, usize::MAX - 1, 4).err(), Some(1));
    drop(lease);
    let mut freed = false;
    r.free(7, 0x1000, || {
        freed = true;
        Ok(())
    })
    .unwrap();
    assert!(freed);
    assert_eq!(r.acquire(7, 0x1000, 1).err(), Some(801));
}
#[test]
fn host_free_waits_for_use_and_excludes_new_acquires() {
    let r = Arc::new(Registry::with_limit(2));
    r.allocate(7, 16, || Ok(0x1000)).unwrap();
    let lease = r.acquire(7, 0x1000, 16).unwrap();
    let started = Arc::new(Barrier::new(2));
    let other = r.clone();
    let b = started.clone();
    let (tx, rx) = std::sync::mpsc::channel();
    let close = std::thread::spawn(move || {
        b.wait();
        other.free(7, 0x1000, || {
            tx.send(()).unwrap();
            Ok(())
        })
    });
    started.wait();
    r.wait_closing(0x1000);
    assert_eq!(r.acquire(7, 0x1000, 1).err(), Some(1));
    assert!(rx.try_recv().is_err());
    drop(lease);
    assert_eq!(close.join().unwrap(), Ok(()));
    assert!(rx.recv().is_ok());
}
#[test]
fn host_reservation_and_uncertain_free_remain_bounded() {
    let r = Registry::with_limit(1);
    assert_eq!(r.allocate(7, 16, || Err(2)), Err(2));
    r.allocate(7, 16, || Ok(0x1000)).unwrap();
    assert_eq!(r.allocate(7, 4, || panic!("reserve first")), Err(2));
    assert_eq!(r.free(7, 0x1000, || Err(709)), Err(709));
    assert_eq!(r.free(7, 0x1000, || panic!("no uncertain retry")), Err(709));
    assert_eq!(
        r.allocate(7, 4, || panic!("failed storage retained")),
        Err(2)
    );
}

#[test]
fn adjacent_host_allocations_resolve_to_the_new_base() {
    let r = Registry::with_limit(2);
    r.allocate(7, 16, || Ok(0x1000)).unwrap();
    r.allocate(7, 16, || Ok(0x1010)).unwrap();
    assert!(r.acquire(7, 0x1010, 16).is_ok());
    assert_eq!(r.acquire(7, 0x101f, 2).err(), Some(1));
}

#[test]
fn native_address_reuse_waits_for_atomic_free_and_removal() {
    use std::sync::mpsc;
    let r = Arc::new(Registry::with_limit(2));
    r.allocate(7, 16, || Ok(0x1000)).unwrap();
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let old = r.clone();
    let a = entered.clone();
    let b = release.clone();
    let free = std::thread::spawn(move || {
        old.free(7, 0x1000, || {
            a.wait();
            b.wait();
            Ok(())
        })
    });
    entered.wait();
    let (start_tx, start_rx) = mpsc::channel();
    let (native_tx, native_rx) = mpsc::channel();
    let new = r.clone();
    let allocate = std::thread::spawn(move || {
        start_tx.send(()).unwrap();
        new.allocate(8, 16, || {
            native_tx.send(()).unwrap();
            Ok(0x1000)
        })
    });
    start_rx.recv().unwrap();
    let early = native_rx.recv_timeout(std::time::Duration::from_millis(100));
    release.wait();
    assert_eq!(free.join().unwrap(), Ok(()));
    let allocated = allocate.join().unwrap();
    assert_eq!(early, Err(mpsc::RecvTimeoutError::Timeout));
    assert_eq!(allocated, Ok(0x1000));
    let held = r.acquire(8, 0x1000, 16).unwrap();
    drop(held);
    assert_eq!(r.free(8, 0x1000, || Ok(())), Ok(()));
}

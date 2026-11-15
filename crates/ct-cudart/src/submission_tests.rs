use crate::submission::Scheduler;
use std::sync::{Arc, Barrier, Mutex};
#[test]
fn queue_returns_before_work_completes_and_preserves_fifo() {
    let q = Scheduler::with_limits(2, 4);
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let log = Arc::new(Mutex::new(Vec::new()));
    let a = entered.clone();
    let b = release.clone();
    let l = log.clone();
    assert_eq!(
        q.submit(7, || Ok(Box::new(move || {
            a.wait();
            b.wait();
            l.lock().unwrap().push(1);
            0
        }))),
        Ok(())
    );
    entered.wait(); // submit returned while the worker remains blocked on release.
    let l = log.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            l.lock().unwrap().push(2);
            0
        }))
    })
    .unwrap();
    assert!(log.lock().unwrap().is_empty());
    release.wait();
    assert_eq!(q.barrier(7, false, || Ok(9)), Ok(9));
    assert_eq!(*log.lock().unwrap(), [1, 2]);
}
#[test]
fn waiting_context_does_not_hold_worker_progress_or_other_context_submission() {
    let q = Arc::new(Scheduler::with_limits(2, 4));
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let a = entered.clone();
    let b = release.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            a.wait();
            b.wait();
            0
        }))
    })
    .unwrap();
    entered.wait();
    let other = q.clone();
    let waiter = std::thread::spawn(move || other.barrier(7, false, || Ok(())));
    q.submit(8, || Ok(Box::new(|| 0))).unwrap();
    release.wait();
    assert_eq!(waiter.join().unwrap(), Ok(()));
    assert_eq!(q.barrier(8, false, || Ok(())), Ok(()));
    assert_eq!(q.submit(9, || panic!("budget")), Err(801));
}
#[test]
fn queue_error_and_panic_complete_and_cleanup_still_runs() {
    let q = Scheduler::with_limits(3, 4);
    q.submit(7, || Ok(Box::new(|| 709))).unwrap();
    assert_eq!(
        q.barrier(7, false, || panic!("skip unsafe action")),
        Err::<(), _>(709)
    );
    let mut freed = false;
    assert_eq!(
        q.barrier(7, true, || {
            freed = true;
            Ok(())
        }),
        Err(709)
    );
    assert!(freed);
    assert_eq!(q.barrier(7, true, || Err::<(), _>(1)), Err(1));
    assert_eq!(q.submit(7, || panic!("failed queue")), Err(709));
    q.submit(8, || Ok(Box::new(|| panic!("job panic"))))
        .unwrap();
    assert_eq!(q.barrier(8, false, || Ok(())), Err(999));
    q.submit(9, || Ok(Box::new(|| 0))).unwrap();
    assert_eq!(q.barrier(9, false, || Ok(())), Ok(()));
}
#[test]
fn queue_start_and_send_failure_leave_no_pending_work_or_retained_capture() {
    let q = Scheduler::with_limits(1, 1);
    q.fail_start_once();
    assert_eq!(q.submit(7, || panic!("startup precedes capture")), Err(2));
    let held = Arc::new(());
    let capture = held.clone();
    q.fail_send_once();
    assert_eq!(
        q.submit(7, || Ok(Box::new(move || {
            drop(capture);
            0
        }))),
        Err(2)
    );
    assert_eq!(Arc::strong_count(&held), 1);
    assert_eq!(q.barrier(7, false, || Ok(())), Ok(()));
    q.submit(7, || Ok(Box::new(|| 0))).unwrap();
    assert_eq!(q.barrier(7, false, || Ok(())), Ok(()));
}

#[test]
fn queue_failed_send_releases_real_host_use_before_free() {
    let q = Scheduler::with_limits(1, 1);
    let hosts = crate::host_ownership::Registry::new();
    hosts.allocate(7, 16, || Ok(0x1000)).unwrap();
    q.fail_send_once();
    assert_eq!(
        q.submit(7, || {
            let held = hosts.acquire(7, 0x1000, 16)?;
            Ok(Box::new(move || {
                drop(held);
                0
            }))
        }),
        Err(2)
    );
    assert_eq!(hosts.free(7, 0x1000, || Ok(())), Ok(()));
    assert_eq!(q.barrier(7, false, || Ok(())), Ok(()));
}
#[test]
fn queue_panic_releases_later_jobs_and_other_contexts_progress() {
    use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
    let q = Scheduler::with_limits(2, 2);
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let a = entered.clone();
    let b = release.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            a.wait();
            b.wait();
            panic!("first failed job")
        }))
    })
    .unwrap();
    entered.wait();
    let ran = Arc::new(AtomicUsize::new(0));
    let r = ran.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            r.fetch_add(1, SeqCst);
            0
        }))
    })
    .unwrap();
    release.wait();
    assert_eq!(q.barrier(7, false, || Ok(())), Err(999));
    assert_eq!(ran.load(SeqCst), 0);
    q.submit(8, || Ok(Box::new(|| 0))).unwrap();
    assert_eq!(q.barrier(8, false, || Ok(())), Ok(()));
}

#[test]
fn first_barrier_excludes_the_first_submission() {
    use std::sync::mpsc;
    let q = Arc::new(Scheduler::with_limits(1, 2));
    let entered = Arc::new(Barrier::new(2));
    let release = Arc::new(Barrier::new(2));
    let sync = q.clone();
    let a = entered.clone();
    let b = release.clone();
    let barrier = std::thread::spawn(move || {
        sync.barrier(7, false, || {
            a.wait();
            b.wait();
            Ok(())
        })
    });
    entered.wait();
    let (start_tx, start_rx) = mpsc::channel();
    let (ran_tx, ran_rx) = mpsc::channel();
    let submit = q.clone();
    let sender = std::thread::spawn(move || {
        start_tx.send(()).unwrap();
        submit.submit(7, || {
            Ok(Box::new(move || {
                ran_tx.send(()).unwrap();
                0
            }))
        })
    });
    start_rx.recv().unwrap();
    let early = ran_rx.recv_timeout(std::time::Duration::from_millis(100));
    release.wait();
    assert_eq!(barrier.join().unwrap(), Ok(()));
    assert_eq!(sender.join().unwrap(), Ok(()));
    assert_eq!(q.barrier(7, false, || Ok(())), Ok(()));
    assert_eq!(early, Err(mpsc::RecvTimeoutError::Timeout));
}

#[test]
fn transaction_commits_only_after_accept_and_completion_can_precede_commit() {
    let q = Scheduler::new();
    let (tx, rx) = std::sync::mpsc::channel();
    let mut published = false;
    q.transaction(
        7,
        false,
        || {
            Ok((
                Box::new(|| 0),
                Some(Box::new(move |c| {
                    tx.send(c).unwrap();
                }) as crate::submission::Notify),
                (),
            ))
        },
        |()| {
            assert_eq!(
                rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap(),
                0
            );
            published = true;
        },
    )
    .unwrap();
    assert!(published);
    q.fail_send_once();
    assert_eq!(
        q.transaction(
            7,
            false,
            || Ok((Box::new(|| 0), None, ())),
            |()| panic!("failed send committed")
        ),
        Err(2)
    );
    q.barrier(7, false, || Ok(())).unwrap();
}
#[test]
fn transaction_notifies_panics_skipped_jobs_and_runs_error_cleanup() {
    let q = Scheduler::new();
    let (tx, rx) = std::sync::mpsc::channel();
    let gate = Arc::new(Barrier::new(2));
    let release = gate.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            release.wait();
            1
        }))
    })
    .unwrap();
    for cleanup in [false, true] {
        let notify = tx.clone();
        q.transaction(
            7,
            cleanup,
            || {
                Ok((
                    Box::new(move || {
                        assert!(cleanup);
                        0
                    }),
                    Some(Box::new(move |c| {
                        notify.send(c).unwrap();
                    }) as crate::submission::Notify),
                    (),
                ))
            },
            |()| {},
        )
        .unwrap();
    }
    gate.wait();
    assert_eq!(
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap(),
        1
    );
    assert_eq!(
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap(),
        0
    );
    assert_eq!(q.barrier(7, true, || Ok(())), Err(1));
    let notify = tx.clone();
    q.transaction(
        8,
        false,
        || {
            Ok((
                Box::new(|| panic!("event action")),
                Some(Box::new(move |c| {
                    notify.send(c).unwrap();
                }) as crate::submission::Notify),
                (),
            ))
        },
        |()| {},
    )
    .unwrap();
    assert_eq!(
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap(),
        999
    );
    assert_eq!(q.barrier(8, true, || Ok(())), Err(999));
    let notify = tx;
    q.transaction(
        8,
        true,
        || {
            Ok((
                Box::new(|| 0),
                Some(Box::new(move |c| {
                    notify.send(c).unwrap();
                }) as crate::submission::Notify),
                (),
            ))
        },
        |()| {},
    )
    .unwrap();
    assert_eq!(
        rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap(),
        0
    );
}
#[test]
fn exclusive_observes_pending_without_waiting_for_completion() {
    let q = Scheduler::new();
    let gate = Arc::new(Barrier::new(2));
    let r = gate.clone();
    q.submit(7, || {
        Ok(Box::new(move || {
            r.wait();
            0
        }))
    })
    .unwrap();
    assert_eq!(q.exclusive(7, || Ok(600)), Ok(600));
    gate.wait();
    q.barrier(7, false, || Ok(())).unwrap();
}

#[test]
fn context_barrier_waits_for_event_notification_publication() {
    let q = Arc::new(Scheduler::new());
    let (entered_tx, entered_rx) = std::sync::mpsc::channel();
    let (release_tx, release_rx) = std::sync::mpsc::channel();
    q.transaction(
        7,
        false,
        || {
            Ok((
                Box::new(|| 0),
                Some(Box::new(move |_| {
                    entered_tx.send(()).unwrap();
                    release_rx.recv().unwrap();
                }) as crate::submission::Notify),
                (),
            ))
        },
        |()| {},
    )
    .unwrap();
    entered_rx
        .recv_timeout(std::time::Duration::from_secs(2))
        .unwrap();
    let (done_tx, done_rx) = std::sync::mpsc::channel();
    let other = q.clone();
    let join = std::thread::spawn(move || {
        let result = other.barrier(7, false, || Ok(()));
        done_tx.send(result).unwrap();
    });
    let premature = done_rx.recv_timeout(std::time::Duration::from_millis(100));
    release_tx.send(()).unwrap();
    join.join().unwrap();
    assert!(
        premature.is_err(),
        "barrier returned before event completion publication"
    );
    assert_eq!(
        done_rx
            .recv_timeout(std::time::Duration::from_secs(2))
            .unwrap(),
        Ok(())
    );
}

use crate::registration::*;
use crate::registration_tests::{image, metadata, register};
use crate::registration_variables::*;
use std::sync::{Arc, Barrier};
fn m() -> VariableMetadata {
    VariableMetadata {
        external: 0,
        size: 8,
        constant: 0,
        global: 0,
    }
}
unsafe fn add(r: &Registry, t: usize, h: usize, v: VariableMetadata) -> Result<(), i32> {
    r.variable(t, h, c"value".as_ptr().cast(), c"value".as_ptr().cast(), v)
}
#[test]
fn variable_metadata_is_owned_and_bounded() {
    let r = Registry::new();
    let t = unsafe { register(&r, &image()) };
    let mut a = b"value\0".to_vec();
    let mut b = a.clone();
    unsafe { r.variable(t, 91, a.as_ptr(), b.as_ptr(), m()) }.unwrap();
    a.fill(0);
    b.fill(0);
    unsafe { add(&r, t, 91, m()) }.unwrap();
    for (v, want) in [
        (VariableMetadata { size: 0, ..m() }, 1),
        (
            VariableMetadata {
                size: 16777217,
                ..m()
            },
            801,
        ),
        (VariableMetadata { external: 2, ..m() }, 1),
        (VariableMetadata { external: 1, ..m() }, 801),
        (VariableMetadata { constant: 1, ..m() }, 801),
        (VariableMetadata { global: 1, ..m() }, 801),
    ] {
        let t = unsafe { register(&r, &image()) };
        assert_eq!(unsafe { add(&r, t, 92, v) }, Err(want));
        r.retire(t).unwrap();
    }
}
#[test]
fn variable_duplicate_conflict_and_capacity() {
    let r = Registry::new();
    let t = unsafe { register(&r, &image()) };
    unsafe { add(&r, t, 1, m()) }.unwrap();
    unsafe { add(&r, t, 1, m()) }.unwrap();
    assert_eq!(
        unsafe { add(&r, t, 1, VariableMetadata { size: 4, ..m() }) },
        Err(1)
    );
    r.retire(t).unwrap();
    let limits = Limits::default();
    assert_eq!((limits.variables, limits.variable_mappings), (256, 2048));
    let mut tokens = Vec::new();
    for group in 0..8 {
        let t = unsafe { register(&r, &image()) };
        for i in 0..256 {
            unsafe { add(&r, t, group * 256 + i + 1, m()) }.unwrap();
        }
        tokens.push(t);
    }
    assert_eq!(unsafe { add(&r, tokens[0], 9999, m()) }, Err(801));
    let next = unsafe { register(&r, &image()) };
    assert_eq!(unsafe { add(&r, next, 9999, m()) }, Err(801));
    r.retire(next).unwrap();
    r.retire(tokens[0]).unwrap();
    let next = unsafe { register(&r, &image()) };
    assert!(unsafe { add(&r, next, 9999, m()) }.is_ok());
}
#[test]
fn variable_terminal_state_precedes_payload() {
    let r = Registry::new();
    let t = unsafe { register(&r, &image()) };
    assert_eq!(
        unsafe { add(&r, t, 1, VariableMetadata { external: 1, ..m() }) },
        Err(801)
    );
    assert_eq!(
        unsafe { r.variable(t, 0, std::ptr::null(), std::ptr::null(), m()) },
        Err(801)
    );
    r.retire(t).unwrap();
    for t in [t, usize::MAX] {
        assert_eq!(
            unsafe { r.variable(t, 0, std::ptr::null(), std::ptr::null(), m()) },
            Err(98)
        );
    }
    let t = unsafe { register(&r, &image()) };
    r.end(t).unwrap();
    assert_eq!(unsafe { add(&r, t, 1, m()) }, Err(1));
}
#[test]
fn retire_during_variable_preparation_cannot_resurrect() {
    let r = Arc::new(Registry::new());
    let t = unsafe { register(&r, &image()) };
    let a = Arc::new(Barrier::new(2));
    let b = Arc::new(Barrier::new(2));
    let (rr, aa, bb) = (r.clone(), a.clone(), b.clone());
    let worker = std::thread::spawn(move || {
        PREPARE_BARRIER.with(|v| *v.borrow_mut() = Some((aa, bb)));
        unsafe { add(&rr, t, 1, m()) }
    });
    a.wait();
    r.retire(t).unwrap();
    b.wait();
    assert_eq!(worker.join().unwrap(), Err(98));
    assert_eq!(r.end(t), Err(98));
}
#[test]
fn variable_blocks_only_its_registration() {
    let r = Registry::new();
    let t = unsafe { register(&r, &image()) };
    let other = unsafe { register(&r, &image()) };
    for (token, host) in [(t, 11), (other, 12)] {
        unsafe { r.function(token, host, c"kernel".as_ptr().cast(), metadata()) }.unwrap();
    }
    unsafe { add(&r, t, 1, m()) }.unwrap();
    r.end(t).unwrap();
    r.end(other).unwrap();
    assert_eq!(r.lease(11).unwrap().image().err(), Some(801));
    assert!(r.lease(12).unwrap().image().is_ok());
}

#[test]
fn u32_bindings_live_through_unregister() {
    let r = Registry::with_limits(Limits {
        variable_mappings: 1,
        ..Limits::default()
    });
    let t = unsafe { register(&r, &image()) };
    unsafe { r.function(t, 11, c"kernel".as_ptr().cast(), metadata()) }.unwrap();
    unsafe { add(&r, t, 91, VariableMetadata { size: 4, ..m() }) }.unwrap();
    r.end(t).unwrap();
    r.end(t).unwrap();
    let lease = r.lease(11).unwrap();
    assert!(lease.image().is_ok());
    assert_eq!(lease.variables()[0].name, b"value\0");
    r.retire(t).unwrap();
    r.retire(t).unwrap();
    assert_eq!(lease.variables()[0].metadata.size, 4);
    assert!(lease.retired());
    assert!(lease.image().is_ok());
    let next = unsafe { register(&r, &image()) };
    unsafe { add(&r, next, 92, VariableMetadata { size: 4, ..m() }) }.unwrap();
}

use super::registration::*;
use std::ffi::c_void;

fn image() -> Vec<u8> {
    let text = b".version 8.0\n.target sm_52\n.address_size 64\n";
    let padded = (text.len() + 1 + 7) & !7;
    let mut b = vec![0; 88 + padded];
    b[..4].copy_from_slice(&0xba55ed50u32.to_le_bytes());
    b[4] = 1;
    b[6] = 16;
    let size = (b.len() - 16) as u64;
    b[8..16].copy_from_slice(&size.to_le_bytes());
    b[16] = 1;
    b[18..20].copy_from_slice(&0x101u16.to_le_bytes());
    b[20..24].copy_from_slice(&72u32.to_le_bytes());
    b[24..32].copy_from_slice(&(padded as u64).to_le_bytes());
    b[36..40].copy_from_slice(&64u32.to_le_bytes());
    b[42] = 8;
    b[44] = 52;
    b[56] = 0x41;
    b[88..88 + text.len()].copy_from_slice(text);
    b
}
fn wrapper(b: &[u8]) -> Wrapper {
    Wrapper {
        magic: 0x466243b1,
        version: 1,
        data: b.as_ptr() as usize,
        extra: 0,
    }
}
unsafe fn register(reg: &Registry, b: &[u8]) -> usize {
    reg.register((&wrapper(b) as *const Wrapper).cast::<c_void>())
        .unwrap()
}
fn metadata() -> FunctionMetadata {
    FunctionMetadata {
        thread_limit: -1,
        optional: [0; 5],
    }
}

#[test]
fn snapshot_survives_source_mutation() {
    let reg = Registry::new();
    let mut b = image();
    let expected = b.clone();
    let token = unsafe { register(&reg, &b) };
    let mut name = b"kernel\0".to_vec();
    unsafe {
        reg.function(token, 11, name.as_ptr(), metadata()).unwrap();
    }
    reg.end(token).unwrap();
    b.fill(0);
    name.fill(b'x');
    let lease = reg.lease(11).unwrap();
    assert_eq!(lease.image(), expected);
    assert_eq!(lease.symbol(), b"kernel\0");
    reg.retire(token).unwrap();
    assert_eq!(reg.lease(11).err(), Some(98));
    assert_eq!(lease.image(), expected);
    assert!(lease.retired());
}

#[test]
fn duplicate_and_end_policy() {
    let reg = Registry::new();
    let b = image();
    let t = unsafe { register(&reg, &b) };
    unsafe {
        reg.function(t, 11, c"one".as_ptr().cast(), metadata())
            .unwrap();
        reg.function(t, 11, c"one".as_ptr().cast(), metadata())
            .unwrap();
        assert_eq!(
            reg.function(t, 11, c"other".as_ptr().cast(), metadata()),
            Err(98)
        );
        reg.function(t, 12, c"valid".as_ptr().cast(), metadata())
            .unwrap();
    }
    reg.end(t).unwrap();
    reg.end(t).unwrap();
    assert_eq!(reg.lease(11).err(), Some(98));
    assert!(reg.lease(12).is_ok());
    assert_eq!(
        unsafe { reg.function(t, 13, c"late".as_ptr().cast(), metadata()) },
        Err(1)
    );
    assert_eq!(reg.lease(12).err(), Some(1));
    reg.retire(t).unwrap();
    reg.retire(t).unwrap();
    assert_eq!(reg.end(t), Err(98));
    assert_eq!(reg.retire(123), Err(98));
}

#[test]
fn tokens_do_not_reuse_and_ambiguity_is_explicit() {
    let reg = Registry::new();
    let b = image();
    let a = unsafe { register(&reg, &b) };
    let t = unsafe { register(&reg, &b) };
    for token in [a, t] {
        unsafe {
            reg.function(token, 11, c"same".as_ptr().cast(), metadata())
                .unwrap();
        }
        reg.end(token).unwrap();
    }
    assert_eq!(reg.lease(11).err(), Some(98));
    reg.retire(a).unwrap();
    assert!(reg.lease(11).is_ok());
    reg.retire(t).unwrap();
    let next = unsafe { register(&reg, &b) };
    assert_ne!(next, a);
    assert_ne!(next, t);
}

#[test]
fn registration_never_calls_driver_and_rejects_bad_wrapper() {
    let reg = Registry::new();
    let b = image();
    let mut w = wrapper(&b);
    assert_eq!(unsafe { reg.register(std::ptr::null()) }, Err(1));
    w.version = 2;
    assert_eq!(
        unsafe { reg.register((&w as *const Wrapper).cast()) },
        Err(801)
    );
    w.version = 1;
    w.magic = 0;
    assert_eq!(
        unsafe { reg.register((&w as *const Wrapper).cast()) },
        Err(1)
    );
    assert_eq!(std::mem::size_of::<Wrapper>(), 24);
    // Registry has no Driver/Platform parameter or bridge access.
}

#[test]
fn failed_mapping_does_not_poison_other_registration() {
    let reg = Registry::new();
    let b = image();
    let a = unsafe { register(&reg, &b) };
    let t = unsafe { register(&reg, &b) };
    unsafe {
        reg.function(a, 11, c"valid".as_ptr().cast(), metadata())
            .unwrap();
    }
    reg.end(a).unwrap();
    reg.fail(t, 801);
    assert!(reg.lease(11).is_ok());
}

#[test]
fn budgets_and_fallible_reservations() {
    let limits = Limits {
        live: 1,
        lifetime: 2,
        functions: 1,
        mappings: 1,
        names: 4,
        raw_bytes: 4096,
    };
    let reg = Registry::with_limits(limits);
    let b = image();
    let a = unsafe { register(&reg, &b) };
    assert_eq!(
        unsafe { reg.register((&wrapper(&b) as *const Wrapper).cast()) },
        Err(801)
    );
    unsafe {
        reg.function(a, 11, c"four".as_ptr().cast(), metadata())
            .unwrap();
    }
    assert_eq!(
        unsafe { reg.function(a, 12, c"five!".as_ptr().cast(), metadata()) },
        Err(801)
    );
    reg.retire(a).unwrap();
    let t = unsafe { register(&reg, &b) };
    reg.retire(t).unwrap();
    assert_eq!(
        unsafe { reg.register((&wrapper(&b) as *const Wrapper).cast()) },
        Err(801)
    );
    let p = Limits::default();
    assert_eq!(
        (
            p.live,
            p.lifetime,
            p.functions,
            p.mappings,
            p.names,
            p.raw_bytes
        ),
        (64, 1024, 512, 4096, 1024, 64 * 1024 * 1024)
    );
}

#[test]
fn retained_image_budget_is_released_only_after_last_lease() {
    let b = image();
    let reg = Registry::with_limits(Limits {
        raw_bytes: b.len(),
        ..Limits::default()
    });
    let t = unsafe { register(&reg, &b) };
    unsafe {
        reg.function(t, 11, c"kernel".as_ptr().cast(), metadata())
            .unwrap();
    }
    reg.end(t).unwrap();
    let lease = reg.lease(11).unwrap();
    reg.retire(t).unwrap();
    assert_eq!(
        unsafe { reg.register((&wrapper(&b) as *const Wrapper).cast()) },
        Err(801)
    );
    drop(lease);
    assert!(unsafe { reg.register((&wrapper(&b) as *const Wrapper).cast()) }.is_ok());
}

#[test]
fn reservation_failure_rolls_back_before_token_publication() {
    let reg = Registry::new();
    let b = image();
    FAIL_RESERVATION.set(true);
    let result = unsafe { reg.register((&wrapper(&b) as *const Wrapper).cast()) };
    FAIL_RESERVATION.set(false);
    assert_eq!(result, Err(2));
    let t = unsafe { register(&reg, &b) };
    FAIL_RESERVATION.set(true);
    let result = unsafe { reg.function(t, 11, c"kernel".as_ptr().cast(), metadata()) };
    FAIL_RESERVATION.set(false);
    assert_eq!(result, Err(2));
    assert_eq!(reg.end(t), Err(2));
    reg.retire(t).unwrap();
}

#[test]
fn mapping_function_and_name_limits_are_independent() {
    let b = image();
    for limits in [
        Limits {
            functions: 1,
            ..Limits::default()
        },
        Limits {
            mappings: 1,
            ..Limits::default()
        },
    ] {
        let reg = Registry::with_limits(limits);
        let t = unsafe { register(&reg, &b) };
        unsafe {
            reg.function(t, 11, c"one".as_ptr().cast(), metadata())
                .unwrap();
        }
        assert_eq!(
            unsafe { reg.function(t, 12, c"two".as_ptr().cast(), metadata()) },
            Err(801)
        );
        reg.retire(t).unwrap();
    }
    let mut name = vec![b'a'; 1025];
    name.push(0);
    assert_eq!(unsafe { copy_name(name.as_ptr(), 1024) }, Err(801));
    name[1024] = 0;
    assert_eq!(
        unsafe { copy_name(name.as_ptr(), 1024) }.unwrap().len(),
        1025
    );
    assert_eq!(unsafe { copy_name(std::ptr::null(), 1024) }, Err(1));
}

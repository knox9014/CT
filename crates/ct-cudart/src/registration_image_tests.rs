use crate::registration::{Limits, Registry, Wrapper};
use crate::registration_images::*;
use crate::registration_tests::{image, metadata, register, wrapper};
use std::ffi::c_void;
fn version2(b: &[u8], list: &[*const u8]) -> Wrapper {
    let mut w = wrapper(b);
    w.version = 2;
    w.extra = list.as_ptr() as usize;
    w
}
#[test]
fn version2_owns_raw_dependencies_and_deduplicates_aliases() {
    let mut b = image();
    let list = [b.as_ptr(), b.as_ptr(), std::ptr::null()];
    let w = version2(&b, &list);
    let owned = unsafe { copy_images((&w as *const Wrapper).cast(), b.len()) }.unwrap();
    assert_eq!(owned.raw_bytes, b.len());
    assert!(owned.prelinked.is_empty());
    let saved = b.clone();
    b.fill(0);
    assert_eq!(owned.primary, saved);
    let b = image();
    let other = b.clone();
    let list = [other.as_ptr(), std::ptr::null()];
    let w = version2(&b, &list);
    assert_eq!(
        unsafe { copy_images((&w as *const Wrapper).cast(), b.len() * 2) }
            .unwrap()
            .raw_bytes,
        b.len() * 2
    );
}
#[test]
fn dependency_slot32_requires_null() {
    let b = image();
    let mut list = vec![b.as_ptr(); 33];
    let w = version2(&b, &list);
    assert_eq!(
        unsafe { copy_images((&w as *const Wrapper).cast(), usize::MAX) }.err(),
        Some(801)
    );
    list[32] = std::ptr::null();
    assert!(unsafe { copy_images((&w as *const Wrapper).cast(), usize::MAX) }.is_ok());
}
#[test]
fn wrapper_is_not_a_raw_dependency() {
    let b = image();
    let other = wrapper(&b);
    let list = [(&other as *const Wrapper).cast::<u8>(), std::ptr::null()];
    let w = version2(&b, &list);
    assert_eq!(
        unsafe { copy_images((&w as *const Wrapper).cast(), usize::MAX) }.err(),
        Some(218)
    );
}
#[test]
fn empty_dependency_list_rejected() {
    let b = image();
    let list = [std::ptr::null()];
    let w = version2(&b, &list);
    assert_eq!(
        unsafe { copy_images((&w as *const Wrapper).cast(), usize::MAX) }.err(),
        Some(1)
    );
}
#[test]
fn dependency_copy_failure_rolls_back() {
    let reg = Registry::new();
    let b = image();
    let other = image();
    let list = [other.as_ptr(), std::ptr::null()];
    let w = version2(&b, &list);
    FAIL_COPY_AFTER.set(Some(1));
    assert_eq!(
        unsafe { reg.register((&w as *const Wrapper).cast()) },
        Err(2)
    );
    FAIL_COPY_AFTER.set(None);
    assert!(unsafe { reg.register((&w as *const Wrapper).cast()) }.is_ok());
    let reg = Registry::with_limits(Limits {
        raw_bytes: b.len(),
        ..Limits::default()
    });
    assert_eq!(
        unsafe { reg.register((&w as *const Wrapper).cast()) },
        Err(801)
    );
    let t = unsafe { register(&reg, &b) };
    reg.retire(t).unwrap();
}
#[test]
fn retired_lease_keeps_all_image_bytes() {
    let b = image();
    let other = image();
    let list = [other.as_ptr(), std::ptr::null()];
    let w = version2(&b, &list);
    let reg = Registry::with_limits(Limits {
        raw_bytes: b.len() * 2,
        ..Limits::default()
    });
    let t = unsafe { reg.register((&w as *const Wrapper).cast::<c_void>()) }.unwrap();
    unsafe { reg.function(t, 901, c"kernel".as_ptr().cast(), metadata()) }.unwrap();
    reg.end(t).unwrap();
    let lease = reg.lease(901).unwrap();
    assert_eq!(lease.image().err(), Some(801));
    reg.retire(t).unwrap();
    assert_eq!(
        unsafe { reg.register((&w as *const Wrapper).cast()) },
        Err(801)
    );
    drop(lease);
    assert!(unsafe { reg.register((&w as *const Wrapper).cast()) }.is_ok());
}

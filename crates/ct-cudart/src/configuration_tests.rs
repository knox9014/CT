use super::configuration::*;
use std::ffi::c_void;
fn config(x: u32) -> Config {
    Config {
        grid: Dim3 { x, y: 1, z: 1 },
        block: Dim3 { x: 16, y: 1, z: 1 },
        shared: 0,
        stream: 0,
    }
}
unsafe fn take() -> Result<Config, i32> {
    let mut c = config(0);
    let code = pop(
        &mut c.grid,
        &mut c.block,
        &mut c.shared,
        (&mut c.stream as *mut usize).cast::<c_void>(),
    );
    if code == 0 {
        Ok(c)
    } else {
        Err(code)
    }
}
#[test]
fn failed_push_preserves_previous_and_other_thread() {
    assert_eq!(push(config(2)), 0);
    assert_eq!(push(config(0)), 9);
    let mut unsupported = config(3);
    unsupported.shared = 1;
    assert_eq!(push(unsupported), 801);
    unsupported.shared = 0;
    unsupported.stream = 1;
    assert_eq!(push(unsupported), 801);
    std::thread::spawn(|| {
        assert_eq!(unsafe { take() }.err(), Some(9));
        assert_eq!(push(config(4)), 0);
        assert_eq!(unsafe { take() }.unwrap().grid.x, 4);
    })
    .join()
    .unwrap();
    assert_eq!(unsafe { take() }.unwrap().grid.x, 2);
    assert_eq!(unsafe { take() }.err(), Some(9));
}
#[test]
fn pop_validates_all_outputs_before_consuming() {
    assert_eq!(push(config(2)), 0);
    assert_eq!(push(config(3)), 0);
    for missing in 0..4 {
        let mut c = config(99);
        let mut g = &mut c.grid as *mut Dim3;
        let mut b = &mut c.block as *mut Dim3;
        let mut s = &mut c.shared as *mut usize;
        let mut st = (&mut c.stream as *mut usize).cast();
        match missing {
            0 => g = std::ptr::null_mut(),
            1 => b = std::ptr::null_mut(),
            2 => s = std::ptr::null_mut(),
            _ => st = std::ptr::null_mut(),
        };
        assert_eq!(unsafe { pop(g, b, s, st) }, 1);
        assert_eq!(c.grid.x, 99);
    }
    assert_eq!(unsafe { take() }.unwrap().grid.x, 3);
    assert_eq!(unsafe { take() }.unwrap().grid.x, 2);
}
#[test]
fn configuration_capacity_and_fallible_growth() {
    for _ in 0..64 {
        assert_eq!(push(config(1)), 0);
    }
    assert_eq!(push(config(1)), 801);
    for _ in 0..64 {
        assert!(unsafe { take() }.is_ok());
    }
    assert_eq!(unsafe { take() }.err(), Some(9));
    FAIL_RESERVATION.set(true);
    assert_eq!(push(config(1)), 2);
    FAIL_RESERVATION.set(false);
    assert_eq!(unsafe { take() }.err(), Some(9));
    assert_eq!(
        (std::mem::size_of::<Dim3>(), std::mem::align_of::<Dim3>()),
        (12, 4)
    );
}
#[test]
fn callback_panic_boundaries() {
    use crate::registration::Registry;
    let r = Registry::new();
    crate::errors::take();
    let result: Result<(), i32> =
        crate::callback_boundary(&r, None, || panic!("injected callback panic"));
    assert_eq!(result, Err(999));
    assert_eq!(crate::errors::peek(), 999);
    assert_eq!(crate::callback_boundary(&r, None, || Ok(())), Ok(()));
    assert_eq!(crate::errors::peek(), 999);
    assert_eq!(crate::errors::take(), 999);
    assert_eq!(crate::errors::peek(), 0);
}

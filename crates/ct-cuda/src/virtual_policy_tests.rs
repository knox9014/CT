use super::virtual_policy::{initialize, parse, Mode};
use std::ffi::OsString;
use std::sync::OnceLock;

#[test]
fn topology_count_is_opt_in_checked_and_never_a_default_or_clamp() {
    use super::virtual_policy::topology_count;
    for (slices, subslices, expected) in [
        (1, 1, Ok(1)),
        (2, 6, Ok(12)),
        (1, i32::MAX as u32, Ok(i32::MAX)),
        (0, 3, Err(801)),
        (3, 0, Err(801)),
        (1, i32::MAX as u32 + 1, Err(801)),
        (u32::MAX, 2, Err(801)),
    ] {
        assert_eq!(topology_count(Mode::Sm52, slices, subslices), expected);
        assert_eq!(topology_count(Mode::Strict, slices, subslices), Err(801));
    }
}

#[test]
fn only_exact_explicit_target_is_virtual() {
    assert_eq!(parse(None), Ok(Mode::Strict));
    assert_eq!(parse(Some(OsString::from("strict"))), Ok(Mode::Strict));
    assert_eq!(
        parse(Some(OsString::from("ct-sm52-subset-v1"))),
        Ok(Mode::Sm52)
    );
    for value in ["", "5.2", "CT-SM52-SUBSET-V1", "ct-sm52-subset-v1 "] {
        assert_eq!(parse(Some(OsString::from(value))), Err(1));
    }
    use std::os::windows::ffi::OsStringExt;
    assert_eq!(parse(Some(OsString::from_wide(&[0xd800]))), Err(1));
}

#[test]
fn invalid_flags_do_not_latch_and_native_failure_cannot_change_policy() {
    let cell = OnceLock::new();
    assert_eq!(
        initialize(
            1,
            &cell,
            || panic!("must not read policy"),
            || panic!("must not initialize native")
        ),
        Err(1)
    );
    assert!(cell.get().is_none());
    assert_eq!(
        initialize(0, &cell, || Some("ct-sm52-subset-v1".into()), || Err(100)),
        Err(100)
    );
    assert_eq!(
        initialize(0, &cell, || panic!("must not reread"), || Ok(())),
        Ok(())
    );
    assert_eq!(cell.get(), Some(&Ok(Mode::Sm52)));
}

#[test]
fn invalid_configuration_is_persistent_and_never_initializes_native() {
    let cell = OnceLock::new();
    assert_eq!(
        initialize(
            0,
            &cell,
            || Some("typo".into()),
            || panic!("native must not run")
        ),
        Err(1)
    );
    assert_eq!(
        initialize(0, &cell, || None, || panic!("native must not run")),
        Err(1)
    );
}

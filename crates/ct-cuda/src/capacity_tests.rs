use super::*;

#[test]
fn shared_limit_is_bounded_by_native_and_translator() {
    for (native, expected) in [
        (0, 0),
        (15, 15),
        (16384, 16384),
        (32768, 16384),
        (u32::MAX, 16384),
    ] {
        assert_eq!(crate::capacity::shared_limit(native), expected);
    }
}

#[test]
fn every_entry_is_checked_individually_before_native_creation() {
    let source = ".version 8.0 .target sm_52 .address_size 64 .entry a(){.shared .align 16 .b8 x[4];ret;} .entry b(){.shared .align 4 .b8 y[32];ret;}";
    let module = ct_codegen_spirv::translate_module(source).unwrap();
    assert_eq!(module.entries[0].static_shared_bytes, 16);
    assert_eq!(module.entries[1].static_shared_bytes, 32);
    assert_eq!(
        crate::capacity::validate_entries(&module.entries, 31),
        Err(UNSUPPORTED)
    );
    assert_eq!(
        crate::capacity::validate_entries(&module.entries, 32),
        Ok(())
    );
    assert_eq!(
        crate::capacity::validate_entries(&module.entries, 47),
        Ok(())
    );
}

#[test]
fn zero_shared_and_exact_profile_boundary() {
    let plain = ct_codegen_spirv::translate_module(
        ".version 8.0 .target sm_52 .address_size 64 .entry plain(){ret;}",
    )
    .unwrap();
    assert_eq!(crate::capacity::validate_entries(&plain.entries, 0), Ok(()));
    let full = ct_codegen_spirv::translate_module(".version 8.0 .target sm_52 .address_size 64 .entry a(){.shared .align 16 .b8 x[16384];ret;} .entry b(){.shared .align 16 .b8 x[16384];ret;}").unwrap();
    assert_eq!(
        crate::capacity::validate_entries(&full.entries, 16383),
        Err(UNSUPPORTED)
    );
    assert_eq!(
        crate::capacity::validate_entries(&full.entries, 16384),
        Ok(())
    );
}

#[test]
fn rejected_capacity_never_calls_native_creator() {
    let module = ct_codegen_spirv::translate_module(
        ".version 8.0 .target sm_52 .address_size 64 .entry a(){.shared .align 16 .b8 x[32];ret;}",
    )
    .unwrap();
    for (native, expected, called) in [(31, Err(UNSUPPORTED), false), (32, Ok(7), true)] {
        let attempted = std::cell::Cell::new(false);
        let result = crate::capacity::create(&module.entries, native, || {
            attempted.set(true);
            Ok(7)
        });
        assert_eq!(result, expected);
        assert_eq!(attempted.get(), called);
    }
    assert_eq!(
        crate::capacity::create::<()>(&module.entries, 32, || Err(777)),
        Err(777)
    );
}

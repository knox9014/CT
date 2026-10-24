use ct_ptx::{parse_module, GlobalStorage, InstructionKind, Value};
fn source(globals: &str, body: &str) -> String {
    format!(".version 8.0\n.target sm_52\n.address_size 64\n{globals}\n.visible .entry test() {{ .reg .b32 %r<2>; {body} ret; }}")
}
#[test]
fn stored_global_u32_profile() {
    for (initializer, want) in [
        ("", 0),
        (" = 7", 7),
        (" = -1", u32::MAX),
        (" = 0xffffffff", u32::MAX),
    ] {
        let m = parse_module(&source(
            &format!(".visible .global .align 4 .u32 value{initializer};"),
            "ld.global.u32 %r1, [value];",
        ))
        .unwrap();
        assert_eq!(
            m.globals[0].storage,
            GlobalStorage::MutableU32 { initializer: want }
        );
        assert_eq!(m.kernels[0].globals, m.globals);
    }
    let decls = (0..256)
        .map(|i| format!(".global .align 4 .u32 g{i};"))
        .collect::<String>();
    assert!(parse_module(&source(&decls, "")).is_ok());
    assert!(parse_module(&source(&(decls + ".global .align 4 .u32 too_many;"), "")).is_err());
    for g in [
        ".global .align 4 .u32 test;",
        ".global .align 4 .u32 x; .global .align 4 .u32 x;",
        ".global .align 4 .u32 x[2];",
    ] {
        assert!(parse_module(&source(g, "")).is_err());
    }
}
#[test]
fn global_volatile_address_forms() {
    let m = parse_module(&source(
        ".global .align 4 .u32 g=7;",
        "ld.volatile.global.u32 %r1, [g]; st.volatile.global.u32 [g], %r1;",
    ))
    .unwrap();
    assert!(
        matches!(&m.kernels[0].blocks[0].instructions[0].kind,InstructionKind::Load{address:Value::Global(n),volatile:true,..} if n=="g")
    );
    for body in [
        "ld.global.u32 %r1, [g+4];",
        "ld.global.s32 %r1, [g];",
        "st.global.b32 [g], 1;",
        "mov.u64 %r1, g;",
        "ld.global.u64 %r1, [g];",
    ] {
        assert!(parse_module(&source(".global .align 4 .u32 g;", body)).is_err());
    }
}
#[test]
fn legacy_global_metadata_stays_unsupported() {
    let m = parse_module(&source(".global .align 8 .u64 old=7;", "")).unwrap();
    assert_eq!(m.globals[0].storage, GlobalStorage::Unsupported);
    assert!(
        parse_module(&source(
            ".global .align 8 .u64 old=7;",
            "ld.global.u32 %r1, [old];"
        ))
        .unwrap_err()
        .unsupported
    );
}

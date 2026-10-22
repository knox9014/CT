use ct_ptx::{parse, parse_module, ParamKind};
const HEADER: &str = ".version 7.0\n.target sm_50\n.address_size 64\n";
const ENTRY: &str =
    ".visible .entry first(.param .u32 value) { .reg .u32 %r; ld.param.u32 %r,[value]; ret; }\n";

#[test]
fn parses_all_entries_with_independent_scopes_and_abi() {
    let source = format!(
        "{HEADER}{ENTRY}{}",
        ENTRY.replace("first", "second").replace(".u32", ".f32")
    );
    let module = parse_module(&source).unwrap();
    assert_eq!(module.kernels.len(), 2);
    assert_eq!(module.profile.major, 7);
    assert_eq!(module.kernels[0].params[0].kind, ParamKind::U32);
    assert_eq!(module.kernels[1].params[0].kind, ParamKind::F32);
    assert_eq!(module.kernels[0].registers.len(), 1);
    assert_eq!(module.kernels[1].registers.len(), 1);
    assert!(parse(&source).unwrap_err().unsupported);
}

#[test]
fn rejects_duplicate_colliding_and_invalid_later_entries() {
    assert!(
        !parse_module(&format!("{HEADER}{ENTRY}{ENTRY}"))
            .unwrap_err()
            .unsupported
    );
    let global = ".global .align 8 .u64 first;\n";
    assert!(parse_module(&format!("{HEADER}{global}{ENTRY}")).is_err());
    for second in [
        ".visible .entry second(){",
        ".visible .entry second(){ bar.sync 0; ret; }",
        ".func ignored(){ret;}",
    ] {
        let error = parse_module(&format!("{HEADER}{ENTRY}\n{second}")).unwrap_err();
        assert!(error.line >= 5, "line {}", error.line);
    }
}

#[test]
fn bounds_entries_and_keeps_unused_global_validation() {
    assert!(parse_module(HEADER).is_err());
    let mut source = HEADER.to_owned();
    for n in 0..32 {
        source.push_str(&ENTRY.replace("first", &format!("entry_{n}")));
    }
    assert_eq!(parse_module(&source).unwrap().kernels.len(), 32);
    source.push_str(&ENTRY.replace("first", "entry_32"));
    assert!(parse_module(&source).unwrap_err().unsupported);
    let source = format!(
        "{HEADER}.global .align 8 .u64 ignored = 1;\n{ENTRY}{}",
        ENTRY.replace("first", "second")
    );
    assert_eq!(parse_module(&source).unwrap().kernels.len(), 2);
}
#[test]
fn static_nvcc_entry_is_module_local_and_does_not_enable_device_linking() {
    let local = ".version 8.0 .target sm_52 .address_size 64 .entry same(){ ret; }";
    let module = ct_ptx::parse_module(local).unwrap();
    assert_eq!(module.kernels.len(), 1);
    assert_eq!(module.kernels[0].name, "same");
    let mixed = format!("{local} .visible .entry other(){{ret;}}");
    assert_eq!(ct_ptx::parse_module(&mixed).unwrap().kernels.len(), 2);
    assert!(ct_ptx::parse_module(&format!("{local} .entry same(){{ret;}}")).is_err());
    for prefix in [".extern ", ".weak ", ".visible .extern "] {
        assert!(
            ct_ptx::parse_module(&local.replace(".entry", &format!("{prefix}.entry"))).is_err()
        );
    }
}

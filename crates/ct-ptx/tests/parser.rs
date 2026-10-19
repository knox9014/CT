use ct_ptx::{parse, ParamKind};
const SOURCE: &str = include_str!("../../../tests/fixtures/vector_add.ptx");

#[test]
fn leading_zero_integer_is_octal_not_decimal() {
    let s = SOURCE.replace("mov.u32 %r3, %tid.x;", "mov.u32 %r3, 010;");
    let k = parse(&s).unwrap();
    let found = k
        .blocks
        .iter()
        .flat_map(|b| &b.instructions)
        .find_map(|i| {
            if let ct_ptx::InstructionKind::Compute { dst, args, .. } = &i.kind {
                if dst == "%r3" {
                    return Some(args[0].clone());
                }
            }
            None
        })
        .unwrap();
    assert!(matches!(found, ct_ptx::Value::Bits(ct_ptx::Ty::U32, 8)));
    assert!(parse(&s.replace("010;", "08;")).is_err());
    let offset = parse(&SOURCE.replace("[%rd4]", "[%rd4+0104]")).unwrap();
    assert!(offset
        .blocks
        .iter()
        .flat_map(|b| &b.instructions)
        .any(|i| { matches!(i.kind, ct_ptx::InstructionKind::Load { offset: 68, .. }) }));
    assert!(parse(&SOURCE.replace("[%rd4]", "[%rd4+08]")).is_err());
}

#[test]
fn rejects_invalid_identifier_and_reserved_special_register_declarations() {
    assert!(parse(&SOURCE.replace("vector_add", ".bad_name")).is_err());
    assert!(parse(".version 7.0 .target sm_50 .address_size 64 .visible .entry k() { .reg .u32 %tid.x; ret; }").is_err());
}

#[test]
fn parses_semantics_independent_of_kernel_and_register_names() {
    let k = parse(SOURCE).expect("valid profile");
    assert_eq!(k.name, "vector_add");
    assert_eq!(k.params.len(), 4);
    assert_eq!(k.params[0].kind, ParamKind::Pointer);
    assert_eq!(k.params[3].kind, ParamKind::U32);
    let renamed = SOURCE
        .replace("vector_add", "unrelated_kernel")
        .replace("%rd", "%address");
    assert_eq!(parse(&renamed).unwrap().name, "unrelated_kernel");
}
#[test]
fn rejects_unknown_modifiers_bad_types_and_uninitialized_registers() {
    for s in [
        SOURCE.replace("add.rn.f32", "add.rz.f32"),
        SOURCE.replace("%f0, %f1", "%r0, %f1"),
        SOURCE.replace("ld.global.f32 %f1, [%rd5];", ""),
        SOURCE.replace(".address_size 64", ".address_size 32"),
        SOURCE.replace("bra DONE", "bra MISSING"),
        SOURCE.replace(".reg .f32 %f<3>;", ".reg .f32 %f<3>; .pragma unknown;"),
    ] {
        assert!(parse(&s).is_err());
    }
}
#[test]
fn rejects_assignment_missing_on_one_branch() {
    let s = SOURCE.replace(
        "ld.global.f32 %f1, [%rd5];",
        "@%p0 bra SKIP; ld.global.f32 %f1, [%rd5]; SKIP:",
    );
    assert!(parse(&s).is_err());
}
#[test]
fn validates_loop_carried_values_and_rejects_missing_initial_accumulator() {
    let s = include_str!("../../../tests/fixtures/matmul.ptx");
    assert_eq!(parse(s).unwrap().name, "matmul");
    assert!(parse(&s.replace("mov.f32 %f0, 0f00000000;", "")).is_err());
    assert!(parse(include_str!("../../../tests/fixtures/saxpy.ptx")).is_ok());
    assert!(parse(include_str!("../../../tests/fixtures/relu.ptx")).is_ok());
}

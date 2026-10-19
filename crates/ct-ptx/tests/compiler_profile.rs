use ct_ptx::{parse, ParamKind};
const BASE: &str = include_str!("../../../tests/fixtures/vector_add.ptx");

fn compiler_shape() -> String {
    BASE.replace(".version 7.0", ".version 8.0")
        .replace("sm_50", "sm_52")
        .replace(".ptr .global .align 4 ", "")
        .replace("mad.lo.u32", "mad.lo.s32")
        .replace("setp.ge.u32", "setp.ge.s32")
        .replace("mul.wide.u32", "mul.wide.s32")
        .replace("add.u64", "add.s64")
        .replace(
            "ld.param.u64 %rd1, [a];",
            "ld.param.u64 %rd1, [a]; cvta.to.global.u64 %rd1, %rd1;",
        )
}

#[test]
fn rejects_ambiguous_u64_and_accepts_proven_pointer_parameters() {
    let mut text = compiler_shape();
    // Use single-definition input registers; all their uses are explicit address conversions.
    text = text
        .replace(".b64 %rd<7>", ".b64 %rd<10>")
        .replace(
            "ld.param.u64 %rd1, [a]; cvta.to.global.u64 %rd1, %rd1;",
            "ld.param.u64 %rd7, [a]; cvta.to.global.u64 %rd1, %rd7;",
        )
        .replace(
            "ld.param.u64 %rd2, [b];",
            "ld.param.u64 %rd8, [b]; cvta.to.global.u64 %rd2, %rd8;",
        )
        .replace(
            "ld.param.u64 %rd3, [c];",
            "ld.param.u64 %rd9, [c]; cvta.to.global.u64 %rd3, %rd9;",
        );
    assert_eq!(parse(&text).unwrap().params[0].kind, ParamKind::Pointer);
    assert!(parse(&compiler_shape()).is_err());
    assert!(parse(&text.replace("cvta.to.global.u64 %rd1, %rd7;", "mov.u64 %rd1, %rd7;")).is_err());
    assert!(parse(&text.replace(
        "cvta.to.global.u64 %rd1, %rd7;",
        "cvta.to.global.u64 %rd1, %rd7; mov.u64 %rd7, 0;"
    ))
    .is_err());
}

#[test]
fn validates_unused_globals_but_rejects_references_and_malformed_initializers() {
    let prefix =
        ".global .align 8 .u64 unused_scalar = 1; .global .align 8 .b8 unused_array[2] = {1, 0};";
    let text = BASE.replace(".visible .entry", &format!("{prefix} .visible .entry"));
    assert!(parse(&text).is_ok());
    assert!(parse(&text.replace("%rd1, [a]", "%rd1, [unused_scalar]")).is_err());
    for invalid in ["{256, 0}", "{1}", "{1, unknown}"] {
        assert!(parse(&text.replace("{1, 0}", invalid)).is_err());
    }
    assert!(parse(&text.replace("unused_scalar = 1", "unused_scalar = unknown")).is_err());
    assert!(parse(&text.replace("unused_array[2]", "unused_array[0]")).is_err());
}

#[test]
fn accepts_u64_equality_for_signed_wide_result_checks() {
    let text = BASE.replace("add.rn.f32 %f2, %f0, %f1;", "mul.wide.s32 %rd0, 0xffffffff, 4; setp.eq.u64 %p0, %rd0, 0xfffffffffffffffc; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;");
    assert!(parse(&text).is_ok());
}

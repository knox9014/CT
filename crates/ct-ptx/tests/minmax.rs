fn source(body: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry clamp() {{ .reg .b32 %r; .reg .b64 %d; {body} ret; }}")
}

#[test]
fn minmax_and_signed_unary_accept_declared_widths() {
    for kind in ["u32", "s32", "u64", "s64"] {
        let reg = if kind.ends_with("32") { "%r" } else { "%d" };
        for op in ["min", "max"] {
            assert!(ct_ptx::parse(&source(&format!("{op}.{kind} {reg},1,2;"))).is_ok());
        }
        if kind.starts_with('s') {
            for op in ["abs", "neg"] {
                assert!(ct_ptx::parse(&source(&format!("{op}.{kind} {reg},1;"))).is_ok());
            }
        }
    }
}

#[test]
fn minmax_unary_reject_bad_types_arities_and_modifiers() {
    for body in [
        "min.s64 %r,1,2;",
        "max.u32 %d,1,2;",
        "abs.s64 %d,1,2;",
        "neg.s32 %r;",
        "min.u64 %d,1;",
        "max.u64 %d,1,2,3;",
        "abs.u32 %r,1;",
        "neg.u64 %d,1;",
        "min.relu.s32 %r,1,2;",
        "min.u16 %r,1,2;",
        "abs.f32 %r,0f3f800000;",
        "abs.s64 %d,%d;",
    ] {
        assert!(ct_ptx::parse(&source(body)).is_err(), "{body}");
    }
}

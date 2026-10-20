fn source(body: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry compare() {{ .reg .b32 %r; .reg .b64 %d; .reg .pred %p; {body} ret; }}")
}

#[test]
fn integer_predicates_and_select_accept_supported_widths() {
    for kind in ["u32", "s32", "u64", "s64"] {
        let reg = if kind.ends_with("32") { "%r" } else { "%d" };
        for relation in ["eq", "ne", "lt", "le", "gt", "ge"] {
            let text = source(&format!(
                "setp.{relation}.{kind} %p,1,2; selp.{kind} {reg},1,2,%p;"
            ));
            assert!(ct_ptx::parse(&text).is_ok(), "{text}");
        }
    }
    for (kind, reg) in [("b32", "%r"), ("b64", "%d")] {
        assert!(ct_ptx::parse(&source(&format!(
            "setp.eq.u32 %p,1,1; selp.{kind} {reg},1,2,%p;"
        )))
        .is_ok());
    }
}

#[test]
fn integer_predicates_reject_bad_widths_and_predicates() {
    for body in [
        "setp.gt.u64 %r,1,2;",
        "setp.ne.s64 %p,1;",
        "setp.le.s64 %p,1,2,3;",
        "setp.gt.u16 %p,1,2;",
        "setp.eq.and.u32 %p,1,2,%p;",
        "setp.gt.ftz.s64 %p,1,2;",
        "setp.eq.b64 %p,1,2;",
        "selp.u64 %r,1,2,%p;",
        "setp.eq.u32 %p,1,1; selp.u64 %d,1,2,1;",
        "selp.s64 %d,1,2,%p;",
    ] {
        assert!(ct_ptx::parse(&source(body)).is_err(), "{body}");
    }
}

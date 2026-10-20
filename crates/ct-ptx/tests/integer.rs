use ct_ptx::{InstructionKind, Op, Ty};
fn source(body: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry bits() {{ .reg .b32 %r<3>; .reg .b64 %d<3>; {body} ret; }}")
}
#[test]
fn converts_all_signed_unsigned_width_pairs_with_source_semantics() {
    for dst in ["s32", "u32", "s64", "u64"] {
        for src in ["s32", "u32", "s64", "u64"] {
            let target = if dst.ends_with("32") {
                Ty::U32
            } else {
                Ty::U64
            };
            let input = if src.ends_with("32") {
                Ty::U32
            } else {
                Ty::U64
            };
            let reg = if target == Ty::U32 { "%r0" } else { "%d0" };
            let k = ct_ptx::parse(&source(&format!("cvt.{dst}.{src} {reg}, 1;"))).unwrap();
            assert!(
                matches!(&k.blocks[0].instructions[0].kind, InstructionKind::Compute {op:Op::Convert{to,signed},ty,..} if *to==target && *ty==input && *signed==src.starts_with('s'))
            );
        }
    }
}
#[test]
fn accepts_bit_operations_and_requires_u32_shift_counts_for_both_widths() {
    for width in [32, 64] {
        let r = if width == 32 { "%r0" } else { "%d0" };
        for op in ["and", "or", "xor"] {
            assert!(ct_ptx::parse(&source(&format!("{op}.b{width} {r}, 1, 2;"))).is_ok());
        }
        assert!(ct_ptx::parse(&source(&format!("not.b{width} {r}, 1;"))).is_ok());
        for op in [
            format!("shl.b{width}"),
            format!("shr.b{width}"),
            format!("shr.u{width}"),
            format!("shr.s{width}"),
        ] {
            assert!(ct_ptx::parse(&source(&format!("mov.u32 %r1, 65; {op} {r}, 1, %r1;"))).is_ok());
            assert!(ct_ptx::parse(&source(&format!("mov.u64 %d1, 1; {op} {r}, 1, %d1;"))).is_err());
        }
    }
}
#[test]
fn rejects_bad_conversions_modifiers_and_uninitialized_operands() {
    for body in [
        "cvt.u32.u64 %d0, 1;",
        "cvt.u64.u32 %r0, 1;",
        "cvt.u32.u64 %r0, %d1;",
        "cvt.sat.s32.u32 %r0, 1;",
        "cvt.u16.u32 %r0, 1;",
        "cvt.u32.f32 %r0, 0f3f800000;",
        "cvt.u32.b32 %r0, 1;",
        "shl.b64 %d0, 1, 0x100000000;",
        "and.b32 %r0, 1;",
        "not.pred %r0, 1;",
    ] {
        assert!(ct_ptx::parse(&source(body)).is_err(), "{body}");
    }
}

use ct_ptx::{InstructionKind, Op, Ty};

fn source(body: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry calc() {{ .reg .b32 %r; .reg .b64 %d; {body} ret; }}")
}

#[test]
fn modular_arithmetic_accepts_all_width_and_signedness_spellings() {
    for (name, expected, count) in [
        ("add", Op::Add, 2),
        ("sub", Op::Sub, 2),
        ("mul.lo", Op::Mul, 2),
        ("mad.lo", Op::Mad, 3),
    ] {
        for kind in ["u32", "s32", "u64", "s64"] {
            let (reg, ty) = if kind.ends_with("32") {
                ("%r", Ty::U32)
            } else {
                ("%d", Ty::U64)
            };
            let operands = if count == 3 { "1, 2, 3" } else { "1, 2" };
            let kernel =
                ct_ptx::parse(&source(&format!("{name}.{kind} {reg}, {operands};"))).unwrap();
            assert!(
                matches!(&kernel.blocks[0].instructions[0].kind, InstructionKind::Compute {op,ty:t,args,..} if *op==expected && *t==ty && args.len()==count)
            );
        }
    }
}

#[test]
fn modular_arithmetic_rejects_width_arity_and_modifier_mismatches() {
    for body in [
        "add.s64 %r, 1, 2;",
        "sub.s32 %d, 1, 2;",
        "mul.lo.u64 %d, 1;",
        "mad.lo.s64 %d, 1, 2;",
        "mad.lo.u64 %d, 1, 2, 3, 4;",
        "add.sat.s32 %r, 1, 2;",
        "mad.hi.u64 %d, 1, 2, 3;",
        "mul.lo.u16 %r, 1, 2;",
        "add.cc.u64 %d, 1, 2;",
        "mad.lo.u64 %d, %d, 1, 2;",
    ] {
        assert!(ct_ptx::parse(&source(body)).is_err(), "{body}");
    }
}

use ct_ptx::{InstructionKind, Ty, Value};

fn source(body: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry constants() {{ .reg .b32 %r; .reg .b64 %d; .reg .pred %p; .reg .f32 %f; {body} ret; }}")
}

#[test]
fn signed_literals_preserve_exact_bits_at_declared_operand_width() {
    for (width, ty, reg) in [(32, Ty::U32, "%r"), (64, Ty::U64, "%d")] {
        let mask = if width == 32 {
            u32::MAX as u64
        } else {
            u64::MAX
        };
        let top = 1u64 << (width - 1);
        for (literal, expected) in [
            ("-1".to_owned(), mask),
            ("-0x1".to_owned(), mask),
            ("-01".to_owned(), mask),
            (format!("-{top}"), top),
            (format!("-0x{top:x}"), top),
            ("-0".to_owned(), 0),
            ("+0".to_owned(), 0),
            ("+01".to_owned(), 1),
            (format!("+0x{mask:x}"), mask),
        ] {
            let k = ct_ptx::parse(&source(&format!("mov.s{width} {reg},{literal};"))).unwrap();
            assert!(
                matches!(&k.blocks[0].instructions[0].kind,InstructionKind::Compute{args,..} if matches!(&args[0],Value::Bits(t,bits) if *t==ty && *bits==expected)),
                "{literal}"
            );
        }
    }
    assert!(ct_ptx::parse(&source("add.u32 %r,1,-1; cvt.u64.s32 %d,-2147483648; shl.b64 %d,%d,-1; setp.lt.s64 %p,%d,-1; selp.b64 %d,-1,+0,%p; st.global.u64 [%d],-1;")).is_ok());
}

#[test]
fn signed_literals_reject_range_errors_and_other_expressions() {
    for body in [
        "mov.s32 %r,-2147483649;",
        "mov.s64 %d,-9223372036854775809;",
        "mov.u32 %r,+4294967296;",
        "mov.u64 %d,+18446744073709551616;",
        "mov.u32 %r,-08;",
        "mov.u32 %r,--1;",
        "mov.u32 %r,+-1;",
        "mov.u32 %r,1+2;",
        "mov.u32 %r,(-1);",
        "mov.u32 %r,-1U;",
        "mov.u32 %r,+%tid.x;",
        "mov.u32 %r,-%r;",
        "mov.f32 %f,-0f3f800000;",
        "mov.f32 %f,+1;",
        "selp.u32 %r,1,2,-1;",
        "mov.u64 %d,0; ld.global.u32 %r,[%d-4];",
        "shl.b64 %d,1,-2147483649;",
    ] {
        assert!(ct_ptx::parse(&source(body)).is_err(), "{body}");
    }
}

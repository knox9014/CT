use ct_ptx::{InstructionKind, ParamKind, Ty};
fn source(width: u32, suffix: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry memory(.param .u64 .ptr .global .align {} p, .param .{} value) {{ .reg .s{} %r; .reg .b64 %a; ld.param.u64 %a,[p]; ld.param.{} %r,[value]; ld.global.{} %r,[%a+{}]; st.global.{} [%a],%r; ret; }}",width/8,if width==64 {"b64"}else{"s32"},width,if width==64 {"s64"}else{"b32"},suffix,width/8,suffix)
}
#[test]
fn preserves_integer_memory_types_and_explicit_scalar_abi() {
    for (width, t) in [(32, Ty::U32), (64, Ty::U64)] {
        for prefix in ["b", "u", "s"] {
            let k = ct_ptx::parse(&source(width, &format!("{prefix}{width}"))).unwrap();
            assert_eq!(k.params[0].alignment, width / 8);
            assert_eq!(
                k.params[1].kind,
                if width == 64 {
                    ParamKind::U64
                } else {
                    ParamKind::U32
                }
            );
            assert!(
                matches!(k.blocks[0].instructions[2].kind,InstructionKind::Load{ty,..} if ty==t)
            );
            assert!(
                matches!(k.blocks[0].instructions[3].kind,InstructionKind::Store{ty,..} if ty==t)
            );
        }
    }
}
#[test]
fn rejects_misaligned_static_offsets_and_weak_wide_pointer_contracts() {
    let text = source(64, "u64");
    for bad in [
        text.replace("%a+8", "%a+4"),
        text.replace(".align 8", ".align 4"),
        text.replace(".align 8", ".align 16"),
        text.replace("ld.global.u64 %r", "ld.global.f32 %r"),
        text.replace(".param .b64 value", ".param .u64 value"),
    ] {
        assert!(ct_ptx::parse(&bad).is_err());
    }
}

#[test]
fn accepts_wide_registers_without_widening_memory_types() {
    let text = include_str!("../../../tests/fixtures/relaxed_memory.ptx");
    let k = ct_ptx::parse(text).unwrap();
    assert!(k.blocks[0].instructions.iter().any(|i| matches!(
        &i.kind, InstructionKind::Load { ty: Ty::U32, dst, .. } if k.registers[dst] == Ty::U64
    )));
    assert!(k.blocks[0].instructions.iter().any(|i| matches!(
        &i.kind, InstructionKind::Store { ty: Ty::U32, value: ct_ptx::Value::Reg(r), .. } if k.registers[r] == Ty::U64
    )));
}

#[test]
fn relaxed_memory_does_not_relax_other_types_or_instructions() {
    let text = include_str!("../../../tests/fixtures/relaxed_memory.ptx");
    for bad in [
        text.replace("ld.global.u32 %x", "ld.global.s32 %x"),
        text.replace("ld.global.u32 %x", "ld.global.f32 %x"),
        text.replace("ld.param.b64 %y, [wide]", "ld.param.b32 %y, [wide]"),
        text.replace("st.global.b32 [%b+8], %y", "st.global.f32 [%b+8], %y"),
        text.replace(
            "st.global.b32 [%b+8], %y",
            "st.global.b32 [%b+8], 0x100000000",
        ),
    ] {
        assert!(ct_ptx::parse(&bad).is_err());
    }
}

#[test]
fn rejects_memory_operands_narrower_than_the_access() {
    let text = ".version 8.0 .target sm_52 .address_size 64 .entry narrow(.param .u64 .ptr .global .align 8 p) { .reg .b64 %a; .reg .b32 %x; ld.param.u64 %a,[p]; mov.u32 %x,1; ld.global.u32 %x,[%a]; st.global.u32 [%a],%x; ret; }";
    ct_ptx::parse(text).unwrap();
    for bad in [
        text.replace("ld.global.u32", "ld.global.u64"),
        text.replace("st.global.u32", "st.global.u64"),
    ] {
        let error = ct_ptx::parse(&bad).unwrap_err();
        assert!(matches!(
            error.message,
            "invalid destination register/type" | "register type mismatch"
        ));
    }
}

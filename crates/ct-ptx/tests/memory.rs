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
        text.replace("ld.global.u64 %r", "ld.global.u32 %r"),
        text.replace(".param .b64 value", ".param .u64 value"),
    ] {
        assert!(ct_ptx::parse(&bad).is_err());
    }
}

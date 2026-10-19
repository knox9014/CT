use ct_codegen_spirv::translate;
use ct_ptx::ParamKind;
const SOURCE: &str = include_str!("../../../tests/fixtures/vector_add.ptx");
#[test]
fn preserves_entry_and_argument_abi_and_does_not_ignore_arithmetic_changes() {
    let first = translate(SOURCE).unwrap();
    assert_eq!(first.entry, "vector_add");
    assert_eq!(first.params[0].kind, ParamKind::Pointer);
    assert_eq!(&first.spirv[..4], &[3, 2, 35, 7]);
    let renamed = translate(&SOURCE.replace("vector_add", "renamed_entry")).unwrap();
    assert_eq!(renamed.entry, "renamed_entry");
    let subtract = translate(&SOURCE.replace("add.rn.f32", "sub.rn.f32")).unwrap();
    assert_ne!(first.spirv, subtract.spirv);
}

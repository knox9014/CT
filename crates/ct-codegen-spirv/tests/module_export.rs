use ct_codegen_spirv::translate_module;

#[test]
fn kernel_float_contraction_is_disabled_without_shader_decorations() {
    let module = translate_module(include_str!("../../../tests/fixtures/multi_entry.ptx")).unwrap();
    let words: Vec<_> = module
        .spirv
        .chunks_exact(4)
        .map(|w| u32::from_le_bytes(w.try_into().unwrap()))
        .collect();
    let mut i = 5;
    let mut entries = Vec::new();
    let mut modes = Vec::new();
    while i < words.len() {
        let count = (words[i] >> 16) as usize;
        let opcode = words[i] & 65535;
        let args = &words[i + 1..i + count];
        if opcode == 21 {
            assert_eq!(args[2], 0, "Kernel integer types must have Signedness 0");
        }
        if opcode == 15 {
            entries.push(args[1]);
        }
        if opcode == 16 && args[1] == 31 {
            modes.push(args[0]);
        }
        assert!(
            !(opcode == 71 && args[1] == 42),
            "NoContraction requires Shader"
        );
        i += count;
    }
    assert_eq!(
        entries, modes,
        "every Kernel entry must disable contraction"
    );
}

#[test]
fn module_export_preserves_both_entry_abis() {
    let fixture = include_str!("../../../tests/fixtures/multi_entry.ptx");
    let second = fixture.find(".visible .entry kernel_sub").unwrap();
    let third = fixture.find(".visible .entry kernel_fill").unwrap();
    let source = format!("{}{}", &fixture[..second], &fixture[third..]);
    let module = translate_module(&source).unwrap();
    assert_eq!(module.entries.len(), 2);
    assert_ne!(module.entries[0].entry, module.entries[1].entry);
    let kinds = |entry: &ct_codegen_spirv::CompiledEntry| {
        entry.params.iter().map(|p| p.kind).collect::<Vec<_>>()
    };
    assert_ne!(kinds(&module.entries[0]), kinds(&module.entries[1]));
    assert_eq!(&module.spirv[..4], &[3, 2, 35, 7]);
}

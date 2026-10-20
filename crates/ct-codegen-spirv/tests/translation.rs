use ct_codegen_spirv::translate;
use ct_ptx::ParamKind;
const SOURCE: &str = include_str!("../../../tests/fixtures/vector_add.ptx");

fn instructions(bytes: &[u8]) -> Vec<(u32, Vec<u32>)> {
    let words: Vec<_> = bytes
        .chunks_exact(4)
        .map(|b| u32::from_le_bytes(b.try_into().unwrap()))
        .collect();
    let mut offset = 5;
    let mut out = Vec::new();
    while offset < words.len() {
        let size = (words[offset] >> 16) as usize;
        assert!(size > 0 && offset + size <= words.len());
        out.push((
            words[offset] & 65535,
            words[offset + 1..offset + size].to_vec(),
        ));
        offset += size;
    }
    out
}

#[test]
fn extracts_each_axis_and_shares_builtin_vectors_across_entries() {
    let mut body = String::new();
    for name in ["nctaid", "ntid", "ctaid", "tid"] {
        for axis in ["x", "y", "z"] {
            body.push_str(&format!("mov.u32 %r, %{name}.{axis};\n"));
        }
    }
    let entry = format!(".visible .entry first() {{ .reg .u32 %r; {body} ret; }}");
    let text = format!(
        ".version 7.0 .target sm_50 .address_size 64 {entry} {}",
        entry.replace("first", "second")
    );
    let compiled = ct_codegen_spirv::translate_module(&text).unwrap();
    let ops = instructions(&compiled.spirv);
    let axes: Vec<_> = ops
        .iter()
        .filter(|(op, _)| *op == 81)
        .map(|(_, a)| a[3])
        .collect();
    assert_eq!(axes, [0, 1, 2].repeat(8));
    let decorations: Vec<_> = ops
        .iter()
        .filter(|(op, a)| *op == 71 && a[1] == 11)
        .map(|(_, a)| a[2])
        .collect();
    assert_eq!(decorations, vec![24, 25, 26, 27]);
    assert_eq!(
        ops.iter().filter(|(op, a)| *op == 59 && a[2] == 1).count(),
        4
    );
}

#[test]
fn emits_one_module_with_distinct_functions_and_shared_signatures() {
    let body = &SOURCE[SOURCE.find(".visible").unwrap()..];
    let source = format!(
        "{SOURCE}{}",
        body.replace("vector_add", "other")
            .replace("add.rn.f32", "sub.rn.f32")
    );
    let compiled = ct_codegen_spirv::translate_module(&source).unwrap();
    assert_eq!(compiled.entries.len(), 2);
    assert_eq!(compiled.entries[0].entry, "vector_add");
    assert_eq!(compiled.entries[1].entry, "other");
    let insts = instructions(&compiled.spirv);
    assert_eq!(
        insts.iter().filter(|(op, _)| *op == 33).count(),
        1,
        "reuse same function type"
    );
    let functions: Vec<_> = insts
        .iter()
        .filter(|(op, _)| *op == 54)
        .map(|(_, v)| v[1])
        .collect();
    assert_eq!(functions.len(), 2);
    assert_ne!(functions[0], functions[1]);
    assert_eq!(
        insts
            .iter()
            .filter(|(op, _)| *op == 15)
            .map(|(_, v)| v[1])
            .collect::<Vec<_>>(),
        functions
    );
    let vars: Vec<_> = insts
        .iter()
        .filter(|(op, v)| *op == 59 && v[2] == 7)
        .map(|(_, v)| v[1])
        .collect();
    assert_eq!(
        vars.len(),
        vars.iter().collect::<std::collections::BTreeSet<_>>().len()
    );
    assert!(translate(&source).err().unwrap().unsupported);
}

#[test]
fn keeps_distinct_signatures_and_entry_builtin_interfaces() {
    let source = format!("{SOURCE}\n.visible .entry no_builtin(.param .f32 scalar) {{ ret; }}");
    let compiled = ct_codegen_spirv::translate_module(&source).unwrap();
    assert_eq!(compiled.entries[1].params[0].kind, ParamKind::F32);
    let insts = instructions(&compiled.spirv);
    assert_eq!(insts.iter().filter(|(op, _)| *op == 33).count(), 2);
    let counts: Vec<_> = insts
        .iter()
        .filter(|(op, _)| *op == 15)
        .map(|(_, v)| {
            let bytes: Vec<_> = v[2..].iter().flat_map(|w| w.to_le_bytes()).collect();
            let name_bytes = bytes.iter().position(|b| *b == 0).unwrap() + 1;
            v.len() - 2 - name_bytes.div_ceil(4)
        })
        .collect();
    assert_eq!(counts, vec![3, 0]);
}
#[test]
fn compiled_profile_matches_parsed_source() {
    for text in [
        SOURCE.to_owned(),
        SOURCE.replace("7.0", "8.0").replace("sm_50", "sm_52"),
    ] {
        assert_eq!(
            translate(&text).unwrap().profile,
            ct_ptx::parse(&text).unwrap().profile
        );
    }
}
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

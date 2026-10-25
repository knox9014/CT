use ct_codegen_spirv::translate_module;
fn words(b: &[u8]) -> Vec<Vec<u32>> {
    let w: Vec<_> = b
        .chunks_exact(4)
        .map(|b| u32::from_le_bytes(b.try_into().unwrap()))
        .collect();
    let mut out = vec![];
    let mut i = 5;
    while i < w.len() {
        let n = (w[i] >> 16) as usize;
        out.push(w[i..i + n].to_vec());
        i += n;
    }
    out
}
fn src() -> String {
    ".version 8.0\n.target sm_52\n.address_size 64\n.global .align 4 .u32 g=7;\n.visible .entry first(.param .u32 n) { .reg .u32 %r; ld.volatile.global.u32 %r,[g]; ret; }\n.entry second(.param .u32 n) { st.global.u32 [g],9; ret; }".into()
}
#[test]
fn mixed_global_initializer_words() {
    let src=".version 8.0\n.target sm_52\n.address_size 64\n.global .align 4 .u32 g=7; .global .align 8 .u64 wide=0x1234567800000000; .entry test(){.reg .b64 %rd; ld.volatile.global.u64 %rd,[wide]; st.volatile.global.u64 [wide],%rd; ret;}";
    let c = translate_module(src).unwrap();
    assert_eq!(c.globals.len(), 2);
    let w = words(&c.spirv);
    assert!(w
        .iter()
        .any(|v| v[0] & 65535 == 43 && v.len() == 5 && v[3] == 0 && v[4] == 0x12345678));
    assert_eq!(
        w.iter().filter(|v| v[0] & 65535 == 59 && v[3] == 5).count(),
        2
    );
    assert!(w
        .iter()
        .any(|v| v[0] & 65535 == 61 && v.len() == 6 && v[5] == 8));
}
#[test]
fn global_storage_shared_across_entries() {
    let c = translate_module(&src()).unwrap();
    let w = words(&c.spirv);
    assert_eq!(c.globals.len(), 1);
    assert_eq!(
        w.iter().filter(|v| v[0] & 65535 == 59 && v[3] == 5).count(),
        1
    );
    assert!(w.iter().any(|v| v[0] & 65535 == 71 && v[2] == 41));
}
#[test]
fn global_does_not_add_parameters() {
    let c = translate_module(&src()).unwrap();
    assert!(c.entries.iter().all(|e| e.params.len() == 1));
    assert_eq!(
        words(&c.spirv)
            .iter()
            .filter(|v| v[0] & 65535 == 55)
            .count(),
        2
    );
}
#[test]
fn global_volatile_memory_operands() {
    let w = words(&translate_module(&src()).unwrap().spirv);
    assert!(w
        .iter()
        .any(|v| v[0] & 65535 == 61 && v.len() == 6 && v[4] == 3 && v[5] == 4));
    assert!(w
        .iter()
        .any(|v| v[0] & 65535 == 62 && v.len() == 5 && v[3] == 2 && v[4] == 4));
}

#[test]
fn unused_globals_have_explicit_host_access() {
    let compiled=translate_module(".version 8.0\n.target sm_52\n.address_size 64\n.global .align 4 .u32 unused; .entry test() { ret; }").unwrap();
    let w = words(&compiled.spirv);
    assert!(w.iter().any(|v| v[0] & 65535 == 17 && v[1] == 6187));
    assert!(w
        .iter()
        .any(|v| v[0] & 65535 == 71 && v[2] == 6188 && v[3] == 3));
}

use ct_ptx::{InstructionKind, Value};

fn source(operand: &str) -> String {
    format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry dimensions() {{ .reg .u32 %r; mov.u32 %r, {operand}; ret; }}")
}

#[test]
fn preserves_all_twelve_special_register_components() {
    for (name, kind) in [("nctaid", 24), ("ntid", 25), ("ctaid", 26), ("tid", 27)] {
        for (axis, component) in [("x", 0), ("y", 1), ("z", 2)] {
            let kernel = ct_ptx::parse(&source(&format!("%{name}.{axis}"))).unwrap();
            match &kernel.blocks[0].instructions[0].kind {
                InstructionKind::Compute { args, .. } => {
                    assert!(matches!(args[0], Value::Builtin(k, c) if k == kind && c == component));
                }
                _ => panic!("expected special register move"),
            }
        }
    }
}

#[test]
fn rejects_non_scalar_components_and_wrong_types() {
    for name in [
        "%tid.w",
        "%tid",
        "%tid.xy",
        "%ctaid.a",
        "%ntid.0",
        "%nctaid.X",
    ] {
        assert!(ct_ptx::parse(&source(name)).is_err());
    }
    assert!(ct_ptx::parse(&source("%tid.y").replace(".u32", ".u64")).is_err());
}

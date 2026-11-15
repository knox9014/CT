use ct_codegen_spirv::translate;
use ct_ptx::ParamKind;
const SOURCE: &str = include_str!("../../../tests/fixtures/vector_add.ptx");

#[test]
fn fma_uses_opencl_fused_instruction_and_retains_separate_arithmetic() {
    assert!(!instructions(&translate(SOURCE).unwrap().spirv)
        .iter()
        .any(|(op, _)| *op == 11));
    let source=".version 8.0 .target sm_52 .address_size 64 .entry fused(){.reg .f32 %f<6>;mov.f32 %f0,0f3f800001;mov.f32 %f1,0f3f7ffffe;mov.f32 %f2,0fbf800000;fma.rn.f32 %f3,%f0,%f1,%f2;mul.rn.f32 %f4,%f0,%f1;add.rn.f32 %f5,%f4,%f2;ret;}";
    let ops = instructions(&translate(source).unwrap().spirv);
    let imports: Vec<_> = ops.iter().filter(|(op, _)| *op == 11).collect();
    assert_eq!(imports.len(), 1);
    let bytes: Vec<_> = imports[0].1[1..]
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    assert_eq!(&bytes[..11], b"OpenCL.std\0");
    let fma: Vec<_> = ops.iter().filter(|(op, _)| *op == 12).collect();
    assert_eq!(fma.len(), 1);
    assert_eq!(fma[0].1.len(), 7);
    assert_eq!(fma[0].1[0], 5);
    assert_eq!(fma[0].1[2], imports[0].1[0]);
    assert_eq!(fma[0].1[3], 26);
    assert_eq!(ops.iter().filter(|(op, _)| *op == 133).count(), 1);
    assert_eq!(ops.iter().filter(|(op, _)| *op == 129).count(), 1);
    assert!(ops.iter().any(|(op, a)| *op == 16 && a[1] == 31));
}

#[test]
fn shared_arrays_have_workgroup_storage_and_distinct_per_entry_identity() {
    let text=".version 8.0 .target sm_52 .address_size 64 .entry first(){.reg .b32 %r; .shared .align 4 .b8 tile[512]; st.shared.u32 [tile],17; bar.sync 0; ld.shared.u32 %r,[tile]; ret;} .entry second(){.reg .f32 %f; .shared .align 4 .b8 tile[512]; st.shared.f32 [tile],0f3f800000; bar.sync 0; ld.shared.f32 %f,[tile]; ret;}";
    let ops = instructions(&ct_codegen_spirv::translate_module(text).unwrap().spirv);
    let objects: Vec<_> = ops
        .iter()
        .filter(|(op, a)| *op == 59 && a[2] == 4)
        .map(|(_, a)| a[1])
        .collect();
    assert_eq!(objects.len(), 2);
    assert_ne!(objects[0], objects[1]);
    for object in objects {
        assert_eq!(
            ops.iter()
                .filter(|(op, a)| *op == 65 && a[2] == object)
                .count(),
            2
        );
        assert!(ops
            .iter()
            .any(|(op, a)| *op == 71 && a == &vec![object, 44, 4]));
    }
    assert!(
        !ops.iter().any(|(op, _)| *op == 120),
        "shared offsets must not become physical global pointers"
    );
    assert_eq!(ops.iter().filter(|(op, _)| *op == 224).count(), 2);
    assert_eq!(
        ops.iter().filter(|(op, _)| *op == 124).count(),
        2,
        "F32 values use bitcasts around U32 shared storage"
    );
}

#[test]
fn selective_pointer_promotion_reaches_the_native_signature() {
    let source = ".version 8.0 .target sm_52 .address_size 64 .entry mixed(.param .u64 wide,.param .u64 narrow) { .reg .b64 %a; .reg .b64 %b; .reg .b64 %c; .reg .b64 %d; .reg .b64 %v; ld.param.u64 %a,[wide]; ld.param.u64 %b,[narrow]; cvta.to.global.u64 %c,%a; cvta.to.global.u64 %d,%b; ld.global.u32 %v,[%d]; st.global.u64 [%c],%v; ret; }";
    let compiled = translate(source).unwrap();
    assert_eq!(
        compiled
            .params
            .iter()
            .map(|p| p.alignment)
            .collect::<Vec<_>>(),
        [8, 4]
    );
    let params: Vec<_> = instructions(&compiled.spirv)
        .into_iter()
        .filter(|(op, _)| *op == 55)
        .map(|(_, a)| a[0])
        .collect();
    assert_eq!(params, [16, 8]);
}

#[test]
fn relaxed_memory_converts_registers_but_keeps_four_byte_accesses() {
    let text = include_str!("../../../tests/fixtures/relaxed_memory.ptx");
    let ops = instructions(&translate(text).unwrap().spirv);
    let loads: Vec<_> = ops
        .iter()
        .filter(|(op, a)| *op == 61 && a.len() == 5 && a[0] == 3)
        .collect();
    assert_eq!(loads.len(), 4);
    for (_, a) in loads {
        assert_eq!(a[4], 4, "memory alignment must remain four bytes");
        let wide = ops
            .iter()
            .find(|(op, b)| *op == 113 && b[0] == 4 && b[2] == a[1])
            .expect("U32 load must be zero-extended");
        assert!(ops
            .iter()
            .any(|(op, b)| *op == 62 && b.len() == 2 && b[1] == wide.1[1]));
    }
    let stores: Vec<_> = ops
        .iter()
        .filter(|(op, a)| *op == 62 && a.len() == 4 && a[3] == 4)
        .collect();
    assert_eq!(stores.len(), 3);
    for (_, a) in stores {
        let narrow = ops
            .iter()
            .find(|(op, b)| *op == 113 && b[0] == 3 && b[1] == a[1])
            .expect("U64 store source must be truncated");
        assert!(ops
            .iter()
            .any(|(op, b)| *op == 61 && b[0] == 4 && b[1] == narrow.1[2]));
    }
}

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
fn signed64_minmax_and_abs_use_typed_comparisons_and_modular_negation() {
    for op in ["min", "max", "abs", "neg"] {
        let args = if matches!(op, "min" | "max") {
            "%d,1"
        } else {
            "%d"
        };
        let text = format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry clamp(.param .b64 a) {{ .reg .b64 %d; ld.param.b64 %d,[a]; {op}.s64 %d,{args}; ret; }}");
        let insts = instructions(&translate(&text).unwrap().spirv);
        if op != "neg" {
            let cmp = insts.iter().find(|(code, _)| *code == 177).unwrap();
            assert!(insts
                .iter()
                .any(|(code, v)| matches!(code, 43 | 61) && v[0] == 4 && v[1] == cmp.1[2]));
            assert!(insts.iter().any(|(code, v)| *code == 169 && v[0] == 4));
        }
        if matches!(op, "abs" | "neg") {
            assert!(insts.iter().any(|(code, v)| *code == 130 && v[0] == 4));
        }
    }
}

#[test]
fn signed64_predicates_use_signed64_operands_and_integer_select() {
    for (relation, opcode) in [("lt", 177), ("le", 179), ("gt", 173), ("ge", 175)] {
        let text = format!(".version 7.0 .target sm_50 .address_size 64 .visible .entry compare(.param .b64 a) {{ .reg .b64 %d; .reg .pred %p; ld.param.b64 %d,[a]; setp.{relation}.s64 %p,%d,1; selp.b64 %d,%d,2,%p; ret; }}");
        let compiled = translate(&text).unwrap();
        let insts = instructions(&compiled.spirv);
        let cmp = insts.iter().find(|(op, _)| *op == opcode).unwrap();
        for operand in &cmp.1[2..] {
            assert!(
                insts
                    .iter()
                    .any(|(op, v)| matches!(op, 43 | 61) && v[0] == 4 && v[1] == *operand),
                "signed compare must retain the 64-bit Kernel operand width"
            );
        }
        assert!(insts.iter().any(|(op, v)| *op == 169 && v[0] == 4));
    }
}

#[test]
fn modular_mad_uses_declared_width_for_product_and_sum() {
    let source = ".version 7.0 .target sm_50 .address_size 64 .visible .entry calc(.param .b64 a) { .reg .b64 %d; ld.param.b64 %d,[a]; mad.lo.s64 %d,%d,0xffffffffffffffff,1; ret; }";
    let compiled = translate(source).unwrap();
    let insts = instructions(&compiled.spirv);
    let product = insts.iter().find(|(op, _)| *op == 132).unwrap();
    let sum = insts.iter().find(|(op, _)| *op == 128).unwrap();
    assert_eq!(product.1[0], 4, "product must be U64");
    assert_eq!(sum.1[0], 4, "sum must be U64");
    assert_eq!(sum.1[2], product.1[1]);
}

#[test]
fn typed_memory_and_scalar64_use_distinct_pointer_and_integer_signatures() {
    let text=".version 7.0 .target sm_50 .address_size 64 .visible .entry mem(.param .u64 .ptr .global .align 8 p,.param .b64 v) { .reg .b64 %a; .reg .s64 %x; ld.param.u64 %a,[p]; ld.param.s64 %x,[v]; st.global.u64 [%a],%x; ld.global.b64 %x,[%a+8]; ret; }";
    let compiled = translate(text).unwrap();
    assert_eq!(compiled.params[1].kind, ParamKind::U64);
    let ops = instructions(&compiled.spirv);
    let global64 = ops
        .iter()
        .find(|(op, a)| *op == 32 && a[1] == 5 && a[2] == 4)
        .unwrap()
        .1[0];
    assert!(ops.iter().any(|(op, a)| *op == 120 && a[0] == global64));
    assert!(ops
        .iter()
        .any(|(op, a)| *op == 61 && a[0] == 4 && a.len() == 5 && a[3..] == [2, 8]));
    assert!(ops
        .iter()
        .any(|(op, a)| *op == 62 && a.len() == 4 && a[2..] == [2, 8]));
    let params: Vec<_> = ops
        .iter()
        .filter(|(op, _)| *op == 55)
        .map(|(_, a)| a[0])
        .collect();
    assert_eq!(params, vec![global64, 4]);
}

#[test]
fn integer_conversion_uses_source_signedness_and_correct_result_width() {
    let text=".version 7.0 .target sm_50 .address_size 64 .visible .entry c() { .reg .b32 %r; .reg .b64 %d; mov.u32 %r, 0xffffffff; cvt.u64.s32 %d, %r; cvt.s64.u32 %d, %r; cvt.s32.s64 %r, %d; cvt.s32.u32 %r, %r; ret; }";
    let ops = instructions(&translate(text).unwrap().spirv);
    assert!(ops.iter().any(|(op, a)| *op == 114 && a[0] == 4));
    assert!(ops.iter().any(|(op, a)| *op == 113 && a[0] == 4));
    assert!(ops.iter().any(|(op, a)| *op == 113 && a[0] == 3));
    assert_eq!(ops.iter().filter(|(op, _)| *op == 114).count(), 1);
}

#[test]
fn every_shift_uses_a_bounded_u32_count_and_oversized_logical_result_select() {
    let text=".version 7.0 .target sm_50 .address_size 64 .visible .entry s() { .reg .b32 %c; .reg .b64 %d; mov.u32 %c, 64; shl.b64 %d, 1, %c; shr.u64 %d, %d, %c; shr.s64 %d, %d, %c; ret; }";
    let ops = instructions(&translate(text).unwrap().spirv);
    let safe: std::collections::BTreeSet<_> = ops
        .iter()
        .filter(|(op, a)| *op == 169 && a[0] == 3)
        .map(|(_, a)| a[1])
        .collect();
    let shifts: Vec<_> = ops
        .iter()
        .filter(|(op, _)| (194..=196).contains(op))
        .collect();
    assert_eq!(shifts.len(), 3);
    assert_eq!(safe.len(), 3);
    let normalized: std::collections::BTreeSet<_> = ops
        .iter()
        .filter(|(op, a)| *op == 113 && a[0] == 4 && safe.contains(&a[2]))
        .map(|(_, a)| a[1])
        .collect();
    assert_eq!(normalized.len(), 3);
    for (_, a) in shifts {
        assert!(normalized.contains(&a[3]));
    }
    assert_eq!(
        ops.iter().filter(|(op, a)| *op == 169 && a[0] == 4).count(),
        2
    );
    assert_eq!(ops.iter().filter(|(op, _)| *op == 174).count(), 3);
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

#[test]
fn block_barrier_is_control_barrier_with_opencl12_memory_ordering() {
    let source=".version 8.0 .target sm_52 .address_size 64 .entry sync() { .reg .u32 %v; mov.u32 %v,%tid.x; bar.sync 0; add.u32 %v,%v,1; bar.sync 0; ret; }";
    let ops = instructions(&translate(source).unwrap().spirv);
    let constants: std::collections::BTreeMap<_, _> = ops
        .iter()
        .filter(|(op, a)| *op == 43 && a[0] == 3)
        .map(|(_, a)| (a[1], a[2]))
        .collect();
    let barriers: Vec<_> = ops.iter().filter(|(op, _)| *op == 224).collect();
    assert_eq!(barriers.len(), 2);
    for (_, args) in barriers {
        assert_eq!(args.len(), 3);
        assert_eq!(constants[&args[0]], 2);
        assert_eq!(constants[&args[1]], 2);
        assert_eq!(constants[&args[2]], 0x310);
    }
    assert!(
        !ops.iter().any(|(op, _)| *op == 225),
        "memory-only barrier cannot rendezvous threads"
    );
}

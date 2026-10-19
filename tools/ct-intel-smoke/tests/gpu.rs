#[test]
#[ignore = "requires Windows x64, Intel Level Zero, and an Arc B390; run explicitly"]
fn arc_b390_executes_spirv_vector_add() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/vector_add.spv");
    let bytes = std::fs::read(path).expect("generate the SPIR-V fixture first");
    let report = ct_intel_smoke::run_smoke(&bytes, "B390")
        .expect("native GPU dispatch and numerical verification must succeed");
    assert!(report.contains("\"status\":\"pass\""));
    assert!(report.contains("\"cuda_compatibility\":false"));
}

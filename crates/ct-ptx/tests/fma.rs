fn source(op: &str) -> String {
    format!(".version 8.0 .target sm_52 .address_size 64 .entry fused(){{.reg .f32 %f<4>;mov.f32 %f0,0f3f800001;mov.f32 %f1,0f3f7ffffe;mov.f32 %f2,0fbf800000;{op};ret;}}")
}
#[test]
fn accepts_only_explicit_nearest_even_f32_fma() {
    ct_ptx::parse(&source("fma.rn.f32 %f3,%f0,%f1,%f2")).unwrap();
    for op in [
        "fma.f32",
        "fma.rz.f32",
        "fma.rm.f32",
        "fma.rp.f32",
        "fma.rn.ftz.f32",
        "fma.rn.sat.f32",
        "fma.rn.f64",
        "fma.rn.f16",
        "mad.rn.f32",
    ] {
        assert!(ct_ptx::parse(&source(&format!("{op} %f3,%f0,%f1,%f2"))).is_err());
    }
    assert!(ct_ptx::parse(&source("fma.rn.f32 %f3,%f0,%f1")).is_err());
}

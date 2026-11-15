use ct_ptx::parse;
fn source(body: &str) -> String {
    format!(".version 8.0 .target sm_52 .address_size 64 .entry uniform(.param .u32 rounds,.param .u64 .ptr .global .align 8 output) {{.reg .pred %p<3>; .reg .b32 %r<8>; .reg .b64 %rd<3>; .shared .align 4 .b8 a[512]; .shared .align 4 .b8 b[512]; {body}}}")
}
#[test]
fn accepts_uniform_loop_with_shared_and_barriers() {
    parse(&source("ld.param.u32 %r0,[rounds];mov.u32 %r1,0;mov.u32 %r2,a;bra.uni HEAD;HEAD:setp.ge.u32 %p0,%r1,%r0;@%p0 bra.uni DONE;st.shared.u32 [%r2],17;bar.sync 0;ld.shared.u32 %r3,[%r2];bar.sync 0;add.u32 %r1,%r1,1;bra.uni HEAD;DONE:ret;")).unwrap();
}
#[test]
fn accepts_only_the_nvcc_nounroll_metadata_pragma() {
    parse(&source(".pragma \"nounroll\";bar.sync 0;ret;")).unwrap();
    assert!(parse(&source(".pragma \"forceinline\";bar.sync 0;ret;")).is_err());
    assert!(parse(&source(".pragma nounroll;bar.sync 0;ret;")).is_err());
}
#[test]
fn accepts_uniform_diamond_with_one_shared_root_and_aligned_offsets() {
    parse(&source("ld.param.u32 %r0,[rounds];mov.u32 %r1,a;setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;add.u32 %r2,%r1,4;bra JOIN;ALT:add.u32 %r2,%r1,8;JOIN:st.shared.u32 [%r2],17;bar.sync 0;ret;")).unwrap();
}
#[test]
fn rejects_varying_control_and_shared_taint_at_merges() {
    for body in [
        "mov.u32 %r0,0;LOOP:setp.eq.u32 %p0,%r0,0;@%p0 bra BODY;ret;BODY:bar.sync 0;mov.u32 %r0,%tid.x;bra LOOP;",
        "START:setp.eq.u32 %p0,%r0,0;@%p0 bra END;bar.sync 0;mov.u32 %r0,0;bra START;END:ret;",
        "ld.param.u64 %rd1,[output];ld.param.u32 %r0,[rounds];setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;mov.u64 %rd0,a;bra JOIN;ALT:mov.u64 %rd0,0;JOIN:st.global.u64 [%rd1],%rd0;ret;",
        "ld.shared.u32 %r0,[a];setp.eq.u32 %p0,%r0,0;@%p0 bra END;bar.sync 0;END:ret;",
        "mov.u64 %rd0,0;ld.global.u32 %r0,[%rd0];setp.eq.u32 %p0,%r0,0;@%p0 bra END;bar.sync 0;END:ret;",
        "mov.u32 %r0,%tid.x;setp.eq.u32 %p0,%r0,0;@%p0 bra.uni END;bar.sync 0;END:ret;",
        "mov.u32 %r0,0;LOOP:bar.sync 0;mov.u32 %r0,%tid.x;setp.lt.u32 %p0,%r0,4;@%p0 bra LOOP;ret;",
        "ld.param.u32 %r0,[rounds];setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;mov.u64 %rd0,a;bra JOIN;ALT:mov.u64 %rd0,0;JOIN:ld.global.u32 %r1,[%rd0];ret;",
        "ld.param.u32 %r0,[rounds];setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;mov.u64 %rd0,a;bra JOIN;ALT:mov.u64 %rd0,b;JOIN:cvta.to.global.u64 %rd1,%rd0;ret;",
        "ld.param.u32 %r0,[rounds];setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;mov.u32 %r1,a;bra JOIN;ALT:mov.u32 %r1,b;JOIN:ld.shared.u32 %r2,[%r1];ret;",
        "ld.param.u32 %r0,[rounds];mov.u32 %r1,a;setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;add.u32 %r2,%r1,4;bra JOIN;ALT:add.u32 %r2,%r1,1;JOIN:ld.shared.u32 %r3,[%r2];ret;",
    ] { assert!(parse(&source(body)).is_err(),"accepted {body}"); }
}

use ct_ptx::parse;
fn source(body: &str) -> String {
    format!(".version 8.0 .target sm_52 .address_size 64 .entry exchange() {{ .reg .b32 %r<8>; .reg .b64 %rd<2>; {body} }}")
}
#[test]
fn accepts_static_shared_nvcc_address_shapes() {
    parse(&source(".shared .align 4 .b8 tile[512]; mov.u32 %r0,tile; mov.u32 %r1,%tid.x; shl.b32 %r2,%r1,2; add.u32 %r3,%r0,%r2; st.shared.u32 [%r3],7; bar.sync 0; ld.shared.u32 %r4,[%r3]; cvt.u64.u32 %rd0,%r3; ld.shared.u32 %r5,[%rd0+4]; ret;")).unwrap();
}
#[test]
fn rejects_shared_crossing_alignment_and_unsupported_storage() {
    for body in [
        ".shared .align 4 .b8 tile[0]; ret;",
        ".shared .align 4 .b8 tile[16388]; ret;",
        ".shared .align 2 .b8 tile[512]; ret;",
        ".extern .shared .align 4 .b8 tile[]; ret;",
        ".shared .align 4 .b8 tile[512]; mov.u32 %r0,tile; add.u32 %r1,%r0,1; ld.shared.u32 %r2,[%r1]; ret;",
        ".shared .align 4 .b8 tile[512]; ld.shared.u32 %r0,[tile+512]; ret;",
        ".shared .align 4 .b8 tile[512]; mov.u64 %rd0,tile; ld.global.u32 %r0,[%rd0]; ret;",
        ".shared .align 4 .b8 tile[512]; mov.u64 %rd0,0; ld.shared.u32 %r0,[%rd0]; ret;",
        ".shared .align 4 .b8 tile[512]; mov.u32 %r0,tile; mul.lo.u32 %r1,%r0,4; ret;",
        ".shared .align 4 .b8 a[512]; .shared .align 4 .b8 b[512]; mov.u32 %r0,a; mov.u32 %r1,b; add.u32 %r2,%r0,%r1; ret;",
        ".shared .align 4 .b8 tile[512]; mov.u32 %r0,%tid.x; bra NEXT; NEXT: ld.shared.u32 %r1,[%rd0]; ret;",
    ] {
        assert!(parse(&source(body)).is_err(), "accepted {body}");
    }
}

#[test]
fn shared_accesses_reject_unknown_modifiers_and_address_escape() {
    for body in [
        ".shared .align 4 .b8 a[512]; ld.shared.unknown.u32 %r0,[a]; ret;",
        ".shared .align 4 .b8 a[512]; st.shared.relaxed.u32 [a],7; ret;",
        ".shared .align 4 .b8 a[512]; mov.u64 %rd0,a; cvta.to.global.u64 %rd1,%rd0; ret;",
        ".shared .align 4 .b8 a[512]; mov.u32 %r0,a; cvt.u64.s32 %rd0,%r0; ret;",
        ".shared .align 4 .b8 a[512]; mov.u64 %rd0,a; st.global.u64 [%rd1],%rd0; ret;",
        ".shared .align 4 .b8 a[512]; mov.u32 %r0,a; st.shared.u32 [a],%r0; ret;",
        ".shared .align 4 .b8 a[512]; mov.u32 %r0,a; mov.u32 %r0,0; ld.shared.u32 %r1,[%r0]; ret;",
        ".shared .align 4 .b8 a[512]; mov.u32 %r0,a; add.u32 %r0,%r0,512; ld.shared.u32 %r1,[%r0]; ret;",
        ".shared .align 16 .b8 a[8196]; .shared .align 16 .b8 b[8188]; ret;",
    ] {assert!(parse(&source(body)).is_err(),"accepted {body}");}
}

#[test]
fn reused_register_tracks_each_distinct_shared_object() {
    let k=parse(&source(".shared .align 4 .b8 a[512]; .shared .align 4 .b8 b[512]; mov.u32 %r0,a; st.shared.u32 [%r0],17; mov.u32 %r0,b; st.shared.u32 [%r0],29; ret;")).unwrap();
    assert_eq!(
        k.shared_access_roots().unwrap(),
        [None, Some(0), None, Some(1)]
    );
}

#[test]
fn truncated_shift_count_cannot_forge_shared_alignment() {
    let text=source(".shared .align 4 .b8 a[512]; mov.u64 %rd0,4294967296; cvt.u32.u64 %r0,%rd0; mov.u32 %r1,%tid.x; shl.b32 %r2,%r1,%r0; mov.u32 %r3,a; add.u32 %r4,%r3,%r2; ld.shared.u32 %r5,[%r4]; ret;");
    assert!(parse(&text).is_err());
}

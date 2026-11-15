fn source(body: &str) -> String {
    format!(".version 8.0 .target sm_52 .address_size 64 .entry rendezvous() {{{body}}}")
}
#[test]
fn canonical_block_barriers_parse_in_one_linear_returning_block() {
    let k = ct_ptx::parse(&source(
        ".reg .u32 %v; mov.u32 %v,%tid.x; bar.sync 0; add.u32 %v,%v,1; bar.sync 0; ret;",
    ))
    .unwrap();
    assert_eq!(k.blocks.len(), 1);
    assert!(format!("{:?}", k.blocks[0].instructions).contains("BlockBarrier"));
}
#[test]
fn unsafe_or_outside_profile_barriers_are_rejected_before_codegen() {
    for body in ["bar.sync 1; ret;","bar.sync 0,32; ret;","bar.sync %id; ret;","bar.warp.sync 0xffffffff; ret;","barrier.sync 0; ret;","bar.arrive 0,32; ret;",
 ".reg .pred %p; setp.eq.u32 %p,0,0; @%p bar.sync 0; ret;",
 ".reg .pred %p; .reg .u32 %v; mov.u32 %v,%tid.x; setp.eq.u32 %p,%v,0; @%p bra END; bar.sync 0; END: ret;",
 ".reg .pred %p; .reg .u32 %v; mov.u32 %v,%tid.y; setp.eq.u32 %p,%v,0; @%p bra.uni NEXT; bar.sync 0; NEXT: ret;","LOOP: bar.sync 0; bra LOOP;",
 ".extern .shared .align 4 .b8 tile[]; bar.sync 0; ret;"] {
  assert!(ct_ptx::parse(&source(body)).is_err(),"accepted {body}");
 }
}
#[test]
fn ordinary_cfg_without_barriers_is_preserved() {
    assert!(ct_ptx::parse(&source("bra NEXT; NEXT: ret;")).is_ok());
}

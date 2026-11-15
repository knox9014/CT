use ct_ptx::parse;

fn kernel(body: &str) -> String {
    format!(".version 8.0 .target sm_52 .address_size 64 .entry mixed(.param .u64 .ptr .global .align 4 narrow,.param .u64 .ptr .global .align 8 wide,.param .u32 index,.param .b64 scalar) {{ .reg .b64 %a; .reg .b64 %b; .reg .b64 %c; .reg .b64 %d; .reg .b64 %v; .reg .b32 %i; .reg .b32 %x; .reg .pred %p; ld.param.u64 %a,[narrow]; ld.param.u64 %b,[wide]; ld.param.u32 %i,[index]; ld.param.b64 %v,[scalar]; setp.eq.u32 %p,%i,0; {body} }}")
}

#[test]
fn unrelated_narrow_pointer_does_not_block_wide_access() {
    let k = parse(&kernel("ld.global.u32 %x,[%a]; mul.wide.u32 %c,%i,8; add.u64 %c,%b,%c; st.global.u64 [%c],%v; ret;")).unwrap();
    assert_eq!(k.params[0].alignment, 4);
    assert_eq!(k.params[1].alignment, 8);
}

#[test]
fn inferred_alignment_is_promoted_only_for_wide_access_roots() {
    let text = kernel("cvta.to.global.u64 %c,%a; cvta.to.global.u64 %d,%b; ld.global.u32 %x,[%c]; st.global.u64 [%d],%v; ret;")
        .replace(".u64 .ptr .global .align 4 narrow", ".u64 narrow")
        .replace(".u64 .ptr .global .align 8 wide", ".u64 wide");
    let k = parse(&text).unwrap();
    assert_eq!(k.params[0].alignment, 4);
    assert_eq!(k.params[1].alignment, 8);
    let only_narrow = text.replace("st.global.u64 [%d],%v", "st.global.u32 [%d],%x");
    let k = parse(&only_narrow).unwrap();
    assert_eq!(k.params[1].alignment, 4);
}

#[test]
fn rejects_unproved_addresses_even_when_every_pointer_is_align8() {
    for body in [
        "mov.u64 %c,4096; st.global.u64 [%c],%v; ret;",
        "st.global.u64 [%v],%v; ret;",
        "add.u64 %c,%b,4; st.global.u64 [%c],%v; ret;",
        "mul.wide.u32 %c,%i,4; add.u64 %c,%b,%c; st.global.u64 [%c],%v; ret;",
        "add.u64 %c,%a,%b; st.global.u64 [%c],%v; ret;",
        "xor.b64 %c,%b,0; add.u64 %c,%a,%c; st.global.u64 [%c],%v; ret;",
    ] {
        assert!(
            parse(&kernel(body).replace(".align 4", ".align 8")).is_err(),
            "{body}"
        );
    }
}

#[test]
fn joins_preserve_only_identical_roots_and_proved_residues() {
    let good = "mov.u64 %c,%b; @%p bra ALTERNATE; add.u64 %c,%b,8; bra JOIN; ALTERNATE: add.u64 %c,%b,16; JOIN: st.global.u64 [%c],%v; ret;";
    parse(&kernel(good)).unwrap();
    assert!(parse(&kernel(&good.replace("%b,16", "%b,4"))).is_err());
    assert!(
        parse(&kernel(&good.replace("%b,16", "%a,16")).replace(".align 4", ".align 8")).is_err()
    );
}

#[test]
fn loop_fixed_point_checks_later_iterations_and_in_place_updates() {
    let good = "mov.u64 %c,%b; LOOP: st.global.u64 [%c],%v; add.u64 %c,%c,8; @%p bra LOOP; ret;";
    parse(&kernel(good)).unwrap();
    assert!(parse(&kernel(&good.replace("%c,%c,8", "%c,%c,4"))).is_err());
    let clobber = "mov.u64 %c,%b; LOOP: st.global.u64 [%c],%v; mov.u64 %c,%v; @%p bra LOOP; ret;";
    assert!(parse(&kernel(clobber)).is_err());
}

#[test]
fn literal_shift_uses_actual_count_not_just_low_bits() {
    let good = "shl.b64 %c,%v,8; add.u64 %c,%b,%c; st.global.u64 [%c],%v; ret;";
    parse(&kernel(good)).unwrap();
    assert!(parse(&kernel(&good.replace("%v,8", "%v,0"))).is_err());
}

#[test]
fn memory_load_clobbers_pointer_origin_after_checking_its_own_address() {
    parse(&kernel("ld.global.u64 %b,[%b]; ret;")).unwrap();
    assert!(parse(&kernel(
        "ld.global.u64 %b,[%b]; st.global.u64 [%b],%v; ret;"
    ))
    .is_err());
}

#[test]
fn explicit_weak_roots_and_narrowed_pointers_are_not_upgraded() {
    assert!(parse(&kernel("st.global.u64 [%a],%v; ret;")).is_err());
    parse(&kernel("cvt.u64.u64 %c,%b; st.global.u64 [%c],%v; ret;")).unwrap();
    assert!(parse(&kernel(
        "cvt.u32.u64 %x,%b; cvt.u64.u32 %c,%x; st.global.u64 [%c],%v; ret;"
    ))
    .is_err());
}

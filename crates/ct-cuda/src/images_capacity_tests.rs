use super::*;
const OLD: Profile = Profile {
    major: 7,
    minor: 0,
    target: 50,
};
const NEW: Profile = Profile {
    major: 8,
    minor: 0,
    target: 52,
};

fn candidate(profile: Profile, shared: &str) -> SourceCandidate {
    SourceCandidate {profile: Some(profile), text: format!(
        ".version {}.{} .target sm_{} .address_size 64 .entry choice(.param .u32 n){{{shared} ret;}}",
        profile.major, profile.minor, profile.target)}
}
fn alternatives(reverse: bool) -> Vec<SourceCandidate> {
    let old = candidate(OLD, ".shared .align 4 .b8 x[4];");
    let new = candidate(NEW, ".shared .align 16 .b8 x[8];");
    if reverse {
        vec![new, old]
    } else {
        vec![old, new]
    }
}

#[test]
fn chooses_highest_fitting_candidate_in_either_record_order() {
    for reverse in [false, true] {
        for (capacity, profile, bytes) in [
            (4, OLD, 4),
            (15, OLD, 4),
            (16, NEW, 16),
            (u32::MAX, NEW, 16),
        ] {
            let selected = super::compile_candidates(alternatives(reverse), capacity).unwrap();
            assert_eq!(selected.profile, profile);
            assert_eq!(selected.entries[0].static_shared_bytes, bytes);
            let expected = alternatives(false)
                .into_iter()
                .find(|c| c.profile == Some(profile))
                .unwrap();
            assert_eq!(
                selected.spirv,
                ct_codegen_spirv::translate_module(&expected.text)
                    .unwrap()
                    .spirv
            );
        }
        for capacity in [0, 3] {
            assert_eq!(
                super::compile_candidates(alternatives(reverse), capacity).err(),
                Some(801)
            );
        }
    }
}

#[test]
fn checks_each_entry_without_adding_independent_budgets() {
    let pair = || {
        let mut old = candidate(OLD, ".shared .align 16 .b8 x[16];");
        old.text
            .push_str(" .entry second(){.shared .align 16 .b8 y[16];ret;}");
        let mut new = candidate(NEW, ".shared .align 4 .b8 x[8];");
        new.text
            .push_str(" .entry second(){.shared .align 16 .b8 y[32];ret;}");
        vec![old, new]
    };
    assert_eq!(super::compile_candidates(pair(), 16).unwrap().profile, OLD);
    assert_eq!(super::compile_candidates(pair(), 32).unwrap().profile, NEW);
}

#[test]
fn raw_single_and_zero_capacity_follow_same_rule() {
    let mut raw = candidate(NEW, ".shared .align 16 .b8 x[16];");
    raw.profile = None;
    assert_eq!(super::compile_candidates(vec![raw], 15).err(), Some(801));
    let mut raw = candidate(NEW, ".shared .align 16 .b8 x[16];");
    raw.profile = None;
    assert_eq!(
        super::compile_candidates(vec![raw], 16).unwrap().profile,
        NEW
    );
    assert_eq!(
        super::compile_candidates(vec![candidate(NEW, "")], 0)
            .unwrap()
            .profile,
        NEW
    );
    assert_eq!(super::compile_candidates(Vec::new(), 0).err(), Some(1));
}

#[test]
fn nonfitting_candidate_cannot_hide_metadata_abi_or_unsupported_errors() {
    for reverse in [false, true] {
        for defect in 0..6 {
            let old = candidate(OLD, "");
            let mut new = candidate(NEW, ".shared .align 16 .b8 x[32];");
            let expected = match defect {
                0 => {
                    new.profile = Some(OLD);
                    218
                }
                1 => {
                    new.text = new.text.replace(".param .u32 n", ".param .f32 n");
                    801
                }
                2 => {
                    new.text = new.text.replace("ret;", "bar.sync 1;ret;");
                    801
                }
                3 => {
                    new = candidate(OLD, ".shared .align 16 .b8 x[32];");
                    801
                }
                4 => {
                    new.text = new
                        .text
                        .replace(".entry choice", ".global .align 4 .u32 g=7; .entry choice");
                    801
                }
                _ => {
                    new.text.pop(); // missing closing brace: malformed, not unsupported
                    218
                }
            };
            let rows = if reverse {
                vec![new, old]
            } else {
                vec![old, new]
            };
            assert_eq!(super::compile_candidates(rows, 16).err(), Some(expected));
        }
    }
}

#[test]
fn realistic_shared_profile_boundaries_preserve_rank() {
    let pair = || {
        vec![
            candidate(OLD, ".shared .align 16 .b8 x[8192];"),
            candidate(NEW, ".shared .align 16 .b8 x[16384];"),
        ]
    };
    assert_eq!(super::compile_candidates(pair(), 8191).err(), Some(801));
    for (capacity, expected) in [(8192, OLD), (16383, OLD), (16384, NEW), (u32::MAX, NEW)] {
        assert_eq!(
            super::compile_candidates(pair(), capacity).unwrap().profile,
            expected
        );
    }
}

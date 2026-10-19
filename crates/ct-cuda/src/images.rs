//! Pure image validation/selection; native module creation happens only afterward.
use super::{INVALID, UNSUPPORTED};
use ct_codegen_spirv::Compiled;
use ct_ptx::{ParamKind, Profile};
use std::ffi::c_void;

pub(crate) struct SourceCandidate {
    pub(crate) profile: Option<Profile>,
    pub(crate) text: String,
}

fn raw(text: String) -> Vec<SourceCandidate> {
    vec![SourceCandidate {
        profile: None,
        text,
    }]
}

/// Caller supplies a readable C string or the full readable declared fatbin.
/// The cap precedes formation of its binary slice, not host-pointer validation.
pub(crate) unsafe fn read_candidates(image: *const c_void) -> Result<Vec<SourceCandidate>, i32> {
    if image.is_null() {
        return Err(INVALID);
    }
    let mut data = Vec::new();
    for i in 0..4 {
        let byte = image.cast::<u8>().add(i).read();
        if byte == 0 {
            return String::from_utf8(data).map(raw).map_err(|_| 218);
        }
        data.push(byte);
    }
    if data == ct_fatbin::MAGIC {
        let error = |e| match e {
            ct_fatbin::Error::Invalid => 218,
            ct_fatbin::Error::Unsupported => UNSUPPORTED,
        };
        let header = std::slice::from_raw_parts(image.cast::<u8>(), 16);
        let size = ct_fatbin::image_size(header).map_err(error)?;
        let bytes = std::slice::from_raw_parts(image.cast::<u8>(), size);
        return ct_fatbin::extract_candidates(bytes)
            .map_err(error)?
            .into_iter()
            .map(|candidate| {
                Ok(SourceCandidate {
                    profile: Some(Profile {
                        major: candidate.profile.major,
                        minor: candidate.profile.minor,
                        target: candidate.profile.target,
                    }),
                    text: String::from_utf8(candidate.text.into_owned()).map_err(|_| 218)?,
                })
            })
            .collect();
    }
    if data == [0xb1, 0x43, 0x62, 0x46] || data == b"\x7fELF" {
        return Err(UNSUPPORTED);
    }
    for i in 4..=ct_fatbin::MAX_PTX_SIZE {
        let byte = image.cast::<u8>().add(i).read();
        if byte == 0 {
            return String::from_utf8(data).map(raw).map_err(|_| 218);
        }
        data.push(byte);
    }
    Err(UNSUPPORTED)
}

pub(crate) fn compile_candidates(candidates: Vec<SourceCandidate>) -> Result<Compiled, i32> {
    if candidates.is_empty()
        || (candidates.len() != 1 && candidates.iter().any(|c| c.profile.is_none()))
    {
        return Err(INVALID);
    }
    if candidates.len() > ct_fatbin::MAX_CANDIDATES {
        return Err(UNSUPPORTED);
    }
    let mut profiles = Vec::new();
    let mut identity: Option<(String, Vec<ParamKind>)> = None;
    let mut selected: Option<(u8, Compiled)> = None;
    for candidate in candidates {
        let compiled = ct_codegen_spirv::translate(&candidate.text).map_err(|e| {
            if e.unsupported {
                UNSUPPORTED
            } else {
                218
            }
        })?;
        if let Some(metadata) = candidate.profile {
            if metadata != compiled.profile {
                return Err(218);
            }
        }
        if profiles.contains(&compiled.profile) {
            return Err(UNSUPPORTED);
        }
        profiles.push(compiled.profile);
        let kinds: Vec<_> = compiled.params.iter().map(|p| p.kind).collect();
        if let Some((name, abi)) = &identity {
            if *name != compiled.entry || *abi != kinds {
                return Err(UNSUPPORTED);
            }
        } else {
            identity = Some((compiled.entry.clone(), kinds));
        }
        let rank = match (
            compiled.profile.major,
            compiled.profile.minor,
            compiled.profile.target,
        ) {
            (7, 0, 50) => 0,
            (8, 0, 52) => 1,
            _ => return Err(UNSUPPORTED),
        };
        if selected.as_ref().is_none_or(|(best, _)| rank > *best) {
            selected = Some((rank, compiled));
        }
    }
    selected.map(|(_, compiled)| compiled).ok_or(INVALID)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ct_ptx::Profile;
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

    fn candidate(profile: Profile, name: &str, ty: &str) -> SourceCandidate {
        SourceCandidate {profile:Some(profile),text:format!(
            ".version {}.{}\n.target sm_{}\n.address_size 64\n.visible .entry {}(.param .{} n) {{ ret; }}",
            profile.major,profile.minor,profile.target,name,ty)}
    }
    #[test]
    fn selects_profile_independent_of_record_order_and_parameter_names() {
        for reverse in [false, true] {
            let old = candidate(OLD, "choice", "u32");
            let mut new = candidate(NEW, "choice", "u32");
            new.text = new.text.replace("u32 n)", "u32 different)");
            let entries = if reverse {
                vec![new, old]
            } else {
                vec![old, new]
            };
            let selected = compile_candidates(entries).unwrap();
            assert_eq!(selected.profile, NEW);
            assert_eq!(selected.params[0].name, "different");
        }
    }
    #[test]
    fn rejects_profile_mismatch_duplicate_and_abi_conflict() {
        let mut mismatch = candidate(OLD, "choice", "u32");
        mismatch.profile = Some(NEW);
        assert_eq!(compile_candidates(vec![mismatch]).err(), Some(218));
        for entries in [
            vec![
                candidate(OLD, "choice", "u32"),
                candidate(OLD, "choice", "u32"),
            ],
            vec![
                candidate(OLD, "choice", "u32"),
                candidate(NEW, "other", "u32"),
            ],
            vec![
                candidate(OLD, "choice", "u32"),
                candidate(NEW, "choice", "f32"),
            ],
        ] {
            assert_eq!(compile_candidates(entries).err(), Some(801));
        }
        let mut extra = candidate(NEW, "choice", "u32");
        extra.text = extra.text.replace("u32 n)", "u32 n, .param .u32 extra)");
        assert_eq!(
            compile_candidates(vec![candidate(OLD, "choice", "u32"), extra]).err(),
            Some(801)
        );
    }
    #[test]
    fn does_not_hide_unsupported_unselected_candidate() {
        let mut old = candidate(OLD, "choice", "u32");
        old.text = old.text.replace("ret;", "bar.sync 0; ret;");
        assert_eq!(
            compile_candidates(vec![candidate(NEW, "choice", "u32"), old]).err(),
            Some(801)
        );
        assert_eq!(compile_candidates(Vec::new()).err(), Some(1));
        let mut raw = candidate(OLD, "choice", "u32");
        raw.profile = None;
        assert_eq!(
            compile_candidates(vec![raw, candidate(NEW, "choice", "u32")]).err(),
            Some(1)
        );
    }
    #[test]
    fn raw_ptx_and_short_c_strings_keep_contract() {
        let mut raw = candidate(OLD, "choice", "u32");
        raw.profile = None;
        assert_eq!(compile_candidates(vec![raw]).unwrap().profile, OLD);
        unsafe {
            for bytes in [b"\0".as_slice(), b"P\0", b"PT\0", b"PTX\0"] {
                let sources = read_candidates(bytes.as_ptr().cast()).unwrap();
                assert_eq!(sources.len(), 1);
                assert_eq!(sources[0].text.as_bytes(), &bytes[..bytes.len() - 1]);
                assert_eq!(sources[0].profile, None);
            }
            assert_eq!(read_candidates(std::ptr::null()).err(), Some(1));
            assert_eq!(
                read_candidates([0xb1u8, 0x43, 0x62, 0x46, 0].as_ptr().cast()).err(),
                Some(801)
            );
            assert_eq!(read_candidates(c"\x7fELF".as_ptr().cast()).err(), Some(801));
            let mut bytes = [0u8; 16];
            bytes[..8].copy_from_slice(&[0x50, 0xed, 0x55, 0xba, 1, 0, 16, 0]);
            bytes[8..].copy_from_slice(&(16u64 * 1024 * 1024).to_le_bytes());
            assert_eq!(read_candidates(bytes.as_ptr().cast()).err(), Some(801));
            bytes[8..].copy_from_slice(&u64::MAX.to_le_bytes());
            assert_eq!(read_candidates(bytes.as_ptr().cast()).err(), Some(218));
        }
    }
}

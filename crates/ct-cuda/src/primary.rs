//! Restricted default-flags primary context API. Lifecycle calls never edit TLS.
use super::*;

fn device(r: &Runtime, device: i32) -> CudaResult {
    let b = backend(r)?;
    if device < 0 || device as usize >= b.devices.len() {
        return Err(INVALID_DEVICE);
    }
    Ok(())
}

fn validate_primary_flags(flags: u32) -> CudaResult {
    if flags & !0x1f != 0 || !matches!(flags & 7, 0 | 1 | 2 | 4) {
        return Err(INVALID);
    }
    if flags != 0 {
        return Err(UNSUPPORTED);
    }
    Ok(())
}

/// Only CT's existing default execution policy is supported; no activation or TLS changes.
#[no_mangle]
pub extern "system" fn cuDevicePrimaryCtxSetFlags_v2(ordinal: i32, flags: u32) -> i32 {
    invoke(|r| {
        device(r, ordinal)?;
        validate_primary_flags(flags)
    })
}

/// # Safety
/// flags must be writable for one unsigned C int.
#[no_mangle]
pub unsafe extern "system" fn cuCtxGetFlags(flags: *mut u32) -> i32 {
    invoke(|r| {
        backend(r)?;
        if flags.is_null() {
            return Err(INVALID);
        }
        flags.write(0);
        context_id(r)?;
        Ok(())
    })
}

/// # Safety
/// output must be writable for one context handle.
#[no_mangle]
pub unsafe extern "system" fn cuDevicePrimaryCtxRetain(
    output: *mut *mut c_void,
    ordinal: i32,
) -> i32 {
    invoke(|r| {
        backend(r)?;
        if output.is_null() {
            return Err(INVALID);
        }
        output.write(std::ptr::null_mut());
        device(r, ordinal)?;
        let Runtime {
            primary,
            backend,
            contexts,
            next,
            ..
        } = r;
        let id = primary.retain(ordinal, || {
            create_owned_context(
                backend.as_mut().ok_or(NOT_INITIALIZED)?,
                contexts,
                next,
                ordinal,
            )
        })?;
        output.write(id as *mut c_void);
        Ok(())
    })
}

/// # Safety
/// flags and active must be valid, nonoverlapping writable C scalars.
#[no_mangle]
pub unsafe extern "system" fn cuDevicePrimaryCtxGetState(
    ordinal: i32,
    flags: *mut u32,
    active: *mut i32,
) -> i32 {
    invoke(|r| {
        device(r, ordinal)?;
        if flags.is_null() || active.is_null() {
            return Err(INVALID);
        }
        flags.write(0);
        active.write(i32::from(r.primary.active(ordinal)));
        Ok(())
    })
}

#[no_mangle]
pub extern "system" fn cuDevicePrimaryCtxRelease_v2(ordinal: i32) -> i32 {
    invoke(|r| {
        device(r, ordinal)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        release_primary(
            &mut r.primary,
            &mut r.contexts,
            &mut r.retired,
            ordinal,
            |c| cleanup_context(b, c),
        )
    })
}

/// Reset resource ownership while preserving retained usage and all TLS stacks.
#[no_mangle]
pub extern "system" fn cuDevicePrimaryCtxReset_v2(ordinal: i32) -> i32 {
    invoke(|r| {
        device(r, ordinal)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        reset_primary(
            &mut r.primary,
            &mut r.contexts,
            &mut r.retired,
            ordinal,
            |c| cleanup_context(b, c),
        )
    })
}

fn reset_primary<T>(
    primary: &mut primary_state::PrimaryContexts,
    contexts: &mut BTreeMap<usize, T>,
    retired: &mut Vec<T>,
    ordinal: i32,
    cleanup: impl FnOnce(&mut T) -> CudaResult,
) -> CudaResult {
    if let Some(id) = primary.reset(ordinal) {
        retire_owned(contexts, retired, id, cleanup)?;
    }
    Ok(())
}

fn release_primary<T>(
    primary: &mut primary_state::PrimaryContexts,
    contexts: &mut BTreeMap<usize, T>,
    retired: &mut Vec<T>,
    ordinal: i32,
    cleanup: impl FnOnce(&mut T) -> CudaResult,
) -> CudaResult {
    if let Some(id) = primary.release(ordinal)? {
        retire_owned(contexts, retired, id, cleanup)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn primary_flags_reject_malformed_and_unimplemented_modes_distinctly() {
        assert_eq!(validate_primary_flags(0), Ok(()));
        for flags in [1, 2, 4, 8, 9, 10, 12, 16, 17, 18, 20, 24, 25, 26, 28] {
            assert_eq!(validate_primary_flags(flags), Err(801), "flags={flags}");
        }
        for flags in [
            3, 5, 6, 7, 11, 13, 14, 15, 19, 21, 22, 23, 27, 29, 30, 31, 32,
        ] {
            assert_eq!(validate_primary_flags(flags), Err(1), "flags={flags}");
        }
        assert_eq!(validate_primary_flags(u32::MAX), Err(1));
        assert_eq!(validate_primary_flags(0x80000000), Err(1));
    }

    #[test]
    fn reset_failure_preserves_usage_and_never_retries_quarantined_resources() {
        let mut primary = primary_state::PrimaryContexts::default();
        primary.retain(0, || Ok(10)).unwrap();
        primary.retain(0, || panic!("reuse")).unwrap();
        let mut contexts = BTreeMap::from([(10, 42)]);
        let mut retired = Vec::new();
        assert_eq!(
            reset_primary(&mut primary, &mut contexts, &mut retired, 0, |_| Err(999)),
            Err(999)
        );
        assert!(!primary.active(0));
        assert!(primary.retired(10));
        assert!(contexts.is_empty());
        assert_eq!(retired, vec![42]);
        assert_eq!(
            reset_primary(&mut primary, &mut contexts, &mut retired, 0, |_| panic!(
                "no retry"
            )),
            Ok(())
        );
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| panic!(
                "no cleanup"
            )),
            Ok(())
        );
        assert_eq!(
            primary.retain(0, || {
                contexts.insert(11, 43);
                Ok(11)
            }),
            Ok(11)
        );
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| panic!(
                "not final"
            )),
            Ok(())
        );
        assert!(primary.active(0));
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| Ok(())),
            Ok(())
        );
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| panic!(
                "over-release"
            )),
            Err(201)
        );
        assert_eq!(retired, vec![42]);
    }

    #[test]
    fn final_release_failure_is_inactive_tombstoned_and_never_retried() {
        let mut primary = primary_state::PrimaryContexts::default();
        primary.retain(0, || Ok(10)).unwrap();
        let mut contexts = BTreeMap::from([(10, 42)]);
        let mut retired = Vec::new();
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| Err(999)),
            Err(999)
        );
        assert!(!primary.active(0));
        assert!(primary.retired(10));
        assert!(contexts.is_empty());
        assert_eq!(retired, vec![42]);
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| panic!(
                "no retry"
            )),
            Err(201)
        );
        assert_eq!(
            primary.retain(0, || {
                contexts.insert(11, 43);
                Ok(11)
            }),
            Ok(11)
        );
        assert!(primary.active(0));
        assert!(primary.retired(10));
        assert_eq!(
            release_primary(&mut primary, &mut contexts, &mut retired, 0, |_| Ok(())),
            Ok(())
        );
        assert!(contexts.is_empty());
        assert_eq!(retired, vec![42]);
    }
}

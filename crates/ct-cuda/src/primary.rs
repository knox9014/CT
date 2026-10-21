//! Restricted default-flags primary context API. Lifecycle calls never edit TLS.
use super::*;

fn device(r: &Runtime, device: i32) -> CudaResult {
    let b = backend(r)?;
    if device < 0 || device as usize >= b.devices.len() {
        return Err(INVALID_DEVICE);
    }
    Ok(())
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

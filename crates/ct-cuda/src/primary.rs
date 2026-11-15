//! Restricted default-flags primary context API. Lifecycle calls never edit TLS.
use super::*;

/// Internal CUDART context callback, exposed to Rust diagnostic consumers only.
/// It is not a named CUDA DLL export or a declaration of private ABI support.
///
/// # Safety
/// A non-null output must be writable for one context handle.
pub unsafe extern "system" fn cudart_primary_context(
    output: *mut *mut c_void,
    ordinal: i32,
) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    // Clear even if the global Runtime lock fails before the adapter is called.
    output.write(std::ptr::null_mut());
    invoke(|r| acquire_primary(r, output, ordinal, false))
}

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
        acquire_primary(r, output, ordinal, true)
    })
}

/// Internal native adapter, not a published CUDA entry point.
///
/// # Safety
/// A non-null output must be writable for one context handle.
unsafe fn acquire_primary(
    r: &mut Runtime,
    output: *mut *mut c_void,
    ordinal: i32,
    retained: bool,
) -> CudaResult {
    if output.is_null() {
        return Err(INVALID);
    }
    output.write(std::ptr::null_mut());
    device(r, ordinal)?;
    if !retained && r.primary.has_pending_usage(ordinal) {
        // Private post-reset identity/activation semantics remain unverified.
        return Err(UNSUPPORTED);
    }
    let Runtime {
        primary,
        backend,
        contexts,
        next,
        ..
    } = r;
    let create = || {
        create_owned_context(
            backend.as_mut().ok_or(NOT_INITIALIZED)?,
            contexts,
            next,
            ordinal,
        )
    };
    let id = if retained {
        primary.retain(ordinal, create)?
    } else {
        primary.get_or_create_unretained(ordinal, create)?
    };
    output.write(id as *mut c_void);
    Ok(())
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
    fn acquisition_clears_output_without_backend_and_rejects_null() {
        let mut r = Runtime::default();
        let mut output = std::ptr::dangling_mut();
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut output, 0, false), Err(3));
            assert!(output.is_null());
            assert_eq!(
                acquire_primary(&mut r, std::ptr::null_mut(), 0, false),
                Err(1)
            );
        }
        assert!(r.contexts.is_empty());
        assert_eq!(r.next, 0);
    }

    #[test]
    #[ignore = "requires real Intel Level Zero GPU; explicitly run alone"]
    fn native_unretained_primary_preserves_tls_and_cleans_resources() {
        struct RestoreTls(Vec<usize>);
        impl Drop for RestoreTls {
            fn drop(&mut self) {
                CURRENT.with(|s| *s.borrow_mut() = std::mem::take(&mut self.0));
            }
        }
        let saved_stack = CURRENT.with(|s| std::mem::take(&mut *s.borrow_mut()));
        let restore = RestoreTls(saved_stack.clone());
        let mut r = Runtime {
            backend: Some(Backend::open().expect("Intel backend required")),
            ..Runtime::default()
        };
        assert!(!r.backend.as_ref().unwrap().devices.is_empty());
        let device_name = r.backend.as_ref().unwrap().devices[0].name.clone();
        let mut handle = std::ptr::dangling_mut();
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, -1, false), Err(101));
            assert!(handle.is_null());
            handle = std::ptr::dangling_mut();
            let invalid = r.backend.as_ref().unwrap().devices.len() as i32;
            assert_eq!(
                acquire_primary(&mut r, &mut handle, invalid, false),
                Err(101)
            );
            assert!(handle.is_null());
            assert!(r.contexts.is_empty());
            assert_eq!(r.next, 0);
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, false), Ok(()));
        }
        let reserved = handle as usize;
        assert!(reserved != 0 && r.contexts.contains_key(&reserved));
        assert!(r.primary.owns(reserved) && !r.primary.active(0));
        assert_eq!(current(), None);
        let ordinary =
            create_owned_context(r.backend.as_mut().unwrap(), &mut r.contexts, &mut r.next, 0)
                .unwrap();
        CURRENT.with(|s| s.borrow_mut().push(ordinary));
        let expected_stack = CURRENT.with(|s| s.borrow().clone());
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, false), Ok(()));
            assert_eq!(handle as usize, reserved);
        }
        let b = r.backend.as_ref().unwrap();
        assert_eq!(
            release_primary(&mut r.primary, &mut r.contexts, &mut r.retired, 0, |c| {
                cleanup_context(b, c)
            }),
            Err(201)
        );
        assert!(r.contexts.contains_key(&reserved));
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, true), Ok(()));
            assert_eq!(handle as usize, reserved);
        }
        assert!(r.primary.active(0));
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, false), Ok(()));
            assert_eq!(handle as usize, reserved);
        }
        // A nonretaining lookup must not require another release.
        let b = r.backend.as_ref().unwrap();
        assert_eq!(
            release_primary(&mut r.primary, &mut r.contexts, &mut r.retired, 0, |c| {
                cleanup_context(b, c)
            }),
            Ok(())
        );
        assert!(r.primary.retired(reserved));
        assert!(!r.contexts.contains_key(&reserved));
        assert!(r.retired.is_empty());
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, false), Ok(()));
        }
        let reset_handle = handle as usize;
        assert_ne!(reset_handle, reserved);
        let b = r.backend.as_ref().unwrap();
        assert_eq!(
            reset_primary(&mut r.primary, &mut r.contexts, &mut r.retired, 0, |c| {
                cleanup_context(b, c)
            }),
            Ok(())
        );
        assert!(r.primary.retired(reset_handle));
        assert!(!r.contexts.contains_key(&reset_handle));
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, true), Ok(()));
        }
        let b = r.backend.as_ref().unwrap();
        assert_eq!(
            reset_primary(&mut r.primary, &mut r.contexts, &mut r.retired, 0, |c| {
                cleanup_context(b, c)
            }),
            Ok(())
        );
        let next = r.next;
        unsafe {
            assert_eq!(acquire_primary(&mut r, &mut handle, 0, false), Err(801));
            assert!(handle.is_null());
        }
        assert_eq!(r.next, next);
        assert!(r.primary.has_pending_usage(0));
        assert_eq!(r.contexts.len(), 1);
        // Consume the usage preserved by reset; no second native cleanup.
        let b = r.backend.as_ref().unwrap();
        assert_eq!(
            release_primary(&mut r.primary, &mut r.contexts, &mut r.retired, 0, |c| {
                cleanup_context(b, c)
            }),
            Ok(())
        );
        assert_eq!(CURRENT.with(|s| s.borrow().clone()), expected_stack);
        assert!(r.retired.is_empty());
        retire_context(&mut r, ordinary).unwrap();
        assert!(r.contexts.is_empty() && r.retired.is_empty());
        assert_eq!(CURRENT.with(|s| s.borrow().clone()), expected_stack);
        CURRENT.with(|s| s.borrow_mut().clear());
        drop(restore);
        assert_eq!(CURRENT.with(|s| s.borrow().clone()), saved_stack);
        println!("native primary adapter passed: device={device_name}; TLS restored; owned/quarantined contexts=0");
    }

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

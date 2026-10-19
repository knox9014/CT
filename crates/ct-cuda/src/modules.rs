use super::*;
use std::ffi::CStr;
const INVALID_HANDLE: i32 = 400;
fn token(r: &mut Runtime) -> Result<usize, i32> {
    r.next = r.next.checked_add(1).ok_or(UNKNOWN)?;
    Ok(r.next)
}
unsafe fn source(image: *const c_void) -> Result<String, i32> {
    if image.is_null() {
        return Err(INVALID);
    }
    let mut data = Vec::new();
    // Inspect incrementally: a one-byte empty PTX C string is a valid input.
    for i in 0..4 {
        let b = image.cast::<u8>().add(i).read();
        if b == 0 {
            return String::from_utf8(data).map_err(|_| 218);
        }
        data.push(b);
    }
    if data == ct_fatbin::MAGIC {
        let error = |e| match e {
            ct_fatbin::Error::Invalid => 218,
            ct_fatbin::Error::Unsupported => UNSUPPORTED,
        };
        // As with CUDA's pointer-only API, the caller must supply the full
        // readable image. The declared cap is checked before forming its slice.
        let header = std::slice::from_raw_parts(image.cast::<u8>(), 16);
        let size = ct_fatbin::image_size(header).map_err(error)?;
        let bytes = std::slice::from_raw_parts(image.cast::<u8>(), size);
        let ptx = ct_fatbin::extract_ptx(bytes).map_err(error)?;
        return std::str::from_utf8(ptx.as_ref())
            .map(str::to_owned)
            .map_err(|_| 218);
    }
    if data == [0xb1, 0x43, 0x62, 0x46] || data == b"\x7fELF" {
        return Err(UNSUPPORTED);
    }
    for i in 4..=262144 {
        let b = image.cast::<u8>().add(i).read();
        if b == 0 {
            return String::from_utf8(data).map_err(|_| 218);
        }
        data.push(b);
    }
    Err(UNSUPPORTED)
}
/// # Safety
/// output must be writable for one handle; image must be a valid NUL-terminated
/// readable PTX string or an entire readable fatbin with its declared byte size.
/// This interface accepts trusted code; arbitrary host pointers cannot be checked.
#[no_mangle]
pub unsafe extern "system" fn cuModuleLoadData(
    output: *mut *mut c_void,
    image: *const c_void,
) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        if output.is_null() {
            return Err(INVALID);
        }
        output.write(std::ptr::null_mut());
        let text = source(image)?;
        let compiled = ct_codegen_spirv::translate(&text).map_err(|e| {
            if e.unsupported {
                UNSUPPORTED
            } else {
                218
            }
        })?;
        let module_id = token(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        let native = b
            .load_module(&mut c.native, &compiled.spirv, &compiled.entry)
            .map_err(native_error)?;
        c.modules.insert(
            module_id,
            OwnedModule {
                native,
                entry: compiled.entry,
                params: compiled.params,
            },
        );
        output.write(module_id as *mut c_void);
        Ok(())
    })
}
/// # Safety
/// output must be writable for one handle and name a readable NUL-terminated name.
#[no_mangle]
pub unsafe extern "system" fn cuModuleGetFunction(
    output: *mut *mut c_void,
    module: *mut c_void,
    name: *const c_char,
) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        if output.is_null() || name.is_null() {
            return Err(INVALID);
        }
        output.write(std::ptr::null_mut());
        let c = r.contexts.get(&id).ok_or(INVALID_CONTEXT)?;
        let m = c.modules.get(&(module as usize)).ok_or(INVALID_HANDLE)?;
        if CStr::from_ptr(name).to_bytes() != m.entry.as_bytes() {
            return Err(500);
        }
        let fid = token(r)?;
        r.contexts
            .get_mut(&id)
            .ok_or(INVALID_CONTEXT)?
            .functions
            .insert(fid, module as usize);
        output.write(fid as *mut c_void);
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuModuleUnload(module: *mut c_void) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        let mid = module as usize;
        let m = c.modules.get_mut(&mid).ok_or(INVALID_HANDLE)?;
        b.unload_module(&mut c.native, &mut m.native)
            .map_err(native_error)?;
        c.modules.remove(&mid);
        c.functions.retain(|_, v| *v != mid);
        Ok(())
    })
}
/// # Safety
/// parameters must be a readable array with one readable pointer per declared
/// parameter, each pointing to its 4/8-byte argument. Pointer arguments must name
/// valid device storage for all accesses performed by the trusted kernel.
#[no_mangle]
pub unsafe extern "system" fn cuLaunchKernel(
    function: *mut c_void,
    gx: u32,
    gy: u32,
    gz: u32,
    bx: u32,
    by: u32,
    bz: u32,
    shared: u32,
    stream: *mut c_void,
    parameters: *mut *mut c_void,
    extra: *mut *mut c_void,
) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        let mid = c
            .functions
            .get(&(function as usize))
            .ok_or(INVALID_HANDLE)?;
        let m = c.modules.get(mid).ok_or(INVALID_HANDLE)?;
        if gy != 1
            || gz != 1
            || by != 1
            || bz != 1
            || shared != 0
            || !stream.is_null()
            || !extra.is_null()
        {
            return Err(UNSUPPORTED);
        }
        let d = &b.devices[c.native.device];
        if gx == 0
            || bx == 0
            || gx > d.max_groups_x
            || bx > d.max_group[0]
            || bx > d.max_group[1]
            || (gx as u64) * (bx as u64) > u32::MAX as u64
        {
            return Err(INVALID);
        }
        if !m.params.is_empty() && parameters.is_null() {
            return Err(INVALID);
        }
        let mut arguments = Vec::new();
        for (i, param) in m.params.iter().enumerate() {
            let pointer = parameters.add(i).read();
            if pointer.is_null() {
                return Err(INVALID);
            }
            let data = match param.kind {
                ParamKind::Pointer => {
                    let value = pointer.cast::<u64>().read_unaligned();
                    if !value.is_multiple_of(4) || !c.allocations.contains(value, 4) {
                        return Err(INVALID);
                    }
                    value.to_ne_bytes().to_vec()
                }
                ParamKind::U32 | ParamKind::F32 => pointer
                    .cast::<u32>()
                    .read_unaligned()
                    .to_ne_bytes()
                    .to_vec(),
            };
            arguments.push(data);
        }
        b.launch(&mut c.native, &m.native, &arguments, gx, bx)
            .map_err(native_error)
    })
}

#[cfg(test)]
mod image_tests {
    use super::source;
    use std::ffi::c_void;

    #[test]
    fn short_text_and_unsupported_binary_headers_have_explicit_results() {
        unsafe {
            for bytes in [b"\0".as_slice(), b"P\0", b"PT\0", b"PTX\0"] {
                assert_eq!(
                    source(bytes.as_ptr().cast::<c_void>()).unwrap().as_bytes(),
                    &bytes[..bytes.len() - 1]
                );
            }
            assert_eq!(
                source([0xb1u8, 0x43, 0x62, 0x46, 0].as_ptr().cast()),
                Err(801)
            );
            let mut oversized = [0u8; 16];
            oversized[..8].copy_from_slice(&[0x50, 0xed, 0x55, 0xba, 1, 0, 16, 0]);
            oversized[8..].copy_from_slice(&(16u64 * 1024 * 1024).to_le_bytes());
            assert_eq!(source(oversized.as_ptr().cast()), Err(801));
            oversized[8..].copy_from_slice(&u64::MAX.to_le_bytes());
            assert_eq!(source(oversized.as_ptr().cast()), Err(218));
        }
    }
}

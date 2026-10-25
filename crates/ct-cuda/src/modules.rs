use super::*;
use std::ffi::CStr;
const INVALID_HANDLE: i32 = 400;
fn token(r: &mut Runtime) -> Result<usize, i32> {
    r.next = r.next.checked_add(1).ok_or(UNKNOWN)?;
    Ok(r.next)
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
        if !output.is_null() {
            output.write(std::ptr::null_mut());
        }
        let id = context_id(r)?;
        if output.is_null() {
            return Err(INVALID);
        }
        let compiled = crate::images::compile_candidates(crate::images::read_candidates(image)?)?;
        let module_id = token(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        let names: Vec<_> = compiled.entries.iter().map(|e| e.entry.as_str()).collect();
        let globals: Vec<_> = compiled
            .globals
            .iter()
            .filter_map(|g| g.storage.byte_size().map(|size| (g.name.as_str(), size)))
            .collect();
        let mut native = b
            .load_module_entries_with_globals(&mut c.native, &compiled.spirv, &names, &globals)
            .map_err(native_error)?;
        let conflict = globals
            .iter()
            .any(|(name, _)| native.global(name).is_none_or(|g| c.conflicts_global(g)));
        if conflict {
            if b.unload_module(&mut c.native, &mut native).is_err() {
                c.modules.insert(
                    module_id,
                    OwnedModule {
                        native,
                        entries: compiled.entries,
                        globals: compiled.globals,
                    },
                );
            }
            return Err(UNKNOWN);
        }
        c.modules.insert(
            module_id,
            OwnedModule {
                native,
                entries: compiled.entries,
                globals: compiled.globals,
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
        if !output.is_null() {
            output.write(std::ptr::null_mut());
        }
        let id = context_id(r)?;
        if output.is_null() || name.is_null() {
            return Err(INVALID);
        }
        let c = r.contexts.get(&id).ok_or(INVALID_CONTEXT)?;
        let m = c.modules.get(&(module as usize)).ok_or(INVALID_HANDLE)?;
        let entry = m
            .entries
            .iter()
            .position(|e| e.entry.as_bytes() == CStr::from_ptr(name).to_bytes())
            .ok_or(500)?;
        let fid = token(r)?;
        r.contexts
            .get_mut(&id)
            .ok_or(INVALID_CONTEXT)?
            .functions
            .insert(
                fid,
                OwnedFunction {
                    module: module as usize,
                    entry,
                },
            );
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
        c.functions.retain(|_, v| v.module != mid);
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
        let owned = c
            .functions
            .get(&(function as usize))
            .ok_or(INVALID_HANDLE)?;
        let m = c.modules.get(&owned.module).ok_or(INVALID_HANDLE)?;
        let entry = m.entries.get(owned.entry).ok_or(INVALID_HANDLE)?;
        if shared != 0 || !stream.is_null() || !extra.is_null() {
            return Err(UNSUPPORTED);
        }
        let d = &b.devices[c.native.device];
        let grid = [gx, gy, gz];
        let block = [bx, by, bz];
        d.validate_launch(grid, block).map_err(|_| INVALID)?;
        if !entry.params.is_empty() && parameters.is_null() {
            return Err(INVALID);
        }
        let mut arguments = Vec::new();
        for (i, param) in entry.params.iter().enumerate() {
            let pointer = parameters.add(i).read();
            if pointer.is_null() {
                return Err(INVALID);
            }
            let data = match param.kind {
                ParamKind::Pointer => {
                    let value = pointer.cast::<u64>().read_unaligned();
                    if !value.is_multiple_of(u64::from(param.alignment))
                        || !c.contains_device(value, param.alignment as usize)
                    {
                        return Err(INVALID);
                    }
                    value.to_ne_bytes().to_vec()
                }
                ParamKind::U64 => pointer
                    .cast::<u64>()
                    .read_unaligned()
                    .to_ne_bytes()
                    .to_vec(),
                ParamKind::U32 | ParamKind::F32 => pointer
                    .cast::<u32>()
                    .read_unaligned()
                    .to_ne_bytes()
                    .to_vec(),
            };
            arguments.push(data);
        }
        b.launch_entry_3d(
            &mut c.native,
            &m.native,
            owned.entry,
            &arguments,
            grid,
            block,
        )
        .map_err(native_error)
    })
}

/// Query one module-owned symbol. Outputs must be nonoverlapping writable storage.
/// # Safety
/// Each non-null output must be writable for its type. Name must be readable up
/// to its NUL terminator, or 129 bytes when no terminator occurs within the bound.
#[no_mangle]
pub unsafe extern "system" fn cuModuleGetGlobal_v2(
    output: *mut u64,
    size: *mut usize,
    module: *mut c_void,
    name: *const c_char,
) -> i32 {
    invoke(|r| {
        if !output.is_null() {
            output.write(0);
        }
        if !size.is_null() {
            size.write(0);
        }
        let id = context_id(r)?;
        let c = &r.contexts[&id];
        let m = c.modules.get(&(module as usize)).ok_or(INVALID_HANDLE)?;
        if (output.is_null() && size.is_null()) || name.is_null() {
            return Err(INVALID);
        }
        let mut bytes = Vec::new();
        for index in 0..=128 {
            let b = name.add(index).read() as u8;
            if b == 0 {
                break;
            }
            if index == 128 {
                return Err(INVALID);
            }
            bytes.push(b);
        }
        if bytes.is_empty() {
            return Err(INVALID);
        }
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        let g = m
            .globals
            .iter()
            .find(|g| g.name.as_bytes() == bytes)
            .ok_or(500)?;
        if matches!(g.storage, ct_ptx::GlobalStorage::Unsupported) {
            return Err(UNSUPPORTED);
        }
        let native = m.native.global(&g.name).ok_or(UNKNOWN)?;
        if !output.is_null() {
            output.write(native.pointer);
        }
        if !size.is_null() {
            size.write(native.size);
        }
        Ok(())
    })
}

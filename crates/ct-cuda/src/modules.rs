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
    for i in 0..=262144 {
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
/// readable PTX string. This interface accepts trusted code, not arbitrary cubins.
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

//! Bounded CPU snapshots of compiler wrappers. Pointers are caller-readable.
use crate::registration::{reserve, Wrapper};
use std::ffi::c_void;
pub struct OwnedImages {
    pub primary: Vec<u8>,
    pub prelinked: Vec<Vec<u8>>,
    pub version: u32,
    pub raw_bytes: usize,
}
fn map(e: ct_fatbin::Error) -> i32 {
    match e {
        ct_fatbin::Error::Invalid => 218,
        ct_fatbin::Error::Unsupported => 801,
        ct_fatbin::Error::Allocation => 2,
    }
}
#[cfg(test)]
thread_local! {pub static FAIL_COPY_AFTER:std::cell::Cell<Option<usize>>=const {std::cell::Cell::new(None)};}
unsafe fn copy_one(pointer: usize, remaining: usize) -> Result<Vec<u8>, i32> {
    if pointer == 0 {
        return Err(1);
    }
    let header = unsafe { std::slice::from_raw_parts(pointer as *const u8, 16) };
    let size = ct_fatbin::image_size(header).map_err(map)?;
    if size > remaining {
        return Err(801);
    }
    #[cfg(test)]
    if let Some(n) = FAIL_COPY_AFTER.get() {
        if n == 0 {
            return Err(2);
        }
        FAIL_COPY_AFTER.set(Some(n - 1));
    }
    let mut b = Vec::new();
    reserve(&mut b, size)?;
    b.extend_from_slice(unsafe { std::slice::from_raw_parts(pointer as *const u8, size) });
    ct_fatbin::inspect_container(&b).map_err(map)?;
    Ok(b)
}
pub unsafe fn copy_images(wrapper: *const c_void, remaining: usize) -> Result<OwnedImages, i32> {
    if wrapper.is_null() {
        return Err(1);
    }
    let w = unsafe { wrapper.cast::<Wrapper>().read_unaligned() };
    if w.magic != 0x466243b1 || w.data == 0 {
        return Err(1);
    }
    if !matches!(w.version, 1 | 2) || (w.version == 1 && w.extra != 0) {
        return Err(801);
    }
    if w.version == 2 && w.extra == 0 {
        return Err(1);
    }
    let primary = unsafe { copy_one(w.data, remaining) }?;
    if w.version == 1 {
        ct_fatbin::extract_candidates(&primary).map_err(map)?;
    }
    let mut result = OwnedImages {
        raw_bytes: primary.len(),
        primary,
        prelinked: Vec::new(),
        version: w.version,
    };
    if w.version == 1 {
        return Ok(result);
    }
    let mut seen = [0usize; 33];
    seen[0] = w.data;
    let mut count = 1;
    for slot in 0..=32 {
        let pointer = unsafe { (w.extra as *const usize).add(slot).read_unaligned() };
        if pointer == 0 {
            return if slot == 0 { Err(1) } else { Ok(result) };
        }
        if slot == 32 {
            return Err(801);
        }
        if seen[..count].contains(&pointer) {
            continue;
        }
        let bytes = unsafe { copy_one(pointer, remaining - result.raw_bytes) }?;
        reserve(&mut result.prelinked, 1)?;
        result.raw_bytes += bytes.len();
        result.prelinked.push(bytes);
        seen[count] = pointer;
        count += 1;
    }
    Err(801)
}

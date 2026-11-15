//! Native host allocations are owned separately from CUDA device-address ranges.
use super::*;
const MAX_BYTES: usize = 256 * 1024 * 1024;
#[derive(Default)]
pub(super) struct HostAllocations {
    records: Vec<(u64, usize)>,
    bytes: usize,
}
impl HostAllocations {
    fn reserve(&mut self, size: usize) -> Result<(), i32> {
        if size == 0 {
            return Err(INVALID);
        }
        if self.records.len() >= 128 || self.bytes.checked_add(size).is_none_or(|n| n > MAX_BYTES) {
            return Err(2);
        }
        self.records.try_reserve_exact(1).map_err(|_| 2)
    }
    fn commit(&mut self, pointer: u64, size: usize) -> Result<(), i32> {
        let end = pointer.checked_add(size as u64).ok_or(UNKNOWN)?;
        if pointer == 0
            || size == 0
            || self.records.len() >= self.records.capacity()
            || self
                .records
                .iter()
                .any(|&(p, n)| pointer < p + n as u64 && p < end)
        {
            return Err(UNKNOWN);
        }
        let bytes = self
            .bytes
            .checked_add(size)
            .filter(|&n| n <= MAX_BYTES)
            .ok_or(UNKNOWN)?;
        self.records.push((pointer, size));
        self.bytes = bytes;
        Ok(())
    }
    fn size(&self, pointer: u64) -> Option<usize> {
        self.records
            .iter()
            .find(|&&(p, _)| p == pointer)
            .map(|&(_, n)| n)
    }
    fn remove(&mut self, pointer: u64) -> bool {
        if let Some(i) = self.records.iter().position(|&(p, _)| p == pointer) {
            let (_, size) = self.records.remove(i);
            self.bytes -= size;
            true
        } else {
            false
        }
    }
    pub(super) fn bases(&self) -> impl Iterator<Item = u64> + '_ {
        self.records.iter().map(|&(p, _)| p)
    }
    pub(super) fn len(&self) -> usize {
        self.records.len()
    }
}
fn flags(value: u32) -> CudaResult {
    if value & !7 != 0 {
        Err(INVALID)
    } else if value != 0 {
        Err(UNSUPPORTED)
    } else {
        Ok(())
    }
}
/// # Safety
/// output must be writable for a host pointer.
#[no_mangle]
pub unsafe extern "system" fn cuMemHostAlloc(
    output: *mut *mut c_void,
    size: usize,
    options: u32,
) -> i32 {
    if output.is_null() || size == 0 {
        return INVALID;
    }
    if let Err(code) = flags(options) {
        return code;
    }
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        c.host.reserve(size)?;
        let pointer = b.allocate_host(&mut c.native, size).map_err(native_error)?;
        if c.host.commit(pointer, size).is_err() {
            // Uncertain/malformed ownership: do not free an alias of existing storage.
            c.native.poisoned = true;
            return Err(UNKNOWN);
        }
        unsafe {
            output.write(pointer as *mut c_void);
        }
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuMemFreeHost(pointer: *mut c_void) -> i32 {
    if pointer.is_null() {
        return INVALID;
    }
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        let pointer = pointer as u64;
        if c.host.size(pointer).is_none() {
            return Err(INVALID);
        }
        b.free(&mut c.native, pointer).map_err(native_error)?;
        c.host.remove(pointer);
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn host_book_reserves_before_commit_and_frees_exact_bases() {
        let mut book = HostAllocations::default();
        assert_eq!(book.reserve(0), Err(1));
        book.reserve(16).unwrap();
        book.commit(0x1000, 16).unwrap();
        assert_eq!(book.bytes, 16);
        assert_eq!(book.size(0x1000), Some(16));
        assert_eq!(book.size(0x1001), None);
        assert!(!book.remove(0x1001));
        assert!(book.remove(0x1000));
        assert!(!book.remove(0x1000));
        assert_eq!(book.bytes, 0);
    }
    #[test]
    fn host_book_enforces_count_byte_and_malformed_span_bounds() {
        let mut book = HostAllocations::default();
        assert_eq!(book.reserve(MAX_BYTES + 1), Err(2));
        book.reserve(MAX_BYTES).unwrap();
        book.commit(0x1000, MAX_BYTES).unwrap();
        assert_eq!(book.reserve(1), Err(2));
        book.remove(0x1000);
        for i in 0..128u64 {
            book.reserve(4).unwrap();
            book.commit(0x1000 + i * 16, 4).unwrap();
        }
        assert_eq!(book.reserve(4), Err(2));
        assert!(book.remove(0x1000));
        book.reserve(4).unwrap();
        for pointer in [0, 0x1010, u64::MAX - 1] {
            assert_eq!(book.commit(pointer, 4), Err(999));
        }
        assert_eq!(book.records.len(), 127);
    }
    #[test]
    fn host_flags_distinguish_unknown_from_unsupported_bits() {
        assert_eq!(flags(0), Ok(()));
        for flag in [1, 2, 3, 4, 5, 6, 7] {
            assert_eq!(flags(flag), Err(801));
        }
        for flag in [8, 9, u32::MAX] {
            assert_eq!(flags(flag), Err(1));
        }
    }
}

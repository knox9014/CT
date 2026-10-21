//! Eager, serialized device-memory subset; no stream or peer-memory semantics.
use super::*;

fn copy_ranges(
    ranges: &AllocationRanges,
    destination: u64,
    source: u64,
    size: usize,
) -> CudaResult {
    if !ranges.contains(destination, size) || !ranges.contains(source, size) {
        return Err(INVALID);
    }
    // contains established nonoverflowing ends. Overlap is a CT restriction,
    // including identical positive spans; it is not a memmove implementation.
    if size > 0 && destination < source + size as u64 && source < destination + size as u64 {
        return Err(INVALID);
    }
    Ok(())
}

fn fill_range(
    ranges: &AllocationRanges,
    destination: u64,
    count: usize,
    width: usize,
) -> Result<usize, i32> {
    let size = count.checked_mul(width).ok_or(INVALID)?;
    if !destination.is_multiple_of(width as u64) || !ranges.contains(destination, size) {
        return Err(INVALID);
    }
    Ok(size)
}

#[no_mangle]
pub extern "system" fn cuMemcpyDtoD_v2(destination: u64, source: u64, size: usize) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        copy_ranges(&c.allocations, destination, source, size)?;
        b.copy_device(&mut c.native, destination, source, size)
            .map_err(native_error)
    })
}

fn fill(destination: u64, value: u32, count: usize, width: usize) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        let size = fill_range(&c.allocations, destination, count, width)?;
        b.fill_device(&mut c.native, destination, value, width, size)
            .map_err(native_error)
    })
}

#[no_mangle]
pub extern "system" fn cuMemsetD8_v2(destination: u64, value: u8, count: usize) -> i32 {
    fill(destination, u32::from(value), count, 1)
}
#[no_mangle]
pub extern "system" fn cuMemsetD16_v2(destination: u64, value: u16, count: usize) -> i32 {
    fill(destination, u32::from(value), count, 2)
}
#[no_mangle]
pub extern "system" fn cuMemsetD32_v2(destination: u64, value: u32, count: usize) -> i32 {
    fill(destination, value, count, 4)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn device_copy_checks_both_ranges_and_excludes_positive_overlap() {
        let mut ranges = AllocationRanges::default();
        assert!(ranges.insert(0x1000, 64));
        for (dst, src, size, expected) in [
            (0x1020, 0x1000, 32, Ok(())),
            (0x1000, 0x1020, 32, Ok(())),
            (0x1001, 0x1000, 32, Err(1)),
            (0x1000, 0x1000, 1, Err(1)),
            (0x1000, 0x1000, 0, Ok(())),
            (0x1040, 0x1000, 0, Err(1)),
            (0x1000, 0x103f, 2, Err(1)),
            (u64::MAX, 0x1000, 2, Err(1)),
        ] {
            assert_eq!(copy_ranges(&ranges, dst, src, size), expected);
        }
    }
    #[test]
    fn typed_fill_checks_count_overflow_alignment_and_zero_address_policy() {
        let mut ranges = AllocationRanges::default();
        assert!(ranges.insert(0x1000, 64));
        assert_eq!(fill_range(&ranges, 0x1000, 16, 4), Ok(64));
        assert_eq!(fill_range(&ranges, 0x1002, 31, 2), Ok(62));
        assert_eq!(fill_range(&ranges, 0x1002, 1, 4), Err(1));
        assert_eq!(fill_range(&ranges, 0x1001, 0, 2), Err(1));
        assert_eq!(fill_range(&ranges, 0x1000, usize::MAX / 2 + 1, 2), Err(1));
        assert_eq!(fill_range(&ranges, 0x1000, 0, 4), Ok(0));
        assert_eq!(fill_range(&ranges, 0x1040, 0, 4), Err(1));
    }
}

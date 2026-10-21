//! Registry metadata only. No peer access or full unified-addressing claim.
use super::*;

fn unique_allocation<'a>(
    candidates: impl Iterator<Item = (usize, bool, &'a AllocationRanges)>,
    pointer: u64,
) -> Result<(usize, u64, usize), i32> {
    let mut found = None;
    for (device, poisoned, ranges) in candidates {
        if let Some((base, bytes)) = ranges.locate(pointer) {
            if found.replace((device, poisoned, base, bytes)).is_some() {
                return Err(UNSUPPORTED);
            }
        }
    }
    let (device, poisoned, base, bytes) = found.ok_or(INVALID)?;
    if poisoned {
        return Err(UNKNOWN);
    }
    Ok((device, base, bytes))
}

/// # Safety
/// Each non-null output must be writable for its declared type. Outputs must
/// not overlap. Both outputs may be null. Errors leave output storage unchanged.
#[no_mangle]
pub unsafe extern "system" fn cuMemGetAddressRange_v2(
    base: *mut u64,
    size: *mut usize,
    pointer: u64,
) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let c = &r.contexts[&id];
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        let (allocation, bytes) = c.allocations.locate(pointer).ok_or(500)?;
        if !base.is_null() {
            base.write(allocation);
        }
        if !size.is_null() {
            size.write(bytes);
        }
        Ok(())
    })
}

fn supported_attribute(attribute: i32) -> CudaResult {
    match attribute {
        8 | 9 | 11 | 12 => Ok(()),
        1..=20 => Err(UNSUPPORTED),
        _ => Err(INVALID),
    }
}

/// # Safety
/// data must be aligned and writable for the requested attribute type: u32 for
/// 8, i32 for9, u64 for11, usize for12. Errors never write to data.
#[no_mangle]
pub unsafe extern "system" fn cuPointerGetAttribute(
    data: *mut c_void,
    attribute: i32,
    pointer: u64,
) -> i32 {
    invoke(|r| {
        backend(r)?;
        if data.is_null() {
            return Err(INVALID);
        }
        supported_attribute(attribute)?;
        let (device, base, bytes) = unique_allocation(
            r.contexts
                .values()
                .map(|c| (c.native.device, c.native.poisoned, &c.allocations)),
            pointer,
        )?;
        match attribute {
            8 => data.cast::<u32>().write(0), // Only native device allocations exist.
            9 => data
                .cast::<i32>()
                .write(i32::try_from(device).map_err(|_| UNKNOWN)?),
            11 => data.cast::<u64>().write(base),
            12 => data.cast::<usize>().write(bytes),
            _ => unreachable!(),
        }
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn metadata_rejects_ambiguous_poisoned_and_missing_allocations() {
        let mut first = AllocationRanges::default();
        let mut second = AllocationRanges::default();
        assert!(first.insert(0x1000, 32));
        assert!(second.insert(0x1010, 32));
        assert_eq!(
            unique_allocation([(2, false, &first)].into_iter(), 0x101f),
            Ok((2, 0x1000, 32))
        );
        assert_eq!(
            unique_allocation(
                [(2, false, &first), (3, false, &second)].into_iter(),
                0x1010
            ),
            Err(801)
        );
        assert_eq!(
            unique_allocation([(2, true, &first)].into_iter(), 0x1000),
            Err(999)
        );
        assert_eq!(
            unique_allocation([(2, false, &first)].into_iter(), 0x1020),
            Err(1)
        );
        assert_eq!(unique_allocation(std::iter::empty(), 0), Err(1));
    }
    #[test]
    fn pointer_attribute_policy_distinguishes_known_unsupported_and_unknown() {
        for attribute in 1..=20 {
            let expected = if [8, 9, 11, 12].contains(&attribute) {
                Ok(())
            } else {
                Err(801)
            };
            assert_eq!(supported_attribute(attribute), expected);
        }
        for attribute in [-1, 0, 21, i32::MAX] {
            assert_eq!(supported_attribute(attribute), Err(1));
        }
    }
}

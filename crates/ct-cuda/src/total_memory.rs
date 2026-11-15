//! Bounded device total, independent of current context and allocation budgets.
use super::*;

fn query_total_memory(r: &Runtime, device: i32) -> Result<usize, i32> {
    let backend = backend(r)?;
    if device < 0 || device as usize >= backend.devices.len() {
        return Err(INVALID_DEVICE);
    }
    let total = backend
        .total_memory(device as usize)
        .map_err(native_error)?;
    usize::try_from(total).map_err(|_| UNSUPPORTED)
}

/// Total advertised for one qualified memory property; not free memory/budget.
///
/// # Safety
/// A non-null output must be writable for one size_t. Only the v3020 ABI is exposed.
#[no_mangle]
pub unsafe extern "system" fn cuDeviceTotalMem_v2(output: *mut usize, device: i32) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    output.write(0);
    invoke(|r| {
        output.write(query_total_memory(r, device)?);
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn total_memory_requires_initialization_before_device_query() {
        let runtime = Runtime::default();
        for device in [0, -1, i32::MAX] {
            assert_eq!(query_total_memory(&runtime, device), Err(3));
        }
    }

    #[test]
    fn total_memory_typed_null_output_is_rejected_without_initialization() {
        let function: unsafe extern "system" fn(*mut usize, i32) -> i32 = cuDeviceTotalMem_v2;
        assert_eq!(unsafe { function(std::ptr::null_mut(), 0) }, 1);
    }
}

//! Optional metadata query; no allocation or free-memory/budget estimate.
use super::*;

impl Backend {
    /// Driver-advertised total for a single memory property with sampled count1.
    /// Multiple domains, zero totals or inconsistent counts are unsupported.
    /// Count observations do not establish an atomic device-property snapshot.
    pub fn total_memory(&self, device: usize) -> NativeResult<u64> {
        let device = self.devices.get(device).ok_or(BAD_ARGUMENT)?;
        type Query = unsafe extern "C" fn(Handle, *mut u32, *mut DeviceMemoryProperties) -> u32;
        let query: Query = unsafe {
            self.api
                .symbol(b"zeDeviceGetMemoryProperties\0")
                .map_err(|_| UNSUPPORTED)?
        };
        let check = |code| {
            if matches!(code, 0x70000001 | 0x70000006) {
                self.api.keep_loaded.set(true);
            }
            if code == 0 {
                Ok(())
            } else {
                Err(code)
            }
        };
        let mut count = 0;
        check(unsafe { query(device.native as Handle, &mut count, null_mut()) })?;
        if count != 1 {
            return Err(UNSUPPORTED);
        }
        let mut property: DeviceMemoryProperties = unsafe { blank() };
        property.stype = 7;
        check(unsafe { query(device.native as Handle, &mut count, &mut property) })?;
        if count != 1 || property.total_size == 0 {
            return Err(UNSUPPORTED);
        }
        count = 0;
        check(unsafe { query(device.native as Handle, &mut count, null_mut()) })?;
        if count != 1 {
            return Err(UNSUPPORTED);
        }
        Ok(property.total_size)
    }
}

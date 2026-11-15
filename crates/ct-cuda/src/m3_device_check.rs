use super::{backend, invoke, INVALID, INVALID_DEVICE};

fn resolve(uuids: impl IntoIterator<Item = [u8; 16]>, wanted: [u8; 16]) -> Option<i32> {
    if wanted == [0; 16] {
        return None;
    }
    let mut matches = uuids
        .into_iter()
        .enumerate()
        .filter(|(_, id)| *id == wanted);
    let (ordinal, _) = matches.next()?;
    if matches.next().is_some() {
        return None;
    }
    i32::try_from(ordinal).ok()
}

/// Diagnostic only. Output must be writable for one C int.
#[no_mangle]
pub unsafe extern "system" fn ctM3ResolveDevice(output: *mut i32) -> i32 {
    invoke(|r| {
        if output.is_null() {
            return Err(INVALID);
        }
        output.write(-1);
        let id = std::env::var("CT_M3_DEVICE_UUID").map_err(|_| INVALID)?;
        if id.len() != 32 || !id.bytes().all(|byte| byte.is_ascii_hexdigit()) {
            return Err(INVALID);
        }
        let mut wanted = [0; 16];
        for (i, byte) in wanted.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&id[i * 2..i * 2 + 2], 16).map_err(|_| INVALID)?;
        }
        let ordinal = resolve(backend(r)?.devices.iter().map(|device| device.uuid), wanted)
            .ok_or(INVALID_DEVICE)?;
        output.write(ordinal);
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::resolve;

    #[test]
    fn physical_selection_survives_reordering_and_rejects_missing_or_duplicate_ids() {
        let a = [1; 16];
        let b = [2; 16];
        assert_eq!(resolve([a, b], b), Some(1));
        assert_eq!(resolve([b, a], b), Some(0));
        assert_eq!(resolve([a], b), None);
        assert_eq!(resolve([b, b], b), None);
        assert_eq!(resolve([[0; 16]], [0; 16]), None);
    }
}

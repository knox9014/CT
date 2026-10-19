//! Bounded, deliberately narrow decoder for raw CUDA fatbin PTX images.
//! No native libraries, decompression, NVIDIA code execution or pointer chasing.
pub const MAGIC: [u8; 4] = 0xba55ed50u32.to_le_bytes();
pub const MAX_IMAGE_SIZE: usize = 16 * 1024 * 1024;
pub const MAX_PTX_SIZE: usize = 262144;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    Invalid,
    Unsupported,
}

fn u16_at(b: &[u8], n: usize) -> Result<u16, Error> {
    Ok(u16::from_le_bytes(
        b.get(n..n.checked_add(2).ok_or(Error::Invalid)?)
            .ok_or(Error::Invalid)?
            .try_into()
            .map_err(|_| Error::Invalid)?,
    ))
}
fn u32_at(b: &[u8], n: usize) -> Result<u32, Error> {
    Ok(u32::from_le_bytes(
        b.get(n..n.checked_add(4).ok_or(Error::Invalid)?)
            .ok_or(Error::Invalid)?
            .try_into()
            .map_err(|_| Error::Invalid)?,
    ))
}
fn u64_at(b: &[u8], n: usize) -> Result<u64, Error> {
    Ok(u64::from_le_bytes(
        b.get(n..n.checked_add(8).ok_or(Error::Invalid)?)
            .ok_or(Error::Invalid)?
            .try_into()
            .map_err(|_| Error::Invalid)?,
    ))
}

/// Read only the fixed header and reject a declared size before allocating or
/// forming a C-ABI slice. Full image readability remains a caller precondition.
pub fn image_size(header: &[u8]) -> Result<usize, Error> {
    if header.len() < 16 || header[..4] != MAGIC {
        return Err(Error::Invalid);
    }
    if u16_at(header, 4)? != 1 || u16_at(header, 6)? != 16 {
        return Err(Error::Unsupported);
    }
    let payload = usize::try_from(u64_at(header, 8)?).map_err(|_| Error::Invalid)?;
    let size = 16usize.checked_add(payload).ok_or(Error::Invalid)?;
    if size > MAX_IMAGE_SIZE {
        return Err(Error::Unsupported);
    }
    if !payload.is_multiple_of(8) {
        return Err(Error::Invalid);
    }
    Ok(size)
}

fn ptx_record<'a>(header: &[u8], payload: &'a [u8]) -> Result<&'a [u8], Error> {
    if u32_at(header, 16)? != 0
        || u32_at(header, 40)? != 0x45
        || header[44..64].iter().any(|b| *b != 0)
    {
        return Err(Error::Unsupported);
    }
    if !matches!(
        (
            u16_at(header, 26)?,
            u16_at(header, 24)?,
            u32_at(header, 28)?
        ),
        (7, 0, 50) | (8, 0, 52)
    ) {
        return Err(Error::Unsupported);
    }
    // Observed nvFatbin12.4 layout: bounded identifier followed by an option
    // descriptor. Nonempty JIT options are rejected rather than silently ignored.
    let metadata = u32_at(header, 20)? as usize;
    if metadata < 64
        || !metadata.is_multiple_of(8)
        || metadata.checked_add(8).ok_or(Error::Invalid)? >= header.len()
    {
        return Err(Error::Invalid);
    }
    let name_offset = u32_at(header, 32)? as usize;
    let name_size = u32_at(header, 36)? as usize;
    if name_size > 1024 {
        return Err(Error::Unsupported);
    }
    if name_offset == 0 {
        if name_size != 0 || header[64..metadata].iter().any(|b| *b != 0) {
            return Err(Error::Invalid);
        }
    } else {
        let end = name_offset.checked_add(name_size).ok_or(Error::Invalid)?;
        if name_offset < 64 || end >= metadata {
            return Err(Error::Invalid);
        }
        if header[64..name_offset].iter().any(|b| *b != 0)
            || header[name_offset..end]
                .iter()
                .any(|b| !b.is_ascii() || *b == 0)
            || header[end..metadata].iter().any(|b| *b != 0)
        {
            return Err(Error::Invalid);
        }
    }
    let option_offset = u32_at(header, metadata)? as usize;
    if u32_at(header, metadata + 4)? != 0 {
        return Err(Error::Unsupported);
    }
    if option_offset != metadata + 8
        || option_offset >= header.len()
        || header[option_offset..].iter().any(|b| *b != 0)
    {
        return Err(Error::Invalid);
    }
    let end = payload.iter().position(|b| *b == 0).ok_or(Error::Invalid)?;
    if end == 0 || end > MAX_PTX_SIZE {
        return Err(Error::Unsupported);
    }
    if !payload[..end].is_ascii() || payload[end..].iter().any(|b| *b != 0) {
        return Err(Error::Invalid);
    }
    Ok(&payload[..end])
}

/// Extract exactly one uncompressed PTX module. Opaque CUBIN records are skipped
/// only after checking their byte ranges; compressed/multiple PTX is unsupported.
pub fn extract_ptx(image: &[u8]) -> Result<&[u8], Error> {
    if image_size(image)? != image.len() {
        return Err(Error::Invalid);
    }
    let mut offset = 16usize;
    let mut count = 0;
    let mut selected = None;
    while offset < image.len() {
        count += 1;
        if count > 256 {
            return Err(Error::Unsupported);
        }
        let remainder = &image[offset..];
        let kind = u16_at(remainder, 0)?;
        if u16_at(remainder, 2)? != 0x101 {
            return Err(Error::Unsupported);
        }
        let header_size = u32_at(remainder, 4)? as usize;
        let payload_size = usize::try_from(u64_at(remainder, 8)?).map_err(|_| Error::Invalid)?;
        if !(64..=4096).contains(&header_size)
            || !header_size.is_multiple_of(8)
            || payload_size == 0
            || !payload_size.is_multiple_of(8)
        {
            return Err(Error::Invalid);
        }
        let end = header_size
            .checked_add(payload_size)
            .ok_or(Error::Invalid)?;
        let record = remainder.get(..end).ok_or(Error::Invalid)?;
        match kind {
            1 => {
                if selected.is_some() {
                    return Err(Error::Unsupported);
                }
                selected = Some(ptx_record(&record[..header_size], &record[header_size..])?);
            }
            2 => {} // NVIDIA machine code is never executed.
            _ => return Err(Error::Unsupported),
        }
        offset = offset.checked_add(end).ok_or(Error::Invalid)?;
    }
    selected.ok_or(Error::Unsupported)
}

//! Bounded, deliberately narrow decoder for raw CUDA fatbin PTX images.
//! No native libraries, NVIDIA code execution or pointer chasing.
use std::borrow::Cow;
pub const MAGIC: [u8; 4] = 0xba55ed50u32.to_le_bytes();
pub const MAX_IMAGE_SIZE: usize = 16 * 1024 * 1024;
pub const MAX_PTX_SIZE: usize = 262144;
pub const MAX_CANDIDATES: usize = 8;
pub const MAX_TOTAL_DECODED_SIZE: usize = 1024 * 1024;

#[cfg(test)]
thread_local! {
    static RESERVE_FAULT: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
    static RESERVE_CALLS: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PtxProfile {
    pub major: u16,
    pub minor: u16,
    pub target: u32,
}
#[derive(Debug)]
pub struct PtxCandidate<'a> {
    pub profile: PtxProfile,
    pub text: Cow<'a, [u8]>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    Invalid,
    Unsupported,
    Allocation,
}

fn reserve<T>(out: &mut Vec<T>, additional: usize) -> Result<(), Error> {
    #[cfg(test)]
    {
        RESERVE_CALLS.set(RESERVE_CALLS.get() + 1);
        if RESERVE_FAULT.get() {
            return Err(Error::Allocation);
        }
    }
    out.try_reserve_exact(additional)
        .map_err(|_| Error::Allocation)
}

fn reserve_bytes(out: &mut Vec<u8>, additional: usize) -> Result<(), Error> {
    reserve(out, additional)
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

/// Outer-container facts only; neither instruction validation nor executability.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ContainerInfo {
    pub record_count: u16,
    pub ptx_records: u16,
    pub machine_records: u16,
}
pub fn inspect_container(image: &[u8]) -> Result<ContainerInfo, Error> {
    if image_size(image)? != image.len() {
        return Err(Error::Invalid);
    }
    let mut info = ContainerInfo {
        record_count: 0,
        ptx_records: 0,
        machine_records: 0,
    };
    let mut offset = 16usize;
    while offset < image.len() {
        if info.record_count == 256 {
            return Err(Error::Unsupported);
        }
        let r = &image[offset..];
        let kind = u16_at(r, 0)?;
        if u16_at(r, 2)? != 0x101 {
            return Err(Error::Unsupported);
        }
        let header = u32_at(r, 4)? as usize;
        let payload = usize::try_from(u64_at(r, 8)?).map_err(|_| Error::Invalid)?;
        if !(64..=4096).contains(&header)
            || !header.is_multiple_of(8)
            || payload == 0
            || !payload.is_multiple_of(8)
        {
            return Err(Error::Invalid);
        }
        let extent = header.checked_add(payload).ok_or(Error::Invalid)?;
        r.get(..extent).ok_or(Error::Invalid)?;
        match kind {
            1 => info.ptx_records += 1,
            2 => info.machine_records += 1,
            _ => return Err(Error::Unsupported),
        }
        info.record_count += 1;
        offset = offset.checked_add(extent).ok_or(Error::Invalid)?;
    }
    Ok(info)
}

// Raw LZ4 block sequences: literal length, literals, LE offset, match length.
// Length extensions and overlapping matches follow the LZ4 block format.
// No unchecked input indexing or output growth beyond the declared/capped size.
fn decompress(block: &[u8], size: usize) -> Result<Vec<u8>, Error> {
    if size == 0 || size > MAX_PTX_SIZE + 8 {
        return Err(Error::Unsupported);
    }
    fn length(block: &[u8], pos: &mut usize, mut n: usize) -> Result<usize, Error> {
        if n == 15 {
            loop {
                let byte = *block.get(*pos).ok_or(Error::Invalid)? as usize;
                *pos += 1;
                n = n.checked_add(byte).ok_or(Error::Invalid)?;
                if byte != 255 {
                    break;
                }
            }
        }
        Ok(n)
    }
    let mut out = Vec::new();
    reserve_bytes(&mut out, size)?;
    let mut pos = 0;
    loop {
        let token = *block.get(pos).ok_or(Error::Invalid)?;
        pos += 1;
        let literals = length(block, &mut pos, (token >> 4) as usize)?;
        let end = pos.checked_add(literals).ok_or(Error::Invalid)?;
        if literals > size - out.len() {
            return Err(Error::Invalid);
        }
        out.extend_from_slice(block.get(pos..end).ok_or(Error::Invalid)?);
        pos = end;
        if pos == block.len() {
            break;
        }
        let offset = u16_at(block, pos)? as usize;
        pos += 2;
        if offset == 0 || offset > out.len() {
            return Err(Error::Invalid);
        }
        let count = length(block, &mut pos, (token & 15) as usize)?
            .checked_add(4)
            .ok_or(Error::Invalid)?;
        if count > size - out.len() {
            return Err(Error::Invalid);
        }
        for _ in 0..count {
            let byte = out[out.len() - offset];
            out.push(byte);
        }
    }
    if out.len() != size {
        return Err(Error::Invalid);
    }
    Ok(out)
}

enum RecordProfile {
    NvFatbin,
    Nvcc12,
}

fn record_profile(header: &[u8]) -> Result<RecordProfile, Error> {
    let profile = match u32_at(header, 40)? {
        0x45 | 0x2045 => RecordProfile::NvFatbin,
        0x41 | 0x2041 if header.len() == 72 => RecordProfile::Nvcc12,
        _ => return Err(Error::Unsupported),
    };
    if header[44..56].iter().any(|b| *b != 0) {
        return Err(Error::Unsupported);
    }
    let ptx = (
        u16_at(header, 26)?,
        u16_at(header, 24)?,
        u32_at(header, 28)?,
    );
    match profile {
        RecordProfile::NvFatbin => {
            if !matches!(ptx, (7, 0, 50) | (8, 0, 52)) {
                return Err(Error::Unsupported);
            }
            nvfatbin_metadata(header)?;
        }
        RecordProfile::Nvcc12 => {
            if ptx != (8, 0, 52)
                || u32_at(header, 20)? != 64
                || u32_at(header, 32)? != 0
                || u32_at(header, 36)? != 0
                || header[64..72].iter().any(|b| *b != 0)
            {
                return Err(Error::Unsupported);
            }
        }
    }
    Ok(profile)
}

fn nvfatbin_metadata(header: &[u8]) -> Result<(), Error> {
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
    Ok(())
}

fn ptx_record<'a>(header: &[u8], payload: &'a [u8]) -> Result<Cow<'a, [u8]>, Error> {
    record_profile(header)?;
    let flags = u32_at(header, 40)?;
    let compressed_size = u32_at(header, 16)? as usize;
    let decoded_size = usize::try_from(u64_at(header, 56)?).map_err(|_| Error::Invalid)?;
    let mut decoded = if matches!(flags, 0x2045 | 0x2041) {
        if compressed_size == 0
            || compressed_size > payload.len()
            || payload.len() - compressed_size >= 8
            || payload[compressed_size..].iter().any(|b| *b != 0)
        {
            return Err(Error::Invalid);
        }
        Cow::Owned(decompress(&payload[..compressed_size], decoded_size)?)
    } else {
        if compressed_size != 0 || decoded_size != 0 {
            return Err(Error::Invalid);
        }
        Cow::Borrowed(payload)
    };
    let end = decoded.iter().position(|b| *b == 0).ok_or(Error::Invalid)?;
    if end == 0 || end > MAX_PTX_SIZE {
        return Err(Error::Unsupported);
    }
    if !decoded[..end].is_ascii() || decoded[end..].iter().any(|b| *b != 0) {
        return Err(Error::Invalid);
    }
    match &mut decoded {
        Cow::Borrowed(bytes) => Ok(Cow::Borrowed(&bytes[..end])),
        Cow::Owned(bytes) => {
            bytes.truncate(end);
            Ok(decoded)
        }
    }
}

/// Extract exactly one plain or bounded LZ4-compressed PTX module. Opaque CUBIN
/// records are skipped after checking byte ranges; multiple PTX is unsupported.
pub fn extract_ptx(image: &[u8]) -> Result<Cow<'_, [u8]>, Error> {
    let mut candidates = extract_candidates(image)?;
    if candidates.len() != 1 {
        return Err(Error::Unsupported);
    }
    Ok(candidates.pop().ok_or(Error::Unsupported)?.text)
}

/// Extract bounded alternative images without choosing a program or linking it.
/// Each candidate's declared decoded/padded size is charged before decompression.
pub fn extract_candidates(image: &[u8]) -> Result<Vec<PtxCandidate<'_>>, Error> {
    if image_size(image)? != image.len() {
        return Err(Error::Invalid);
    }
    let mut offset = 16usize;
    let mut count = 0;
    let mut candidates = Vec::new();
    let mut decoded_total = 0usize;
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
                if candidates.len() >= MAX_CANDIDATES {
                    return Err(Error::Unsupported);
                }
                let declared = if matches!(u32_at(record, 40)?, 0x2045 | 0x2041) {
                    let size = usize::try_from(u64_at(record, 56)?).map_err(|_| Error::Invalid)?;
                    if size == 0 || size > MAX_PTX_SIZE + 8 {
                        return Err(Error::Unsupported);
                    }
                    size
                } else {
                    payload_size
                };
                decoded_total = decoded_total.checked_add(declared).ok_or(Error::Invalid)?;
                if decoded_total > MAX_TOTAL_DECODED_SIZE {
                    return Err(Error::Unsupported);
                }
                reserve(&mut candidates, 1)?;
                let text = ptx_record(&record[..header_size], &record[header_size..])?;
                candidates.push(PtxCandidate {
                    profile: PtxProfile {
                        major: u16_at(record, 26)?,
                        minor: u16_at(record, 24)?,
                        target: u32_at(record, 28)?,
                    },
                    text,
                });
            }
            2 => {} // NVIDIA machine code is never executed.
            _ => return Err(Error::Unsupported),
        }
        offset = offset.checked_add(end).ok_or(Error::Invalid)?;
    }
    if candidates.is_empty() {
        return Err(Error::Unsupported);
    }
    Ok(candidates)
}

#[cfg(test)]
mod allocation_tests {
    use super::*;

    #[test]
    fn decoded_limit_precedes_reserve() {
        RESERVE_CALLS.set(0);
        RESERVE_FAULT.set(true);
        assert_eq!(decompress(&[0], MAX_PTX_SIZE + 9), Err(Error::Unsupported));
        assert_eq!(RESERVE_CALLS.get(), 0);
        RESERVE_FAULT.set(false);
    }

    #[test]
    fn reservation_failure_is_not_invalid_ptx() {
        RESERVE_FAULT.set(true);
        let result = decompress(&[0x20, b'a', 0], 2);
        RESERVE_FAULT.set(false);
        assert!(
            result.is_err(),
            "injected reserve failure must prevent decoding"
        );
        assert_ne!(result, Err(Error::Invalid));
        assert_ne!(result, Err(Error::Unsupported));
        assert_eq!(result, Err(Error::Allocation));
    }

    #[test]
    fn candidate_reservation_is_fallible() {
        let mut b = vec![0u8; 96];
        b[..4].copy_from_slice(&MAGIC);
        b[4] = 1;
        b[6] = 16;
        b[8..16].copy_from_slice(&80u64.to_le_bytes());
        b[16] = 1;
        b[18..20].copy_from_slice(&0x101u16.to_le_bytes());
        b[20..24].copy_from_slice(&72u32.to_le_bytes());
        b[24..32].copy_from_slice(&8u64.to_le_bytes());
        b[36..40].copy_from_slice(&64u32.to_le_bytes());
        b[42] = 8;
        b[44] = 52;
        b[56] = 0x41;
        b[88] = b'x';
        RESERVE_FAULT.set(true);
        let result = extract_candidates(&b);
        RESERVE_FAULT.set(false);
        assert!(matches!(result, Err(Error::Allocation)));
    }

    #[test]
    fn public_decoded_limit_precedes_candidate_reserve() {
        let mut b = vec![0u8; 96];
        b[..4].copy_from_slice(&MAGIC);
        b[4] = 1;
        b[6] = 16;
        b[8..16].copy_from_slice(&80u64.to_le_bytes());
        b[16] = 1;
        b[18..20].copy_from_slice(&0x101u16.to_le_bytes());
        b[20..24].copy_from_slice(&72u32.to_le_bytes());
        b[24..32].copy_from_slice(&8u64.to_le_bytes());
        b[32..36].copy_from_slice(&1u32.to_le_bytes());
        b[36..40].copy_from_slice(&64u32.to_le_bytes());
        b[42] = 8;
        b[44] = 52;
        b[56..60].copy_from_slice(&0x2041u32.to_le_bytes());
        b[72..80].copy_from_slice(&262153u64.to_le_bytes());
        RESERVE_CALLS.set(0);
        RESERVE_FAULT.set(true);
        let result = extract_candidates(&b);
        RESERVE_FAULT.set(false);
        assert!(matches!(result, Err(Error::Unsupported)));
        assert_eq!(RESERVE_CALLS.get(), 0);
    }
}

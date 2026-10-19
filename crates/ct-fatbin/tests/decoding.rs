use ct_fatbin::{extract_ptx, image_size, Error, MAX_IMAGE_SIZE};

fn put32(b: &mut [u8], offset: usize, value: u32) {
    b[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}
fn put64(b: &mut [u8], offset: usize, value: u64) {
    b[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}
fn record(kind: u16, text: &[u8]) -> Vec<u8> {
    let mut b = vec![0; 88];
    b[..2].copy_from_slice(&kind.to_le_bytes());
    b[2..4].copy_from_slice(&0x101u16.to_le_bytes());
    put32(&mut b, 4, 88);
    put32(&mut b, 20, 72);
    put32(&mut b, 24, 8 << 16);
    put32(&mut b, 28, 52);
    put32(&mut b, 40, 0x45);
    put32(&mut b, 72, 80);
    let mut payload = text.to_vec();
    payload.push(0);
    while !payload.len().is_multiple_of(8) {
        payload.push(0);
    }
    put64(&mut b, 8, payload.len() as u64);
    b.extend(payload);
    b
}
fn image(records: &[Vec<u8>]) -> Vec<u8> {
    let mut b = vec![0; 16];
    put32(&mut b, 0, 0xba55ed50);
    b[4] = 1;
    b[6] = 16;
    put64(&mut b, 8, records.iter().map(|r| r.len() as u64).sum());
    for r in records {
        b.extend(r);
    }
    b
}
const TEXT: &[u8] = b".version 8.0\n.target sm_52\n.address_size 64\n";

#[test]
fn extracts_one_ptx_and_skips_bounded_opaque_cubin() {
    let b = image(&[record(2, b"opaque synthetic cubin"), record(1, TEXT)]);
    assert_eq!(image_size(&b[..16]), Ok(b.len()));
    assert_eq!(extract_ptx(&b).unwrap(), TEXT);
}

#[test]
fn rejects_every_truncation_and_trailing_bytes_without_panicking() {
    let b = image(&[record(1, TEXT)]);
    for size in 0..b.len() {
        assert!(extract_ptx(&b[..size]).is_err(), "{size}");
    }
    // Keep the shortened outer length consistent to reach inner record checks.
    for size in (16..b.len()).step_by(8) {
        let mut shortened = b[..size].to_vec();
        put64(&mut shortened, 8, (size - 16) as u64);
        assert!(extract_ptx(&shortened).is_err(), "inner truncation {size}");
    }
    let mut extra = b;
    extra.push(0);
    assert_eq!(extract_ptx(&extra), Err(Error::Invalid));
}

#[test]
fn rejects_unsupported_and_ambiguous_modules() {
    assert_eq!(
        extract_ptx(&image(&[record(2, b"cubin")])),
        Err(Error::Unsupported)
    );
    assert_eq!(
        extract_ptx(&image(&[record(1, TEXT), record(1, TEXT)])),
        Err(Error::Unsupported)
    );
    for (offset, value) in [(2, 0x102), (40, 0x41), (24, 9 << 16), (28, 90), (76, 3)] {
        let mut r = record(1, TEXT);
        if offset == 2 {
            r[2..4].copy_from_slice(&(value as u16).to_le_bytes());
        } else {
            put32(&mut r, offset, value);
        }
        assert_eq!(
            extract_ptx(&image(&[r])),
            Err(Error::Unsupported),
            "offset {offset}"
        );
    }
}

fn compressed_record(block: &[u8], decoded_size: u64) -> Vec<u8> {
    let mut r = record(1, b"placeholder");
    r.truncate(88);
    put32(&mut r, 40, 0x2045);
    put32(&mut r, 16, block.len() as u32);
    put64(&mut r, 56, decoded_size);
    r.extend(block);
    while !r.len().is_multiple_of(8) {
        r.push(0);
    }
    let payload_size = (r.len() - 88) as u64;
    put64(&mut r, 8, payload_size);
    r
}

#[test]
fn compressed_literals_and_overlapping_matches_decode() {
    // Three literals, 12 overlapping copies, then five terminal literals.
    let block = [
        0x38, b'a', b'b', b'c', 3, 0, 0x50, b'x', b'y', b'z', b'!', 0,
    ];
    assert_eq!(
        extract_ptx(&image(&[compressed_record(&block, 20)]))
            .unwrap()
            .as_ref(),
        b"abcabcabcabcabcxyz!"
    );
    let mut block = vec![0xf0, (TEXT.len() + 1 - 15) as u8];
    block.extend(TEXT);
    block.push(0);
    assert_eq!(
        extract_ptx(&image(&[compressed_record(
            &block,
            (TEXT.len() + 1) as u64
        )]))
        .unwrap(),
        TEXT
    );
    // Extended match length, with byte-wise overlap offset one.
    let block = [0x1f, b'a', 1, 0, 255, 30, 0x50, b'b', b'c', b'd', b'e', 0];
    let mut expected = vec![b'a'; 305];
    expected.extend(b"bcde");
    assert_eq!(
        extract_ptx(&image(&[compressed_record(&block, 310)])).unwrap(),
        expected
    );
    // Extended literals can contain multiple 255 continuation bytes.
    let mut block = vec![0xf0, 255, 255, 10];
    block.extend(vec![b'x'; 534]);
    block.push(0);
    assert_eq!(
        extract_ptx(&image(&[compressed_record(&block, 535)])).unwrap(),
        vec![b'x'; 534]
    );
}

#[test]
fn compressed_stream_bounds_and_padding_are_checked() {
    let good = [0x50, b'a', b'b', b'c', b'd', 0];
    assert!(extract_ptx(&image(&[compressed_record(&good, 5)])).is_ok());
    for size in 0..good.len() {
        assert!(extract_ptx(&image(&[compressed_record(&good[..size], 5)])).is_err());
    }
    for (block, size) in [
        (&[0xf0][..], 16),                    // missing extended literal length
        (&[0x10, b'a', 0, 0, 0][..], 5),      // zero offset
        (&[0x10, b'a', 2, 0, 0][..], 5),      // before output start
        (&[0x1f, b'a', 1, 0, 255][..], 1000), // missing match extension
        (&good[..], 4),
        (&good[..], 6), // exact decoded size required
    ] {
        assert!(extract_ptx(&image(&[compressed_record(block, size)])).is_err());
    }
    let r = compressed_record(&good, ct_fatbin::MAX_PTX_SIZE as u64 + 9);
    assert_eq!(extract_ptx(&image(&[r])), Err(Error::Unsupported));
    for offset in [16, 56] {
        let mut r = compressed_record(&good, 5);
        put32(&mut r, offset, u32::MAX);
        assert!(extract_ptx(&image(&[r])).is_err());
    }
    let mut r = compressed_record(&good, 5);
    *r.last_mut().unwrap() = 1;
    assert_eq!(extract_ptx(&image(&[r])), Err(Error::Invalid));
    // An uncompressed record cannot declare decompressed data.
    let mut r = record(1, TEXT);
    put64(&mut r, 56, 5);
    assert!(extract_ptx(&image(&[r])).is_err());
}

#[test]
#[ignore = "requires locally generated NVIDIA nvFatbin reference files"]
fn genuine_compressed_and_plain_ptx_are_identical() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.cache/reference/m3e");
    let plain = std::fs::read(root.join("plain.fatbin")).unwrap();
    let compressed = std::fs::read(root.join("compressed.fatbin")).unwrap();
    assert_eq!(
        extract_ptx(&plain).unwrap(),
        extract_ptx(&compressed).unwrap()
    );
}

#[test]
fn rejects_invalid_sizes_metadata_and_text_padding() {
    for (offset, value) in [
        (4, 0),
        (4, 0xfffffff8),
        (8, 0xfffffff8),
        (12, u32::MAX),
        (20, 0xfffffff8),
        (72, 0xfffffff8),
    ] {
        let mut r = record(1, TEXT);
        put32(&mut r, offset, value);
        assert!(extract_ptx(&image(&[r])).is_err());
    }
    let mut b = image(&[record(1, TEXT)]);
    put64(&mut b, 8, MAX_IMAGE_SIZE as u64);
    assert!(image_size(&b).is_err());
    put64(&mut b, 8, u64::MAX);
    assert!(image_size(&b).is_err());
    let mut r = record(1, TEXT);
    *r.last_mut().unwrap() = 1;
    assert_eq!(extract_ptx(&image(&[r])), Err(Error::Invalid));
    let mut r = record(1, TEXT);
    r[88..].fill(b'x');
    assert_eq!(extract_ptx(&image(&[r])), Err(Error::Invalid));
}

#[test]
fn bounded_mutations_do_not_panic_and_record_count_is_limited() {
    let mut seed = 0x5a17u32;
    let mut block = vec![0xf0, (TEXT.len() + 1 - 15) as u8];
    block.extend(TEXT);
    block.push(0);
    for base in [
        image(&[record(1, TEXT)]),
        image(&[compressed_record(&block, (TEXT.len() + 1) as u64)]),
    ] {
        for size in 0..base.len() {
            assert!(extract_ptx(&base[..size]).is_err());
        }
        for _ in 0..2048 {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let mut bytes = base.clone();
            let index = seed as usize % bytes.len();
            bytes[index] = (seed >> 24) as u8;
            let _ = extract_ptx(&bytes);
        }
    }
    let records = vec![record(2, b"opaque"); 257];
    assert_eq!(extract_ptx(&image(&records)), Err(Error::Unsupported));
    for (offset, value) in [(32, 1), (32, 0xfffffff0), (36, u32::MAX), (20, 65)] {
        let mut r = record(1, TEXT);
        put32(&mut r, offset, value);
        assert!(extract_ptx(&image(&[r])).is_err());
    }
}

//! Explicit hardware probe; ordinary unit tests never open a GPU.
#![cfg(all(windows, target_pointer_width = "64"))]
use ct_backend_intel::Backend;

#[test]
#[ignore = "requires an Intel GPU and System32 Level Zero; run explicitly"]
fn native_gpu_clock_survives_memory_roundtrips() {
    let mut backend = Backend::open().expect("open Level Zero");
    let filter = std::env::var("CT_TEST_DEVICE").unwrap_or_else(|_| "B390".into());
    let index = backend
        .devices
        .iter()
        .position(|d| d.name.contains(&filter))
        .expect("requested Intel GPU missing; do not silently select another device");
    let mut context = backend.create_context(index).expect("create context");
    let mut allocations = Vec::new();
    let result = (|| -> Result<(), String> {
        let pointer = backend
            .allocate(&mut context, 4096)
            .map_err(|e| format!("allocate: {e:#x}"))?;
        allocations.push(pointer);
        let mut input: Vec<u32> = (0..1024).map(|i| i * 13 + 7).collect();
        let mut output = vec![0u32; 1024];
        backend
            .synchronize(&mut context)
            .map_err(|e| format!("sync: {e:#x}"))?;
        let before = backend
            .timestamp(&mut context)
            .map_err(|e| format!("start clock: {e:#x}"))?;
        for _ in 0..8 {
            unsafe {
                backend
                    .copy(&mut context, pointer, input.as_mut_ptr().cast(), 4096, true)
                    .map_err(|e| format!("upload: {e:#x}"))?;
                backend
                    .copy(
                        &mut context,
                        pointer,
                        output.as_mut_ptr().cast(),
                        4096,
                        false,
                    )
                    .map_err(|e| format!("download: {e:#x}"))?;
            }
            if output != input {
                return Err("memory roundtrip mismatch".into());
            }
        }
        backend
            .synchronize(&mut context)
            .map_err(|e| format!("sync: {e:#x}"))?;
        let after = backend
            .timestamp(&mut context)
            .map_err(|e| format!("stop clock: {e:#x}"))?;
        if before.frequency != after.frequency || before.bits != after.bits {
            return Err("clock metadata changed during probe".into());
        }
        let mask = u64::MAX >> (64 - before.bits);
        let delta = after.ticks.wrapping_sub(before.ticks) & mask;
        if delta == 0 {
            return Err("GPU counter did not advance".into());
        }
        println!(
            "GPU_CLOCK_OK frequency={} bits={} delta_ticks={} roundtrips=8 words=1024",
            before.frequency, before.bits, delta
        );
        Ok(())
    })();
    let cleanup = backend.destroy_context(&mut context, &allocations);
    result.expect("GPU clock and memory probe");
    cleanup.expect("context cleanup");
}

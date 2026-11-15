//! CUDA-visible capacity policy; physical Intel metadata stays in the backend.
use ct_codegen_spirv::CompiledEntry;

pub(crate) fn shared_limit(native: u32) -> u32 {
    native.min(ct_ptx::MAX_STATIC_SHARED_BYTES)
}

pub(crate) fn validate_entries(entries: &[CompiledEntry], native: u32) -> Result<(), i32> {
    if entries
        .iter()
        .any(|e| e.static_shared_bytes > shared_limit(native))
    {
        Err(super::UNSUPPORTED)
    } else {
        Ok(())
    }
}

pub(crate) fn create<T>(
    entries: &[CompiledEntry],
    native: u32,
    create: impl FnOnce() -> Result<T, i32>,
) -> Result<T, i32> {
    validate_entries(entries, native)?;
    create()
}

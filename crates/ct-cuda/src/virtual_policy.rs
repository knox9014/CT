//! Explicit experimental software target. The Driver owns the only process latch.
use std::ffi::OsString;
use std::sync::OnceLock;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Mode {
    Strict,
    Sm52,
}

pub(crate) fn parse(value: Option<OsString>) -> Result<Mode, i32> {
    match value.as_deref().map(|s| s.to_str()) {
        None | Some(Some("strict")) => Ok(Mode::Strict),
        Some(Some("ct-sm52-subset-v1")) => Ok(Mode::Sm52),
        _ => Err(super::INVALID),
    }
}

static POLICY: OnceLock<Result<Mode, i32>> = OnceLock::new();

pub(crate) fn initialize(
    flags: u32,
    cell: &OnceLock<Result<Mode, i32>>,
    read: impl FnOnce() -> Option<OsString>,
    native: impl FnOnce() -> super::CudaResult,
) -> super::CudaResult {
    if flags != 0 {
        return Err(super::INVALID);
    }
    (*cell.get_or_init(|| parse(read())))?;
    native()
}

pub(crate) fn initialize_process(
    flags: u32,
    native: impl FnOnce() -> super::CudaResult,
) -> super::CudaResult {
    initialize(
        flags,
        &POLICY,
        || std::env::var_os("CT_VIRTUAL_TARGET"),
        native,
    )
}

pub(crate) fn current() -> Result<Mode, i32> {
    POLICY.get().copied().unwrap_or(Err(super::NOT_INITIALIZED))
}

/// Software-target topology hint from maximum native dimensions, not active SMs.
pub(crate) fn topology_count(mode: Mode, slices: u32, subslices: u32) -> Result<i32, i32> {
    if mode == Mode::Strict || slices == 0 || subslices == 0 {
        return Err(super::UNSUPPORTED);
    }
    let count = slices.checked_mul(subslices).ok_or(super::UNSUPPORTED)?;
    i32::try_from(count).map_err(|_| super::UNSUPPORTED)
}

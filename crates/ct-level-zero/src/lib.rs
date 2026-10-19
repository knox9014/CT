//! Internal, minimal Level Zero FFI. No CUDA compatibility exports.
pub mod abi;
#[cfg(windows)]
pub mod loader;

use std::cell::Cell;
use std::ffi::c_char;
thread_local! { static LAST: Cell<i32> = const { Cell::new(0) }; }
pub fn from_driver(code: i32) -> i32 {
    match code {
        0 | 1 | 2 | 3 | 100 | 101 | 709 | 801 | 999 => code,
        201 => 49,
        _ => 999,
    }
}
pub fn record(code: i32) -> i32 {
    if code != 0 {
        LAST.with(|last| last.set(code));
    }
    code
}
pub fn peek() -> i32 {
    LAST.with(Cell::get)
}
pub fn take() -> i32 {
    LAST.with(|last| last.replace(0))
}
pub fn text(code: i32, description: bool) -> *const c_char {
    let (name, message): (&[u8], &[u8]) = match code {
        0 => (b"cudaSuccess\0", b"no error\0"),
        1 => (b"cudaErrorInvalidValue\0", b"invalid argument\0"),
        2 => (b"cudaErrorMemoryAllocation\0", b"out of memory\0"),
        3 => (b"cudaErrorInitializationError\0", b"initialization error\0"),
        9 => (
            b"cudaErrorInvalidConfiguration\0",
            b"invalid launch configuration\0",
        ),
        21 => (
            b"cudaErrorInvalidMemcpyDirection\0",
            b"invalid copy direction\0",
        ),
        35 => (
            b"cudaErrorInsufficientDriver\0",
            b"compatible driver unavailable\0",
        ),
        49 => (
            b"cudaErrorIncompatibleDriverContext\0",
            b"incompatible driver context\0",
        ),
        100 => (b"cudaErrorNoDevice\0", b"no device\0"),
        101 => (b"cudaErrorInvalidDevice\0", b"invalid device ordinal\0"),
        98 => (
            b"cudaErrorInvalidDeviceFunction\0",
            b"invalid device function\0",
        ),
        218 => (b"cudaErrorInvalidPtx\0", b"invalid PTX\0"),
        400 => (
            b"cudaErrorInvalidResourceHandle\0",
            b"invalid resource handle\0",
        ),
        709 => (b"cudaErrorContextIsDestroyed\0", b"context is destroyed\0"),
        801 => (b"cudaErrorNotSupported\0", b"operation not supported\0"),
        999 => (b"cudaErrorUnknown\0", b"unknown error\0"),
        _ => (b"unrecognized error code\0", b"unrecognized error code\0"),
    };
    (if description { message } else { name }).as_ptr().cast()
}

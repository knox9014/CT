// TEST-ONLY synthetic protocol peer. Never CT compatibility or a GPU backend.
#![allow(non_snake_case)]
use std::ffi::{c_char, c_void, CStr};
use std::ptr::null_mut;
use std::sync::Mutex;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Row {
    kind: u32,
    version: i32,
    flags: u64,
    result: i32,
    status: i32,
    found: i32,
    value: i32,
    symbol: [u8; 64],
    uuid: [u8; 16],
}
const EMPTY: Row = Row {
    kind: 0,
    version: 0,
    flags: 0,
    result: 0,
    status: -1,
    found: 0,
    value: 0,
    symbol: [0; 64],
    uuid: [0; 16],
};
struct State {
    mode: u32,
    enabled: bool,
    configured: bool,
    started: bool,
    count: usize,
    overflow: bool,
    rows: [Row; 512],
}
impl State {
    const fn new() -> Self {
        Self {
            mode: 0,
            enabled: false,
            configured: false,
            started: false,
            count: 0,
            overflow: false,
            rows: [EMPTY; 512],
        }
    }
}
static STATE: Mutex<State> = Mutex::new(State::new());
fn record(mut row: Row, name: &[u8]) {
    let n = name.len().min(63);
    row.symbol[..n].copy_from_slice(&name[..n]);
    let mut state = STATE.lock().unwrap();
    state.started = true;
    if state.enabled {
        let i = state.count;
        if i < 512 {
            state.rows[i] = row;
            state.count += 1;
        } else {
            state.overflow = true;
        }
    }
}

#[no_mangle]
pub extern "system" fn ctPeerConfigure(mode: u32, enabled: u32) -> i32 {
    if mode > 4 || enabled > 1 {
        return 1;
    }
    let mut state = STATE.lock().unwrap();
    if state.started || state.configured {
        return 801;
    }
    state.mode = mode;
    state.enabled = enabled == 1;
    state.configured = true;
    0
}

// Caller provides valid, sufficiently sized nonoverlapping storage. Test-only ABI.
#[no_mangle]
pub unsafe extern "system" fn ctPeerSnapshot(
    output: *mut Row,
    capacity: u32,
    count: *mut u32,
    overflow: *mut u32,
) -> i32 {
    if count.is_null() || overflow.is_null() || capacity > 512 || (capacity > 0 && output.is_null())
    {
        return 1;
    }
    let state = STATE.lock().unwrap();
    count.write(state.count as u32);
    overflow.write(u32::from(state.overflow));
    if capacity > 0 {
        std::ptr::copy_nonoverlapping(
            state.rows.as_ptr(),
            output,
            state.count.min(capacity as usize),
        );
    }
    0
}

#[no_mangle]
pub unsafe extern "system" fn cuDriverGetVersion(output: *mut i32) -> i32 {
    let mode = STATE.lock().unwrap().mode;
    let (mut result, value) = [(801, 0), (0, 0), (0, 11000), (0, 12000), (0, 12090)][mode as usize];
    if output.is_null() {
        result = 1;
    } else {
        output.write(value);
    }
    record(
        Row {
            kind: 3,
            result,
            value: if output.is_null() { 0 } else { value },
            ..EMPTY
        },
        b"cuDriverGetVersion",
    );
    result
}

#[no_mangle]
pub extern "system" fn cuInit(flags: u32) -> i32 {
    let result = if flags == 0 { 801 } else { 1 };
    record(
        Row {
            kind: 4,
            result,
            flags: u64::from(flags),
            ..EMPTY
        },
        b"cuInit",
    );
    result
}

// Opaque UUID is read as its public 16-byte representation. No table is created.
#[no_mangle]
pub unsafe extern "system" fn cuGetExportTable(output: *mut *const c_void, id: *const u8) -> i32 {
    if !output.is_null() {
        output.write(std::ptr::null());
    }
    let mut row = Row {
        kind: 5,
        result: 801,
        ..EMPTY
    };
    if output.is_null() || id.is_null() {
        row.result = 1;
    } else {
        std::ptr::copy_nonoverlapping(id, row.uuid.as_mut_ptr(), 16);
    }
    let result = row.result;
    record(row, b"cuGetExportTable");
    result
}

unsafe fn resolve(
    symbol: *const c_char,
    output: *mut *mut c_void,
    version: i32,
    flags: u64,
    status: *mut i32,
    legacy: bool,
) -> i32 {
    if !output.is_null() {
        output.write(null_mut());
    }
    if !status.is_null() {
        status.write(1);
    }
    let name = if symbol.is_null() {
        b"<null>".as_slice()
    } else {
        CStr::from_ptr(symbol).to_bytes()
    };
    let mut row = Row {
        kind: if legacy { 2 } else { 1 },
        version,
        flags,
        status: if status.is_null() { -1 } else { 1 },
        ..EMPTY
    };
    if symbol.is_null() || output.is_null() || version <= 0 || flags > 2 || name.len() > 63 {
        row.result = 1;
    } else if version > 12090 {
        row.result = 801;
    } else {
        let entry = match name {
            b"cuInit" => Some((2000, cuInit as *const () as *mut c_void)),
            b"cuDriverGetVersion" => Some((2020, cuDriverGetVersion as *const () as *mut c_void)),
            b"cuGetExportTable" => Some((3000, cuGetExportTable as *const () as *mut c_void)),
            b"cuGetProcAddress" if version < 12000 => {
                Some((11030, cuGetProcAddress as *const () as *mut c_void))
            }
            b"cuGetProcAddress" => Some((12000, cuGetProcAddress_v2 as *const () as *mut c_void)),
            _ => None,
        };
        if let Some((minimum, pointer)) = entry {
            if version >= minimum {
                output.write(pointer);
                row.found = 1;
                row.status = 0;
            } else {
                row.status = 2;
            }
        }
        if legacy && row.found == 0 {
            row.result = 500;
        }
        if !status.is_null() {
            status.write(row.status);
        } else {
            row.status = -1;
        }
    }
    let result = row.result;
    record(row, name);
    result
}

#[no_mangle]
pub unsafe extern "system" fn cuGetProcAddress(
    symbol: *const c_char,
    output: *mut *mut c_void,
    version: i32,
    flags: u64,
) -> i32 {
    resolve(symbol, output, version, flags, null_mut(), true)
}
#[no_mangle]
pub unsafe extern "system" fn cuGetProcAddress_v2(
    symbol: *const c_char,
    output: *mut *mut c_void,
    version: i32,
    flags: u64,
    status: *mut i32,
) -> i32 {
    resolve(symbol, output, version, flags, status, false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{dangling_mut, null, null_mut};
    static SERIAL: std::sync::Mutex<()> = std::sync::Mutex::new(());
    fn reset() {
        *STATE.lock().unwrap() = State::new();
    }

    #[test]
    fn responses_are_fixed_inputs_and_configuration_latches() {
        let _serial = SERIAL.lock().unwrap();
        for (mode, code, value) in [
            (0, 801, 0),
            (1, 0, 0),
            (2, 0, 11000),
            (3, 0, 12000),
            (4, 0, 12090),
        ] {
            reset();
            assert_eq!(ctPeerConfigure(99, 1), 1);
            assert_eq!(ctPeerConfigure(mode, 2), 1);
            assert_eq!(ctPeerConfigure(mode, 1), 0);
            assert_eq!(ctPeerConfigure(mode, 1), 801);
            let mut out = -1;
            unsafe {
                assert_eq!(cuDriverGetVersion(&mut out), code);
            }
            assert_eq!(out, value);
        }
    }

    #[test]
    fn init_and_export_tables_never_succeed() {
        let _serial = SERIAL.lock().unwrap();
        reset();
        unsafe {
            assert_eq!(cuDriverGetVersion(null_mut()), 1);
            assert_eq!(cuInit(0), 801);
            assert_eq!(cuInit(1), 1);
            let id = [7u8; 16];
            let mut output = dangling_mut::<std::ffi::c_void>() as *const _;
            assert_eq!(cuGetExportTable(&mut output, id.as_ptr()), 801);
            assert!(output.is_null());
            output = dangling_mut::<std::ffi::c_void>();
            assert_eq!(cuGetExportTable(&mut output, null()), 1);
            assert!(output.is_null());
            assert_eq!(cuGetExportTable(null_mut(), id.as_ptr()), 1);
        }
        assert_eq!(ctPeerConfigure(3, 1), 801);
    }

    #[test]
    fn resolvers_expose_only_inert_surface_with_both_abis() {
        let _serial = SERIAL.lock().unwrap();
        reset();
        unsafe {
            for name in [
                c"cuMemAlloc",
                c"cuLaunchKernel",
                c"cuDeviceGetCount",
                c"unknown",
            ] {
                let mut p = dangling_mut();
                let mut status = -1;
                assert_eq!(
                    cuGetProcAddress_v2(name.as_ptr(), &mut p, 12000, 0, &mut status),
                    0
                );
                assert_eq!((p, status), (null_mut(), 1));
                assert_eq!(cuGetProcAddress(name.as_ptr(), &mut p, 12000, 0), 500);
                assert!(p.is_null());
            }
            let mut p = null_mut();
            let mut status = -1;
            assert_eq!(
                cuGetProcAddress_v2(c"cuGetProcAddress".as_ptr(), &mut p, 11999, 2, &mut status),
                0
            );
            assert_eq!(p, cuGetProcAddress as *const () as *mut _);
            assert_eq!(
                cuGetProcAddress_v2(c"cuGetProcAddress".as_ptr(), &mut p, 12000, 2, &mut status),
                0
            );
            assert_eq!(p, cuGetProcAddress_v2 as *const () as *mut _);
            for (version, flags, code) in [(0, 0, 1), (12091, 0, 801), (12000, 3, 1)] {
                assert_eq!(
                    cuGetProcAddress_v2(c"cuInit".as_ptr(), &mut p, version, flags, &mut status),
                    code
                );
                assert_eq!((p, status), (null_mut(), 1));
            }
            assert_eq!(cuGetProcAddress_v2(null(), &mut p, 2000, 0, &mut status), 1);
            assert_eq!(
                cuGetProcAddress_v2(c"cuInit".as_ptr(), null_mut(), 2000, 0, &mut status),
                1
            );
        }
    }

    #[test]
    fn trace_is_bounded_and_disabled_mode_preserves_behavior() {
        let _serial = SERIAL.lock().unwrap();
        reset();
        assert_eq!(std::mem::size_of::<Row>(), 112);
        assert_eq!(ctPeerConfigure(3, 1), 0);
        let mut value = 0;
        for _ in 0..600 {
            unsafe {
                assert_eq!(cuDriverGetVersion(&mut value), 0);
            }
        }
        assert_eq!(value, 12000);
        let mut count = 0;
        let mut overflow = 0;
        unsafe {
            assert_eq!(ctPeerSnapshot(null_mut(), 0, &mut count, &mut overflow), 0);
        }
        assert_eq!((count, overflow), (512, 1));
        reset();
        assert_eq!(ctPeerConfigure(3, 0), 0);
        unsafe {
            assert_eq!(cuDriverGetVersion(&mut value), 0);
            assert_eq!(ctPeerSnapshot(null_mut(), 0, &mut count, &mut overflow), 0);
        }
        assert_eq!((value, count, overflow), (12000, 0, 0));
    }
}

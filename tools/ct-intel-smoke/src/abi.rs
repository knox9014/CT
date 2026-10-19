//! Minimal C layout subset checked against oneapi-src/level-zero v1.27.0.
//! No CUDA exports or compatibility behavior are implemented here.
use std::ffi::{c_char, c_void};
pub type Handle = *mut c_void;

#[repr(C)]
pub struct DriverProperties {
    pub stype: u32,
    pub next: *mut c_void,
    pub uuid: [u8; 16],
    pub version: u32,
}
#[repr(C)]
pub struct DeviceProperties {
    pub stype: u32,
    pub next: *mut c_void,
    pub kind: u32,
    pub vendor: u32,
    pub device: u32,
    pub flags: u32,
    pub subdevice: u32,
    pub clock: u32,
    pub max_alloc: u64,
    pub contexts: u32,
    pub priority: u32,
    pub threads_per_eu: u32,
    pub simd: u32,
    pub eus_per_subslice: u32,
    pub subslices: u32,
    pub slices: u32,
    pub timer: u64,
    pub timestamp_bits: u32,
    pub kernel_timestamp_bits: u32,
    pub uuid: [u8; 16],
    pub name: [u8; 256],
}
#[repr(C)]
pub struct ComputeProperties {
    pub stype: u32,
    pub next: *mut c_void,
    pub max_total: u32,
    pub max_x: u32,
    pub max_y: u32,
    pub max_z: u32,
    pub count_x: u32,
    pub count_y: u32,
    pub count_z: u32,
    pub shared_mem: u32,
    pub subgroup_count: u32,
    pub subgroup_sizes: [u32; 8],
}
#[repr(C)]
pub struct QueueGroupProperties {
    pub stype: u32,
    pub next: *mut c_void,
    pub flags: u32,
    pub max_fill_size: usize,
    pub count: u32,
}
#[repr(C)]
pub struct ContextDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub flags: u32,
}
#[repr(C)]
pub struct QueueDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub ordinal: u32,
    pub index: u32,
    pub flags: u32,
    pub mode: u32,
    pub priority: u32,
}
#[repr(C)]
pub struct ListDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub ordinal: u32,
    pub flags: u32,
}
#[repr(C)]
pub struct DeviceAllocDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub flags: u32,
    pub ordinal: u32,
}
#[repr(C)]
pub struct HostAllocDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub flags: u32,
}
#[repr(C)]
pub struct ModuleDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub format: u32,
    pub size: usize,
    pub input: *const u8,
    pub flags: *const c_char,
    pub constants: *const c_void,
}
#[repr(C)]
pub struct KernelDesc {
    pub stype: u32,
    pub next: *const c_void,
    pub flags: u32,
    pub name: *const c_char,
}
#[repr(C)]
pub struct GroupCount {
    pub x: u32,
    pub y: u32,
    pub z: u32,
}

/// All types in this module have only integer, byte-array, or pointer fields.
/// Callers set the documented structure type before passing them to the driver.
pub unsafe fn blank<T>() -> T {
    std::mem::zeroed()
}

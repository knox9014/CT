//! Experimental Windows x64 native memory backend; no CUDA semantics here.
#![cfg(all(windows, target_pointer_width = "64"))]
use ct_level_zero::abi::*;
#[cfg(not(test))]
use ct_level_zero::loader::Api;
#[cfg(test)]
use fault_tests::Api;
use std::ffi::c_void;
use std::ptr::{null, null_mut};

pub type NativeResult<T> = Result<T, u32>;
const DEPENDENCY: u32 = 0x70020000;
const BAD_ARGUMENT: u32 = 0x78000004;
const UNKNOWN: u32 = 0x7ffffffe;

macro_rules! ze {
    ($api:expr, $name:literal, ($($ty:ty),*), ($($arg:expr),* $(,)?)) => {(|| -> NativeResult<()> {
        let f: unsafe extern "C" fn($($ty),*) -> u32 =
            $api.symbol(concat!($name,"\0").as_bytes()).map_err(|_| DEPENDENCY)?;
        let code = f($($arg),*);
        if code == 0 { Ok(()) } else { Err(code) }
    })()};
}

#[cfg(test)]
mod fault_tests;
mod modules;

pub struct Device {
    driver: usize,
    native: usize,
    pub name: String,
    pub max_group: [u32; 4],
    pub max_groups: [u32; 3],
}
pub struct Backend {
    api: Api,
    pub devices: Vec<Device>,
    // Failed native resources are deliberately retained, never retried blindly.
    orphaned: Vec<usize>,
}
pub struct Context {
    native: usize,
    list: usize,
    max_fill_pattern: usize,
    retained_patterns: Vec<Box<[u8]>>,
    pub device: usize,
    pub poisoned: bool,
    staging: Vec<usize>,
    retained_modules: Vec<Module>,
    retained_build_logs: Vec<usize>,
}
pub struct Module {
    native: usize,
    kernels: Vec<usize>,
}

impl Context {
    /// A fatal device state invalidates this context even before submission.
    fn observe<T>(&mut self, api: &Api, result: NativeResult<T>) -> NativeResult<T> {
        if matches!(result, Err(0x70000001 | 0x70000006)) {
            self.poisoned = true;
            api.keep_loaded.set(true);
        }
        result
    }
}

impl Backend {
    pub fn open() -> NativeResult<Self> {
        unsafe {
            let api = Api::open().map_err(|_| DEPENDENCY)?;
            ze!(api, "zeInit", (u32), (1))?;
            let mut count = 0;
            ze!(
                api,
                "zeDriverGet",
                (*mut u32, *mut Handle),
                (&mut count, null_mut())
            )?;
            let mut drivers = vec![null_mut(); count as usize];
            if count > 0 {
                ze!(
                    api,
                    "zeDriverGet",
                    (*mut u32, *mut Handle),
                    (&mut count, drivers.as_mut_ptr())
                )?;
            }
            let mut devices = Vec::new();
            for driver in drivers.into_iter().take(count as usize) {
                let mut n = 0;
                ze!(
                    api,
                    "zeDeviceGet",
                    (Handle, *mut u32, *mut Handle),
                    (driver, &mut n, null_mut())
                )?;
                if n == 0 {
                    continue;
                }
                let mut handles = vec![null_mut(); n as usize];
                ze!(
                    api,
                    "zeDeviceGet",
                    (Handle, *mut u32, *mut Handle),
                    (driver, &mut n, handles.as_mut_ptr())
                )?;
                for device in handles.into_iter().take(n as usize) {
                    let mut properties: DeviceProperties = blank();
                    properties.stype = 3;
                    ze!(
                        api,
                        "zeDeviceGetProperties",
                        (Handle, *mut DeviceProperties),
                        (device, &mut properties)
                    )?;
                    if properties.kind != 1 || properties.vendor != 0x8086 {
                        continue;
                    }
                    let mut compute: ComputeProperties = blank();
                    compute.stype = 4;
                    ze!(
                        api,
                        "zeDeviceGetComputeProperties",
                        (Handle, *mut ComputeProperties),
                        (device, &mut compute)
                    )?;
                    let end = properties
                        .name
                        .iter()
                        .position(|&v| v == 0)
                        .unwrap_or(properties.name.len());
                    devices.push(Device {
                        driver: driver as usize,
                        native: device as usize,
                        name: String::from_utf8_lossy(&properties.name[..end]).into_owned(),
                        max_group: [
                            compute.max_total,
                            compute.max_x,
                            compute.max_y,
                            compute.max_z,
                        ],
                        max_groups: [compute.count_x, compute.count_y, compute.count_z]
                            .map(|v| v.min(i32::MAX as u32)),
                    });
                }
            }
            Ok(Self {
                api,
                devices,
                orphaned: Vec::new(),
            })
        }
    }

    pub fn create_context(&mut self, index: usize) -> NativeResult<Context> {
        unsafe {
            let d = self.devices.get(index).ok_or(BAD_ARGUMENT)?;
            let device = d.native as Handle;
            let mut count = 0;
            ze!(
                self.api,
                "zeDeviceGetCommandQueueGroupProperties",
                (Handle, *mut u32, *mut QueueGroupProperties),
                (device, &mut count, null_mut())
            )?;
            if count == 0 {
                return Err(UNKNOWN);
            }
            let mut props: Vec<QueueGroupProperties> = (0..count)
                .map(|_| {
                    let mut p: QueueGroupProperties = blank();
                    p.stype = 6;
                    p
                })
                .collect();
            ze!(
                self.api,
                "zeDeviceGetCommandQueueGroupProperties",
                (Handle, *mut u32, *mut QueueGroupProperties),
                (device, &mut count, props.as_mut_ptr())
            )?;
            let ordinal = props
                .iter()
                .take(count as usize)
                .position(|p| p.flags & 1 != 0 && p.count > 0)
                .ok_or(UNKNOWN)? as u32;
            let desc = ContextDesc {
                stype: 0xd,
                next: null(),
                flags: 0,
            };
            let mut context = null_mut();
            ze!(
                self.api,
                "zeContextCreate",
                (Handle, *const ContextDesc, *mut Handle),
                (d.driver as Handle, &desc, &mut context)
            )?;
            let queue = QueueDesc {
                stype: 0xe,
                next: null(),
                ordinal,
                index: 0,
                flags: 0,
                mode: 1,
                priority: 0,
            };
            let mut list = null_mut();
            let result = ze!(
                self.api,
                "zeCommandListCreateImmediate",
                (Handle, Handle, *const QueueDesc, *mut Handle),
                (context, device, &queue, &mut list)
            );
            if let Err(code) = result {
                if ze!(self.api, "zeContextDestroy", (Handle), (context)).is_err() {
                    self.orphaned.push(context as usize);
                    self.api.keep_loaded.set(true);
                }
                return Err(code);
            }
            Ok(Context {
                native: context as usize,
                list: list as usize,
                max_fill_pattern: props[ordinal as usize].max_fill_size,
                retained_patterns: Vec::new(),
                device: index,
                poisoned: false,
                staging: Vec::new(),
                retained_modules: Vec::new(),
                retained_build_logs: Vec::new(),
            })
        }
    }

    pub fn allocate(&self, c: &mut Context, size: usize) -> NativeResult<u64> {
        if c.poisoned || size == 0 {
            return Err(BAD_ARGUMENT);
        }
        unsafe {
            let descriptor = DeviceAllocDesc {
                stype: 0x15,
                next: null(),
                flags: 0,
                ordinal: 0,
            };
            let mut pointer = null_mut();
            let result = ze!(
                self.api,
                "zeMemAllocDevice",
                (
                    Handle,
                    *const DeviceAllocDesc,
                    usize,
                    usize,
                    Handle,
                    *mut Handle
                ),
                (
                    c.native as Handle,
                    &descriptor,
                    size,
                    64,
                    self.devices[c.device].native as Handle,
                    &mut pointer
                )
            );
            c.observe(&self.api, result)?;
            if pointer.is_null() {
                return Err(UNKNOWN);
            }
            Ok(pointer as u64)
        }
    }
    pub fn free(&self, c: &mut Context, pointer: u64) -> NativeResult<()> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        unsafe {
            let result = ze!(
                self.api,
                "zeMemFree",
                (Handle, Handle),
                (c.native as Handle, pointer as Handle)
            );
            if result.is_err() {
                c.poisoned = true;
                self.api.keep_loaded.set(true);
            }
            result
        }
    }

    /// # Safety
    /// host must be valid for size bytes in the appropriate read/write direction.
    /// device must name an allocation range owned by c; caller serializes access.
    pub unsafe fn copy(
        &self,
        c: &mut Context,
        device: u64,
        host: *mut c_void,
        size: usize,
        to_device: bool,
    ) -> NativeResult<()> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        if size == 0 {
            return Ok(());
        }
        let desc = HostAllocDesc {
            stype: 0x16,
            next: null(),
            flags: 0,
        };
        let mut staging = null_mut();
        let result = ze!(
            self.api,
            "zeMemAllocHost",
            (Handle, *const HostAllocDesc, usize, usize, *mut Handle),
            (c.native as Handle, &desc, size, 64, &mut staging)
        );
        c.observe(&self.api, result)?;
        if staging.is_null() {
            return Err(UNKNOWN);
        }
        c.staging.push(staging as usize);
        if to_device {
            std::ptr::copy_nonoverlapping(host.cast::<u8>(), staging.cast::<u8>(), size);
        }
        let (dst, src) = if to_device {
            (device as Handle, staging)
        } else {
            (staging, device as Handle)
        };
        // Synchronous immediate-list mode guarantees completion on success. If
        // the append fails, preserve staging and poison the context conservatively.
        let result = ze!(
            self.api,
            "zeCommandListAppendMemoryCopy",
            (
                Handle,
                Handle,
                *const c_void,
                usize,
                Handle,
                u32,
                *mut Handle
            ),
            (c.list as Handle, dst, src, size, null_mut(), 0, null_mut())
        );
        if let Err(code) = result {
            c.poisoned = true;
            self.api.keep_loaded.set(true);
            return Err(code);
        }
        if !to_device {
            std::ptr::copy_nonoverlapping(staging.cast::<u8>(), host.cast::<u8>(), size);
        }
        let result = ze!(
            self.api,
            "zeMemFree",
            (Handle, Handle),
            (c.native as Handle, staging)
        );
        if let Err(code) = result {
            c.poisoned = true;
            self.api.keep_loaded.set(true);
            return Err(code);
        }
        c.staging.pop();
        Ok(())
    }
    /// The caller validates both owned ranges and excludes overlap.
    pub fn copy_device(
        &self,
        c: &mut Context,
        destination: u64,
        source: u64,
        size: usize,
    ) -> NativeResult<()> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        if size == 0 {
            return Ok(());
        }
        let result = unsafe {
            ze!(
                self.api,
                "zeCommandListAppendMemoryCopy",
                (
                    Handle,
                    Handle,
                    *const c_void,
                    usize,
                    Handle,
                    u32,
                    *mut Handle
                ),
                (
                    c.list as Handle,
                    destination as Handle,
                    source as *const c_void,
                    size,
                    null_mut(),
                    0,
                    null_mut()
                )
            )
        };
        self.observe_submission(c, result)
    }
    /// The caller validates ownership, alignment, and count multiplication.
    pub fn fill_device(
        &self,
        c: &mut Context,
        destination: u64,
        value: u32,
        width: usize,
        size: usize,
    ) -> NativeResult<()> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        if !matches!(width, 1 | 2 | 4)
            || !destination.is_multiple_of(width as u64)
            || !size.is_multiple_of(width)
        {
            return Err(BAD_ARGUMENT);
        }
        if size == 0 {
            return Ok(());
        }
        if width > c.max_fill_pattern {
            return Err(0x78000003);
        }
        // Keep pattern storage alive even if a failed append leaves completion
        // uncertain. Synchronous-list success establishes safe reclamation.
        c.retained_patterns
            .push(value.to_le_bytes().to_vec().into_boxed_slice());
        let pattern = c.retained_patterns.last().unwrap();
        let result = unsafe {
            ze!(
                self.api,
                "zeCommandListAppendMemoryFill",
                (
                    Handle,
                    Handle,
                    *const c_void,
                    usize,
                    usize,
                    Handle,
                    u32,
                    *mut Handle
                ),
                (
                    c.list as Handle,
                    destination as Handle,
                    pattern.as_ptr().cast(),
                    width,
                    size,
                    null_mut(),
                    0,
                    null_mut()
                )
            )
        };
        self.observe_submission(c, result)?;
        c.retained_patterns.pop();
        Ok(())
    }
    fn observe_submission(&self, c: &mut Context, result: NativeResult<()>) -> NativeResult<()> {
        if result.is_err() {
            c.poisoned = true;
            self.api.keep_loaded.set(true);
        }
        result
    }
    pub fn synchronize(&self, c: &mut Context) -> NativeResult<()> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        let result = unsafe {
            ze!(
                self.api,
                "zeCommandListHostSynchronize",
                (Handle, u64),
                (c.list as Handle, 30_000_000_000)
            )
        };
        if result.is_err() {
            c.poisoned = true;
            self.api.keep_loaded.set(true);
        }
        result
    }
    pub fn destroy_context(&self, c: &mut Context, allocations: &[u64]) -> NativeResult<()> {
        if c.poisoned {
            self.api.keep_loaded.set(true);
            return Err(UNKNOWN);
        }
        unsafe {
            let result = ze!(
                self.api,
                "zeCommandListDestroy",
                (Handle),
                (c.list as Handle)
            );
            if let Err(code) = result {
                c.poisoned = true;
                self.api.keep_loaded.set(true);
                return Err(code);
            }
            c.list = 0;
            for &pointer in allocations {
                if let Err(code) = ze!(
                    self.api,
                    "zeMemFree",
                    (Handle, Handle),
                    (c.native as Handle, pointer as Handle)
                ) {
                    c.poisoned = true;
                    self.api.keep_loaded.set(true);
                    return Err(code);
                }
            }
            let result = ze!(self.api, "zeContextDestroy", (Handle), (c.native as Handle));
            if result.is_err() {
                c.poisoned = true;
                self.api.keep_loaded.set(true);
            }
            result
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    struct MissingSymbols;
    impl MissingSymbols {
        unsafe fn symbol<T: Copy>(&self, _name: &[u8]) -> Result<T, String> {
            Err("synthetic missing export".into())
        }
    }
    #[test]
    fn missing_symbol_reaches_the_resource_error_handler() {
        fn operation() -> NativeResult<bool> {
            unsafe {
                let api = MissingSymbols;
                let result = ze!(api, "zeSyntheticMissing", (), ());
                Ok(result.is_err())
            }
        }
        assert_eq!(operation(), Ok(true));
    }
}

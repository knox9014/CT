//! Lazy calls through the already owned/pinned Driver, not a second loader.
use crate::configuration::Config;
use crate::driver::{DriverBridge, DriverCalls, DriverResult};
use std::ffi::c_void;
pub type Module = usize;
pub type Function = usize;
pub trait KernelDriver: DriverCalls {
    /// Runtime-domain preparation error; preserve loader35 without Driver mapping.
    fn prepare_kernel(&self) -> Result<(), i32>;
    fn prepare_globals(&self) -> Result<(), i32>;
    fn global(&self, module: Module, symbol: &[u8]) -> DriverResult<(u64, usize)>;
    fn attribute(&self, attribute: i32, device: i32) -> DriverResult<i32>;
    fn load(&self, image: &[u8]) -> DriverResult<Module>;
    fn function(&self, module: Module, symbol: &[u8]) -> DriverResult<Function>;
    fn unload(&self, module: Module) -> i32;
    unsafe fn launch(&self, function: Function, config: Config, args: *mut *mut c_void) -> i32;
}
impl DriverBridge {
    fn global_function(&self) -> Result<usize, i32> {
        crate::cached(&self.global, || {
            #[cfg(windows)]
            {
                crate::platform::resolve_global(
                    &crate::platform::windows::WinPlatform,
                    &self._owned,
                )
            }
            #[cfg(not(windows))]
            {
                Err(35)
            }
        })
        .copied()
    }
    fn kernel_table(&self) -> Result<&[usize; 5], i32> {
        crate::cached(&self.kernel, || {
            #[cfg(windows)]
            {
                crate::platform::resolve_kernel(
                    &crate::platform::windows::WinPlatform,
                    &self._owned,
                )
            }
            #[cfg(not(windows))]
            {
                Err(35)
            }
        })
    }
}
macro_rules! invoke {
    ($s:expr,$index:expr,$ty:ty,$fallback:expr,$($arg:expr),*) => {{
        let table=match $s.kernel_table() {Ok(t)=>t,Err(_)=>return $fallback};
        let function:$ty=unsafe {std::mem::transmute(table[$index])};
        unsafe {function($($arg),*)}
    }};
}
fn output(code: i32, value: usize) -> DriverResult<usize> {
    if code != 0 {
        Err(code)
    } else if value == 0 {
        Err(999)
    } else {
        Ok(value)
    }
}
impl KernelDriver for DriverBridge {
    fn prepare_globals(&self) -> Result<(), i32> {
        self.global_function().map(|_| ())
    }
    fn global(&self, module: Module, symbol: &[u8]) -> DriverResult<(u64, usize)> {
        if symbol.last() != Some(&0) {
            return Err(1);
        }
        let address = self.global_function().map_err(|_| 999)?;
        let function: unsafe extern "system" fn(*mut u64, *mut usize, usize, *const u8) -> i32 =
            unsafe { std::mem::transmute(address) };
        let (mut pointer, mut size) = (0, 0);
        let code = unsafe { function(&mut pointer, &mut size, module, symbol.as_ptr()) };
        if code != 0 {
            Err(code)
        } else {
            Ok((pointer, size))
        }
    }
    fn prepare_kernel(&self) -> Result<(), i32> {
        self.kernel_table().map(|_| ())
    }
    fn attribute(&self, attribute: i32, device: i32) -> DriverResult<i32> {
        let mut out = 0;
        let code = invoke!(
            self,
            4,
            unsafe extern "system" fn(*mut i32, i32, i32) -> i32,
            Err(999),
            &mut out,
            attribute,
            device
        );
        if code == 0 {
            Ok(out)
        } else {
            Err(code)
        }
    }
    fn load(&self, image: &[u8]) -> DriverResult<Module> {
        let mut out = 0usize;
        let code = invoke!(
            self,
            0,
            unsafe extern "system" fn(*mut usize, *const c_void) -> i32,
            Err(999),
            &mut out,
            image.as_ptr().cast()
        );
        output(code, out)
    }
    fn function(&self, module: Module, symbol: &[u8]) -> DriverResult<Function> {
        if symbol.last() != Some(&0) {
            return Err(1);
        }
        let mut out = 0usize;
        let code = invoke!(
            self,
            1,
            unsafe extern "system" fn(*mut usize, usize, *const u8) -> i32,
            Err(999),
            &mut out,
            module,
            symbol.as_ptr()
        );
        output(code, out)
    }
    fn unload(&self, module: Module) -> i32 {
        invoke!(
            self,
            3,
            unsafe extern "system" fn(usize) -> i32,
            999,
            module
        )
    }
    unsafe fn launch(&self, function: Function, c: Config, args: *mut *mut c_void) -> i32 {
        invoke!(
            self,
            2,
            unsafe extern "system" fn(
                usize,
                u32,
                u32,
                u32,
                u32,
                u32,
                u32,
                u32,
                *mut c_void,
                *mut *mut c_void,
                *mut *mut c_void,
            ) -> i32,
            999,
            function,
            c.grid.x,
            c.grid.y,
            c.grid.z,
            c.block.x,
            c.block.y,
            c.block.z,
            c.shared as u32,
            c.stream as *mut c_void,
            args,
            std::ptr::null_mut()
        )
    }
}

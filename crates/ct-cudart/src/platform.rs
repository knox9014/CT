pub const SYMBOLS: [&[u8]; 15] = [
    b"cuInit\0",
    b"cuDeviceGetCount\0",
    b"cuDeviceGet\0",
    b"cuCtxGetCurrent\0",
    b"cuCtxGetDevice\0",
    b"cuCtxSetCurrent\0",
    b"cuDevicePrimaryCtxRetain\0",
    b"cuDevicePrimaryCtxRelease_v2\0",
    b"cuCtxSynchronize\0",
    b"cuMemAlloc_v2\0",
    b"cuMemFree_v2\0",
    b"cuMemcpyHtoD_v2\0",
    b"cuMemcpyDtoH_v2\0",
    b"cuMemcpyDtoD_v2\0",
    b"cuMemsetD8_v2\0",
];
pub trait Platform {
    type Owned;
    fn load_owned(&self) -> Result<Self::Owned, i32>;
    fn check_identity(&self, modules: &Self::Owned) -> Result<(), i32>;
    fn resolve(&self, modules: &Self::Owned, name: &[u8]) -> Result<usize, i32>;
    fn pin(&self, modules: &Self::Owned) -> Result<(), i32>;
}
pub fn bootstrap<P: Platform>(platform: &P) -> Result<(P::Owned, [usize; 15]), i32> {
    let owned = platform.load_owned()?;
    platform.check_identity(&owned)?;
    let mut table = [0; 15];
    for (out, name) in table.iter_mut().zip(SYMBOLS) {
        *out = platform.resolve(&owned, name)?;
    }
    platform.pin(&owned)?;
    Ok((owned, table))
}

#[cfg(windows)]
pub mod windows {
    use super::Platform;
    use std::ffi::{c_void, OsString};
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use std::path::{Path, PathBuf};
    type Handle = *mut c_void;
    #[repr(C)]
    #[derive(Default, PartialEq, Eq)]
    struct FileInfo {
        attributes: u32,
        created: [u32; 2],
        accessed: [u32; 2],
        written: [u32; 2],
        volume: u32,
        size_high: u32,
        size_low: u32,
        links: u32,
        index_high: u32,
        index_low: u32,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetModuleHandleExW(flags: u32, address: *const u16, module: *mut Handle) -> i32;
        fn GetModuleFileNameW(module: Handle, path: *mut u16, size: u32) -> u32;
        fn LoadLibraryExW(path: *const u16, file: Handle, flags: u32) -> Handle;
        fn FreeLibrary(module: Handle) -> i32;
        fn GetProcAddress(module: Handle, name: *const u8) -> *mut c_void;
        fn GetCurrentProcess() -> Handle;
        fn K32EnumProcessModules(
            process: Handle,
            modules: *mut Handle,
            size: u32,
            needed: *mut u32,
        ) -> i32;
        fn CreateFileW(
            path: *const u16,
            access: u32,
            share: u32,
            security: Handle,
            creation: u32,
            flags: u32,
            template: Handle,
        ) -> Handle;
        fn GetFileInformationByHandle(file: Handle, info: *mut FileInfo) -> i32;
        fn CloseHandle(file: Handle) -> i32;
    }
    struct Module(usize);
    impl Drop for Module {
        fn drop(&mut self) {
            unsafe {
                FreeLibrary(self.0 as Handle);
            }
        }
    }
    fn hold(address: usize, pin: bool) -> Result<Module, i32> {
        let mut module = std::ptr::null_mut();
        if unsafe { GetModuleHandleExW(4 | u32::from(pin), address as *const u16, &mut module) }
            == 0
        {
            return Err(35);
        }
        Ok(Module(module as usize))
    }
    fn path(module: &Module) -> Result<PathBuf, i32> {
        let mut buffer = vec![0u16; 32768];
        let size = unsafe {
            GetModuleFileNameW(module.0 as Handle, buffer.as_mut_ptr(), buffer.len() as u32)
        } as usize;
        if size == 0 || size >= buffer.len() {
            return Err(35);
        }
        Ok(PathBuf::from(OsString::from_wide(&buffer[..size])))
    }
    fn wide(path: &Path) -> Vec<u16> {
        path.as_os_str().encode_wide().chain(Some(0)).collect()
    }
    fn identity(path: &Path) -> Result<(u32, u32, u32), i32> {
        let file = unsafe {
            CreateFileW(
                wide(path).as_ptr(),
                0,
                7,
                std::ptr::null_mut(),
                3,
                0,
                std::ptr::null_mut(),
            )
        };
        if file as isize == -1 {
            return Err(35);
        }
        let mut info = FileInfo::default();
        let ok = unsafe { GetFileInformationByHandle(file, &mut info) };
        unsafe {
            CloseHandle(file);
        }
        if ok == 0 {
            return Err(35);
        }
        Ok((info.volume, info.index_high, info.index_low))
    }
    pub struct Owned {
        runtime: Module,
        driver: Module,
        expected: (u32, u32, u32),
    }
    pub struct WinPlatform;
    impl Platform for WinPlatform {
        type Owned = Owned;
        fn load_owned(&self) -> Result<Owned, i32> {
            let runtime = hold(Self::load_owned as *const () as usize, false)?;
            let adjacent = path(&runtime)?.parent().ok_or(35)?.join("nvcuda.dll");
            let expected = identity(&adjacent)?;
            // Own every enumerated handle before inspecting it; disappearing modules fail closed.
            let mut handles = vec![std::ptr::null_mut(); 2048];
            let mut needed = 0;
            if unsafe {
                K32EnumProcessModules(
                    GetCurrentProcess(),
                    handles.as_mut_ptr(),
                    (handles.len() * std::mem::size_of::<Handle>()) as u32,
                    &mut needed,
                )
            } == 0
                || needed as usize > handles.len() * std::mem::size_of::<Handle>()
            {
                return Err(35);
            }
            let mut candidates = Vec::new();
            for &handle in &handles[..needed as usize / std::mem::size_of::<Handle>()] {
                let module = hold(handle as usize, false)?;
                let location = path(&module)?;
                if location
                    .file_name()
                    .is_some_and(|n| n.to_string_lossy().eq_ignore_ascii_case("nvcuda.dll"))
                {
                    if identity(&location)? != expected {
                        return Err(35);
                    }
                    candidates.push(module);
                }
            }
            let driver =
                unsafe { LoadLibraryExW(wide(&adjacent).as_ptr(), std::ptr::null_mut(), 0x1100) };
            if driver.is_null() {
                return Err(35);
            }
            let driver = Module(driver as usize);
            if candidates.iter().any(|m| m.0 != driver.0) {
                return Err(35);
            }
            Ok(Owned {
                runtime,
                driver,
                expected,
            })
        }
        fn check_identity(&self, owned: &Owned) -> Result<(), i32> {
            if identity(&path(&owned.driver)?)? != owned.expected {
                Err(35)
            } else {
                Ok(())
            }
        }
        fn resolve(&self, owned: &Owned, name: &[u8]) -> Result<usize, i32> {
            let address =
                unsafe { GetProcAddress(owned.driver.0 as Handle, name.as_ptr()) } as usize;
            if address == 0 || hold(address, false)?.0 != owned.driver.0 {
                return Err(35);
            }
            Ok(address)
        }
        fn pin(&self, owned: &Owned) -> Result<(), i32> {
            let _runtime = hold(owned.runtime.0, true)?;
            let _driver = hold(owned.driver.0, true)?;
            Ok(())
        }
    }
}

use std::cell::Cell;
use std::ffi::{c_char, c_void};

#[link(name = "kernel32")]
extern "system" {
    fn LoadLibraryExW(name: *const u16, file: *mut c_void, flags: u32) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const c_char) -> *mut c_void;
    fn FreeLibrary(module: *mut c_void) -> i32;
}

pub struct Api {
    module: usize,
    pub keep_loaded: Cell<bool>,
}
impl Api {
    pub fn open() -> Result<Self, String> {
        let name: Vec<u16> = "ze_loader.dll\0".encode_utf16().collect();
        // LOAD_LIBRARY_SEARCH_SYSTEM32: never resolve an application-local DLL.
        let module = unsafe { LoadLibraryExW(name.as_ptr(), std::ptr::null_mut(), 0x800) };
        if module.is_null() {
            return Err(format!(
                "System32 ze_loader.dll unavailable: {}",
                std::io::Error::last_os_error()
            ));
        }
        Ok(Self {
            module: module as usize,
            keep_loaded: Cell::new(false),
        })
    }

    /// Caller must use the exact C ABI signature from the pinned Level Zero header.
    ///
    /// # Safety
    /// T must be the matching function-pointer type, and name must be one NUL-
    /// terminated ASCII export name from the official Level Zero header.
    pub unsafe fn symbol<T: Copy>(&self, name: &[u8]) -> Result<T, String> {
        if name.last() != Some(&0) || std::mem::size_of::<T>() != std::mem::size_of::<*mut c_void>()
        {
            return Err("invalid function-pointer request".into());
        }
        let address = GetProcAddress(self.module as *mut c_void, name.as_ptr().cast());
        if address.is_null() {
            return Err(format!(
                "Level Zero symbol unavailable: {}",
                String::from_utf8_lossy(&name[..name.len() - 1])
            ));
        }
        Ok(std::mem::transmute_copy(&address))
    }
}
impl Drop for Api {
    fn drop(&mut self) {
        // Pending GPU work retains both buffers and the loader until process exit.
        if !self.keep_loaded.get() {
            unsafe {
                FreeLibrary(self.module as *mut c_void);
            }
        }
    }
}

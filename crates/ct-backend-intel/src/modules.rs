//! Native module lifetimes and synchronous launches, serialized by CT runtime.
use super::*;
use std::ffi::CString;

impl Backend {
    pub fn load_module(&self, c: &mut Context, code: &[u8], entry: &str) -> NativeResult<Module> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        let name = CString::new(entry).map_err(|_| BAD_ARGUMENT)?;
        unsafe {
            let mut module = Module {
                native: 0,
                kernel: 0,
            };
            let mut handle = null_mut();
            let mut log = null_mut();
            let descriptor = ModuleDesc {
                stype: 0x1b,
                next: null(),
                format: 0,
                size: code.len(),
                input: code.as_ptr(),
                flags: c"".as_ptr(),
                constants: null(),
            };
            let mut result = ze!(
                self.api,
                "zeModuleCreate",
                (Handle, Handle, *const ModuleDesc, *mut Handle, *mut Handle),
                (
                    c.native as Handle,
                    self.devices[c.device].native as Handle,
                    &descriptor,
                    &mut handle,
                    &mut log
                )
            );
            module.native = handle as usize;
            if !log.is_null() {
                if let Err(code) = ze!(self.api, "zeModuleBuildLogDestroy", (Handle), (log)) {
                    result = Err(code);
                }
            }
            if result.is_ok() {
                let descriptor = KernelDesc {
                    stype: 0x1d,
                    next: null(),
                    flags: 0,
                    name: name.as_ptr(),
                };
                let mut kernel = null_mut();
                result = ze!(
                    self.api,
                    "zeKernelCreate",
                    (Handle, *const KernelDesc, *mut Handle),
                    (handle, &descriptor, &mut kernel)
                );
                module.kernel = kernel as usize;
            }
            if let Err(code) = result {
                if self.unload_module(c, &mut module).is_err() {
                    c.retained_modules.push(module);
                }
                return Err(code);
            }
            Ok(module)
        }
    }
    pub fn unload_module(&self, c: &mut Context, module: &mut Module) -> NativeResult<()> {
        if c.poisoned {
            self.api.keep_loaded.set(true);
            return Err(UNKNOWN);
        }
        unsafe {
            if module.kernel != 0 {
                if let Err(code) = ze!(
                    self.api,
                    "zeKernelDestroy",
                    (Handle),
                    (module.kernel as Handle)
                ) {
                    c.poisoned = true;
                    self.api.keep_loaded.set(true);
                    return Err(code);
                }
                module.kernel = 0;
            }
            if module.native != 0 {
                if let Err(code) = ze!(
                    self.api,
                    "zeModuleDestroy",
                    (Handle),
                    (module.native as Handle)
                ) {
                    c.poisoned = true;
                    self.api.keep_loaded.set(true);
                    return Err(code);
                }
                module.native = 0;
            }
        }
        Ok(())
    }
    pub fn launch(
        &self,
        c: &mut Context,
        module: &Module,
        args: &[Vec<u8>],
        grid: u32,
        block: u32,
    ) -> NativeResult<()> {
        if c.poisoned || module.kernel == 0 {
            return Err(UNKNOWN);
        }
        unsafe {
            for (index, data) in args.iter().enumerate() {
                ze!(
                    self.api,
                    "zeKernelSetArgumentValue",
                    (Handle, u32, usize, *const c_void),
                    (
                        module.kernel as Handle,
                        index as u32,
                        data.len(),
                        data.as_ptr().cast()
                    )
                )?;
            }
            ze!(
                self.api,
                "zeKernelSetGroupSize",
                (Handle, u32, u32, u32),
                (module.kernel as Handle, block, 1, 1)
            )?;
            let groups = GroupCount {
                x: grid,
                y: 1,
                z: 1,
            };
            let result = ze!(
                self.api,
                "zeCommandListAppendLaunchKernel",
                (Handle, Handle, *const GroupCount, Handle, u32, *mut Handle),
                (
                    c.list as Handle,
                    module.kernel as Handle,
                    &groups,
                    null_mut(),
                    0,
                    null_mut()
                )
            );
            if result.is_err() {
                c.poisoned = true;
                self.api.keep_loaded.set(true);
            }
            result
        }
    }
}

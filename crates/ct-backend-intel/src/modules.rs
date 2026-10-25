//! Native module lifetimes and synchronous launches, serialized by CT runtime.
use super::*;
fn validate_global_extent(
    pointer: u64,
    actual: usize,
    expected: usize,
    prior: impl IntoIterator<Item = NativeGlobal>,
) -> NativeResult<()> {
    let end = pointer.checked_add(actual as u64).ok_or(BAD_ARGUMENT)?;
    if !matches!(expected, 4 | 8)
        || actual != expected
        || pointer == 0
        || !pointer.is_multiple_of(expected as u64)
        || prior.into_iter().any(|g| {
            g.pointer
                .checked_add(g.size as u64)
                .is_none_or(|other_end| pointer < other_end && g.pointer < end)
        })
    {
        return Err(BAD_ARGUMENT);
    }
    Ok(())
}
use std::ffi::CString;

fn validate_dimensions(
    grid: [u32; 3],
    block: [u32; 3],
    max_groups: [u32; 3],
    max_group: [u32; 4],
) -> NativeResult<()> {
    let mut volume = 1u64;
    for axis in 0..3 {
        if grid[axis] == 0
            || block[axis] == 0
            || grid[axis] > max_groups[axis]
            || block[axis] > max_group[axis + 1]
            || u64::from(grid[axis]) * u64::from(block[axis]) > u64::from(u32::MAX)
        {
            return Err(BAD_ARGUMENT);
        }
        volume = volume
            .checked_mul(u64::from(block[axis]))
            .ok_or(BAD_ARGUMENT)?;
    }
    if volume > u64::from(max_group[0]) {
        return Err(BAD_ARGUMENT);
    }
    Ok(())
}

impl Device {
    pub fn validate_launch(&self, grid: [u32; 3], block: [u32; 3]) -> NativeResult<()> {
        validate_dimensions(grid, block, self.max_groups, self.max_group)
    }
}

fn create_kernel_handles(
    names: &[CString],
    handles: &mut Vec<usize>,
    mut create: impl FnMut(&CString, &mut usize) -> NativeResult<()>,
) -> NativeResult<()> {
    for name in names {
        let mut handle = 0;
        let result = create(name, &mut handle);
        if handle != 0 {
            handles.push(handle);
        }
        result?;
        if handle == 0 {
            return Err(UNKNOWN);
        }
    }
    Ok(())
}

fn destroy_kernel_handles(
    handles: &mut [usize],
    mut destroy: impl FnMut(usize) -> NativeResult<()>,
) -> NativeResult<()> {
    for handle in handles {
        if *handle != 0 {
            destroy(*handle)?;
            *handle = 0;
        }
    }
    Ok(())
}

impl Backend {
    pub fn load_module(&self, c: &mut Context, code: &[u8], entry: &str) -> NativeResult<Module> {
        self.load_module_entries(c, code, &[entry])
    }
    pub fn load_module_entries(
        &self,
        c: &mut Context,
        code: &[u8],
        entries: &[&str],
    ) -> NativeResult<Module> {
        self.load_module_entries_with_globals(c, code, entries, &[])
    }
    pub fn load_module_entries_with_globals(
        &self,
        c: &mut Context,
        code: &[u8],
        entries: &[&str],
        globals: &[(&str, usize)],
    ) -> NativeResult<Module> {
        if c.poisoned {
            return Err(UNKNOWN);
        }
        if entries.is_empty() || entries.len() > 32 {
            return Err(BAD_ARGUMENT);
        }
        let mut unique = std::collections::BTreeSet::new();
        let mut names = Vec::new();
        for entry in entries {
            if entry.is_empty() || !unique.insert(*entry) {
                return Err(BAD_ARGUMENT);
            }
            names.push(CString::new(*entry).map_err(|_| BAD_ARGUMENT)?);
        }
        if globals.len() > 256 {
            return Err(BAD_ARGUMENT);
        }
        let mut global_records = Vec::new();
        global_records
            .try_reserve_exact(globals.len())
            .map_err(|_| 0x70000003u32)?;
        for &(name, size) in globals {
            if name.is_empty() || name.len() > 128 || !matches!(size, 4 | 8) || !unique.insert(name)
            {
                return Err(BAD_ARGUMENT);
            }
            global_records.push((
                CString::new(name).map_err(|_| BAD_ARGUMENT)?,
                NativeGlobal { pointer: 0, size },
            ));
        }
        type GetGlobal =
            unsafe extern "C" fn(Handle, *const std::ffi::c_char, *mut usize, *mut Handle) -> u32;
        let get_global: Option<GetGlobal> = if globals.is_empty() {
            None
        } else {
            Some(
                unsafe { self.api.symbol(b"zeModuleGetGlobalPointer\0") }
                    .map_err(|_| 0x78000003u32)?,
            )
        };
        unsafe {
            let mut module = Module {
                native: 0,
                kernels: Vec::with_capacity(names.len()),
                globals: global_records,
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
            let _ = c.observe(&self.api, result);
            if !log.is_null() {
                if c.poisoned {
                    c.retained_build_logs.push(log as usize);
                } else if let Err(code) = ze!(self.api, "zeModuleBuildLogDestroy", (Handle), (log))
                {
                    c.poisoned = true;
                    self.api.keep_loaded.set(true);
                    c.retained_build_logs.push(log as usize);
                    // A cleanup failure must not replace the original error.
                    if result.is_ok() {
                        result = Err(code);
                    }
                }
            }
            if result.is_ok() {
                result = create_kernel_handles(&names, &mut module.kernels, |name, storage| {
                    let descriptor = KernelDesc {
                        stype: 0x1d,
                        next: null(),
                        flags: 0,
                        name: name.as_ptr(),
                    };
                    let mut kernel = null_mut();
                    let created = ze!(
                        self.api,
                        "zeKernelCreate",
                        (Handle, *const KernelDesc, *mut Handle),
                        (handle, &descriptor, &mut kernel)
                    );
                    *storage = kernel as usize;
                    created
                });
                let _ = c.observe(&self.api, result);
            }
            if result.is_ok() {
                if let Some(query) = get_global {
                    for index in 0..module.globals.len() {
                        let mut size = 0;
                        let mut pointer = null_mut();
                        let code = query(
                            handle,
                            module.globals[index].0.as_ptr(),
                            &mut size,
                            &mut pointer,
                        );
                        // A declared CT symbol absent from native storage is unsupported.
                        // Keep this operation-specific; other native errors retain their code.
                        let query_result = match code {
                            0 => Ok(()),
                            0x78000010 => Err(0x78000003), // INVALID_GLOBAL_NAME -> UNSUPPORTED_FEATURE
                            _ => Err(code),
                        };
                        result = c.observe(&self.api, query_result);
                        if result.is_err() {
                            break;
                        }
                        let base = pointer as u64;
                        if validate_global_extent(
                            base,
                            size,
                            module.globals[index].1.size,
                            module.globals[..index].iter().map(|(_, g)| *g),
                        )
                        .is_err()
                        {
                            result = Err(BAD_ARGUMENT);
                            break;
                        }
                        module.globals[index].1 = NativeGlobal {
                            pointer: base,
                            size,
                        };
                    }
                }
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
            if let Err(code) = destroy_kernel_handles(&mut module.kernels, |kernel| {
                ze!(self.api, "zeKernelDestroy", (Handle), (kernel as Handle))
            }) {
                c.poisoned = true;
                self.api.keep_loaded.set(true);
                return Err(code);
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
                module.globals.clear();
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
        self.launch_entry(c, module, 0, args, grid, block)
    }
    pub fn launch_entry(
        &self,
        c: &mut Context,
        module: &Module,
        entry: usize,
        args: &[Vec<u8>],
        grid: u32,
        block: u32,
    ) -> NativeResult<()> {
        self.launch_entry_3d(c, module, entry, args, [grid, 1, 1], [block, 1, 1])
    }
    pub fn launch_entry_3d(
        &self,
        c: &mut Context,
        module: &Module,
        entry: usize,
        args: &[Vec<u8>],
        grid: [u32; 3],
        block: [u32; 3],
    ) -> NativeResult<()> {
        let kernel = *module.kernels.get(entry).ok_or(BAD_ARGUMENT)?;
        if c.poisoned || kernel == 0 {
            return Err(UNKNOWN);
        }
        self.devices
            .get(c.device)
            .ok_or(BAD_ARGUMENT)?
            .validate_launch(grid, block)?;
        unsafe {
            for (index, data) in args.iter().enumerate() {
                let result = ze!(
                    self.api,
                    "zeKernelSetArgumentValue",
                    (Handle, u32, usize, *const c_void),
                    (
                        kernel as Handle,
                        index as u32,
                        data.len(),
                        data.as_ptr().cast()
                    )
                );
                c.observe(&self.api, result)?;
            }
            let result = ze!(
                self.api,
                "zeKernelSetGroupSize",
                (Handle, u32, u32, u32),
                (kernel as Handle, block[0], block[1], block[2])
            );
            c.observe(&self.api, result)?;
            let groups = GroupCount {
                x: grid[0],
                y: grid[1],
                z: grid[2],
            };
            let result = ze!(
                self.api,
                "zeCommandListAppendLaunchKernel",
                (Handle, Handle, *const GroupCount, Handle, u32, *mut Handle),
                (
                    c.list as Handle,
                    kernel as Handle,
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

#[cfg(test)]
mod cleanup_tests {
    use super::*;
    #[test]
    fn validates_mixed_global_extents() {
        let prior = [NativeGlobal {
            pointer: 4096,
            size: 4,
        }];
        assert!(validate_global_extent(4104, 8, 8, prior).is_ok());
        assert!(validate_global_extent(4100, 4, 4, prior).is_ok());
        for (pointer, actual, expected) in [
            (0, 8, 8),
            (4100, 8, 8),
            (4104, 4, 8),
            (4096, 8, 8),
            (u64::MAX - 7, 8, 8),
            (4104, 16, 16),
        ] {
            assert!(validate_global_extent(pointer, actual, expected, prior).is_err());
        }
        assert!(validate_global_extent(
            4100,
            4,
            4,
            [NativeGlobal {
                pointer: 4096,
                size: 8
            }]
        )
        .is_err());
    }
    #[test]
    fn validates_each_dimension_and_checked_block_volume() {
        let group = [96, 32, 16, 8];
        let counts = [101, 71, 43];
        assert_eq!(
            validate_dimensions([3, 5, 7], [4, 3, 2], counts, group),
            Ok(())
        );
        assert_eq!(validate_dimensions(counts, [1; 3], counts, group), Ok(()));
        assert_eq!(
            validate_dimensions([1; 3], [8, 4, 3], counts, group),
            Ok(())
        );
        for axis in 0..3 {
            for bad in [0, counts[axis] + 1] {
                let mut grid = [1; 3];
                grid[axis] = bad;
                assert_eq!(
                    validate_dimensions(grid, [1; 3], counts, group),
                    Err(BAD_ARGUMENT)
                );
            }
            for bad in [0, group[axis + 1] + 1] {
                let mut block = [1; 3];
                block[axis] = bad;
                assert_eq!(
                    validate_dimensions([1; 3], block, counts, group),
                    Err(BAD_ARGUMENT)
                );
            }
            let mut grid = [1; 3];
            grid[axis] = u32::MAX;
            let mut block = [1; 3];
            block[axis] = 2;
            assert_eq!(
                validate_dimensions(grid, block, [u32::MAX; 3], [u32::MAX; 4]),
                Err(BAD_ARGUMENT)
            );
        }
        assert_eq!(
            validate_dimensions([1; 3], [8, 4, 4], counts, group),
            Err(BAD_ARGUMENT)
        );
        assert_eq!(
            validate_dimensions([1; 3], [u32::MAX; 3], [u32::MAX; 3], [u32::MAX; 4]),
            Err(BAD_ARGUMENT)
        );
    }
    #[test]
    fn failed_destroy_retains_only_live_handles_and_skips_destroyed_ones() {
        let mut handles = [11, 0, 22, 33];
        let mut calls = Vec::new();
        let result = destroy_kernel_handles(&mut handles, |h| {
            calls.push(h);
            if h == 22 {
                Err(UNKNOWN)
            } else {
                Ok(())
            }
        });
        assert_eq!(result, Err(UNKNOWN));
        assert_eq!(calls, vec![11, 22]);
        assert_eq!(handles, [0, 0, 22, 33]);
        calls.clear();
        destroy_kernel_handles(&mut handles, |h| {
            calls.push(h);
            Ok(())
        })
        .unwrap();
        assert_eq!(calls, vec![22, 33]);
        assert_eq!(handles, [0, 0, 0, 0]);
    }
    #[test]
    fn failed_creation_retains_partial_handles_for_ordered_cleanup() {
        let names = [
            CString::new("first").unwrap(),
            CString::new("second").unwrap(),
            CString::new("third").unwrap(),
        ];
        let mut handles = Vec::new();
        let mut count = 0;
        let result = create_kernel_handles(&names, &mut handles, |_, handle| {
            count += 1;
            *handle = count;
            if count == 2 {
                Err(UNKNOWN)
            } else {
                Ok(())
            }
        });
        assert_eq!(result, Err(UNKNOWN));
        assert_eq!(count, 2);
        assert_eq!(handles, vec![1, 2]);
        let mut destroyed = Vec::new();
        destroy_kernel_handles(&mut handles, |h| {
            destroyed.push(h);
            Ok(())
        })
        .unwrap();
        assert_eq!(destroyed, vec![1, 2]);
        assert_eq!(handles, vec![0, 0]);
    }
}

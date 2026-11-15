//! Private fake foreign calls; production backend methods remain the test subject.
use super::*;
use std::cell::{Cell, RefCell};
use std::collections::BTreeMap;

const LOST: u32 = 0x70000001;
const RESET: u32 = 0x70000006;
const OOM: u32 = 0x70000003;
#[derive(Default)]
struct State {
    calls: Vec<(&'static str, usize)>,
    counts: BTreeMap<&'static str, usize>,
    failures: Vec<(&'static str, usize, u32)>,
    build_log: bool,
    buffers: BTreeMap<usize, Box<[u8]>>,
    next: usize,
    global_results: Vec<(usize, usize)>,
    global_names: Vec<String>,
    missing_global_api: bool,
    missing_clock: bool,
    missing_clock_properties: bool,
    clock_frequency: u64,
    clock_bits: u32,
    clock_ticks: u64,
    clock_stypes: Vec<u32>,
    topology: (u32, u32),
    missing_memory_properties: bool,
    memory_counts: Vec<u32>,
    memory_total: u64,
    memory_queries: Vec<(usize, u32, bool, u32, bool)>,
    missing_kernel_resources: bool,
    kernel_resource_values: [u32; 11],
}
impl State {
    fn call(&mut self, name: &'static str, handle: Handle) -> u32 {
        self.calls.push((name, handle as usize));
        let count = self.counts.entry(name).or_default();
        *count += 1;
        self.failures
            .iter()
            .find(|&&(expected, nth, _)| name == expected && *count == nth)
            .map_or(0, |&(_, _, code)| code)
    }
    fn handle(&mut self) -> Handle {
        self.next += 1;
        (100 + self.next) as Handle
    }
    fn buffer(&mut self, size: usize) -> Handle {
        let mut data = vec![0u8; size].into_boxed_slice();
        let address = data.as_mut_ptr() as usize;
        self.buffers.insert(address, data);
        address as Handle
    }
}
thread_local! { static STATE: RefCell<State> = RefCell::new(State::default()); }
fn state<T>(f: impl FnOnce(&mut State) -> T) -> T {
    STATE.with(|s| f(&mut s.borrow_mut()))
}
fn arm(name: &'static str, nth: usize, code: u32) {
    state(|s| {
        s.failures
            .push((name, s.counts.get(name).copied().unwrap_or(0) + nth, code))
    });
}
fn count(name: &str) -> usize {
    state(|s| s.calls.iter().filter(|(n, _)| *n == name).count())
}
pub(super) struct Api {
    pub keep_loaded: Cell<bool>,
}
impl Api {
    pub fn open() -> Result<Self, String> {
        Ok(Self {
            keep_loaded: Cell::new(false),
        })
    }
    pub unsafe fn symbol<T: Copy>(&self, name: &[u8]) -> Result<T, String> {
        if name == b"zeKernelGetProperties\0" && state(|s| s.missing_kernel_resources) {
            return Err("missing optional kernel properties API".into());
        }
        if name == b"zeDeviceGetMemoryProperties\0" && state(|s| s.missing_memory_properties) {
            return Err("missing optional memory properties API".into());
        }
        if name == b"zeModuleGetGlobalPointer\0" && state(|s| s.missing_global_api) {
            return Err("missing optional global API".into());
        }
        if name == b"zeDeviceGetGlobalTimestamps\0" && state(|s| s.missing_clock) {
            return Err("missing optional clock API".into());
        }
        if name == b"zeDeviceGetProperties\0" && state(|s| s.missing_clock_properties) {
            return Err("missing optional clock properties API".into());
        }
        let address = match name {
            b"zeInit\0" => enumerate_init as *const (),
            b"zeDriverGet\0" => enumerate_drivers as *const (),
            b"zeDeviceGet\0" => enumerate_devices as *const (),
            b"zeDeviceGetComputeProperties\0" => enumerate_compute as *const (),
            b"zeDeviceGetMemoryProperties\0" => memory_properties as *const (),
            b"zeDeviceGetProperties\0" => clock_properties as *const (),
            b"zeDeviceGetGlobalTimestamps\0" => clock_timestamp as *const (),
            b"zeMemAllocHost\0" => alloc_host as *const (),
            b"zeMemAllocDevice\0" => alloc_device as *const (),
            b"zeMemFree\0" => free as *const (),
            b"zeCommandListAppendMemoryCopy\0" => copy as *const (),
            b"zeCommandListAppendMemoryFill\0" => fill as *const (),
            b"zeModuleCreate\0" => create_module as *const (),
            b"zeModuleGetGlobalPointer\0" => get_global as *const (),
            b"zeModuleBuildLogDestroy\0" => destroy_log as *const (),
            b"zeKernelCreate\0" => create_kernel as *const (),
            b"zeKernelGetProperties\0" => kernel_properties as *const (),
            b"zeKernelSetArgumentValue\0" => argument as *const (),
            b"zeKernelSetGroupSize\0" => group as *const (),
            b"zeCommandListAppendLaunchKernel\0" => launch as *const (),
            b"zeCommandListHostSynchronize\0" => synchronize as *const (),
            b"zeKernelDestroy\0" => destroy_kernel as *const (),
            b"zeModuleDestroy\0" => destroy_module as *const (),
            b"zeCommandListDestroy\0" => destroy_list as *const (),
            b"zeContextDestroy\0" => destroy_context as *const (),
            _ => return Err("unimplemented synthetic symbol".into()),
        };
        assert_eq!(std::mem::size_of::<T>(), std::mem::size_of_val(&address));
        Ok(std::mem::transmute_copy(&address))
    }
}
unsafe extern "C" fn kernel_properties(kernel: Handle, out: *mut KernelProperties) -> u32 {
    state(|s| {
        let code = s.call("zeKernelGetProperties", kernel);
        assert_eq!((*out).stype, 0x1e);
        assert!((*out).next.is_null());
        let v = s.kernel_resource_values;
        (*out).num_kernel_args = v[0];
        (*out).required_group_size_x = v[1];
        (*out).required_group_size_y = v[2];
        (*out).required_group_size_z = v[3];
        (*out).required_num_subgroups = v[4];
        (*out).required_subgroup_size = v[5];
        (*out).max_subgroup_size = v[6];
        (*out).max_num_subgroups = v[7];
        (*out).local_mem_size = v[8];
        (*out).private_mem_size = v[9];
        (*out).spill_mem_size = v[10];
        (*out).uuid = [0xa5; 32];
        code
    })
}

fn resource_module() -> Module {
    Module {
        native: 90,
        kernels: vec![91, 92],
        globals: Vec::new(),
    }
}

#[test]
fn kernel_resources_preserve_every_raw_field_and_select_entry() {
    let (b, mut c) = fixture();
    let values = [7, 2, 3, 4, 5, 8, 32, 17, 1024, 96, 128];
    state(|s| s.kernel_resource_values = values);
    let actual = b.kernel_resources(&mut c, &resource_module(), 1).unwrap();
    assert_eq!(
        actual,
        KernelResources {
            num_kernel_args: 7,
            required_group_size: [2, 3, 4],
            required_num_subgroups: 5,
            required_subgroup_size: 8,
            max_subgroup_size: 32,
            max_num_subgroups: 17,
            local_mem_bytes: 1024,
            private_mem_bytes: 96,
            spill_mem_bytes: 128,
        }
    );
    assert_eq!(state(|s| s.calls.clone()), [("zeKernelGetProperties", 92)]);
    assert!(!c.poisoned);
}

#[test]
fn kernel_resources_preserve_zeroes_without_inventing_limits() {
    let (b, mut c) = fixture();
    let actual = b.kernel_resources(&mut c, &resource_module(), 0).unwrap();
    assert_eq!(actual.max_subgroup_size, 0);
    assert_eq!(actual.max_num_subgroups, 0);
    assert_eq!(actual.local_mem_bytes, 0);
    assert_eq!(actual.required_group_size, [0; 3]);
}

#[test]
fn kernel_resources_reject_dead_invalid_and_poisoned_before_native_query() {
    let (b, mut c) = fixture();
    let mut module = resource_module();
    for entry in [2, usize::MAX] {
        assert_eq!(
            b.kernel_resources(&mut c, &module, entry),
            Err(BAD_ARGUMENT)
        );
    }
    module.kernels[0] = 0;
    assert_eq!(b.kernel_resources(&mut c, &module, 0), Err(BAD_ARGUMENT));
    module.native = 0;
    assert_eq!(b.kernel_resources(&mut c, &module, 1), Err(BAD_ARGUMENT));
    c.poisoned = true;
    assert_eq!(b.kernel_resources(&mut c, &module, 1), Err(UNKNOWN));
    assert_eq!(state(|s| s.calls.len()), 0);
}

#[test]
fn kernel_resources_optional_query_and_native_failures_preserve_error_policy() {
    let (b, mut c) = fixture();
    state(|s| s.missing_kernel_resources = true);
    assert_eq!(
        b.kernel_resources(&mut c, &resource_module(), 0),
        Err(UNSUPPORTED)
    );
    assert!(!c.poisoned);
    assert_eq!(state(|s| s.calls.len()), 0);
    for code in [OOM, UNSUPPORTED, LOST, RESET] {
        let (b, mut c) = fixture();
        arm("zeKernelGetProperties", 1, code);
        assert_eq!(b.kernel_resources(&mut c, &resource_module(), 0), Err(code));
        assert_eq!(c.poisoned, matches!(code, LOST | RESET));
        assert_eq!(b.api.keep_loaded.get(), c.poisoned);
        if c.poisoned {
            assert_eq!(
                b.kernel_resources(&mut c, &resource_module(), 0),
                Err(UNKNOWN)
            );
            assert_eq!(count("zeKernelGetProperties"), 1);
        } else {
            assert!(b.kernel_resources(&mut c, &resource_module(), 0).is_ok());
            assert_eq!(count("zeKernelGetProperties"), 2);
        }
    }
}
unsafe extern "C" fn memory_properties(
    device: Handle,
    count: *mut u32,
    props: *mut DeviceMemoryProperties,
) -> u32 {
    state(|s| {
        let code = s.call("zeDeviceGetMemoryProperties", device);
        if code != 0 {
            return code;
        }
        let (stype, next_null) = if props.is_null() {
            (0, true)
        } else {
            ((*props).stype, (*props).next.is_null())
        };
        s.memory_queries
            .push((device as usize, *count, !props.is_null(), stype, next_null));
        let result = if s.memory_counts.is_empty() {
            1
        } else {
            s.memory_counts.remove(0)
        };
        if !props.is_null() {
            assert_eq!(*count, 1);
            assert_eq!(stype, 7);
            assert!(next_null);
            if result > 0 {
                (*props).total_size = s.memory_total;
            }
        } else {
            assert_eq!(*count, 0);
        }
        count.write(result);
        0
    })
}
unsafe extern "C" fn clock_properties(device: Handle, out: *mut DeviceProperties) -> u32 {
    state(|s| {
        let code = s.call("zeDeviceGetProperties", device);
        s.clock_stypes.push((*out).stype);
        if code == 0 {
            if (*out).stype == 3 {
                (*out).kind = 1;
                (*out).vendor = 0x8086;
                (*out).slices = s.topology.0;
                (*out).subslices = s.topology.1;
            }
            (*out).timer = s.clock_frequency;
            (*out).timestamp_bits = s.clock_bits;
        }
        code
    })
}
unsafe extern "C" fn enumerate_init(flags: u32) -> u32 {
    assert_eq!(flags, 1);
    0
}
unsafe extern "C" fn enumerate_drivers(count: *mut u32, out: *mut Handle) -> u32 {
    count.write(1);
    if !out.is_null() {
        out.write(1usize as Handle);
    }
    0
}
unsafe extern "C" fn enumerate_devices(_: Handle, count: *mut u32, out: *mut Handle) -> u32 {
    count.write(1);
    if !out.is_null() {
        out.write(2usize as Handle);
    }
    0
}
unsafe extern "C" fn enumerate_compute(_: Handle, out: *mut ComputeProperties) -> u32 {
    (*out).max_total = 1024;
    0
}

#[test]
fn enumeration_preserves_raw_maximum_topology_even_when_policy_would_refuse() {
    for pair in [(0, 3), (3, 0), (2, 6), (u32::MAX, 2)] {
        state(|s| {
            *s = State {
                topology: pair,
                ..State::default()
            }
        });
        let backend = Backend::open().unwrap();
        assert_eq!(backend.devices.len(), 1);
        assert_eq!(backend.devices[0].max_slices, pair.0);
        assert_eq!(backend.devices[0].max_subslices_per_slice, pair.1);
    }
}
unsafe extern "C" fn clock_timestamp(device: Handle, host: *mut u64, ticks: *mut u64) -> u32 {
    state(|s| {
        let code = s.call("zeDeviceGetGlobalTimestamps", device);
        if code == 0 {
            s.clock_ticks += 100;
            host.write(777);
            ticks.write(s.clock_ticks);
        }
        code
    })
}
unsafe extern "C" fn alloc_host(
    ctx: Handle,
    _: *const HostAllocDesc,
    size: usize,
    _: usize,
    out: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeMemAllocHost", ctx);
        if code == 0 {
            out.write(s.buffer(size));
        }
        code
    })
}
unsafe extern "C" fn alloc_device(
    ctx: Handle,
    _: *const DeviceAllocDesc,
    size: usize,
    _: usize,
    _: Handle,
    out: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeMemAllocDevice", ctx);
        if code == 0 {
            out.write(s.buffer(size));
        }
        code
    })
}
unsafe extern "C" fn free(_: Handle, pointer: Handle) -> u32 {
    state(|s| {
        let code = s.call("zeMemFree", pointer);
        if code == 0 {
            assert!(
                s.buffers.remove(&(pointer as usize)).is_some(),
                "double or foreign free"
            );
        }
        code
    })
}
unsafe extern "C" fn copy(
    list: Handle,
    dst: Handle,
    src: *const c_void,
    size: usize,
    _: Handle,
    _: u32,
    _: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeCommandListAppendMemoryCopy", list);
        if code == 0 {
            std::ptr::copy_nonoverlapping(src.cast::<u8>(), dst.cast::<u8>(), size);
        }
        code
    })
}
unsafe extern "C" fn fill(
    list: Handle,
    dst: Handle,
    pattern: *const c_void,
    width: usize,
    size: usize,
    _: Handle,
    _: u32,
    _: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeCommandListAppendMemoryFill", list);
        if code == 0 {
            for offset in 0..size {
                dst.cast::<u8>()
                    .add(offset)
                    .write(pattern.cast::<u8>().add(offset % width).read());
            }
        }
        code
    })
}
unsafe extern "C" fn create_module(
    ctx: Handle,
    _: Handle,
    _: *const ModuleDesc,
    out: *mut Handle,
    log: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeModuleCreate", ctx);
        if code == 0 {
            out.write(s.handle());
        }
        log.write(if s.build_log { s.handle() } else { null_mut() });
        code
    })
}
unsafe extern "C" fn create_kernel(module: Handle, _: *const KernelDesc, out: *mut Handle) -> u32 {
    state(|s| {
        let code = s.call("zeKernelCreate", module);
        out.write(s.handle());
        code
    })
}
unsafe extern "C" fn argument(kernel: Handle, _: u32, _: usize, _: *const c_void) -> u32 {
    state(|s| s.call("zeKernelSetArgumentValue", kernel))
}
unsafe extern "C" fn group(kernel: Handle, _: u32, _: u32, _: u32) -> u32 {
    state(|s| s.call("zeKernelSetGroupSize", kernel))
}
unsafe extern "C" fn launch(
    list: Handle,
    _: Handle,
    _: *const GroupCount,
    _: Handle,
    _: u32,
    _: *mut Handle,
) -> u32 {
    state(|s| s.call("zeCommandListAppendLaunchKernel", list))
}
unsafe extern "C" fn synchronize(list: Handle, _: u64) -> u32 {
    state(|s| s.call("zeCommandListHostSynchronize", list))
}
macro_rules! destroy {
    ($fn:ident, $name:literal) => {
        unsafe extern "C" fn $fn(handle: Handle) -> u32 {
            state(|s| s.call($name, handle))
        }
    };
}
destroy!(destroy_kernel, "zeKernelDestroy");
destroy!(destroy_module, "zeModuleDestroy");
destroy!(destroy_list, "zeCommandListDestroy");
destroy!(destroy_context, "zeContextDestroy");
destroy!(destroy_log, "zeModuleBuildLogDestroy");

fn fixture() -> (Backend, Context) {
    state(|s| {
        *s = State {
            clock_frequency: 2_000_000,
            clock_bits: 40,
            memory_total: 1u64 << 40,
            ..State::default()
        }
    });
    let b = Backend {
        api: Api::open().unwrap(),
        devices: vec![Device {
            driver: 1,
            native: 2,
            name: "synthetic".into(),
            uuid: [0; 16],
            max_group: [1024; 4],
            max_groups: [1024; 3],
            shared_mem: 65536,
            max_slices: 0,
            max_subslices_per_slice: 0,
        }],
        orphaned: Vec::new(),
    };
    (b, context(3))
}

#[test]
fn memory_total_rejects_invalid_device_before_native_calls() {
    let (b, _) = fixture();
    assert_eq!(b.total_memory(usize::MAX), Err(BAD_ARGUMENT));
    assert_eq!(state(|s| s.calls.len()), 0);
}

#[test]
fn memory_total_preserves_driver_reported_64_bit_value_and_query_abi() {
    let (b, _) = fixture();
    assert_eq!(b.total_memory(0), Ok(1u64 << 40));
    assert_eq!(
        state(|s| s.memory_queries.clone()),
        vec![
            (2, 0, false, 0, true),
            (2, 1, true, 7, true),
            (2, 0, false, 0, true)
        ]
    );
    assert_eq!(count("zeContextCreate"), 0);
}

#[test]
fn memory_total_missing_symbol_and_ambiguous_counts_are_unsupported() {
    let (b, _) = fixture();
    state(|s| s.missing_memory_properties = true);
    assert_eq!(b.total_memory(0), Err(UNSUPPORTED));
    assert_eq!(state(|s| s.calls.len()), 0);
    for (counts, calls) in [
        (vec![0], 1),
        (vec![2], 1),
        (vec![u32::MAX], 1),
        (vec![1, 0], 2),
        (vec![1, 2], 2),
        (vec![1, 1, 0], 3),
        (vec![1, 1, 2], 3),
    ] {
        let (b, _) = fixture();
        state(|s| s.memory_counts = counts);
        assert_eq!(b.total_memory(0), Err(UNSUPPORTED));
        assert_eq!(count("zeDeviceGetMemoryProperties"), calls);
    }
    let (b, _) = fixture();
    state(|s| s.memory_total = 0);
    assert_eq!(b.total_memory(0), Err(UNSUPPORTED));
    assert_eq!(count("zeDeviceGetMemoryProperties"), 2);
}

#[test]
fn memory_total_preserves_each_native_error_and_latches_fatal_loader_lifetime() {
    for nth in 1..=3 {
        for code in [LOST, RESET, OOM, UNSUPPORTED, UNKNOWN] {
            let (b, _) = fixture();
            arm("zeDeviceGetMemoryProperties", nth, code);
            assert_eq!(b.total_memory(0), Err(code));
            assert_eq!(count("zeDeviceGetMemoryProperties"), nth);
            assert_eq!(b.api.keep_loaded.get(), matches!(code, LOST | RESET));
        }
    }
}
fn context(id: usize) -> Context {
    Context {
        native: id,
        list: id + 10,
        max_fill_pattern: 4,
        retained_patterns: Vec::new(),
        device: 0,
        poisoned: false,
        staging: Vec::new(),
        retained_modules: Vec::new(),
        retained_build_logs: Vec::new(),
    }
}
fn loaded(b: &Backend, c: &mut Context) -> Module {
    b.load_module_entries(c, &[3, 2, 35, 7], &["first", "second"])
        .unwrap()
}
fn run(b: &Backend, c: &mut Context, m: &Module) -> NativeResult<()> {
    b.launch_entry_3d(c, m, 0, &[vec![0; 4]], [2, 3, 2], [3, 2, 2])
}
fn blocked(b: &Backend, c: &mut Context, m: &mut Module, address: u64) {
    let before = state(|s| s.calls.len());
    let mut host = [0u8; 4];
    assert!(b.allocate(c, 4).is_err());
    assert!(b.free(c, address).is_err());
    assert!(unsafe { b.copy(c, address, host.as_mut_ptr().cast(), 4, true) }.is_err());
    assert!(unsafe { b.copy(c, address, host.as_mut_ptr().cast(), 0, false) }.is_err());
    assert!(b.load_module(c, &[0; 4], "first").is_err());
    assert!(run(b, c, m).is_err());
    assert!(b.synchronize(c).is_err());
    assert!(b.unload_module(c, m).is_err());
    assert!(b.destroy_context(c, &[address]).is_err());
    assert_eq!(
        state(|s| s.calls.len()),
        before,
        "poisoned context reached native driver"
    );
    assert!(b.api.keep_loaded.get());
}

#[test]
fn failed_launch_reports_original_error_and_blocks_every_later_native_operation() {
    let (b, mut c) = fixture();
    let address = b.allocate(&mut c, 4).unwrap();
    let mut m = loaded(&b, &mut c);
    arm("zeCommandListAppendLaunchKernel", 1, LOST);
    assert_eq!(run(&b, &mut c, &m), Err(LOST));
    assert!(c.poisoned);
    blocked(&b, &mut c, &mut m, address);
    assert!(state(|s| s.buffers.contains_key(&(address as usize))));
    assert_ne!(m.native, 0);
    assert!(m.kernels.iter().all(|&h| h != 0));
    let mut other = context(90);
    assert_eq!(b.synchronize(&mut other), Ok(()));
}

#[test]
fn failed_copy_preserves_staging_and_does_not_publish_unconfirmed_dtoh_bytes() {
    for to_device in [true, false] {
        let (b, mut c) = fixture();
        let address = b.allocate(&mut c, 4).unwrap();
        let mut host = [7u8; 4];
        arm("zeCommandListAppendMemoryCopy", 1, LOST);
        assert_eq!(
            unsafe { b.copy(&mut c, address, host.as_mut_ptr().cast(), 4, to_device) },
            Err(LOST)
        );
        assert_eq!(host, [7; 4]);
        assert!(c.poisoned);
        assert_eq!(c.staging.len(), 1);
        assert!(state(|s| s.buffers.contains_key(&c.staging[0])));
        assert_eq!(count("zeMemFree"), 0);
        let mut m = Module {
            globals: Vec::new(),
            native: 101,
            kernels: vec![102],
        };
        blocked(&b, &mut c, &mut m, address);
    }
}

#[test]
fn failed_staging_free_retains_buffer_and_is_never_retried() {
    let (b, mut c) = fixture();
    let address = b.allocate(&mut c, 4).unwrap();
    let mut host = [9u8; 4];
    arm("zeMemFree", 1, LOST);
    assert_eq!(
        unsafe { b.copy(&mut c, address, host.as_mut_ptr().cast(), 4, true) },
        Err(LOST)
    );
    assert_eq!(c.staging.len(), 1);
    assert!(c.poisoned);
    assert_eq!(count("zeMemFree"), 1);
    let mut m = Module {
        globals: Vec::new(),
        native: 101,
        kernels: vec![102],
    };
    blocked(&b, &mut c, &mut m, address);
    assert_eq!(count("zeMemFree"), 1);
}

#[test]
fn failed_synchronization_poison_stops_cleanup_of_possibly_live_resources() {
    let (b, mut c) = fixture();
    let address = b.allocate(&mut c, 4).unwrap();
    let mut m = loaded(&b, &mut c);
    arm("zeCommandListHostSynchronize", 1, 1);
    assert_eq!(b.synchronize(&mut c), Err(1));
    assert!(c.poisoned);
    blocked(&b, &mut c, &mut m, address);
}

#[test]
fn partial_kernel_cleanup_never_destroys_a_module_with_live_kernels() {
    let (b, mut c) = fixture();
    let mut m = loaded(&b, &mut c);
    let original = m.kernels.clone();
    arm("zeKernelDestroy", 2, LOST);
    assert_eq!(b.unload_module(&mut c, &mut m), Err(LOST));
    assert_eq!(m.kernels, vec![0, original[1]]);
    assert_ne!(m.native, 0);
    assert_eq!(count("zeModuleDestroy"), 0);
    assert!(b.unload_module(&mut c, &mut m).is_err());
    assert_eq!(count("zeKernelDestroy"), 2);
}

#[test]
fn failed_module_destroy_retains_native_module_without_redestroying_kernels() {
    let (b, mut c) = fixture();
    let mut m = loaded(&b, &mut c);
    arm("zeModuleDestroy", 1, LOST);
    assert_eq!(b.unload_module(&mut c, &mut m), Err(LOST));
    assert_eq!(m.kernels, vec![0, 0]);
    assert_ne!(m.native, 0);
    assert!(b.unload_module(&mut c, &mut m).is_err());
    assert_eq!(count("zeKernelDestroy"), 2);
    assert_eq!(count("zeModuleDestroy"), 1);
}

#[test]
fn failed_context_cleanup_stops_at_first_uncertain_resource_without_retry() {
    for name in ["zeCommandListDestroy", "zeMemFree", "zeContextDestroy"] {
        let (b, mut c) = fixture();
        let address = b.allocate(&mut c, 4).unwrap();
        arm(name, 1, LOST);
        assert_eq!(b.destroy_context(&mut c, &[address]), Err(LOST));
        assert!(c.poisoned);
        let calls = state(|s| s.calls.len());
        assert!(b.destroy_context(&mut c, &[address]).is_err());
        assert_eq!(state(|s| s.calls.len()), calls);
        if name == "zeCommandListDestroy" {
            assert_eq!(count("zeMemFree"), 0);
            assert_ne!(c.list, 0);
        }
        if name != "zeContextDestroy" {
            assert_eq!(count("zeContextDestroy"), 0);
            assert!(state(|s| s.buffers.contains_key(&(address as usize))));
        }
    }
}

#[test]
fn fatal_setup_errors_poison_but_ordinary_setup_errors_allow_a_later_launch() {
    for name in ["zeKernelSetArgumentValue", "zeKernelSetGroupSize"] {
        for code in [LOST, RESET, BAD_ARGUMENT] {
            let (b, mut c) = fixture();
            let mut m = loaded(&b, &mut c);
            arm(name, 1, code);
            assert_eq!(run(&b, &mut c, &m), Err(code));
            assert_eq!(count("zeCommandListAppendLaunchKernel"), 0);
            if code == BAD_ARGUMENT {
                assert!(!c.poisoned);
                assert_eq!(run(&b, &mut c, &m), Ok(()));
            } else {
                assert!(c.poisoned, "fatal kernel setup error left context usable");
                blocked(&b, &mut c, &mut m, 0);
            }
        }
    }
}

#[test]
fn fatal_memory_errors_and_any_free_error_poison_but_allocation_oom_allows_retry() {
    for name in ["zeMemAllocDevice", "zeMemAllocHost", "zeMemFree"] {
        for code in [LOST, RESET, OOM] {
            let (b, mut c) = fixture();
            let address = b.allocate(&mut c, 4).unwrap();
            arm(name, 1, code);
            let mut host = [1u8; 4];
            let result = match name {
                "zeMemAllocDevice" => b.allocate(&mut c, 4).map(|_| ()),
                "zeMemAllocHost" => unsafe {
                    b.copy(&mut c, address, host.as_mut_ptr().cast(), 4, true)
                },
                _ => b.free(&mut c, address),
            };
            assert_eq!(result, Err(code));
            if code == OOM && name != "zeMemFree" {
                assert!(!c.poisoned);
                assert_eq!(b.synchronize(&mut c), Ok(()));
            } else {
                assert!(c.poisoned, "fatal memory error left context usable");
                let mut m = Module {
                    globals: Vec::new(),
                    native: 101,
                    kernels: vec![102],
                };
                blocked(&b, &mut c, &mut m, address);
            }
        }
    }
}

#[test]
fn fatal_module_creation_error_poison_prevents_reusing_the_context() {
    for code in [LOST, RESET, OOM] {
        let (b, mut c) = fixture();
        arm("zeModuleCreate", 1, code);
        assert_eq!(b.load_module(&mut c, &[0; 4], "first").err(), Some(code));
        if code == OOM {
            assert!(!c.poisoned);
            assert!(b.load_module(&mut c, &[0; 4], "first").is_ok());
        } else {
            assert!(c.poisoned, "fatal module creation left context usable");
        }
    }
}

#[test]
fn partial_creation_failure_cleans_returned_handles_before_module() {
    let (b, mut c) = fixture();
    arm("zeKernelCreate", 2, OOM);
    assert_eq!(
        b.load_module_entries(&mut c, &[0; 4], &["first", "second", "third"])
            .err(),
        Some(OOM)
    );
    assert_eq!(count("zeKernelCreate"), 2);
    assert_eq!(count("zeKernelDestroy"), 2);
    assert_eq!(count("zeModuleDestroy"), 1);
    assert!(!c.poisoned);
    let names = state(|s| s.calls.iter().map(|(n, _)| *n).collect::<Vec<_>>());
    assert!(
        names.iter().rposition(|&n| n == "zeKernelDestroy")
            < names.iter().position(|&n| n == "zeModuleDestroy")
    );
}

#[test]
fn successful_copy_returns_bytes_and_releases_each_staging_buffer_once() {
    let (b, mut c) = fixture();
    let address = b.allocate(&mut c, 4).unwrap();
    let mut source = [1u8, 2, 3, 4];
    let mut destination = [0u8; 4];
    unsafe {
        b.copy(&mut c, address, source.as_mut_ptr().cast(), 4, true)
            .unwrap();
        b.copy(&mut c, address, destination.as_mut_ptr().cast(), 4, false)
            .unwrap();
    }
    assert_eq!(destination, [1, 2, 3, 4]);
    assert!(c.staging.is_empty());
    assert_eq!(count("zeMemFree"), 2);
    b.free(&mut c, address).unwrap();
    assert!(state(|s| s.buffers.is_empty()));
}

#[test]
fn module_build_log_failure_preserves_primary_error_and_stops_native_cleanup() {
    for initial in [0, OOM, LOST] {
        let (b, mut c) = fixture();
        state(|s| s.build_log = true);
        if initial != 0 {
            arm("zeModuleCreate", 1, initial);
        }
        arm("zeModuleBuildLogDestroy", 1, BAD_ARGUMENT);
        let expected = if initial == 0 { BAD_ARGUMENT } else { initial };
        assert_eq!(
            b.load_module(&mut c, &[0; 4], "first").err(),
            Some(expected)
        );
        assert!(
            c.poisoned,
            "uncertain build log cleanup left context usable"
        );
        assert_eq!(c.retained_build_logs.len(), 1);
        assert_eq!(count("zeKernelCreate"), 0);
        assert_eq!(count("zeModuleDestroy"), 0);
        assert_eq!(
            count("zeModuleBuildLogDestroy"),
            usize::from(initial != LOST)
        );
        assert!(b.api.keep_loaded.get());
    }
}

#[test]
fn fatal_partial_kernel_creation_preserves_handles_instead_of_destroying_them() {
    let (b, mut c) = fixture();
    arm("zeKernelCreate", 2, LOST);
    assert_eq!(
        b.load_module_entries(&mut c, &[0; 4], &["first", "second"])
            .err(),
        Some(LOST)
    );
    assert!(c.poisoned);
    assert_eq!(c.retained_modules.len(), 1);
    assert_eq!(c.retained_modules[0].kernels.len(), 2);
    assert!(c.retained_modules[0].kernels.iter().all(|&h| h != 0));
    assert_eq!(count("zeKernelDestroy"), 0);
    assert_eq!(count("zeModuleDestroy"), 0);
}

#[test]
fn context_free_failure_after_one_success_does_not_retry_either_allocation() {
    let (b, mut c) = fixture();
    let a = b.allocate(&mut c, 4).unwrap();
    let d = b.allocate(&mut c, 4).unwrap();
    arm("zeMemFree", 2, LOST);
    assert_eq!(b.destroy_context(&mut c, &[a, d]), Err(LOST));
    assert!(!state(|s| s.buffers.contains_key(&(a as usize))));
    assert!(state(|s| s.buffers.contains_key(&(d as usize))));
    assert!(b.destroy_context(&mut c, &[a, d]).is_err());
    assert_eq!(count("zeMemFree"), 2);
    assert_eq!(count("zeContextDestroy"), 0);
}

#[test]
fn direct_device_commands_poison_on_failure_and_never_submit_again() {
    for fill in [false, true] {
        let (b, mut c) = fixture();
        let source = b.allocate(&mut c, 16).unwrap();
        let destination = b.allocate(&mut c, 16).unwrap();
        let command = if fill {
            "zeCommandListAppendMemoryFill"
        } else {
            "zeCommandListAppendMemoryCopy"
        };
        arm(command, 1, LOST);
        let result = if fill {
            b.fill_device(&mut c, destination, 0xaabbccdd, 4, 16)
        } else {
            b.copy_device(&mut c, destination, source, 16)
        };
        assert_eq!(result, Err(LOST));
        assert!(c.poisoned && b.api.keep_loaded.get());
        assert_eq!(c.retained_patterns.len(), usize::from(fill));
        let before = state(|s| s.calls.len());
        assert!(b.copy_device(&mut c, destination, source, 0).is_err());
        assert!(b.fill_device(&mut c, destination, 0, 1, 0).is_err());
        assert!(b.destroy_context(&mut c, &[source, destination]).is_err());
        assert_eq!(state(|s| s.calls.len()), before);
        assert_eq!(count("zeMemFree"), 0);
    }
}

#[test]
fn device_fill_respects_selected_queue_pattern_limit_without_poisoning() {
    let (b, mut c) = fixture();
    let address = b.allocate(&mut c, 16).unwrap();
    c.max_fill_pattern = 1;
    let before = state(|s| s.calls.len());
    assert_eq!(
        b.fill_device(&mut c, address, 0x12345678, 4, 16),
        Err(0x78000003)
    );
    assert_eq!(b.fill_device(&mut c, address, 0, 2, 16), Err(0x78000003));
    assert_eq!(state(|s| s.calls.len()), before);
    assert!(!c.poisoned && !b.api.keep_loaded.get());
    assert_eq!(b.fill_device(&mut c, address, 0x78, 1, 16), Ok(()));
    assert_eq!(count("zeCommandListAppendMemoryFill"), 1);
    assert!(c.retained_patterns.is_empty());
    assert_eq!(b.free(&mut c, address), Ok(()));
}

unsafe extern "C" fn get_global(
    module: Handle,
    name: *const std::ffi::c_char,
    size: *mut usize,
    pointer: *mut Handle,
) -> u32 {
    state(|s| {
        let code = s.call("zeModuleGetGlobalPointer", module);
        let index = s.global_names.len();
        s.global_names
            .push(std::ffi::CStr::from_ptr(name).to_str().unwrap().to_string());
        let (n, p) = s
            .global_results
            .get(index)
            .copied()
            .unwrap_or((4, 0x1000 + index * 4));
        size.write(n);
        pointer.write(p as Handle);
        code
    })
}
#[test]
fn module_globals_are_native_owned_and_exactly_named() {
    let (b, mut c) = fixture();
    let mut m = b
        .load_module_entries_with_globals(
            &mut c,
            &[0; 4],
            &["first"],
            &[("counter", 4), ("zero", 4)],
        )
        .unwrap();
    assert_eq!(m.global("counter").unwrap().pointer, 0x1000);
    assert_eq!(m.global("zero").unwrap().size, 4);
    assert!(m.global("absent").is_none());
    assert_eq!(state(|s| s.global_names.clone()), ["counter", "zero"]);
    b.unload_module(&mut c, &mut m).unwrap();
    assert!(m.global("counter").is_none());
    assert_eq!(count("zeMemFree"), 0);
    assert_eq!(count("zeModuleDestroy"), 1);
}
#[test]
fn bad_global_result_rolls_back_without_memory_free() {
    for result in [(8, 0x1000), (4, 0), (4, 0x1001), (4, usize::MAX - 3)] {
        let (b, mut c) = fixture();
        state(|s| s.global_results.push(result));
        assert!(b
            .load_module_entries_with_globals(&mut c, &[0; 4], &["first"], &[("g", 4)])
            .is_err());
        assert_eq!(count("zeModuleDestroy"), 1);
        assert_eq!(count("zeMemFree"), 0);
        assert!(c.retained_modules.is_empty());
    }
    let (b, mut c) = fixture();
    state(|s| s.global_results = vec![(4, 0x1000), (4, 0x1000)]);
    assert!(b
        .load_module_entries_with_globals(&mut c, &[0; 4], &["first"], &[("g", 4), ("h", 4)])
        .is_err());
    assert_eq!(count("zeModuleDestroy"), 1);
}
#[test]
fn global_failure_retains_module_if_cleanup_is_uncertain() {
    for nth in [1, 2] {
        let (b, mut c) = fixture();
        arm("zeModuleGetGlobalPointer", nth, OOM);
        arm("zeModuleDestroy", 1, OOM);
        let result =
            b.load_module_entries_with_globals(&mut c, &[0; 4], &["first"], &[("g", 4), ("h", 4)]);
        assert!(matches!(result, Err(OOM)));
        assert!(c.poisoned);
        assert_eq!(c.retained_modules.len(), 1);
        assert_eq!(count("zeMemFree"), 0);
    }
}
#[test]
fn optional_global_api_does_not_affect_no_global_modules() {
    let (b, mut c) = fixture();
    state(|s| s.missing_global_api = true);
    let mut m = loaded(&b, &mut c);
    b.unload_module(&mut c, &mut m).unwrap();
    assert!(matches!(
        b.load_module_entries_with_globals(&mut c, &[0; 4], &["first"], &[("g", 4)]),
        Err(0x78000003)
    ));
    assert_eq!(count("zeModuleCreate"), 1);
}

#[test]
fn native_missing_global_is_unsupported_and_keeps_cleanup_policy() {
    for (nth, failed_cleanup) in [(1, false), (2, false), (1, true), (2, true)] {
        let (b, mut c) = fixture();
        arm("zeModuleGetGlobalPointer", nth, 0x78000010);
        if failed_cleanup {
            arm("zeModuleDestroy", 1, OOM);
        }
        let result =
            b.load_module_entries_with_globals(&mut c, &[0; 4], &["first"], &[("g", 4), ("h", 4)]);
        assert!(matches!(result, Err(0x78000003)));
        assert_eq!(c.retained_modules.len(), usize::from(failed_cleanup));
        assert_eq!(c.poisoned, failed_cleanup);
        assert_eq!(count("zeMemFree"), 0);
    }
}

#[test]
fn owned_host_allocation_uses_native_host_storage_and_free() {
    let (b, mut c) = fixture();
    assert!(b.allocate_host(&mut c, 0).is_err());
    assert_eq!(count("zeMemAllocHost"), 0);
    let p = b.allocate_host(&mut c, 32).unwrap();
    assert_eq!(count("zeMemAllocHost"), 1);
    assert_eq!(count("zeMemAllocDevice"), 0);
    unsafe {
        std::ptr::write_bytes(p as *mut u8, 0x5a, 32);
    }
    assert!(state(|s| s.buffers[&(p as usize)]
        .iter()
        .all(|&v| v == 0x5a)));
    assert_eq!(b.free(&mut c, p), Ok(()));
    assert!(!state(|s| s.buffers.contains_key(&(p as usize))));
}

#[test]
fn owned_host_allocation_oom_retries_but_fatal_error_poisons() {
    let (b, mut c) = fixture();
    arm("zeMemAllocHost", 1, OOM);
    assert_eq!(b.allocate_host(&mut c, 16), Err(OOM));
    assert!(!c.poisoned);
    let p = b.allocate_host(&mut c, 16).unwrap();
    assert_eq!(b.free(&mut c, p), Ok(()));
    arm("zeMemAllocHost", 1, LOST);
    assert_eq!(b.allocate_host(&mut c, 16), Err(LOST));
    assert!(c.poisoned);
    let before = count("zeMemAllocHost");
    assert!(b.allocate_host(&mut c, 16).is_err());
    assert_eq!(count("zeMemAllocHost"), before);
    assert!(b.api.keep_loaded.get());
}

#[test]
fn owned_host_free_failure_keeps_storage_and_never_retries() {
    let (b, mut c) = fixture();
    let p = b.allocate_host(&mut c, 32).unwrap();
    arm("zeMemFree", 1, OOM);
    assert_eq!(b.free(&mut c, p), Err(OOM));
    assert!(c.poisoned);
    assert!(state(|s| s.buffers.contains_key(&(p as usize))));
    assert!(b.free(&mut c, p).is_err());
    assert!(b.destroy_context(&mut c, &[p]).is_err());
    assert_eq!(count("zeMemFree"), 1);
    assert_eq!(count("zeContextDestroy"), 0);
}

#[test]
fn mixed_host_device_cleanup_orders_and_quarantines_partial_free() {
    for fail in [false, true] {
        let (b, mut c) = fixture();
        let device = b.allocate(&mut c, 16).unwrap();
        let host = b.allocate_host(&mut c, 16).unwrap();
        if fail {
            arm("zeMemFree", 2, OOM);
        }
        let result = b.destroy_context(&mut c, &[device, host]);
        if fail {
            assert_eq!(result, Err(OOM));
            assert!(c.poisoned);
            assert!(!state(|s| s.buffers.contains_key(&(device as usize))));
            assert!(state(|s| s.buffers.contains_key(&(host as usize))));
            let before = count("zeMemFree");
            assert!(b.destroy_context(&mut c, &[device, host]).is_err());
            assert_eq!(count("zeMemFree"), before);
            assert_eq!(count("zeContextDestroy"), 0);
        } else {
            assert_eq!(result, Ok(()));
            assert_eq!(count("zeContextDestroy"), 1);
            state(|s| {
                let list = s
                    .calls
                    .iter()
                    .position(|&(n, _)| n == "zeCommandListDestroy")
                    .unwrap();
                let first = s.calls.iter().position(|&(n, _)| n == "zeMemFree").unwrap();
                let ctx = s
                    .calls
                    .iter()
                    .position(|&(n, _)| n == "zeContextDestroy")
                    .unwrap();
                assert!(list < first && first < ctx);
            });
        }
    }
}

#[test]
fn gpu_clock_uses_explicit_frequency_properties_and_real_ticks() {
    let (b, mut c) = fixture();
    let stamp = b.timestamp(&mut c).unwrap();
    assert_eq!(stamp.frequency, 2_000_000);
    assert_eq!(stamp.bits, 40);
    assert_eq!(stamp.ticks, 100);
    assert_eq!(count("zeDeviceGetGlobalTimestamps"), 1);
    assert!(state(|s| s.clock_stypes.iter().all(|&v| v == 0x20006)));
}
#[test]
fn gpu_clock_missing_api_and_invalid_metadata_are_unsupported_without_poison() {
    let (b, mut c) = fixture();
    state(|s| s.missing_clock = true);
    assert_eq!(b.timestamp(&mut c).err(), Some(0x78000003));
    assert!(!c.poisoned);
    state(|s| {
        s.missing_clock = false;
        s.clock_frequency = 0;
    });
    assert_eq!(b.timestamp(&mut c).err(), Some(0x78000003));
    assert!(!c.poisoned);
}
#[test]
fn gpu_clock_failure_observes_fatal_device_state() {
    let (b, mut c) = fixture();
    arm("zeDeviceGetGlobalTimestamps", 1, LOST);
    assert_eq!(b.timestamp(&mut c).err(), Some(LOST));
    assert!(c.poisoned);
    assert!(b.api.keep_loaded.get());
    let before = count("zeDeviceGetGlobalTimestamps");
    assert!(b.timestamp(&mut c).is_err());
    assert_eq!(count("zeDeviceGetGlobalTimestamps"), before);
}

#[test]
fn gpu_clock_rejects_all_invalid_widths_before_sampling() {
    for bits in [0, 65, u32::MAX] {
        let (b, mut c) = fixture();
        state(|s| s.clock_bits = bits);
        assert_eq!(b.timestamp(&mut c), Err(UNSUPPORTED));
        assert_eq!(count("zeDeviceGetGlobalTimestamps"), 0);
        assert!(!c.poisoned);
    }
    for bits in [1, 32, 64] {
        let (b, mut c) = fixture();
        state(|s| s.clock_bits = bits);
        assert_eq!(b.timestamp(&mut c).unwrap().bits, bits);
    }
}
#[test]
fn gpu_clock_missing_properties_and_invalid_device_do_not_call_native() {
    let (b, mut c) = fixture();
    state(|s| s.missing_clock_properties = true);
    assert_eq!(b.timestamp(&mut c), Err(UNSUPPORTED));
    assert_eq!(state(|s| s.calls.len()), 0);
    c.device = usize::MAX;
    assert_eq!(b.timestamp(&mut c), Err(BAD_ARGUMENT));
    assert_eq!(state(|s| s.calls.len()), 0);
}
#[test]
fn gpu_clock_property_errors_observe_fatal_state_and_do_not_sample() {
    for code in [LOST, RESET, OOM, UNSUPPORTED] {
        let (b, mut c) = fixture();
        arm("zeDeviceGetProperties", 1, code);
        assert_eq!(b.timestamp(&mut c), Err(code));
        assert_eq!(count("zeDeviceGetGlobalTimestamps"), 0);
        assert_eq!(c.poisoned, matches!(code, LOST | RESET));
        assert_eq!(b.api.keep_loaded.get(), c.poisoned);
    }
}
#[test]
fn gpu_clock_recoverable_sample_error_allows_retry() {
    let (b, mut c) = fixture();
    arm("zeDeviceGetGlobalTimestamps", 1, OOM);
    assert_eq!(b.timestamp(&mut c), Err(OOM));
    assert!(!c.poisoned);
    assert!(!b.api.keep_loaded.get());
    assert_eq!(b.timestamp(&mut c).unwrap().ticks, 100);
}

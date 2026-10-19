//! Unsafe FFI stays in this native M0 executable, not in a CUDA-facing API.
use crate::abi::*;
use crate::loader::Api;
use crate::{group_count, verify_sum};
use std::ffi::c_void;
use std::ptr::{null, null_mut};

macro_rules! call {
    ($api:expr, $name:literal, ($($ty:ty),*), ($($arg:expr),* $(,)?)) => {{
        let function: unsafe extern "C" fn($($ty),*) -> u32 =
            $api.symbol(concat!($name, "\0").as_bytes())?;
        checked($name, function($($arg),*))
    }};
}
fn checked(operation: &str, code: u32) -> Result<(), String> {
    if code == 0 {
        Ok(())
    } else {
        Err(format!("{operation}: Level Zero result 0x{code:08x}"))
    }
}
fn json_string(value: &str) -> String {
    let mut result = String::from("\"");
    for c in value.chars() {
        match c {
            '"' => result.push_str("\\\""),
            '\\' => result.push_str("\\\\"),
            c if c < ' ' => result.push_str(&format!("\\u{:04x}", c as u32)),
            c => result.push(c),
        }
    }
    result.push('"');
    result
}
fn device_name(value: &[u8]) -> String {
    String::from_utf8_lossy(&value[..value.iter().position(|&b| b == 0).unwrap_or(value.len())])
        .into_owned()
}

struct Resources<'a> {
    api: &'a Api,
    context: Handle,
    queue: Handle,
    module: Handle,
    kernel: Handle,
    lists: Vec<Handle>,
    allocations: Vec<Handle>,
    pending: bool,
}
impl<'a> Resources<'a> {
    fn new(api: &'a Api) -> Self {
        Self {
            api,
            context: null_mut(),
            queue: null_mut(),
            module: null_mut(),
            kernel: null_mut(),
            lists: vec![],
            allocations: vec![],
            pending: false,
        }
    }
    unsafe fn release(&mut self) -> Result<(), String> {
        if self.pending {
            self.api.keep_loaded.set(true);
            return Err(
                "GPU completion not confirmed; retaining live resources until process exit".into(),
            );
        }
        let mut errors = Vec::new();
        macro_rules! release_handle {
            ($name:literal, $handle:expr) => {
                if !$handle.is_null() {
                    if let Err(error) = call!(self.api, $name, (Handle), ($handle)) {
                        errors.push(error);
                    }
                    $handle = null_mut();
                }
            };
        }
        for mut list in self.lists.drain(..).rev() {
            if let Err(error) = call!(self.api, "zeCommandListDestroy", (Handle), (list)) {
                errors.push(error);
            }
            // No further use of a destroyed command list.
            list = null_mut();
            let _ = list;
        }
        release_handle!("zeKernelDestroy", self.kernel);
        release_handle!("zeModuleDestroy", self.module);
        for allocation in self.allocations.drain(..).rev() {
            if let Err(error) = call!(
                self.api,
                "zeMemFree",
                (Handle, Handle),
                (self.context, allocation)
            ) {
                errors.push(error);
            }
        }
        release_handle!("zeCommandQueueDestroy", self.queue);
        release_handle!("zeContextDestroy", self.context);
        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors.join("; "))
        }
    }
    unsafe fn allocate(
        &mut self,
        device: Handle,
        bytes: usize,
        host: bool,
    ) -> Result<Handle, String> {
        let mut pointer = null_mut();
        if host {
            let descriptor = HostAllocDesc {
                stype: 0x16,
                next: null(),
                flags: 0,
            };
            call!(
                self.api,
                "zeMemAllocHost",
                (Handle, *const HostAllocDesc, usize, usize, *mut Handle),
                (self.context, &descriptor, bytes, 64, &mut pointer)
            )?;
        } else {
            let descriptor = DeviceAllocDesc {
                stype: 0x15,
                next: null(),
                flags: 0,
                ordinal: 0,
            };
            call!(
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
                (self.context, &descriptor, bytes, 64, device, &mut pointer)
            )?;
        }
        if pointer.is_null() {
            return Err("driver returned a null allocation".into());
        }
        self.allocations.push(pointer);
        Ok(pointer)
    }
}
impl Drop for Resources<'_> {
    fn drop(&mut self) {
        if let Err(error) = unsafe { self.release() } {
            eprintln!("cleanup: {error}");
        }
    }
}

unsafe fn copy(
    api: &Api,
    list: Handle,
    dst: Handle,
    src: Handle,
    bytes: usize,
) -> Result<(), String> {
    call!(
        api,
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
        (list, dst, src, bytes, null_mut(), 0, null_mut())
    )
}
unsafe fn barrier(api: &Api, list: Handle) -> Result<(), String> {
    call!(
        api,
        "zeCommandListAppendBarrier",
        (Handle, Handle, u32, *mut Handle),
        (list, null_mut(), 0, null_mut())
    )
}

pub fn run(module: &[u8], filter: &str) -> Result<String, String> {
    if module.len() < 20 || !module.len().is_multiple_of(4) || module[..4] != [3, 2, 35, 7] {
        return Err("invalid SPIR-V module header/word alignment".into());
    }
    if filter.is_empty() {
        return Err("an explicit Intel GPU name filter is required".into());
    }
    let api = Api::open()?;
    // These calls use official C layouts and signatures. The selected device and
    // queue limits are validated before any host slices or dispatches are made.
    unsafe { execute(&api, module, filter) }
}

unsafe fn execute(api: &Api, module: &[u8], filter: &str) -> Result<String, String> {
    call!(api, "zeInit", (u32), (1))?;
    let mut count = 0;
    call!(
        api,
        "zeDriverGet",
        (*mut u32, *mut Handle),
        (&mut count, null_mut())
    )?;
    if count == 0 {
        return Err("no Level Zero driver".into());
    }
    let mut drivers = vec![null_mut(); count as usize];
    call!(
        api,
        "zeDriverGet",
        (*mut u32, *mut Handle),
        (&mut count, drivers.as_mut_ptr())
    )?;
    let mut selected = None;
    for driver in drivers.into_iter().take(count as usize) {
        let mut n = 0;
        call!(
            api,
            "zeDeviceGet",
            (Handle, *mut u32, *mut Handle),
            (driver, &mut n, null_mut())
        )?;
        let mut devices = vec![null_mut(); n as usize];
        if n == 0 {
            continue;
        }
        call!(
            api,
            "zeDeviceGet",
            (Handle, *mut u32, *mut Handle),
            (driver, &mut n, devices.as_mut_ptr())
        )?;
        for device in devices.into_iter().take(n as usize) {
            let mut properties: DeviceProperties = blank();
            properties.stype = 3;
            call!(
                api,
                "zeDeviceGetProperties",
                (Handle, *mut DeviceProperties),
                (device, &mut properties)
            )?;
            if properties.kind == 1
                && properties.vendor == 0x8086
                && device_name(&properties.name)
                    .to_lowercase()
                    .contains(&filter.to_lowercase())
            {
                if selected.is_some() {
                    return Err("multiple matching Intel GPUs; selection is ambiguous".into());
                }
                selected = Some((driver, device, properties));
            }
        }
    }
    let (driver, device, properties) =
        selected.ok_or_else(|| format!("no Intel GPU matching {filter:?}"))?;
    let name = device_name(&properties.name);
    let mut driver_properties: DriverProperties = blank();
    driver_properties.stype = 1;
    call!(
        api,
        "zeDriverGetProperties",
        (Handle, *mut DriverProperties),
        (driver, &mut driver_properties)
    )?;
    let mut api_version = 0;
    call!(
        api,
        "zeDriverGetApiVersion",
        (Handle, *mut u32),
        (driver, &mut api_version)
    )?;
    let mut compute: ComputeProperties = blank();
    compute.stype = 4;
    call!(
        api,
        "zeDeviceGetComputeProperties",
        (Handle, *mut ComputeProperties),
        (device, &mut compute)
    )?;
    let mut queue_count = 0;
    call!(
        api,
        "zeDeviceGetCommandQueueGroupProperties",
        (Handle, *mut u32, *mut QueueGroupProperties),
        (device, &mut queue_count, null_mut())
    )?;
    if queue_count == 0 {
        return Err("no command queue groups".into());
    }
    let mut queue_properties: Vec<QueueGroupProperties> = (0..queue_count)
        .map(|_| {
            let mut p: QueueGroupProperties = blank();
            p.stype = 6;
            p
        })
        .collect();
    call!(
        api,
        "zeDeviceGetCommandQueueGroupProperties",
        (Handle, *mut u32, *mut QueueGroupProperties),
        (device, &mut queue_count, queue_properties.as_mut_ptr())
    )?;
    let ordinal = queue_properties
        .iter()
        .take(queue_count as usize)
        .position(|p| p.flags & 1 != 0 && p.count > 0)
        .ok_or("no compute-capable queue")? as u32;
    eprintln!(
        "selected {name}; Intel device 0x{:04x}; compute queue {ordinal}",
        properties.device
    );

    let mut resources = Resources::new(api);
    let context_desc = ContextDesc {
        stype: 0xd,
        next: null(),
        flags: 0,
    };
    call!(
        api,
        "zeContextCreate",
        (Handle, *const ContextDesc, *mut Handle),
        (driver, &context_desc, &mut resources.context)
    )?;
    let queue_desc = QueueDesc {
        stype: 0xe,
        next: null(),
        ordinal,
        index: 0,
        flags: 0,
        mode: 2,
        priority: 0,
    };
    call!(
        api,
        "zeCommandQueueCreate",
        (Handle, Handle, *const QueueDesc, *mut Handle),
        (resources.context, device, &queue_desc, &mut resources.queue)
    )?;
    let desc = ModuleDesc {
        stype: 0x1b,
        next: null(),
        format: 0,
        size: module.len(),
        input: module.as_ptr(),
        flags: c"".as_ptr(),
        constants: null(),
    };
    let create: unsafe extern "C" fn(
        Handle,
        Handle,
        *const ModuleDesc,
        *mut Handle,
        *mut Handle,
    ) -> u32 = api.symbol(b"zeModuleCreate\0")?;
    let mut log = null_mut();
    let result = create(
        resources.context,
        device,
        &desc,
        &mut resources.module,
        &mut log,
    );
    let build_log = read_build_log(api, log)?;
    checked("zeModuleCreate", result).map_err(|e| format!("{e}; build log: {build_log}"))?;
    let kernel_desc = KernelDesc {
        stype: 0x1d,
        next: null(),
        flags: 0,
        name: c"vector_add".as_ptr(),
    };
    call!(
        api,
        "zeKernelCreate",
        (Handle, *const KernelDesc, *mut Handle),
        (resources.module, &kernel_desc, &mut resources.kernel)
    )?;
    let mut cases = vec![];
    for group_size in [64, 128] {
        if group_size > compute.max_total || group_size > compute.max_x {
            return Err(format!(
                "required group size {group_size} exceeds device limits"
            ));
        }
        for n in [1, 63, 64, 65, 255, 256, 257, 100003] {
            cases.push(run_case(
                &mut resources,
                device,
                ordinal,
                n,
                group_size,
                compute.count_x,
            )?);
        }
    }
    resources.release()?;
    Ok(format!(
        concat!(
            "{{\"schema_version\":1,\"status\":\"pass\",\"stage\":\"M0-native\",",
            "\"cuda_compatibility\":false,\"cpu_fallback\":false,\"device\":{},",
            "\"vendor_id\":{},\"device_id\":{},\"driver_version_raw\":{},",
            "\"level_zero_api\":\"{}.{}\",\"queue_ordinal\":{},",
            "\"max_group_size\":{},\"max_group_count_x\":{},\"build_log\":{},",
            "\"cleanup\":\"pass\",\"cases\":[{}]}}"
        ),
        json_string(&name),
        properties.vendor,
        properties.device,
        driver_properties.version,
        api_version >> 16,
        api_version & 0xffff,
        ordinal,
        compute.max_total,
        compute.count_x,
        json_string(&build_log),
        cases.join(",")
    ))
}

unsafe fn read_build_log(api: &Api, log: Handle) -> Result<String, String> {
    if log.is_null() {
        return Ok(String::new());
    }
    let result = (|| {
        let mut size = 0;
        call!(
            api,
            "zeModuleBuildLogGetString",
            (Handle, *mut usize, *mut u8),
            (log, &mut size, null_mut())
        )?;
        if size > 65536 {
            return Err("module build log exceeds 64 KiB".into());
        }
        let mut bytes = vec![0_u8; size.max(1)];
        if size != 0 {
            call!(
                api,
                "zeModuleBuildLogGetString",
                (Handle, *mut usize, *mut u8),
                (log, &mut size, bytes.as_mut_ptr())
            )?;
        }
        Ok(device_name(&bytes))
    })();
    call!(api, "zeModuleBuildLogDestroy", (Handle), (log))?;
    result
}

unsafe fn run_case(
    r: &mut Resources<'_>,
    device: Handle,
    ordinal: u32,
    n: usize,
    group_size: u32,
    max_groups: u32,
) -> Result<String, String> {
    let api = r.api;
    let groups = group_count(n, group_size)?;
    if groups > max_groups {
        return Err("dispatch exceeds device group-count limit".into());
    }
    let guard = group_size as usize;
    let bytes = n * size_of::<f32>();
    let output_bytes = (n + guard) * size_of::<f32>();
    let a = r.allocate(device, bytes, true)?;
    let b = r.allocate(device, bytes, true)?;
    let output = r.allocate(device, output_bytes, true)?;
    // Driver host allocations start uninitialized. Initialize through raw writes;
    // do not create f32 references yet or retain references across GPU mutation.
    for i in 0..n {
        a.cast::<f32>()
            .add(i)
            .write(((i % 257) as f32 - 128.0) * 0.25);
        b.cast::<f32>()
            .add(i)
            .write(((i * 7 % 193) as f32 - 96.0) * 0.5);
        output.cast::<f32>().add(i).write(f32::NAN);
    }
    for i in n..n + guard {
        output.cast::<f32>().add(i).write(-12345.25);
    }
    let device_a = r.allocate(device, bytes, false)?;
    let device_b = r.allocate(device, bytes, false)?;
    let device_c = r.allocate(device, output_bytes, false)?;
    let list_desc = ListDesc {
        stype: 0xf,
        next: null(),
        ordinal,
        flags: 0,
    };
    let mut list = null_mut();
    call!(
        api,
        "zeCommandListCreate",
        (Handle, Handle, *const ListDesc, *mut Handle),
        (r.context, device, &list_desc, &mut list)
    )?;
    r.lists.push(list);
    copy(api, list, device_a, a, bytes)?;
    copy(api, list, device_b, b, bytes)?;
    copy(api, list, device_c, output, output_bytes)?;
    barrier(api, list)?;
    for (index, pointer) in [device_a, device_b, device_c].iter().enumerate() {
        call!(
            api,
            "zeKernelSetArgumentValue",
            (Handle, u32, usize, *const c_void),
            (
                r.kernel,
                index as u32,
                size_of::<Handle>(),
                (pointer as *const Handle).cast()
            )
        )?;
    }
    let length = n as u32;
    call!(
        api,
        "zeKernelSetArgumentValue",
        (Handle, u32, usize, *const c_void),
        (
            r.kernel,
            3,
            size_of::<u32>(),
            (&length as *const u32).cast()
        )
    )?;
    call!(
        api,
        "zeKernelSetGroupSize",
        (Handle, u32, u32, u32),
        (r.kernel, group_size, 1, 1)
    )?;
    let dispatch = GroupCount {
        x: groups,
        y: 1,
        z: 1,
    };
    call!(
        api,
        "zeCommandListAppendLaunchKernel",
        (Handle, Handle, *const GroupCount, Handle, u32, *mut Handle),
        (list, r.kernel, &dispatch, null_mut(), 0, null_mut())
    )?;
    barrier(api, list)?;
    copy(api, list, output, device_c, output_bytes)?;
    call!(api, "zeCommandListClose", (Handle), (list))?;
    // Even a failed submission may leave device work outstanding. Do not free
    // resources unless the queue completion call confirms success.
    r.pending = true;
    call!(
        api,
        "zeCommandQueueExecuteCommandLists",
        (Handle, u32, *mut Handle, Handle),
        (r.queue, 1, &mut list, null_mut())
    )?;
    call!(
        api,
        "zeCommandQueueSynchronize",
        (Handle, u64),
        (r.queue, 30_000_000_000)
    )?;
    r.pending = false;
    // All memory is initialized and device writes are complete before borrowing.
    let host_a = std::slice::from_raw_parts(a.cast::<f32>(), n);
    let host_b = std::slice::from_raw_parts(b.cast::<f32>(), n);
    let host_output = std::slice::from_raw_parts(output.cast::<f32>(), n + guard);
    let max_error = verify_sum(host_a, host_b, &host_output[..n])?;
    if host_output[n..].iter().any(|&v| v != -12345.25) {
        return Err(format!("kernel wrote beyond n={n}"));
    }
    eprintln!("pass n={n}, group={group_size}, groups={groups}, error={max_error}");
    Ok(format!("{{\"n\":{n},\"group_size\":{group_size},\"groups\":{groups},\"checked\":{n},\"guard_checked\":{guard},\"max_abs_error\":{max_error}}}"))
}

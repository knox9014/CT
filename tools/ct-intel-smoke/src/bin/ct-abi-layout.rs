//! Development-only ABI probe, compared with tests/abi_layout.c.
#[allow(dead_code)]
#[path = "../abi.rs"]
mod abi;
use abi::*;
use std::mem::{align_of, offset_of, size_of};

fn main() {
    macro_rules! layout {
        ($name:literal, $t:ty, $($field:ident),+ $(,)?) => {{
            let offsets = [$(offset_of!($t, $field)),+];
            println!("{} {} {} {:?}", $name, size_of::<$t>(), align_of::<$t>(), offsets);
        }};
    }
    layout!(
        "DriverProperties",
        DriverProperties,
        stype,
        next,
        uuid,
        version
    );
    layout!(
        "DeviceProperties",
        DeviceProperties,
        stype,
        next,
        kind,
        vendor,
        device,
        flags,
        subdevice,
        clock,
        max_alloc,
        contexts,
        priority,
        threads_per_eu,
        simd,
        eus_per_subslice,
        subslices,
        slices,
        timer,
        timestamp_bits,
        kernel_timestamp_bits,
        uuid,
        name
    );
    layout!(
        "ComputeProperties",
        ComputeProperties,
        stype,
        next,
        max_total,
        max_x,
        max_y,
        max_z,
        count_x,
        count_y,
        count_z,
        shared_mem,
        subgroup_count,
        subgroup_sizes
    );
    layout!(
        "QueueGroupProperties",
        QueueGroupProperties,
        stype,
        next,
        flags,
        max_fill_size,
        count
    );
    layout!("ContextDesc", ContextDesc, stype, next, flags);
    layout!(
        "QueueDesc",
        QueueDesc,
        stype,
        next,
        ordinal,
        index,
        flags,
        mode,
        priority
    );
    layout!("ListDesc", ListDesc, stype, next, ordinal, flags);
    layout!(
        "DeviceAllocDesc",
        DeviceAllocDesc,
        stype,
        next,
        flags,
        ordinal
    );
    layout!("HostAllocDesc", HostAllocDesc, stype, next, flags);
    layout!(
        "ModuleDesc",
        ModuleDesc,
        stype,
        next,
        format,
        size,
        input,
        flags,
        constants
    );
    layout!("KernelDesc", KernelDesc, stype, next, flags, name);
    layout!("GroupCount", GroupCount, x, y, z);
}

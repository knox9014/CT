//! Raw compiled-kernel metadata. These fields are not CUDA function attributes.
use super::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct KernelResources {
    pub num_kernel_args: u32,
    pub required_group_size: [u32; 3],
    pub required_num_subgroups: u32,
    pub required_subgroup_size: u32,
    pub max_subgroup_size: u32,
    pub max_num_subgroups: u32,
    /// Native local memory per thread group, not CUDA thread-local memory.
    pub local_mem_bytes: u32,
    /// Native compiler-allocated private memory per thread.
    pub private_mem_bytes: u32,
    /// Native compiler spill allocation; no per-CUDA-thread conversion is implied.
    pub spill_mem_bytes: u32,
}

impl Backend {
    /// Query one live module entry without setting arguments/group size or launching.
    /// As with launch/unload, the caller must pair the module with its owning context
    /// and backend. UUID bytes remain internal and are never part of this result.
    pub fn kernel_resources(
        &self,
        context: &mut Context,
        module: &Module,
        entry: usize,
    ) -> NativeResult<KernelResources> {
        if context.poisoned {
            return Err(UNKNOWN);
        }
        let kernel = *module.kernels.get(entry).ok_or(BAD_ARGUMENT)?;
        if module.native == 0 || kernel == 0 {
            return Err(BAD_ARGUMENT);
        }
        type Query = unsafe extern "C" fn(Handle, *mut KernelProperties) -> u32;
        let query: Query = unsafe {
            self.api
                .symbol(b"zeKernelGetProperties\0")
                .map_err(|_| UNSUPPORTED)?
        };
        let mut props: KernelProperties = unsafe { blank() };
        props.stype = 0x1e;
        let code = unsafe { query(kernel as Handle, &mut props) };
        context.observe(&self.api, if code == 0 { Ok(()) } else { Err(code) })?;
        Ok(KernelResources {
            num_kernel_args: props.num_kernel_args,
            required_group_size: [
                props.required_group_size_x,
                props.required_group_size_y,
                props.required_group_size_z,
            ],
            required_num_subgroups: props.required_num_subgroups,
            required_subgroup_size: props.required_subgroup_size,
            max_subgroup_size: props.max_subgroup_size,
            max_num_subgroups: props.max_num_subgroups,
            local_mem_bytes: props.local_mem_size,
            private_mem_bytes: props.private_mem_size,
            spill_mem_bytes: props.spill_mem_size,
        })
    }
}

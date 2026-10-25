//! Synchronous opaque host-symbol operations over the shared native module.
use crate::kernel_driver::KernelDriver;
use crate::kernels::KernelRuntime;
use crate::state::Runtime;
use std::ffi::c_void;

pub struct Transfer {
    pub data: *mut c_void,
    pub count: usize,
    pub offset: usize,
    pub kind: i32,
    pub to: bool,
}
impl Transfer {
    fn preflight(&self) -> Result<usize, i32> {
        match (self.to, self.kind) {
            (_, 4) => return Err(801),
            (true, 1 | 3) | (false, 2 | 3) => {}
            _ => return Err(21),
        }
        let end = self.offset.checked_add(self.count).ok_or(1)?;
        if self.count > 0
            && (self.data.is_null() || (self.data as usize).checked_add(self.count).is_none())
        {
            return Err(1);
        }
        Ok(end)
    }
    fn check_bound(&self, end: usize, bound: usize) -> Result<(), i32> {
        if end > bound {
            Err(1)
        } else {
            Ok(())
        }
    }
}
pub unsafe fn query<'a, D: KernelDriver + 'a, T>(
    kernels: &KernelRuntime,
    runtime: impl FnOnce() -> Result<&'a Runtime<D>, i32>,
    host: usize,
    output: *mut T,
    select: impl FnOnce(u64, usize) -> T,
) -> i32 {
    let result = (|| {
        if output.is_null() {
            return Err(1);
        }
        // Exactly one lease stays alive through provider initialization and output write.
        let lease = kernels.registry.symbol(host)?;
        lease.data.image()?;
        let rt = runtime()?;
        let value = kernels.with_symbol(rt, &lease, |_, p, n| Ok(select(p, n)))?;
        unsafe {
            output.write(value);
        }
        Ok(())
    })();
    result.err().unwrap_or(0)
}
pub unsafe fn copy<'a, D: KernelDriver + 'a>(
    kernels: &KernelRuntime,
    runtime: impl FnOnce() -> Result<&'a Runtime<D>, i32>,
    host: usize,
    transfer: Transfer,
) -> i32 {
    let result = (|| {
        let end = transfer.preflight()?;
        let lease = match kernels.registry.symbol(host) {
            Ok(lease) => lease,
            Err(code) => {
                transfer.check_bound(end, 4)?;
                return Err(code);
            }
        };
        let size = lease
            .data
            .variables()
            .get(lease.variable_index)
            .ok_or(801)?
            .metadata
            .size;
        transfer.check_bound(end, if matches!(size, 4 | 8) { size } else { 4 })?;
        lease.data.image()?;
        let rt = runtime()?;
        kernels.with_symbol(rt, &lease, |driver, pointer, _| {
            if transfer.count == 0 {
                return Ok(());
            }
            // Binding validation established a matching nonoverflowing scalar extent.
            let address = pointer + transfer.offset as u64;
            let code = match (transfer.to, transfer.kind) {
                (true, 1) => unsafe {
                    driver.copy_htod(address, transfer.data.cast(), transfer.count)
                },
                (false, 2) => unsafe {
                    driver.copy_dtoh(transfer.data.cast(), address, transfer.count)
                },
                (true, 3) => driver.copy_dtod(address, transfer.data as u64, transfer.count),
                (false, 3) => driver.copy_dtod(transfer.data as u64, address, transfer.count),
                _ => unreachable!(),
            };
            if code == 0 {
                Ok(())
            } else {
                Err(code)
            }
        })
    })();
    result.err().unwrap_or(0)
}

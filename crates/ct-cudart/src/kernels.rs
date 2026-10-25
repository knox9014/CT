//! Context-keyed native ownership; constructor callbacks never enter this cache.
use crate::configuration::{preflight, Config};
use crate::driver::Context;
use crate::kernel_driver::{Function, KernelDriver, Module};
use crate::registration::{RegistrationData, Registry, SymbolLease};
use crate::state::Runtime;
use std::ffi::c_void;
use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Mutex, TryLockError};

#[derive(Clone, Copy)]
enum Phase {
    Fresh,
    Live,
    Retired,
    Failed(i32),
    Cleaned,
}
struct FunctionSlot {
    symbol: Arc<Vec<u8>>,
    result: Result<Function, i32>,
}
#[derive(Clone, Copy)]
struct Binding {
    pointer: u64,
    size: usize,
}
struct EntryState {
    phase: Phase,
    module: Option<Module>,
    reserved: bool,
    cleanup_error: Option<i32>,
    functions: Vec<FunctionSlot>,
    bindings: Vec<Binding>,
}
struct Entry {
    context: Context,
    data: Arc<RegistrationData>,
    gate: Mutex<EntryState>,
}
pub struct KernelRuntime {
    pub registry: Registry,
    cache: Mutex<Vec<Arc<Entry>>>,
    slots: AtomicUsize,
    capacity: usize,
}
enum Operation {
    Load,
    Lookup,
    Launch,
    Unload,
}
fn native_error(code: i32, op: Operation) -> i32 {
    match code {
        218 if matches!(op, Operation::Load) => 218,
        400 => 400,
        500 if matches!(op, Operation::Lookup) => 98,
        _ => crate::errors::from_driver(code),
    }
}
impl KernelRuntime {
    pub fn new() -> Self {
        Self::with_capacity(128)
    }
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            registry: Registry::new(),
            cache: Mutex::new(Vec::new()),
            slots: AtomicUsize::new(0),
            capacity: capacity.min(128),
        }
    }
    fn entry(&self, data: &Arc<RegistrationData>, context: Context) -> Result<Arc<Entry>, i32> {
        let mut cache = self.cache.lock().map_err(|_| 999)?;
        if let Some(entry) = cache
            .iter()
            .find(|e| e.context == context && e.data.id == data.id)
        {
            return Ok(entry.clone());
        }
        if cache.len() >= self.capacity {
            return Err(801);
        }
        #[cfg(test)]
        if FAIL_RESERVATION.get() {
            return Err(2);
        }
        cache.try_reserve_exact(1).map_err(|_| 2)?;
        let mut functions = Vec::new();
        functions.try_reserve_exact(512).map_err(|_| 2)?;
        let mut bindings = Vec::new();
        bindings
            .try_reserve_exact(data.variables().len())
            .map_err(|_| 2)?;
        let entry = Arc::new(Entry {
            context,
            data: data.clone(),
            gate: Mutex::new(EntryState {
                phase: Phase::Fresh,
                module: None,
                reserved: false,
                cleanup_error: None,
                functions,
                bindings,
            }),
        });
        cache.push(entry.clone());
        Ok(entry)
    }
    fn reserve_slot(&self) -> Result<(), i32> {
        self.slots
            .fetch_update(SeqCst, SeqCst, |n| (n < self.capacity).then_some(n + 1))
            .map(|_| ())
            .map_err(|_| 801)
    }
    pub unsafe fn launch<D: KernelDriver>(
        &self,
        runtime: &Runtime<D>,
        host: usize,
        config: Config,
        args: *mut *mut c_void,
    ) -> i32 {
        match unsafe { self.launch_result(runtime, host, config, args) } {
            Ok(()) => 0,
            Err(c) => c,
        }
    }
    unsafe fn launch_result<D: KernelDriver>(
        &self,
        runtime: &Runtime<D>,
        host: usize,
        config: Config,
        args: *mut *mut c_void,
    ) -> Result<(), i32> {
        let lease = self.registry.lease(host)?;
        lease.image()?;
        let code = preflight(config);
        if code != 0 {
            return Err(code);
        }
        let context = runtime
            .ensure_current()
            .map_err(crate::errors::from_driver)?;
        runtime.driver.prepare_kernel()?;
        if !lease.variables().is_empty() {
            runtime.driver.prepare_globals()?;
        }
        let device = runtime
            .driver
            .context_device()
            .map_err(crate::errors::from_driver)?;
        let mut caps = [0u64; 7];
        for (i, cap) in caps.iter_mut().enumerate() {
            let value = runtime
                .driver
                .attribute(i as i32 + 1, device)
                .map_err(crate::errors::from_driver)?;
            if value <= 0 {
                return Err(999);
            }
            *cap = value as u64;
        }
        let mut volume = 1u64;
        for axis in 0..3 {
            let grid = u64::from(config.grid.axes()[axis]);
            let block = u64::from(config.block.axes()[axis]);
            if grid > caps[4 + axis] || block > caps[1 + axis] || grid * block > u64::from(u32::MAX)
            {
                return Err(9);
            }
            volume = volume.checked_mul(block).ok_or(9)?;
        }
        if volume > caps[0] {
            return Err(9);
        }
        self.drain(&runtime.driver, context)?;
        let entry = self.entry(&lease.data, context)?;
        let mut state = entry.gate.lock().map_err(|_| 999)?;
        let module = self.ensure_module(&runtime.driver, &lease.data, &mut state)?;
        let function = if let Some(slot) = state
            .functions
            .iter()
            .find(|s| s.symbol.as_slice() == lease.symbol())
        {
            slot.result
        } else {
            if state.functions.len() >= 512 {
                return Err(801);
            }
            let result = runtime
                .driver
                .function(module, lease.symbol())
                .map_err(|c| native_error(c, Operation::Lookup));
            // Capacity and all retirement storage were reserved before native load.
            state.functions.push(FunctionSlot {
                symbol: lease.symbol.clone(),
                result,
            });
            result
        }?;
        let code = unsafe { runtime.driver.launch(function, config, args) };
        if code != 0 {
            let mapped = native_error(code, Operation::Launch);
            if matches!(code, 400 | 709) {
                state.phase = Phase::Failed(mapped);
            }
            return Err(mapped);
        }
        Ok(())
    }
    fn ensure_module<D: KernelDriver>(
        &self,
        driver: &D,
        data: &Arc<RegistrationData>,
        state: &mut EntryState,
    ) -> Result<Module, i32> {
        match state.phase {
            Phase::Failed(code) => return Err(code),
            Phase::Cleaned => return Err(98),
            _ => {}
        }
        if matches!(state.phase, Phase::Fresh) {
            self.reserve_slot()?;
            state.reserved = true;
            match driver.load(data.image()?) {
                Ok(module) => {
                    // Own the native handle before any binding lookup can fail or block.
                    state.module = Some(module);
                    for variable in data.variables() {
                        let binding = driver.global(module, &variable.name);
                        let failure = match binding {
                            Ok((pointer, size))
                                if pointer != 0
                                    && matches!(size, 4 | 8)
                                    && pointer.is_multiple_of(size as u64)
                                    && size == variable.metadata.size
                                    && pointer.checked_add(size as u64).is_some() =>
                            {
                                state.bindings.push(Binding { pointer, size });
                                None
                            }
                            Ok(_) | Err(500 | 801) => Some(801),
                            Err(code) => Some(crate::errors::from_driver(code)),
                        };
                        if let Some(code) = failure {
                            state.bindings.clear();
                            state.phase = Phase::Failed(code);
                            return Err(code);
                        }
                    }
                    state.phase = if data.retired() {
                        Phase::Retired
                    } else {
                        Phase::Live
                    };
                }
                Err(code) => {
                    let mapped = native_error(code, Operation::Load);
                    state.phase = Phase::Failed(mapped);
                    // Only the CT Driver's defined no-output error paths release a slot.
                    if matches!(
                        code,
                        1 | 2 | 3 | 100 | 101 | 201 | 218 | 400 | 500 | 709 | 801
                    ) {
                        state.reserved = false;
                        self.slots.fetch_sub(1, SeqCst);
                    }
                    return Err(mapped);
                }
            }
        }
        state.module.ok_or(999)
    }
    pub fn with_symbol<D: KernelDriver, T>(
        &self,
        runtime: &Runtime<D>,
        lease: &SymbolLease,
        action: impl FnOnce(&D, u64, usize) -> Result<T, i32>,
    ) -> Result<T, i32> {
        lease.data.image()?;
        let context = runtime
            .ensure_current()
            .map_err(crate::errors::from_driver)?;
        runtime.driver.prepare_kernel()?;
        runtime.driver.prepare_globals()?;
        self.drain(&runtime.driver, context)?;
        let entry = self.entry(&lease.data, context)?;
        let mut state = entry.gate.lock().map_err(|_| 999)?;
        self.ensure_module(&runtime.driver, &lease.data, &mut state)?;
        let binding = *state.bindings.get(lease.variable_index).ok_or(801)?;
        match action(&runtime.driver, binding.pointer, binding.size) {
            Ok(value) => Ok(value),
            Err(code) => {
                let mapped = native_error(code, Operation::Launch);
                if matches!(code, 400 | 709) {
                    state.phase = Phase::Failed(mapped);
                }
                Err(mapped)
            }
        }
    }
    pub fn drain<D: KernelDriver>(&self, driver: &D, current: Context) -> Result<(), i32> {
        let entries = {
            let cache = self.cache.lock().map_err(|_| 999)?;
            let mut entries = Vec::new();
            entries.try_reserve_exact(cache.len()).map_err(|_| 2)?;
            entries.extend(cache.iter().cloned());
            entries
        };
        for entry in entries {
            if entry.context != current
                || !entry.data.retired.load(SeqCst)
                || entry.data.active.load(SeqCst) != 0
            {
                continue;
            }
            let mut state = match entry.gate.try_lock() {
                Ok(s) => s,
                Err(TryLockError::WouldBlock) => continue,
                Err(TryLockError::Poisoned(_)) => return Err(999),
            };
            if let Some(code) = state.cleanup_error {
                return Err(code);
            }
            if let Some(module) = state.module {
                let code = driver.unload(module);
                if code != 0 {
                    let mapped = native_error(code, Operation::Unload);
                    state.cleanup_error = Some(mapped);
                    state.phase = Phase::Failed(mapped);
                    return Err(mapped);
                }
                state.module = None;
                if state.reserved {
                    state.reserved = false;
                    self.slots.fetch_sub(1, SeqCst);
                }
            }
            // A failed native call with uncertain ownership keeps its reservation.
            if state.reserved {
                continue;
            }
            state.phase = Phase::Cleaned;
            state.functions.clear();
            state.bindings.clear();
            let mut cache = self.cache.lock().map_err(|_| 999)?;
            cache.retain(|candidate| !Arc::ptr_eq(candidate, &entry));
        }
        Ok(())
    }
}
#[cfg(test)]
thread_local! {pub static FAIL_RESERVATION:std::cell::Cell<bool> = const {std::cell::Cell::new(false)};}

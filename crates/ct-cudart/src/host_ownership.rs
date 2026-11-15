//! Own host-use leases until queued commands have finished.
use crate::driver::Context;
use std::sync::{Arc, Condvar, Mutex, OnceLock};
#[derive(Clone, Copy)]
enum Phase {
    Open,
    Closing,
    Released,
    Failed(i32),
}
struct State {
    uses: usize,
    phase: Phase,
}
struct Entry {
    context: Context,
    pointer: usize,
    size: usize,
    state: Mutex<State>,
    changed: Condvar,
}
pub struct Use {
    entry: Arc<Entry>,
}
impl Drop for Use {
    fn drop(&mut self) {
        let mut state = self.entry.state.lock().unwrap_or_else(|e| e.into_inner());
        state.uses = state.uses.saturating_sub(1);
        self.entry.changed.notify_all();
    }
}
pub struct Registry {
    entries: Mutex<Vec<Arc<Entry>>>,
    limit: usize,
}
impl Registry {
    pub fn new() -> Self {
        Self::with_limit(1024)
    }
    pub fn with_limit(limit: usize) -> Self {
        Self {
            entries: Mutex::new(Vec::new()),
            limit: limit.min(1024),
        }
    }
    pub fn allocate(
        &self,
        context: Context,
        size: usize,
        native: impl FnOnce() -> Result<usize, i32>,
    ) -> Result<usize, i32> {
        if context == 0 {
            return Err(49);
        }
        if size == 0 {
            return Err(1);
        }
        let mut entries = self.entries.lock().map_err(|_| 999)?;
        if entries.len() >= self.limit {
            return Err(2);
        }
        entries.try_reserve_exact(1).map_err(|_| 2)?;
        let pointer = native()?;
        let end = pointer.checked_add(size).ok_or(999)?;
        if pointer == 0
            || entries
                .iter()
                .any(|e| pointer < e.pointer + e.size && e.pointer < end)
        {
            return Err(999);
        }
        entries.push(Arc::new(Entry {
            context,
            pointer,
            size,
            state: Mutex::new(State {
                uses: 0,
                phase: Phase::Open,
            }),
            changed: Condvar::new(),
        }));
        Ok(pointer)
    }
    pub fn acquire(&self, context: Context, pointer: usize, size: usize) -> Result<Use, i32> {
        let end = pointer.checked_add(size).ok_or(1)?;
        let entry = self
            .entries
            .lock()
            .map_err(|_| 999)?
            .iter()
            .find(|e| e.pointer <= pointer && pointer < e.pointer + e.size)
            .cloned()
            .ok_or(801)?;
        if context != entry.context || end > entry.pointer + entry.size {
            return Err(1);
        }
        let mut state = entry.state.lock().map_err(|_| 999)?;
        match state.phase {
            Phase::Open => {}
            Phase::Failed(code) => return Err(code),
            _ => return Err(1),
        }
        state.uses = state.uses.checked_add(1).ok_or(801)?;
        drop(state);
        Ok(Use { entry })
    }
    #[cfg(test)]
    pub fn wait_closing(&self, pointer: usize) {
        let entry = self
            .entries
            .lock()
            .unwrap()
            .iter()
            .find(|e| e.pointer == pointer)
            .unwrap()
            .clone();
        let mut state = entry.state.lock().unwrap();
        while matches!(state.phase, Phase::Open) {
            state = entry.changed.wait(state).unwrap();
        }
    }
    pub fn free(
        &self,
        context: Context,
        pointer: usize,
        native: impl FnOnce() -> Result<(), i32>,
    ) -> Result<(), i32> {
        let entry = self
            .entries
            .lock()
            .map_err(|_| 999)?
            .iter()
            .find(|e| e.pointer == pointer)
            .cloned();
        // Existing synchronous interop may free a Driver-owned allocation not known here.
        let Some(entry) = entry else {
            return native();
        };
        if context != entry.context {
            return Err(1);
        }
        let mut state = entry.state.lock().map_err(|_| 999)?;
        match state.phase {
            Phase::Open => {}
            Phase::Failed(code) => return Err(code),
            _ => return Err(1),
        }
        state.phase = Phase::Closing;
        entry.changed.notify_all();
        while state.uses != 0 {
            state = entry.changed.wait(state).map_err(|_| 999)?;
        }
        // Serialize physical address reuse with allocation's reserve/native/commit.
        // Allocation never waits for entry state while holding this registry lock.
        let mut entries = self.entries.lock().map_err(|_| 999)?;
        match native() {
            Ok(()) => {
                state.phase = Phase::Released;
                drop(state);
                entries.retain(|e| !Arc::ptr_eq(e, &entry));
                Ok(())
            }
            Err(code) => {
                state.phase = Phase::Failed(code);
                Err(code)
            }
        }
    }
}
static HOSTS: OnceLock<Registry> = OnceLock::new();
pub fn registry() -> &'static Registry {
    HOSTS.get_or_init(Registry::new)
}

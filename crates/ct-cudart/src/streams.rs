//! Context-owned opaque stream tokens for the synchronous backend.
//! Gates serialize use/close; mutex acquisition does not promise FIFO submission.
use crate::{
    driver::{Context, DriverCalls},
    state::Runtime,
};
use std::sync::{Arc, Mutex, OnceLock};
const BASE: usize = 0x4354_0000;
const STRIDE: usize = 16;
#[derive(Clone, Copy)]
enum Phase {
    Open,
    Failed(i32),
    Closed,
}
pub struct Lease {
    context: Context,
    phase: Mutex<Phase>,
}
impl Lease {
    pub fn run<T>(
        &self,
        context: Context,
        action: impl FnOnce() -> Result<T, i32>,
    ) -> Result<T, i32> {
        if self.context != context {
            return Err(400);
        }
        let mut phase = self.phase.lock().map_err(|_| 999)?;
        match *phase {
            Phase::Closed => return Err(400),
            Phase::Failed(code) => return Err(code),
            Phase::Open => {}
        }
        let result = action();
        if matches!(result, Err(709)) {
            *phase = Phase::Failed(709);
        }
        result
    }
}
struct Book {
    entries: Vec<Arc<Lease>>,
    live: usize,
}
pub struct Registry {
    book: Mutex<Book>,
    live_limit: usize,
    lifetime_limit: usize,
}
impl Registry {
    pub fn new() -> Self {
        Self::with_limits(128, 4096)
    }
    pub fn with_limits(live: usize, lifetime: usize) -> Self {
        Self {
            book: Mutex::new(Book {
                entries: Vec::new(),
                live: 0,
            }),
            live_limit: live.min(128),
            lifetime_limit: lifetime.min(4096),
        }
    }
    pub fn create(&self, context: Context, flags: u32) -> Result<usize, i32> {
        if flags > 1 {
            return Err(1);
        }
        if context == 0 {
            return Err(49);
        }
        let mut book = self.book.lock().map_err(|_| 999)?;
        if book.live >= self.live_limit || book.entries.len() >= self.lifetime_limit {
            return Err(801);
        }
        let token = book
            .entries
            .len()
            .checked_add(1)
            .and_then(|n| n.checked_mul(STRIDE))
            .and_then(|n| BASE.checked_add(n))
            .ok_or(801)?;
        book.entries.try_reserve_exact(1).map_err(|_| 2)?;
        book.entries.push(Arc::new(Lease {
            context,
            phase: Mutex::new(Phase::Open),
        }));
        book.live += 1;
        Ok(token)
    }
    pub fn lease(&self, token: usize) -> Result<Arc<Lease>, i32> {
        if token == 0 {
            return Err(400);
        }
        let offset = token.checked_sub(BASE).ok_or(801)?;
        if offset == 0 || offset % STRIDE != 0 {
            return Err(801);
        }
        let book = self.book.lock().map_err(|_| 999)?;
        book.entries.get(offset / STRIDE - 1).cloned().ok_or(801)
    }
    pub fn preflight(&self, token: usize) -> Result<(), i32> {
        if token == 0 {
            return Ok(());
        }
        let lease = self.lease(token)?;
        let phase = lease.phase.lock().map_err(|_| 999)?;
        match *phase {
            Phase::Open => Ok(()),
            Phase::Closed => Err(400),
            Phase::Failed(code) => Err(code),
        }
    }
    pub fn close_preflight(&self, token: usize) -> Result<(), i32> {
        let lease = self.lease(token)?;
        let phase = lease.phase.lock().map_err(|_| 999)?;
        if matches!(*phase, Phase::Closed) {
            Err(400)
        } else {
            Ok(())
        }
    }
    pub fn run<T>(
        &self,
        context: Context,
        token: usize,
        action: impl FnOnce() -> Result<T, i32>,
    ) -> Result<T, i32> {
        self.lease(token)?.run(context, action)
    }
    pub fn close(
        &self,
        context: Context,
        token: usize,
        finish: impl FnOnce() -> Result<(), i32>,
    ) -> Result<(), i32> {
        let lease = self.lease(token)?;
        if lease.context != context {
            return Err(400);
        }
        // No registry lock is held while waiting for an operation's gate.
        let mut phase = lease.phase.lock().map_err(|_| 999)?;
        if matches!(*phase, Phase::Closed) {
            return Err(400);
        }
        *phase = Phase::Closed;
        let result = finish();
        self.book.lock().map_err(|_| 999)?.live -= 1;
        result
    }
}
static STREAMS: OnceLock<Registry> = OnceLock::new();
pub fn registry() -> &'static Registry {
    STREAMS.get_or_init(Registry::new)
}
pub fn create_preflight(out: *mut usize, flags: u32) -> Option<i32> {
    if out.is_null() || flags > 1 {
        Some(1)
    } else {
        None
    }
}
pub unsafe fn create_query<D: DriverCalls>(
    registry: &Registry,
    rt: &Runtime<D>,
    out: *mut usize,
    flags: u32,
) -> i32 {
    if let Some(code) = create_preflight(out, flags) {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return crate::errors::from_driver(code),
    };
    match registry.create(context, flags) {
        Ok(token) => {
            unsafe {
                *out = token;
            }
            0
        }
        Err(code) => code,
    }
}
pub unsafe fn create(out: *mut usize, flags: u32) -> i32 {
    if let Some(code) = create_preflight(out, flags) {
        return code;
    }
    match crate::bridge() {
        Ok(rt) => unsafe { create_query(registry(), rt, out, flags) },
        Err(code) => code,
    }
}
pub fn destroy_query<D: DriverCalls>(
    registry: &Registry,
    rt: &Runtime<D>,
    token: usize,
    finish: impl FnOnce(&D, Context) -> Result<(), i32>,
) -> i32 {
    if let Err(code) = registry.close_preflight(token) {
        return code;
    }
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return crate::errors::from_driver(code),
    };
    registry
        .close(context, token, || finish(&rt.driver, context))
        .err()
        .unwrap_or(0)
}
pub fn destroy(token: usize) -> i32 {
    if let Err(code) = registry().close_preflight(token) {
        return code;
    }
    let rt = match crate::bridge() {
        Ok(rt) => rt,
        Err(code) => return code,
    };
    destroy_query(registry(), rt, token, |driver, context| {
        crate::submission::scheduler().barrier(context, true, || {
            crate::kernel_runtime().drain(driver, context)?;
            match crate::errors::from_driver(driver.synchronize()) {
                0 => Ok(()),
                code => Err(code),
            }
        })
    })
}

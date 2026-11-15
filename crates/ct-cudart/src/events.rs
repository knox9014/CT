//! Runtime event generations and ordered Driver work.
use crate::submission::{Action, Notify, Scheduler};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc, Condvar, Mutex, OnceLock,
};
#[derive(Default)]
pub struct Completion {
    result: Mutex<Option<i32>>,
    changed: Condvar,
}
impl Completion {
    fn finish(&self, code: i32) {
        let mut s = self.result.lock().unwrap_or_else(|e| e.into_inner());
        if s.is_none() {
            *s = Some(code);
            self.changed.notify_all();
        }
    }
    pub fn poll(&self) -> Result<(), i32> {
        match *self.result.lock().map_err(|_| 999)? {
            None => Err(600),
            Some(0) => Ok(()),
            Some(c) => Err(c),
        }
    }
    pub fn wait(&self) -> Result<(), i32> {
        let mut s = self.result.lock().map_err(|_| 999)?;
        while s.is_none() {
            s = self.changed.wait(s).map_err(|_| 999)?;
        }
        match *s {
            Some(0) => Ok(()),
            Some(c) => Err(c),
            None => Err(999),
        }
    }
}
struct State {
    closed: bool,
    latest: Option<Arc<Completion>>,
}
struct Slot {
    context: usize,
    native: usize,
    state: Mutex<State>,
}
pub struct Registry {
    entries: Mutex<Vec<Arc<Slot>>>,
    live: AtomicUsize,
    live_limit: usize,
    lifetime_limit: usize,
}
impl Registry {
    pub fn new() -> Self {
        Self::with_limits(128, 4096)
    }
    pub fn with_limits(live: usize, lifetime: usize) -> Self {
        Self {
            entries: Mutex::new(Vec::new()),
            live: AtomicUsize::new(0),
            live_limit: live.min(128),
            lifetime_limit: lifetime.min(4096),
        }
    }
    pub fn create(
        &self,
        context: usize,
        allocate: impl FnOnce() -> Result<usize, i32>,
    ) -> Result<usize, i32> {
        if context == 0 {
            return Err(49);
        }
        let mut entries = self.entries.lock().map_err(|_| 999)?;
        if self.live.load(Ordering::SeqCst) >= self.live_limit
            || entries.len() >= self.lifetime_limit
        {
            return Err(801);
        }
        entries.try_reserve_exact(1).map_err(|_| 2)?;
        let native = allocate()?;
        if native == 0 {
            return Err(999);
        }
        let token = 0x4556_0000 + (entries.len() + 1) * 16;
        entries.push(Arc::new(Slot {
            context,
            native,
            state: Mutex::new(State {
                closed: false,
                latest: None,
            }),
        }));
        self.live.fetch_add(1, Ordering::SeqCst);
        Ok(token)
    }
    fn slot(&self, token: usize) -> Result<Arc<Slot>, i32> {
        let offset = token
            .checked_sub(0x4556_0000)
            .filter(|v| *v > 0 && v % 16 == 0)
            .ok_or(400)?;
        self.entries
            .lock()
            .map_err(|_| 999)?
            .get(offset / 16 - 1)
            .cloned()
            .ok_or(400)
    }
    pub fn preflight(&self, token: usize) -> Result<(), i32> {
        let slot = self.slot(token)?;
        if slot.state.lock().map_err(|_| 999)?.closed {
            Err(400)
        } else {
            Ok(())
        }
    }
    fn check(slot: &Slot, state: &State, context: usize) -> Result<(), i32> {
        if slot.context != context || state.closed {
            Err(400)
        } else {
            Ok(())
        }
    }
    pub fn snapshot(&self, context: usize, token: usize) -> Result<Option<Arc<Completion>>, i32> {
        let slot = self.slot(token)?;
        let state = slot.state.lock().map_err(|_| 999)?;
        Self::check(&slot, &state, context)?;
        Ok(state.latest.clone())
    }
    pub fn synchronize(&self, context: usize, token: usize) -> Result<(), i32> {
        if let Some(done) = self.snapshot(context, token)? {
            done.wait()
        } else {
            Ok(())
        }
    }
    pub fn record(
        &self,
        q: &Scheduler,
        context: usize,
        token: usize,
        action: impl FnOnce(usize) -> i32 + Send + 'static,
    ) -> Result<(), i32> {
        let slot = self.slot(token)?;
        q.transaction(
            context,
            false,
            || {
                let guard = slot.state.lock().map_err(|_| 999)?;
                Self::check(&slot, &guard, context)?;
                let done = Arc::new(Completion::default());
                let notify = done.clone();
                let native = slot.native;
                Ok((
                    Box::new(move || action(native)) as Action,
                    Some(Box::new(move |code| notify.finish(code)) as Notify),
                    (guard, done),
                ))
            },
            |(mut guard, done)| {
                guard.latest = Some(done);
            },
        )
    }
    pub fn destroy(
        &self,
        q: &Scheduler,
        context: usize,
        token: usize,
        free: impl FnOnce(usize) -> i32 + Send + 'static,
    ) -> Result<(), i32> {
        let slot = self.slot(token)?;
        q.transaction(
            context,
            true,
            || {
                let guard = slot.state.lock().map_err(|_| 999)?;
                Self::check(&slot, &guard, context)?;
                let native = slot.native;
                Ok((Box::new(move || free(native)) as Action, None, guard))
            },
            |mut guard| {
                guard.closed = true;
                self.live.fetch_sub(1, Ordering::SeqCst);
            },
        )
    }
    pub fn elapsed(
        &self,
        q: &Scheduler,
        context: usize,
        start: usize,
        end: usize,
        read: impl FnOnce(usize, usize) -> Result<f32, i32>,
    ) -> Result<f32, i32> {
        let a = self.slot(start)?;
        let b = self.slot(end)?;
        let ready = |slot: &Slot, state: &State| {
            Self::check(slot, state, context)?;
            state.latest.as_ref().ok_or(400)?.poll()
        };
        q.exclusive(context, || {
            if start == end {
                let s = a.state.lock().map_err(|_| 999)?;
                ready(&a, &s)?;
                return read(a.native, a.native);
            }
            let (first, second) = if start < end { (&a, &b) } else { (&b, &a) };
            let s = first.state.lock().map_err(|_| 999)?;
            let t = second.state.lock().map_err(|_| 999)?;
            ready(first, &s)?;
            ready(second, &t)?;
            read(a.native, b.native)
        })
    }
}
static EVENTS: OnceLock<Registry> = OnceLock::new();
pub fn registry() -> &'static Registry {
    EVENTS.get_or_init(Registry::new)
}

// Driver return codes are translated exactly once; preparation errors are
// already in the Runtime domain and bypass this mapper.
pub fn driver_error(code: i32) -> i32 {
    match code {
        400 | 600 => code,
        _ => crate::errors::from_driver(code),
    }
}
fn context(rt: &crate::state::Runtime<crate::driver::DriverBridge>) -> Result<usize, i32> {
    rt.ensure_current().map_err(driver_error)
}
pub fn create(rt: &crate::state::Runtime<crate::driver::DriverBridge>) -> Result<usize, i32> {
    use crate::driver::DriverCalls;
    let ctx = context(rt)?;
    rt.driver.prepare_events()?;
    crate::submission::scheduler().barrier(ctx, false, || {
        registry().create(ctx, || rt.driver.event_create().map_err(driver_error))
    })
}
pub fn record(
    rt: &'static crate::state::Runtime<crate::driver::DriverBridge>,
    token: usize,
    stream: usize,
) -> Result<(), i32> {
    use crate::driver::DriverCalls;
    let ctx = context(rt)?;
    let submit = || {
        registry().record(crate::submission::scheduler(), ctx, token, move |native| {
            let selected = driver_error(rt.driver.set_current(ctx));
            if selected != 0 {
                return selected;
            }
            let recorded = driver_error(rt.driver.event_record(native));
            if recorded != 0 {
                return recorded;
            }
            driver_error(rt.driver.event_synchronize(native))
        })
    };
    if stream == 0 {
        submit()
    } else {
        crate::streams::registry().run(ctx, stream, submit)
    }
}
pub fn synchronize(
    rt: &crate::state::Runtime<crate::driver::DriverBridge>,
    token: usize,
) -> Result<(), i32> {
    registry().synchronize(context(rt)?, token)
}
pub fn destroy(
    rt: &'static crate::state::Runtime<crate::driver::DriverBridge>,
    token: usize,
) -> Result<(), i32> {
    use crate::driver::DriverCalls;
    let ctx = context(rt)?;
    registry().destroy(crate::submission::scheduler(), ctx, token, move |native| {
        let selected = driver_error(rt.driver.set_current(ctx));
        if selected != 0 {
            return selected;
        }
        driver_error(rt.driver.event_destroy(native))
    })
}
pub fn elapsed(
    rt: &crate::state::Runtime<crate::driver::DriverBridge>,
    a: usize,
    b: usize,
) -> Result<f32, i32> {
    use crate::driver::DriverCalls;
    registry().elapsed(
        crate::submission::scheduler(),
        context(rt)?,
        a,
        b,
        |x, y| {
            let value = rt.driver.event_elapsed(x, y).map_err(driver_error)?;
            if value.is_finite() && value >= 0.0 {
                Ok(value)
            } else {
                Err(999)
            }
        },
    )
}

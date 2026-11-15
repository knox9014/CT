//! A bounded FIFO worker and context-wide submission/completion fences.
use crate::driver::Context;
use std::cell::Cell;
use std::sync::{mpsc, Arc, Condvar, Mutex, OnceLock};
use std::thread::{self, JoinHandle};
pub type Action = Box<dyn FnOnce() -> i32 + Send + 'static>;
pub type Notify = Box<dyn FnOnce(i32) + Send + 'static>;
thread_local! {static IN_WORKER:Cell<bool>=const {Cell::new(false)};}
#[derive(Default)]
struct Progress {
    pending: usize,
    error: Option<i32>,
}
struct Node {
    context: Context,
    gate: Mutex<()>,
    progress: Mutex<Progress>,
    changed: Condvar,
}
fn complete(node: &Node, code: i32) {
    let mut state = node.progress.lock().unwrap_or_else(|e| e.into_inner());
    if state.pending > 0 {
        state.pending -= 1;
    } else {
        state.error.get_or_insert(999);
    }
    if code != 0 {
        state.error.get_or_insert(code);
    }
    node.changed.notify_all();
}
struct Job {
    action: Option<Action>,
    node: Arc<Node>,
    notify: Option<Notify>,
    cleanup: bool,
}
impl Job {
    fn finish(&mut self, code: i32) {
        if let Some(notify) = self.notify.take() {
            let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| notify(code)));
        }
        complete(&self.node, code);
    }
}
impl Drop for Job {
    fn drop(&mut self) {
        if let Some(action) = self.action.take() {
            let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| drop(action)));
            self.finish(999);
        }
    }
}
struct Worker {
    sender: mpsc::SyncSender<Job>,
    thread: JoinHandle<()>,
}
pub struct Scheduler {
    nodes: Mutex<Vec<Arc<Node>>>,
    worker: Mutex<Option<Worker>>,
    contexts: usize,
    capacity: usize,
    #[cfg(test)]
    fail_start: std::sync::atomic::AtomicBool,
    #[cfg(test)]
    fail_send: std::sync::atomic::AtomicBool,
}
impl Scheduler {
    pub fn new() -> Self {
        Self::with_limits(128, 256)
    }
    pub fn with_limits(contexts: usize, capacity: usize) -> Self {
        Self {
            nodes: Mutex::new(Vec::new()),
            worker: Mutex::new(None),
            contexts: contexts.min(128),
            capacity: capacity.clamp(1, 256),
            #[cfg(test)]
            fail_start: std::sync::atomic::AtomicBool::new(false),
            #[cfg(test)]
            fail_send: std::sync::atomic::AtomicBool::new(false),
        }
    }
    fn node(&self, context: Context, create: bool) -> Result<Option<Arc<Node>>, i32> {
        let mut nodes = self.nodes.lock().map_err(|_| 999)?;
        if let Some(node) = nodes.iter().find(|n| n.context == context) {
            return Ok(Some(node.clone()));
        }
        if !create {
            return Ok(None);
        }
        if context == 0 {
            return Err(49);
        }
        if nodes.len() >= self.contexts {
            return Err(801);
        }
        nodes.try_reserve_exact(1).map_err(|_| 2)?;
        let node = Arc::new(Node {
            context,
            gate: Mutex::new(()),
            progress: Mutex::new(Progress::default()),
            changed: Condvar::new(),
        });
        nodes.push(node.clone());
        Ok(Some(node))
    }
    fn sender(&self) -> Result<mpsc::SyncSender<Job>, i32> {
        let mut worker = self.worker.lock().map_err(|_| 999)?;
        if worker.is_none() {
            #[cfg(test)]
            if self
                .fail_start
                .swap(false, std::sync::atomic::Ordering::SeqCst)
            {
                return Err(2);
            }
            let (tx, rx) = mpsc::sync_channel::<Job>(self.capacity);
            let thread = thread::Builder::new()
                .name("CT-copy".into())
                .spawn(move || {
                    IN_WORKER.with(|v| v.set(true));
                    while let Ok(mut job) = rx.recv() {
                        let prior = job
                            .node
                            .progress
                            .lock()
                            .unwrap_or_else(|e| e.into_inner())
                            .error;
                        let action = job.action.take().expect("accepted job owns its action");
                        let code = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                            if !job.cleanup {
                                if let Some(code) = prior {
                                    drop(action);
                                    return code;
                                }
                            }
                            action()
                        }))
                        .unwrap_or(999);
                        job.finish(code);
                    }
                })
                .map_err(|_| 2)?;
            *worker = Some(Worker { sender: tx, thread });
        }
        Ok(worker.as_ref().ok_or(999)?.sender.clone())
    }
    pub fn submit(
        &self,
        context: Context,
        build: impl FnOnce() -> Result<Action, i32>,
    ) -> Result<(), i32> {
        self.transaction(context, false, || Ok((build()?, None, ())), |()| {})
    }
    /// Build and infallibly publish metadata under one context gate. T stays on
    /// the caller thread and may carry a lock guard; only Action/Notify are sent.
    pub fn transaction<T>(
        &self,
        context: Context,
        cleanup: bool,
        build: impl FnOnce() -> Result<(Action, Option<Notify>, T), i32>,
        commit: impl FnOnce(T),
    ) -> Result<(), i32> {
        if IN_WORKER.with(Cell::get) {
            return Err(999);
        }
        let node = self.node(context, true)?.ok_or(999)?;
        let _gate = node.gate.lock().map_err(|_| 999)?;
        if !cleanup {
            if let Some(code) = node.progress.lock().map_err(|_| 999)?.error {
                return Err(code);
            }
        }
        let sender = self.sender()?;
        let (action, notify, data) = build()?;
        #[cfg(test)]
        if self
            .fail_send
            .swap(false, std::sync::atomic::Ordering::SeqCst)
        {
            drop(action);
            return Err(2);
        }
        {
            let mut progress = node.progress.lock().map_err(|_| 999)?;
            progress.pending = progress.pending.checked_add(1).ok_or(801)?;
        }
        sender
            .send(Job {
                action: Some(action),
                node: node.clone(),
                notify,
                cleanup,
            })
            .map_err(|_| 999)?;
        commit(data);
        Ok(())
    }
    /// Readiness checks must not implicitly wait for every pending context job.
    pub fn exclusive<T>(
        &self,
        context: Context,
        action: impl FnOnce() -> Result<T, i32>,
    ) -> Result<T, i32> {
        if IN_WORKER.with(Cell::get) {
            return Err(999);
        }
        let node = self.node(context, true)?.ok_or(999)?;
        let _gate = node.gate.lock().map_err(|_| 999)?;
        action()
    }
    /// Observe only errors already published by completed work. Do not create
    /// a node, start a worker, acquire a submission gate or wait for pending work.
    pub fn observed_error(&self, context: Context) -> Result<(), i32> {
        if context == 0 {
            return Err(49);
        }
        let Some(node) = self.node(context, false)? else {
            return Ok(());
        };
        let error = node.progress.lock().map_err(|_| 999)?.error;
        error.map_or(Ok(()), Err)
    }
    pub fn barrier<T>(
        &self,
        context: Context,
        cleanup: bool,
        action: impl FnOnce() -> Result<T, i32>,
    ) -> Result<T, i32> {
        if IN_WORKER.with(Cell::get) {
            return Err(999);
        }
        let node = self.node(context, true)?.ok_or(999)?;
        let _gate = node.gate.lock().map_err(|_| 999)?;
        let mut state = node.progress.lock().map_err(|_| 999)?;
        while state.pending != 0 {
            state = node.changed.wait(state).map_err(|_| 999)?;
        }
        let prior = state.error;
        drop(state);
        if !cleanup {
            if let Some(code) = prior {
                return Err(code);
            }
        }
        let value = action()?;
        if let Some(code) = prior {
            Err(code)
        } else {
            Ok(value)
        }
    }
    #[cfg(test)]
    pub fn fail_start_once(&self) {
        self.fail_start
            .store(true, std::sync::atomic::Ordering::SeqCst);
    }
    #[cfg(test)]
    pub fn fail_send_once(&self) {
        self.fail_send
            .store(true, std::sync::atomic::Ordering::SeqCst);
    }
}
impl Drop for Scheduler {
    fn drop(&mut self) {
        if let Some(worker) = self
            .worker
            .get_mut()
            .unwrap_or_else(|e| e.into_inner())
            .take()
        {
            drop(worker.sender);
            if worker.thread.thread().id() != thread::current().id() {
                let _ = worker.thread.join();
            }
        }
    }
}
static SCHEDULER: OnceLock<Scheduler> = OnceLock::new();
pub fn scheduler() -> &'static Scheduler {
    SCHEDULER.get_or_init(Scheduler::new)
}

#[cfg(test)]
mod abandoned_tests {
    use super::*;
    #[test]
    fn abandoned_accepted_job_notifies_and_releases_pending() {
        let node = Arc::new(Node {
            context: 7,
            gate: Mutex::new(()),
            progress: Mutex::new(Progress {
                pending: 1,
                error: None,
            }),
            changed: Condvar::new(),
        });
        let (tx, rx) = mpsc::channel();
        drop(Job {
            action: Some(Box::new(|| panic!("abandoned action executed"))),
            node: node.clone(),
            notify: Some(Box::new(move |code| {
                tx.send(code).unwrap();
            })),
            cleanup: false,
        });
        assert_eq!(rx.recv().unwrap(), 999);
        let progress = node.progress.lock().unwrap();
        assert_eq!(progress.pending, 0);
        assert_eq!(progress.error, Some(999));
    }
    #[test]
    fn notifier_panic_does_not_kill_worker_or_leave_pending() {
        let q = Scheduler::new();
        q.transaction(
            7,
            false,
            || {
                Ok((
                    Box::new(|| 0),
                    Some(Box::new(|_| panic!("notifier panic"))),
                    (),
                ))
            },
            |()| {},
        )
        .unwrap();
        q.barrier(7, false, || Ok(())).unwrap();
        q.submit(7, || Ok(Box::new(|| 0))).unwrap();
        q.barrier(7, false, || Ok(())).unwrap();
    }
}

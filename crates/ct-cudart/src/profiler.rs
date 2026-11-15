//! Explicit no-collector compatibility mode: never advertises capture, writes
//! traces, synchronizes work or changes native profiler state. Success means
//! a valid Runtime context with no already observed asynchronous queue error.
use crate::{driver::DriverCalls, errors::from_driver, state::Runtime, submission::Scheduler};
pub fn no_collector<D: DriverCalls>(rt: &Runtime<D>, queue: &Scheduler) -> i32 {
    let context = match rt.ensure_current() {
        Ok(c) => c,
        Err(code) => return from_driver(code),
    };
    queue.observed_error(context).err().unwrap_or(0)
}

//! Bounded synchronous Driver events over the device-global GPU clock.
use super::*;
use ct_backend_intel::Timestamp;
use std::time::Instant;

#[derive(Clone, Copy)]
struct Mark {
    stamp: Timestamp,
    order: usize,
    before: Instant,
    after: Instant,
}
struct Event {
    id: usize,
    record: Option<Mark>,
}
#[derive(Default)]
pub(super) struct Events {
    records: Vec<Event>,
}
impl Events {
    fn reserve(&mut self) -> CudaResult {
        if self.records.len() >= 128 {
            return Err(2);
        }
        self.records.try_reserve_exact(1).map_err(|_| 2)
    }
    fn insert(&mut self, id: usize) {
        self.records.push(Event { id, record: None });
    }
    fn get(&self, id: usize) -> Result<&Event, i32> {
        self.records.iter().find(|e| e.id == id).ok_or(400)
    }
    fn get_mut(&mut self, id: usize) -> Result<&mut Event, i32> {
        self.records.iter_mut().find(|e| e.id == id).ok_or(400)
    }
    fn record(&mut self, id: usize, sample: impl FnOnce() -> Result<Mark, i32>) -> CudaResult {
        let event = self.get_mut(id)?;
        let mark = sample()?;
        event.record = Some(mark);
        Ok(())
    }
    fn remove(&mut self, id: usize) -> bool {
        if let Some(i) = self.records.iter().position(|e| e.id == id) {
            self.records.remove(i);
            true
        } else {
            false
        }
    }
}
fn flags(value: u32) -> CudaResult {
    if value & !7 != 0 {
        Err(INVALID)
    } else if value != 0 {
        Err(UNSUPPORTED)
    } else {
        Ok(())
    }
}
fn elapsed(start: &Mark, end: &Mark) -> Result<f32, i32> {
    let a = start.stamp;
    let b = end.stamp;
    if a.frequency == 0
        || a.frequency != b.frequency
        || a.bits != b.bits
        || !(1..=64).contains(&a.bits)
    {
        return Err(UNSUPPORTED);
    }
    if end.order < start.order {
        return Err(INVALID);
    }
    if end.order == start.order {
        return Ok(0.0);
    }
    let half = 1u128 << (a.bits - 1);
    // CPU time is only a conservative ambiguity bound, never the output value.
    let upper = end
        .after
        .checked_duration_since(start.before)
        .ok_or(UNSUPPORTED)?;
    let scaled = upper
        .as_nanos()
        .checked_mul(a.frequency as u128)
        .ok_or(UNSUPPORTED)?;
    if scaled >= half * 1_000_000_000 {
        return Err(UNSUPPORTED);
    }
    let mask = u64::MAX >> (64 - a.bits);
    let delta = b.ticks.wrapping_sub(a.ticks) & mask;
    if delta as u128 >= half {
        return Err(UNSUPPORTED);
    }
    let milliseconds = (delta as f64 * 1000.0 / a.frequency as f64) as f32;
    if !milliseconds.is_finite() {
        return Err(UNSUPPORTED);
    }
    Ok(milliseconds)
}
/// # Safety
/// output must be writable for one event handle; errors preserve its value.
#[no_mangle]
pub unsafe extern "system" fn cuEventCreate(output: *mut *mut c_void, options: u32) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    if let Err(code) = flags(options) {
        return code;
    }
    invoke(|r| {
        let context = context_id(r)?;
        let id = r.next.checked_add(1).ok_or(UNKNOWN)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&context).ok_or(INVALID_CONTEXT)?;
        c.events.reserve()?;
        b.timestamp(&mut c.native).map_err(native_error)?;
        c.events.insert(id);
        r.next = id;
        unsafe {
            output.write(id as *mut c_void);
        }
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuEventRecord(event: *mut c_void, stream: *mut c_void) -> i32 {
    if !stream.is_null() {
        return UNSUPPORTED;
    }
    invoke(|r| {
        let context = context_id(r)?;
        let order = r.next.checked_add(1).ok_or(UNKNOWN)?;
        let b = r.backend.as_ref().ok_or(NOT_INITIALIZED)?;
        let c = r.contexts.get_mut(&context).ok_or(INVALID_CONTEXT)?;
        c.events.record(event as usize, || {
            let before = Instant::now();
            let stamp = b.timestamp(&mut c.native).map_err(native_error)?;
            let after = Instant::now();
            Ok(Mark {
                stamp,
                order,
                before,
                after,
            })
        })?;
        r.next = order;
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuEventSynchronize(event: *mut c_void) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let c = r.contexts.get(&id).ok_or(INVALID_CONTEXT)?;
        c.events.get(event as usize)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        // Native Driver commands and record are synchronous in this profile.
        // An event never recorded is also already complete.
        Ok(())
    })
}
#[no_mangle]
pub extern "system" fn cuEventDestroy_v2(event: *mut c_void) -> i32 {
    invoke(|r| {
        let id = context_id(r)?;
        let c = r.contexts.get_mut(&id).ok_or(INVALID_CONTEXT)?;
        // No native event pool exists: only bounded counter metadata is removed.
        if c.events.remove(event as usize) {
            Ok(())
        } else {
            Err(400)
        }
    })
}
/// # Safety
/// output must be writable for one f32; errors preserve its value.
#[no_mangle]
pub unsafe extern "system" fn cuEventElapsedTime(
    output: *mut f32,
    start: *mut c_void,
    end: *mut c_void,
) -> i32 {
    if output.is_null() {
        return INVALID;
    }
    invoke(|r| {
        let id = context_id(r)?;
        let c = r.contexts.get(&id).ok_or(INVALID_CONTEXT)?;
        let a = c.events.get(start as usize)?.record.as_ref().ok_or(400)?;
        let b = c.events.get(end as usize)?.record.as_ref().ok_or(400)?;
        if c.native.poisoned {
            return Err(UNKNOWN);
        }
        let value = elapsed(a, b)?;
        unsafe {
            output.write(value);
        }
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};
    fn mark(ticks: u64, bits: u32, frequency: u64, order: usize, at: Instant) -> Mark {
        Mark {
            stamp: ct_backend_intel::Timestamp {
                ticks,
                bits,
                frequency,
            },
            order,
            before: at,
            after: at,
        }
    }
    #[test]
    fn failed_record_preserves_previous_and_invalid_handle_skips_sampling() {
        let mut events = Events::default();
        events.reserve().unwrap();
        events.insert(7);
        let now = Instant::now();
        events.record(7, || Ok(mark(11, 32, 1000, 1, now))).unwrap();
        assert_eq!(events.record(7, || Err(999)), Err(999));
        assert_eq!(events.get(7).unwrap().record.unwrap().stamp.ticks, 11);
        assert_eq!(
            events.record(8, || panic!("unknown handle sampled")),
            Err(400)
        );
    }
    #[test]
    fn elapsed_uses_gpu_ticks_and_masks_single_wrap() {
        let now = Instant::now();
        let a = mark(250, 8, 1000, 1, now);
        let b = mark(0x106, 8, 1000, 2, now + Duration::from_millis(20));
        assert_eq!(elapsed(&a, &b), Ok(12.0));
        assert_eq!(elapsed(&a, &a), Ok(0.0));
    }
    #[test]
    fn elapsed_rejects_reverse_order_and_unrelated_clocks() {
        let now = Instant::now();
        let a = mark(50, 32, 1000, 2, now);
        assert_eq!(elapsed(&a, &mark(60, 32, 1000, 1, now)), Err(1));
        assert_eq!(elapsed(&a, &mark(60, 31, 1000, 3, now)), Err(801));
        assert_eq!(elapsed(&a, &mark(60, 32, 999, 3, now)), Err(801));
        assert_eq!(elapsed(&a, &mark(40, 32, 1000, 3, now)), Err(801));
    }
    #[test]
    fn elapsed_rejects_multiwrap_and_halfperiod_boundary() {
        let now = Instant::now();
        let a = mark(1, 8, 1000, 1, now);
        assert_eq!(
            elapsed(&a, &mark(2, 8, 1000, 2, now + Duration::from_millis(513))),
            Err(801)
        );
        assert_eq!(elapsed(&a, &mark(129, 8, 1000, 2, now)), Err(801));
        assert_eq!(
            elapsed(&a, &mark(2, 8, 1000, 2, now + Duration::from_millis(128))),
            Err(801)
        );
    }
    #[test]
    fn elapsed_checks_metadata_64bit_wrap_and_bound_overflow() {
        let now = Instant::now();
        let a = mark(u64::MAX - 9, 64, 1000, 1, now);
        assert_eq!(
            elapsed(&a, &mark(10, 64, 1000, 2, now + Duration::from_millis(25))),
            Ok(20.0)
        );
        for bits in [0, 65] {
            let a = mark(1, bits, 1000, 1, now);
            assert_eq!(elapsed(&a, &a), Err(801));
        }
        let a = mark(1, 64, 0, 1, now);
        assert_eq!(elapsed(&a, &a), Err(801));
        let a = mark(1, 64, u64::MAX, 1, now);
        assert_eq!(
            elapsed(&a, &mark(2, 64, u64::MAX, 2, now + Duration::from_secs(2))),
            Err(801)
        );
    }
    #[test]
    fn event_book_limits_exact_ownership_and_rerecord() {
        let mut book = Events::default();
        let now = Instant::now();
        assert_eq!(book.get(7).err(), Some(400));
        for id in 1..=128 {
            book.reserve().unwrap();
            book.insert(id);
        }
        assert_eq!(book.reserve(), Err(2));
        assert!(book.remove(7));
        assert!(!book.remove(7));
        book.reserve().unwrap();
        book.insert(129);
        book.get_mut(129).unwrap().record = Some(mark(5, 32, 1000, 1, now));
        book.get_mut(129).unwrap().record = Some(mark(7, 32, 1000, 2, now));
        assert_eq!(
            book.get(129).unwrap().record.as_ref().unwrap().stamp.ticks,
            7
        );
        assert_eq!(book.get(7).err(), Some(400));
    }
    #[test]
    fn event_flags_distinguish_invalid_from_unsupported() {
        assert_eq!(flags(0), Ok(()));
        for value in 1..=7 {
            assert_eq!(flags(value), Err(801));
        }
        assert_eq!(flags(8), Err(1));
        assert_eq!(flags(u32::MAX), Err(1));
    }
}

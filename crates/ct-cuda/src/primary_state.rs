//! Device primary ownership, independent of native resources and TLS.
use std::collections::{BTreeMap, BTreeSet};

struct Primary {
    context: Option<usize>,
    references: usize,
}

#[derive(Default)]
pub(crate) struct PrimaryContexts {
    devices: BTreeMap<i32, Primary>,
    retired: BTreeSet<usize>,
}

impl PrimaryContexts {
    /// Reset preserved usage but removed the owned native handle.
    pub fn has_pending_usage(&self, device: i32) -> bool {
        self.devices
            .get(&device)
            .is_some_and(|p| p.references > 0 && p.context.is_none())
    }

    /// Obtain ownership without adding retained usage. Fresh ownership is inactive;
    /// usage preserved by reset can make a recreated context active immediately.
    /// This internal policy does not establish private CUDA reset semantics.
    pub fn get_or_create_unretained(
        &mut self,
        device: i32,
        create: impl FnOnce() -> Result<usize, i32>,
    ) -> Result<usize, i32> {
        if let Some(context) = self.devices.get(&device).and_then(|p| p.context) {
            return Ok(context);
        }
        let context = create()?;
        self.devices
            .entry(device)
            .or_insert(Primary {
                context: None,
                references: 0,
            })
            .context = Some(context);
        Ok(context)
    }

    pub fn retain(
        &mut self,
        device: i32,
        create: impl FnOnce() -> Result<usize, i32>,
    ) -> Result<usize, i32> {
        let references = self
            .devices
            .get(&device)
            .map_or(0, |p| p.references)
            .checked_add(1)
            .ok_or(999)?;
        let context = self.get_or_create_unretained(device, create)?;
        // The successful lookup above always publishes an owned entry.
        self.devices.get_mut(&device).unwrap().references = references;
        Ok(context)
    }

    pub fn release(&mut self, device: i32) -> Result<Option<usize>, i32> {
        let primary = self.devices.get_mut(&device).ok_or(201)?;
        if primary.references == 0 {
            return Err(201);
        }
        if primary.references > 1 {
            primary.references -= 1;
            return Ok(None);
        }
        let context = primary.context;
        self.devices.remove(&device);
        if let Some(context) = context {
            self.retired.insert(context);
        }
        Ok(context)
    }

    /// Deactivate resources without consuming any retained usage.
    pub fn reset(&mut self, device: i32) -> Option<usize> {
        let context = self.devices.get_mut(&device)?.context.take()?;
        self.retired.insert(context);
        Some(context)
    }

    pub fn active(&self, device: i32) -> bool {
        self.devices
            .get(&device)
            .is_some_and(|primary| primary.context.is_some() && primary.references > 0)
    }

    pub fn owns(&self, context: usize) -> bool {
        self.devices
            .values()
            .any(|primary| primary.context == Some(context))
    }

    pub fn retired(&self, context: usize) -> bool {
        self.retired.contains(&context)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pending_usage_requires_missing_handle_and_positive_references() {
        let mut state = PrimaryContexts::default();
        assert!(!state.has_pending_usage(0));
        state.get_or_create_unretained(0, || Ok(10)).unwrap();
        assert!(!state.has_pending_usage(0));
        state.reset(0);
        assert!(!state.has_pending_usage(0));
        state.retain(0, || Ok(11)).unwrap();
        assert!(!state.has_pending_usage(0));
        state.reset(0);
        assert!(state.has_pending_usage(0));
        assert!(!state.has_pending_usage(1));
        assert_eq!(state.retain(0, || Err(2)), Err(2));
        assert!(state.has_pending_usage(0));
        state.retain(0, || Ok(12)).unwrap();
        assert!(!state.has_pending_usage(0));
    }

    #[test]
    fn inactive_lookup_preserves_identity_without_acquiring_usage() {
        let mut state = PrimaryContexts::default();
        assert_eq!(state.get_or_create_unretained(0, || Ok(17)), Ok(17));
        assert!(!state.active(0));
        assert!(state.owns(17));
        assert_eq!(state.devices[&0].references, 0);
        assert_eq!(
            state.get_or_create_unretained(0, || panic!("reuse")),
            Ok(17)
        );
        assert_eq!(state.release(0), Err(201));
        assert!(state.owns(17));
        assert!(!state.retired(17));
        assert_eq!(state.retain(0, || panic!("same reserved handle")), Ok(17));
        assert!(state.active(0));
        assert_eq!(state.devices[&0].references, 1);
        assert_eq!(
            state.get_or_create_unretained(0, || panic!("reuse active")),
            Ok(17)
        );
        assert_eq!(state.devices[&0].references, 1);
        assert_eq!(state.release(0), Ok(Some(17)));
        assert!(state.retired(17));
    }

    #[test]
    fn inactive_creation_failure_and_retained_usage_are_transactional() {
        let mut state = PrimaryContexts::default();
        assert_eq!(state.get_or_create_unretained(0, || Err(2)), Err(2));
        assert!(!state.devices.contains_key(&0));
        state.retain(0, || Ok(17)).unwrap();
        state.reset(0);
        assert_eq!(state.get_or_create_unretained(0, || Err(2)), Err(2));
        assert_eq!(state.devices[&0].references, 1);
        assert!(!state.active(0));
        assert_eq!(state.get_or_create_unretained(0, || Ok(18)), Ok(18));
        assert!(state.active(0)); // Existing retained usage was preserved by reset.
        assert_eq!(state.devices[&0].references, 1);
        state.devices.get_mut(&0).unwrap().references = usize::MAX;
        assert_eq!(
            state.retain(0, || panic!("overflow before allocation")),
            Err(999)
        );
        assert_eq!(state.devices[&0].references, usize::MAX);
        assert!(state.owns(18));
    }

    #[test]
    fn inactive_reset_retires_identity_without_touching_other_devices() {
        let mut state = PrimaryContexts::default();
        state.get_or_create_unretained(0, || Ok(17)).unwrap();
        state.retain(1, || Ok(20)).unwrap();
        assert_eq!(state.reset(0), Some(17));
        assert!(state.retired(17));
        assert!(!state.owns(17));
        assert_eq!(state.reset(0), None);
        assert_eq!(state.release(0), Err(201));
        assert_eq!(state.get_or_create_unretained(0, || Ok(18)), Ok(18));
        assert!(!state.active(0));
        assert_eq!(state.devices[&0].references, 0);
        assert!(state.active(1) && state.owns(20));
        assert_eq!(state.release(1), Ok(Some(20)));
    }

    #[test]
    fn reset_preserves_usage_across_fresh_generation_and_repeated_reset() {
        let mut state = PrimaryContexts::default();
        assert_eq!(state.reset(0), None);
        state.retain(0, || Ok(10)).unwrap();
        state.retain(0, || panic!("reuse")).unwrap();
        assert_eq!(state.reset(0), Some(10));
        assert!(!state.active(0));
        assert!(state.retired(10));
        assert!(!state.owns(10));
        assert_eq!(state.reset(0), None);
        assert_eq!(state.retain(0, || Ok(11)), Ok(11));
        assert!(state.retired(10));
        assert_eq!(state.release(0), Ok(None));
        assert_eq!(state.release(0), Ok(None));
        assert!(state.active(0));
        assert_eq!(state.reset(0), Some(11));
        assert_eq!(state.release(0), Ok(None));
        assert_eq!(state.release(0), Err(201));
        assert!(state.retired(10) && state.retired(11));
    }

    #[test]
    fn inactive_releases_and_device_isolation_do_not_create_resources() {
        let mut state = PrimaryContexts::default();
        state.retain(0, || Ok(10)).unwrap();
        state.retain(0, || panic!("reuse")).unwrap();
        state.retain(1, || Ok(20)).unwrap();
        assert_eq!(state.reset(0), Some(10));
        assert!(state.active(1) && state.owns(20));
        assert_eq!(state.release(0), Ok(None));
        assert_eq!(state.release(0), Ok(None));
        assert_eq!(state.release(0), Err(201));
        assert_eq!(state.reset(0), None);
        assert_eq!(state.release(1), Ok(Some(20)));
    }

    #[test]
    fn reactivation_failure_and_overflow_preserve_inactive_usage() {
        let mut state = PrimaryContexts::default();
        state.retain(0, || Ok(10)).unwrap();
        state.retain(0, || panic!("reuse")).unwrap();
        state.reset(0);
        assert_eq!(state.retain(0, || Err(2)), Err(2));
        assert!(!state.active(0));
        assert_eq!(state.devices[&0].references, 2);
        state.devices.get_mut(&0).unwrap().references = usize::MAX;
        assert_eq!(
            state.retain(0, || panic!("must check overflow first")),
            Err(999)
        );
        assert!(!state.active(0));
        assert_eq!(state.devices[&0].references, usize::MAX);
    }

    #[test]
    fn retains_share_one_lazy_context_and_final_release_retires_it() {
        let mut state = PrimaryContexts::default();
        assert!(!state.active(0));
        assert_eq!(state.release(0), Err(201));
        assert_eq!(state.retain(0, || Ok(17)), Ok(17));
        assert_eq!(state.retain(0, || panic!("must reuse context")), Ok(17));
        assert!(state.active(0));
        assert!(state.owns(17));
        assert_eq!(state.release(0), Ok(None));
        assert!(!state.retired(17));
        assert_eq!(state.release(0), Ok(Some(17)));
        assert!(!state.active(0));
        assert!(!state.owns(17));
        assert!(state.retired(17));
        assert_eq!(state.release(0), Err(201));
        assert_eq!(state.retain(0, || Ok(18)), Ok(18));
        assert!(state.retired(17));
        assert!(!state.retired(18));
    }

    #[test]
    fn failed_creation_publishes_nothing_and_devices_are_independent() {
        let mut state = PrimaryContexts::default();
        assert_eq!(state.retain(0, || Err(2)), Err(2));
        assert!(!state.active(0));
        assert_eq!(state.release(0), Err(201));
        assert_eq!(state.retain(0, || Ok(10)), Ok(10));
        assert_eq!(state.retain(1, || Ok(11)), Ok(11));
        assert_eq!(state.release(0), Ok(Some(10)));
        assert!(state.active(1));
        assert!(state.owns(11));
        assert_eq!(state.release(1), Ok(Some(11)));
    }

    #[test]
    fn reference_overflow_preserves_the_existing_context() {
        let mut state = PrimaryContexts::default();
        state.retain(0, || Ok(10)).unwrap();
        state.devices.get_mut(&0).unwrap().references = usize::MAX;
        assert_eq!(
            state.retain(0, || panic!("no new native allocation")),
            Err(999)
        );
        assert_eq!(state.devices[&0].references, usize::MAX);
        assert!(state.owns(10));
        assert!(!state.retired(10));
    }
}

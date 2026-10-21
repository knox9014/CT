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
    pub fn retain(
        &mut self,
        device: i32,
        create: impl FnOnce() -> Result<usize, i32>,
    ) -> Result<usize, i32> {
        if let Some(primary) = self.devices.get_mut(&device) {
            let references = primary.references.checked_add(1).ok_or(999)?;
            let context = match primary.context {
                Some(context) => context,
                None => create()?,
            };
            primary.context = Some(context);
            primary.references = references;
            return Ok(context);
        }
        let context = create()?;
        self.devices.insert(
            device,
            Primary {
                context: Some(context),
                references: 1,
            },
        );
        Ok(context)
    }

    pub fn release(&mut self, device: i32) -> Result<Option<usize>, i32> {
        let primary = self.devices.get_mut(&device).ok_or(201)?;
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
            .is_some_and(|primary| primary.context.is_some())
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

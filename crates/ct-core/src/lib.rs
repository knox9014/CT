use std::collections::BTreeMap;

#[derive(Default)]
pub struct AllocationRanges(BTreeMap<u64, usize>);

impl AllocationRanges {
    pub fn insert(&mut self, base: u64, size: usize) -> bool {
        let Some(end) = base.checked_add(size as u64) else {
            return false;
        };
        if base == 0
            || size == 0
            || self
                .0
                .range(..=base)
                .next_back()
                .is_some_and(|(&b, &s)| b + s as u64 > base)
            || self.0.range(base..).next().is_some_and(|(&b, _)| b < end)
        {
            return false;
        }
        self.0.insert(base, size);
        true
    }
    pub fn contains(&self, address: u64, size: usize) -> bool {
        let Some(end) = address.checked_add(size as u64) else {
            return false;
        };
        self.0
            .range(..=address)
            .next_back()
            .is_some_and(|(&base, &bytes)| {
                address < base + bytes as u64 && end <= base + bytes as u64
            })
    }
    /// The live allocation containing this address; one-past is excluded.
    pub fn locate(&self, address: u64) -> Option<(u64, usize)> {
        let (&base, &bytes) = self.0.range(..=address).next_back()?;
        (address < base + bytes as u64).then_some((base, bytes))
    }
    pub fn remove(&mut self, base: u64) -> bool {
        self.0.remove(&base).is_some()
    }
    pub fn bases(&self) -> Vec<u64> {
        self.0.keys().copied().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn allocation_lookup_distinguishes_adjacent_ranges_gaps_and_removed_entries() {
        let mut ranges = AllocationRanges::default();
        assert!(ranges.insert(0x1000, 16));
        assert!(ranges.insert(0x1010, 32));
        assert_eq!(ranges.locate(0x100f), Some((0x1000, 16)));
        assert_eq!(ranges.locate(0x1010), Some((0x1010, 32)));
        for address in [0, 0xfff, 0x1030, u64::MAX] {
            assert_eq!(ranges.locate(address), None);
        }
        assert!(ranges.remove(0x1000));
        assert_eq!(ranges.locate(0x1000), None);
        assert_eq!(ranges.locate(0x1011), Some((0x1010, 32)));
    }
    #[test]
    fn accepts_only_owned_nonoverflowing_ranges_and_exact_bases_for_free() {
        let mut ranges = AllocationRanges::default();
        assert!(ranges.insert(0x1000, 16));
        assert!(ranges.contains(0x1000, 16));
        assert!(ranges.contains(0x1004, 12));
        assert!(!ranges.contains(0x1004, 13));
        assert!(!ranges.contains(0x0fff, 1));
        assert!(!ranges.contains(0x1010, 1));
        assert!(!ranges.contains(0x1000, usize::MAX));
        assert!(!ranges.insert(0x1008, 16));
        assert!(!ranges.insert(0, 16));
        assert!(!ranges.insert(u64::MAX - 2, 8));
        assert!(ranges.insert(0x1010, 16));
        assert!(!ranges.contains(0x1000, 32));
        assert!(!ranges.remove(0x1001));
        assert!(ranges.remove(0x1000));
        assert!(!ranges.remove(0x1000));
        assert!(!ranges.contains(0x1000, 1));
        assert!(ranges.contains(0x1010, 16));
    }
}

//! Module addresses participate in access checks, while allocation ownership stays separate.
use super::*;
use ct_backend_intel::NativeGlobal;

pub(crate) trait DeviceRanges {
    fn contains_device(&self, address: u64, bytes: usize) -> bool;
}
impl DeviceRanges for AllocationRanges {
    fn contains_device(&self, address: u64, bytes: usize) -> bool {
        self.contains(address, bytes)
    }
}
fn in_global(g: NativeGlobal, address: u64, bytes: usize) -> bool {
    let Some(end) = address.checked_add(bytes as u64) else {
        return false;
    };
    let Some(limit) = g.pointer.checked_add(g.size as u64) else {
        return false;
    };
    address >= g.pointer && address < limit && end <= limit
}
impl OwnedContext {
    pub(crate) fn global_ranges(&self) -> impl Iterator<Item = NativeGlobal> + '_ {
        self.modules
            .values()
            .flat_map(|m| m.globals.iter().filter_map(|g| m.native.global(&g.name)))
    }
    pub(crate) fn is_global_address(&self, address: u64) -> bool {
        self.global_ranges().any(|g| in_global(g, address, 0))
    }
    pub(crate) fn conflicts_global(&self, g: NativeGlobal) -> bool {
        let end = g.pointer + g.size as u64;
        self.allocations.locate(g.pointer).is_some()
            || self
                .allocations
                .bases()
                .into_iter()
                .any(|b| b >= g.pointer && b < end)
            || self
                .global_ranges()
                .any(|old| g.pointer < old.pointer + old.size as u64 && old.pointer < end)
    }
}
impl DeviceRanges for OwnedContext {
    fn contains_device(&self, address: u64, bytes: usize) -> bool {
        self.allocations.contains(address, bytes)
            || self.global_ranges().any(|g| in_global(g, address, bytes))
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn global_range_is_exact_and_excludes_one_past_and_overflow() {
        let g = NativeGlobal {
            pointer: 0x1000,
            size: 4,
        };
        for (p, n, want) in [
            (0x1000, 4, true),
            (0x1003, 1, true),
            (0x1003, 0, true),
            (0x1004, 0, false),
            (0xfff, 1, false),
            (0x1000, 5, false),
            (u64::MAX, 4, false),
        ] {
            assert_eq!(in_global(g, p, n), want);
        }
    }
}

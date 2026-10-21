//! Stack edits specific to ordinary context destruction; never prune buried entries.
pub(crate) fn pop_destroyed_current(stack: &mut Vec<usize>, id: usize) {
    if stack.last() == Some(&id) {
        stack.pop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn destroy_pops_one_current_entry_and_preserves_buried_duplicates() {
        let mut stack = vec![10, 20, 10];
        pop_destroyed_current(&mut stack, 10);
        assert_eq!(stack, vec![10, 20]);
        pop_destroyed_current(&mut stack, 10);
        assert_eq!(stack, vec![10, 20]);
        pop_destroyed_current(&mut stack, 20);
        assert_eq!(stack, vec![10]);
        pop_destroyed_current(&mut stack, 10);
        assert!(stack.is_empty());
        pop_destroyed_current(&mut stack, 10);
        assert!(stack.is_empty());
        let mut duplicates = vec![10, 10];
        pop_destroyed_current(&mut duplicates, 10);
        assert_eq!(duplicates, vec![10]);
    }
}

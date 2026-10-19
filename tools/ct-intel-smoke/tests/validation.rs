use ct_intel_smoke::{group_count, verify_sum};

// Breaks caught: accepting stale/no-op output, mismatched lengths, or NaN;
// dispatching too few groups or overflowing the supported 32-bit index range.
#[test]
fn validates_real_sum_and_rejects_stale_output() {
    assert_eq!(
        verify_sum(&[1.0, -2.0, 0.25], &[3.0, 5.0, -0.5], &[4.0, 3.0, -0.25]),
        Ok(0.0)
    );
    assert!(verify_sum(&[1.0], &[2.0], &[0.0]).is_err());
}

#[test]
fn rejects_mismatched_lengths_and_nonfinite_results() {
    assert!(verify_sum(&[1.0], &[2.0], &[]).is_err());
    assert!(verify_sum(&[1.0], &[], &[1.0]).is_err());
    assert!(verify_sum(&[1.0], &[2.0], &[f32::NAN]).is_err());
    assert!(verify_sum(&[1.0], &[2.0], &[f32::INFINITY]).is_err());
    assert!(verify_sum(&[f32::NAN], &[2.0], &[3.0]).is_err());
}

#[test]
fn rounds_dispatch_up_at_boundaries_and_rejects_invalid_sizes() {
    assert_eq!(group_count(1, 64), Ok(1));
    assert_eq!(group_count(63, 64), Ok(1));
    assert_eq!(group_count(64, 64), Ok(1));
    assert_eq!(group_count(65, 64), Ok(2));
    assert_eq!(group_count(100003, 128), Ok(782));
    assert!(group_count(0, 64).is_err());
    assert!(group_count(64, 0).is_err());
    assert!(group_count(u32::MAX as usize + 1, 64).is_err());
    assert!(group_count(u32::MAX as usize, 64).is_err());
}

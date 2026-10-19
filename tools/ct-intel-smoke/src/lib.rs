//! Native Intel backend experiment. This is not a CUDA compatibility driver.

#[cfg(all(windows, target_pointer_width = "64"))]
mod abi;
#[cfg(all(windows, target_pointer_width = "64"))]
mod level_zero;
#[cfg(all(windows, target_pointer_width = "64"))]
mod loader;

pub fn verify_sum(a: &[f32], b: &[f32], actual: &[f32]) -> Result<f32, String> {
    if a.is_empty() || a.len() != b.len() || a.len() != actual.len() {
        return Err("nonempty input/output lengths must match".into());
    }
    let mut max_error = 0.0_f32;
    for (i, ((&x, &y), &value)) in a.iter().zip(b).zip(actual).enumerate() {
        let expected = x + y;
        if !x.is_finite() || !y.is_finite() || !expected.is_finite() || !value.is_finite() {
            return Err(format!("nonfinite value at index {i}"));
        }
        let error = (value - expected).abs();
        if error > 1e-5 + 1e-4 * expected.abs() {
            return Err(format!(
                "incorrect output at index {i}: {value}, expected {expected}"
            ));
        }
        max_error = max_error.max(error);
    }
    Ok(max_error)
}

pub fn group_count(n: usize, group_size: u32) -> Result<u32, String> {
    if n == 0 || n > u32::MAX as usize || group_size == 0 {
        return Err("positive u32 length and group size required".into());
    }
    let groups = (n as u64).div_ceil(group_size as u64);
    if groups * group_size as u64 > u32::MAX as u64 {
        return Err("padded dispatch exceeds the supported u32 index range".into());
    }
    Ok(groups as u32)
}

pub fn run_smoke(module: &[u8], device_name: &str) -> Result<String, String> {
    #[cfg(all(windows, target_pointer_width = "64"))]
    {
        level_zero::run(module, device_name)
    }
    #[cfg(not(all(windows, target_pointer_width = "64")))]
    {
        let _ = (module, device_name);
        Err("M0 native probe requires Windows x64".into())
    }
}

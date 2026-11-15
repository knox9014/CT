//! Explicit device metadata query; no memory allocation or CUDA support claim.
#![cfg(all(windows, target_pointer_width = "64"))]
use ct_backend_intel::Backend;

#[test]
#[ignore = "requires selected Intel GPU; run explicitly in a fresh process"]
fn native_device_total_reports_single_driver_memory_property() {
    let backend = Backend::open().expect("Intel backend required");
    let filter = std::env::var("CT_TEST_DEVICE").unwrap_or_else(|_| "B390".into());
    let index = backend
        .devices
        .iter()
        .position(|d| d.name.contains(&filter))
        .expect("selected Intel device missing");
    let first = backend
        .total_memory(index)
        .expect("single memory property required");
    let second = backend.total_memory(index).expect("repeat metadata query");
    assert!(first > 0);
    assert_eq!(first, second);
    println!(
        "device memory metadata passed: device={}; bytes={first}; property_count=1; queries=2",
        backend.devices[index].name
    );
}

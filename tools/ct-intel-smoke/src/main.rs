fn main() {
    let mut args = std::env::args_os().skip(1);
    let fixture = args
        .next()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| {
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../tests/fixtures/vector_add.spv")
        });
    let filter = args.next().map(|v| v.to_string_lossy().into_owned());
    if args.next().is_some() {
        eprintln!("usage: ct-intel-smoke [vector_add.spv] [Intel GPU name filter]");
        std::process::exit(2);
    }
    let result = std::fs::read(&fixture)
        .map_err(|error| format!("cannot read SPIR-V fixture: {error}"))
        .and_then(|bytes| match filter.as_deref() {
            Some(name) => ct_intel_smoke::run_smoke(&bytes, name),
            None => ct_intel_smoke::run_smoke_auto(&bytes),
        });
    match result {
        Ok(report) => println!("{report}"),
        Err(error) => {
            eprintln!("M0 native probe failed: {error}");
            std::process::exit(1);
        }
    }
}

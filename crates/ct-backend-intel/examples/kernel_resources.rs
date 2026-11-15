//! Development-only raw metadata query; no CUDA attributes or kernel launch.
use ct_backend_intel::{Backend, NativeResult};

fn inspect() -> Result<(), String> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: kernel_resources INPUT.spv ENTRY".into());
    }
    let entry = args[1].to_str().ok_or("entry must be UTF-8")?;
    let code = std::fs::read(&args[0]).map_err(|_| "input_io")?;
    let mut backend = Backend::open().map_err(|e| format!("backend={e:#x}"))?;
    let matches: Vec<_> = backend
        .devices
        .iter()
        .enumerate()
        .filter(|(_, d)| d.name.contains("B390"))
        .map(|(ordinal, _)| ordinal)
        .collect();
    if matches.len() != 1 {
        return Err("requires exactly one B390 match".into());
    }
    let ordinal = matches[0];
    let device_name = backend.devices[ordinal].name.clone();
    let mut context = backend
        .create_context(ordinal)
        .map_err(|e| format!("context={e:#x}"))?;
    let queried = (|| -> NativeResult<_> {
        let mut module = backend.load_module(&mut context, &code, entry)?;
        let result = backend.kernel_resources(&mut context, &module, 0);
        let cleanup = backend.unload_module(&mut context, &mut module);
        match (result, cleanup) {
            (Err(e), _) | (Ok(_), Err(e)) => Err(e),
            (Ok(v), Ok(())) => Ok(v),
        }
    })();
    let cleanup = backend.destroy_context(&mut context, &[]);
    let value = queried.map_err(|e| format!("query={e:#x}"))?;
    cleanup.map_err(|e| format!("cleanup={e:#x}"))?;
    let name_hex: String = device_name.bytes().map(|b| format!("{b:02x}")).collect();
    println!(
        concat!(
            "{{\"device_name_hex\":\"{}\",\"num_kernel_args\":{},",
            "\"required_group_size\":[{},{},{}],\"required_num_subgroups\":{},",
            "\"required_subgroup_size\":{},\"max_subgroup_size\":{},",
            "\"max_num_subgroups\":{},\"local_mem_bytes\":{},",
            "\"private_mem_bytes\":{},\"spill_mem_bytes\":{}}}"
        ),
        name_hex,
        value.num_kernel_args,
        value.required_group_size[0],
        value.required_group_size[1],
        value.required_group_size[2],
        value.required_num_subgroups,
        value.required_subgroup_size,
        value.max_subgroup_size,
        value.max_num_subgroups,
        value.local_mem_bytes,
        value.private_mem_bytes,
        value.spill_mem_bytes
    );
    Ok(())
}

fn main() {
    if let Err(e) = inspect() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

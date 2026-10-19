//! Developer-only translation utility. Outputs stay local unless explicitly reviewed.
fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        eprintln!("usage: translate input.ptx output.spv");
        std::process::exit(2);
    }
    let result = std::fs::read_to_string(&args[0])
        .map_err(|_| "cannot read PTX input".to_owned())
        .and_then(|s| ct_codegen_spirv::translate(&s).map_err(|e| e.to_string()))
        .and_then(|c| {
            std::fs::write(&args[1], c.spirv).map_err(|_| "cannot write local output".to_owned())
        });
    if let Err(e) = result {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

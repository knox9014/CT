//! Developer module export. Diagnostics never include PTX or private paths.
use std::path::Path;

fn export(input: &Path, output: &Path) -> Result<(), (i32, String)> {
    // Read first so an accidental identical input/output path cannot erase input.
    let source = std::fs::read_to_string(input).map_err(|_| (2, "input_io".into()));
    if input == output
        || matches!((input.canonicalize(), output.canonicalize()), (Ok(a), Ok(b)) if a == b)
    {
        return Err((2, "input_output_alias".into()));
    }
    match std::fs::remove_file(output) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(_) => return Err((2, "output_io".into())),
    }
    let module = ct_codegen_spirv::translate_module(&source?).map_err(|e| {
        let (code, category) = if e.unsupported {
            (3, "unsupported")
        } else {
            (1, "invalid_translation")
        };
        (code, format!("line={} category={category}", e.line))
    })?;
    std::fs::write(output, module.spirv).map_err(|_| {
        let _ = std::fs::remove_file(output);
        (2, "output_io".into())
    })
}

fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        eprintln!("usage: translate_module INPUT OUTPUT");
        std::process::exit(2);
    }
    if let Err((code, diagnostic)) = export(Path::new(&args[0]), Path::new(&args[1])) {
        eprintln!("{diagnostic}");
        std::process::exit(code);
    }
}

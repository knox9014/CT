use super::*;
use crate::symbols::{copy, query, Transfer};
fn ready_mixed(k: &KernelRuntime) -> usize {
    let t = unsafe { register(&k.registry, &image()) };
    unsafe {
        k.registry
            .function(t, 11, c"one".as_ptr().cast(), metadata())
            .unwrap();
        for (host, name, size) in [(91, c"value", 4), (93, c"wide", 8)] {
            k.registry
                .variable(
                    t,
                    host,
                    name.as_ptr().cast(),
                    name.as_ptr().cast(),
                    crate::registration_variables::VariableMetadata {
                        external: 0,
                        size,
                        constant: 0,
                        global: 0,
                    },
                )
                .unwrap();
        }
    }
    k.registry.end(t).unwrap();
    t
}
#[test]
fn symbol_mixed_width_ranges() {
    let k = KernelRuntime::new();
    ready_mixed(&k);
    let f = Fake::default();
    f.0.global_overrides
        .lock()
        .unwrap()
        .insert(b"wide\0".to_vec(), (4104, 8));
    let rt = Runtime::new(f.clone());
    for (host, size) in [(91, 4usize), (93, 8usize)] {
        let mut output = 123;
        assert_eq!(
            unsafe { query(&k, || Ok(&rt), host, &mut output, |_, n| n) },
            0
        );
        assert_eq!(output, size);
        assert_eq!(transfer(&k, &rt, host, true, 1, 1234, 1, size - 1), 0);
        assert_eq!(transfer(&k, &rt, host, false, 2, 0, 0, size), 0);
        assert_eq!(transfer(&k, &rt, host, false, 2, 1234, 1, size), 1);
    }
    assert_eq!(transfer(&k, &rt, 91, true, 1, 1234, 5, 0), 1);
    assert_eq!(transfer(&k, &rt, 93, true, 1, 1234, 8, 0), 0);
}
#[test]
fn symbol_u64_lookup_error_precedence() {
    let k = KernelRuntime::new();
    let t = ready_mixed(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    for host in [0, 92] {
        assert_eq!(transfer(&k, &rt, host, true, 1, 1234, 5, 0), 1);
        assert_eq!(transfer(&k, &rt, host, true, 1, 1234, 4, 0), 13);
    }
    k.registry.fail(t, 2);
    assert_eq!(transfer(&k, &rt, 93, true, 1, 1234, 5, 0), 1);
    assert_eq!(transfer(&k, &rt, 93, true, 1, 1234, 4, 0), 2);
    assert_eq!(f.0.loads.load(SeqCst), 0);
}
#[test]
fn symbol_u64_binding_validation() {
    for (pointer, size) in [(4100, 8), (4104, 4), (u64::MAX - 7, 8)] {
        let k = KernelRuntime::new();
        ready_mixed(&k);
        let f = Fake::default();
        f.0.global_overrides
            .lock()
            .unwrap()
            .insert(b"wide\0".to_vec(), (pointer, size));
        let rt = Runtime::new(f.clone());
        let mut output = 123;
        assert_eq!(address(&k, &rt, 93, &mut output), 801);
        assert_eq!(output, 123);
        assert_eq!(address(&k, &rt, 91, &mut output), 801);
        assert_eq!(f.0.loads.load(SeqCst), 1);
    }
}
fn address(k: &KernelRuntime, rt: &Runtime<Fake>, host: usize, out: &mut usize) -> i32 {
    unsafe { query(k, || Ok(rt), host, out, |p, _| p as usize) }
}
#[allow(clippy::too_many_arguments)] // Table-driven adapter for the public C arguments.
fn transfer(
    k: &KernelRuntime,
    rt: &Runtime<Fake>,
    host: usize,
    to: bool,
    kind: i32,
    data: usize,
    count: usize,
    offset: usize,
) -> i32 {
    unsafe {
        copy(
            k,
            || Ok(rt),
            host,
            Transfer {
                to,
                kind,
                data: data as *mut c_void,
                count,
                offset,
            },
        )
    }
}
#[test]
fn symbol_query_outputs_unchanged() {
    let k = KernelRuntime::new();
    ready_globals(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    let mut out = 123usize;
    for host in [0, 92, usize::MAX] {
        assert_eq!(address(&k, &rt, host, &mut out), 13);
        assert_eq!(out, 123);
    }
    assert_eq!(f.0.loads.load(SeqCst), 0);
    f.0.global_prepare_error.store(35, SeqCst);
    assert_eq!(address(&k, &rt, 91, &mut out), 35);
    assert_eq!(out, 123);
    f.0.global_prepare_error.store(0, SeqCst);
    assert_eq!(address(&k, &rt, 91, &mut out), 0);
    assert_eq!(out, 4096);
    let mut size = 0;
    assert_eq!(unsafe { query(&k, || Ok(&rt), 91, &mut size, |_, n| n) }, 0);
    assert_eq!(size, 4);
    let k = KernelRuntime::new();
    ready_globals(&k);
    f.0.global_error.store(500, SeqCst);
    assert_eq!(address(&k, &rt, 91, &mut out), 801);
    assert_eq!(out, 4096);
    let mut size = 123;
    assert_eq!(
        unsafe { query(&k, || Ok(&rt), 91, &mut size, |_, n| n) },
        801
    );
    assert_eq!(size, 123);
}
#[test]
fn symbol_combined_error_precedence() {
    let k = KernelRuntime::new();
    let t = ready_globals(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    k.registry.fail(t, 2);
    assert_eq!(
        transfer(&k, &rt, 92, true, 2, 0, usize::MAX, usize::MAX),
        21
    );
    assert_eq!(transfer(&k, &rt, 92, true, 4, 0, 1, 0), 801);
    assert_eq!(transfer(&k, &rt, 91, true, 1, 8, 2, 3), 1);
    assert_eq!(transfer(&k, &rt, 91, true, 1, 8, 1, 0), 2);
    assert_eq!(
        unsafe { query(&k, || Ok(&rt), 91, std::ptr::null_mut::<usize>(), |_, n| n) },
        1
    );
    assert_eq!(f.0.loads.load(SeqCst), 0);
    // Output/pointer preflight must not even initialize a provider.
    assert_eq!(
        unsafe {
            query::<Fake, usize>(
                &k,
                || panic!("provider"),
                91,
                std::ptr::null_mut(),
                |_, n| n,
            )
        },
        1
    );
}
#[test]
fn symbol_copy_bounds_and_zero() {
    let k = KernelRuntime::new();
    ready_globals(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    for (to, kind) in [(true, 1), (true, 3), (false, 2), (false, 3)] {
        for offset in 0..=4 {
            assert_eq!(transfer(&k, &rt, 91, to, kind, 0, 0, offset), 0);
        }
        assert_eq!(transfer(&k, &rt, 92, to, kind, 0, 0, 4), 13);
        for (p, n, o) in [
            (0, 1, 0),
            (8, 2, 3),
            (8, 0, 5),
            (8, 1, usize::MAX),
            (usize::MAX, 1, 0),
        ] {
            assert_eq!(transfer(&k, &rt, 91, to, kind, p, n, o), 1);
        }
        assert!(f.0.copies.lock().unwrap().is_empty());
    }
    assert_eq!(f.0.loads.load(SeqCst), 1);
    assert_eq!(transfer(&k, &rt, 91, true, 1, 8192, 2, 1), 0);
    assert_eq!(transfer(&k, &rt, 91, false, 2, 8192, 1, 3), 0);
    assert_eq!(transfer(&k, &rt, 91, true, 3, 8192, 4, 0), 0);
    assert_eq!(transfer(&k, &rt, 91, false, 3, 8192, 4, 0), 0);
    assert_eq!(
        *f.0.copies.lock().unwrap(),
        [
            (1, 4097, 8192, 2),
            (2, 8192, 4099, 1),
            (3, 4096, 8192, 4),
            (3, 8192, 4096, 4)
        ]
    );
}
#[test]
fn symbol_copy_driver_errors() {
    for error in [1, 400, 709] {
        let k = KernelRuntime::new();
        ready_globals(&k);
        let f = Fake::default();
        let rt = Runtime::new(f.clone());
        f.0.copy_error.store(error, SeqCst);
        assert_eq!(transfer(&k, &rt, 91, true, 1, 8192, 1, 0), error);
        f.0.copy_error.store(0, SeqCst);
        let expected = if error == 1 { 0 } else { error };
        assert_eq!(transfer(&k, &rt, 91, true, 1, 8192, 1, 0), expected);
        assert_eq!(unsafe { launch(&k, &rt) }, expected);
    }
}
#[test]
fn symbol_unregister_before_context() {
    let k = KernelRuntime::new();
    let t = ready_globals(&k);
    let f = Fake::default();
    let rt = Runtime::new(f.clone());
    let mut out = 0;
    let code = unsafe {
        query(
            &k,
            || {
                k.registry.retire(t).unwrap();
                k.drain(&f, 77).unwrap();
                Ok(&rt)
            },
            91,
            &mut out,
            |p, _| p,
        )
    };
    assert_eq!(code, 0);
    assert_eq!(out, 4096);
    assert_eq!(f.0.unloads.load(SeqCst), 0);
    k.drain(&f, 77).unwrap();
    assert_eq!(f.0.unloads.load(SeqCst), 1);
    assert_eq!(address(&k, &rt, 91, &mut 0), 13);
}
#[test]
fn symbol_unregister_during_copy() {
    let k = Arc::new(KernelRuntime::new());
    let t = ready_globals(&k);
    let f = Fake::default();
    let rt = Arc::new(Runtime::new(f.clone()));
    let a = Arc::new(Barrier::new(2));
    let b = Arc::new(Barrier::new(2));
    *f.0.copy_barrier.lock().unwrap() = Some((a.clone(), b.clone()));
    let (kk, rr) = (k.clone(), rt.clone());
    let worker = std::thread::spawn(move || transfer(&kk, &rr, 91, true, 1, 8192, 1, 0));
    a.wait();
    k.registry.retire(t).unwrap();
    k.drain(&f, 77).unwrap();
    assert_eq!(f.0.unloads.load(SeqCst), 0);
    b.wait();
    assert_eq!(worker.join().unwrap(), 0);
    k.drain(&f, 77).unwrap();
    assert_eq!(f.0.unloads.load(SeqCst), 1);
}

#[test]
fn symbol_export_preflight_and_tls() {
    crate::cudaGetLastError();
    let mut out = 8192usize as *mut c_void;
    assert_eq!(
        unsafe { crate::cudaGetSymbolAddress(&mut out, std::ptr::null()) },
        13
    );
    assert_eq!(out as usize, 8192);
    assert_eq!(crate::cudaPeekAtLastError(), 13);
    assert_eq!(
        unsafe { crate::cudaMemcpyToSymbol(std::ptr::null(), std::ptr::null(), 0, 0, 0) },
        21
    );
    assert_eq!(crate::cudaGetLastError(), 21);
    assert_eq!(
        unsafe { crate::cudaMemcpyFromSymbol(std::ptr::null_mut(), std::ptr::null(), 0, 0, 4) },
        801
    );
    assert_eq!(crate::cudaPeekAtLastError(), 801);
    assert_eq!(
        unsafe { crate::cudaMemcpy(std::ptr::null_mut(), std::ptr::null(), 0, 1) },
        0
    );
    assert_eq!(crate::cudaGetLastError(), 801);
    assert_eq!(
        unsafe { std::ffi::CStr::from_ptr(crate::cudaGetErrorName(13)) }.to_bytes(),
        b"cudaErrorInvalidSymbol"
    );
    let _address: unsafe extern "system" fn(*mut *mut c_void, *const c_void) -> i32 =
        crate::cudaGetSymbolAddress;
    let _size: unsafe extern "system" fn(*mut usize, *const c_void) -> i32 =
        crate::cudaGetSymbolSize;
    let _to: unsafe extern "system" fn(*const c_void, *const c_void, usize, usize, i32) -> i32 =
        crate::cudaMemcpyToSymbol;
    let _from: unsafe extern "system" fn(*mut c_void, *const c_void, usize, usize, i32) -> i32 =
        crate::cudaMemcpyFromSymbol;
}

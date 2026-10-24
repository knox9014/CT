//! CPU-only compiler registration. No platform/Driver imports or native cleanup.
use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Mutex, OnceLock};

pub type Token = usize;
pub type RegistrationId = u64;
#[repr(C)]
pub struct Wrapper {
    pub magic: u32,
    pub version: u32,
    pub data: usize,
    pub extra: usize,
}
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct FunctionMetadata {
    pub thread_limit: i32,
    pub optional: [usize; 5],
}
#[derive(Clone, Copy)]
pub struct Limits {
    pub live: usize,
    pub lifetime: usize,
    pub functions: usize,
    pub mappings: usize,
    pub names: usize,
    pub raw_bytes: usize,
    pub variables: usize,
    pub variable_mappings: usize,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            live: 64,
            lifetime: 1024,
            functions: 512,
            mappings: 4096,
            names: 1024,
            raw_bytes: 64 * 1024 * 1024,
            variables: 256,
            variable_mappings: 2048,
        }
    }
}
pub struct Image {
    pub contents: crate::registration_images::OwnedImages,
    budget: Arc<AtomicUsize>,
}
impl Drop for Image {
    fn drop(&mut self) {
        debug_assert_eq!(
            self.contents.raw_bytes,
            self.contents.primary.len()
                + self.contents.prelinked.iter().map(Vec::len).sum::<usize>()
        );
        self.budget.fetch_sub(self.contents.raw_bytes, SeqCst);
    }
}
pub struct RegistrationData {
    pub id: RegistrationId,
    pub image: Image,
    pub retired: AtomicBool,
    pub active: AtomicUsize,
    pub variables: OnceLock<Vec<crate::registration_variables::Variable>>,
}
pub struct LaunchLease {
    pub data: Arc<RegistrationData>,
    pub(crate) symbol: Arc<Vec<u8>>,
}
impl LaunchLease {
    pub fn image(&self) -> Result<&[u8], i32> {
        let variables = self.data.variables.get().ok_or(98)?;
        if self.data.image.contents.version != 1
            || variables.iter().any(|v| {
                v.metadata.size != 4
                    || v.metadata.external != 0
                    || v.metadata.constant != 0
                    || v.metadata.global != 0
            })
        {
            return Err(801);
        }
        Ok(&self.data.image.contents.primary)
    }
    pub fn variables(&self) -> &[crate::registration_variables::Variable] {
        self.data.variables.get().map(Vec::as_slice).unwrap_or(&[])
    }
    pub fn symbol(&self) -> &[u8] {
        &self.symbol
    }
    pub fn retired(&self) -> bool {
        self.data.retired.load(SeqCst)
    }
}
impl Drop for LaunchLease {
    fn drop(&mut self) {
        self.data.active.fetch_sub(1, SeqCst);
    }
}
enum Status {
    Building,
    Ready,
    Failed(i32),
    Retired,
}
struct Mapping {
    host: usize,
    symbol: Arc<Vec<u8>>,
    metadata: FunctionMetadata,
    error: i32,
}
struct Record {
    token: Box<u8>,
    state: Status,
    data: Option<Arc<RegistrationData>>,
    functions: Vec<Mapping>,
    variables: Vec<crate::registration_variables::Variable>,
    variable_count: usize,
}
impl Record {
    fn identity(&self) -> Token {
        (&*self.token as *const u8) as usize
    }
}
struct Inner {
    records: Vec<Record>,
    live: usize,
    mappings: usize,
    variable_mappings: usize,
}
pub struct Registry {
    inner: Mutex<Inner>,
    limits: Limits,
    raw_bytes: Arc<AtomicUsize>,
}

pub(crate) fn reserve<T>(v: &mut Vec<T>, count: usize) -> Result<(), i32> {
    #[cfg(test)]
    if FAIL_RESERVATION.get() {
        return Err(2);
    }
    v.try_reserve_exact(count).map_err(|_| 2)
}
#[cfg(test)]
thread_local! { pub static FAIL_RESERVATION: std::cell::Cell<bool> = const {std::cell::Cell::new(false)}; }

pub unsafe fn copy_name(name: *const u8, limit: usize) -> Result<Vec<u8>, i32> {
    if name.is_null() {
        return Err(1);
    }
    let mut out = Vec::new();
    reserve(&mut out, limit + 1)?;
    for i in 0..=limit {
        let byte = unsafe { name.add(i).read() };
        if byte == 0 {
            if out.is_empty() {
                return Err(1);
            }
            out.push(0);
            return Ok(out);
        }
        if i == limit {
            return Err(801);
        }
        if !byte.is_ascii() {
            return Err(1);
        }
        out.push(byte);
    }
    Err(801)
}
impl Registry {
    pub fn new() -> Self {
        Self::with_limits(Limits::default())
    }
    pub fn with_limits(limits: Limits) -> Self {
        Self {
            inner: Mutex::new(Inner {
                records: Vec::new(),
                live: 0,
                mappings: 0,
                variable_mappings: 0,
            }),
            limits,
            raw_bytes: Arc::new(AtomicUsize::new(0)),
        }
    }
    pub unsafe fn register(&self, wrapper: *const c_void) -> Result<Token, i32> {
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        if inner.live >= self.limits.live || inner.records.len() >= self.limits.lifetime {
            return Err(801);
        }
        let remaining = self
            .limits
            .raw_bytes
            .saturating_sub(self.raw_bytes.load(SeqCst));
        let contents = unsafe { crate::registration_images::copy_images(wrapper, remaining) }?;
        let size = contents.raw_bytes;
        reserve(&mut inner.records, 1)?;
        let id = inner.records.len() as u64 + 1;
        let mut functions = Vec::new();
        reserve(&mut functions, self.limits.functions)?;
        let token = Box::new(0u8);
        let identity = (&*token as *const u8) as usize;
        let data = Arc::new(RegistrationData {
            id,
            image: Image {
                contents,
                budget: self.raw_bytes.clone(),
            },
            retired: AtomicBool::new(false),
            active: AtomicUsize::new(0),
            variables: OnceLock::new(),
        });
        self.raw_bytes.fetch_add(size, SeqCst);
        inner.records.push(Record {
            token,
            state: Status::Building,
            data: Some(data),
            functions,
            variables: Vec::new(),
            variable_count: 0,
        });
        inner.live += 1;
        Ok(identity)
    }
    pub fn fail(&self, token: Token, code: i32) {
        if let Ok(mut inner) = self.inner.lock() {
            if let Some(r) = inner.records.iter_mut().find(|r| r.identity() == token) {
                if matches!(r.state, Status::Building | Status::Ready) {
                    r.state = Status::Failed(code);
                }
            }
        }
    }
    // Reject terminal tokens before inspecting untrusted callback payloads.
    pub fn function_state(&self, token: Token) -> Result<(), i32> {
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let r = inner
            .records
            .iter_mut()
            .find(|r| r.identity() == token)
            .ok_or(98)?;
        match r.state {
            Status::Building => Ok(()),
            Status::Failed(code) => Err(code),
            Status::Retired => Err(98),
            Status::Ready => {
                r.state = Status::Failed(1);
                Err(1)
            }
        }
    }
    pub fn fail_mapping(&self, token: Token, host: usize, code: i32) -> i32 {
        let Ok(mut inner) = self.inner.lock() else {
            return 999;
        };
        let Some(index) = inner.records.iter().position(|r| r.identity() == token) else {
            return 98;
        };
        let capacity = inner.mappings < self.limits.mappings;
        let r = &mut inner.records[index];
        // Recheck after payload preparation, which runs outside the registry lock.
        let code = match r.state {
            Status::Retired => return 98,
            Status::Failed(first) => return first,
            Status::Ready => 1,
            Status::Building => code,
        };
        r.state = Status::Failed(code);
        if host == 0 {
            return code;
        }
        if let Some(mapping) = r.functions.iter_mut().find(|m| m.host == host) {
            mapping.error = code;
            return code;
        }
        if !capacity || r.functions.len() >= self.limits.functions {
            return code;
        }
        // Failure association storage was reserved before publishing the token.
        r.functions.push(Mapping {
            host,
            symbol: Arc::new(Vec::new()),
            metadata: FunctionMetadata {
                thread_limit: -1,
                optional: [0; 5],
            },
            error: code,
        });
        inner.mappings += 1;
        code
    }
    pub unsafe fn function(
        &self,
        token: Token,
        host: usize,
        symbol: *const u8,
        metadata: FunctionMetadata,
    ) -> Result<(), i32> {
        self.function_state(token)?;
        let prepared = (|| {
            if host == 0 {
                return Err(1);
            }
            if metadata.thread_limit != -1 || metadata.optional != [0; 5] {
                return Err(801);
            }
            unsafe { copy_name(symbol, self.limits.names) }
        })();
        let symbol = match prepared {
            Ok(s) => s,
            Err(code) => {
                return Err(self.fail_mapping(token, host, code));
            }
        };
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let index = inner
            .records
            .iter()
            .position(|r| r.identity() == token)
            .ok_or(98)?;
        match inner.records[index].state {
            Status::Building => {}
            Status::Failed(code) => return Err(code),
            Status::Retired => return Err(98),
            Status::Ready => {
                inner.records[index].state = Status::Failed(1);
                return Err(1);
            }
        }
        let r = &mut inner.records[index];
        if let Some(m) = r.functions.iter_mut().find(|m| m.host == host) {
            if *m.symbol == symbol && m.metadata == metadata && m.error == 0 {
                return Ok(());
            }
            m.error = 98;
            return Err(98);
        }
        if r.functions.len() >= self.limits.functions || inner.mappings >= self.limits.mappings {
            inner.records[index].state = Status::Failed(801);
            return Err(801);
        }
        let r = &mut inner.records[index];
        if let Err(code) = reserve(&mut r.functions, 1) {
            r.state = Status::Failed(code);
            return Err(code);
        }
        r.functions.push(Mapping {
            host,
            symbol: Arc::new(symbol),
            metadata,
            error: 0,
        });
        inner.mappings += 1;
        Ok(())
    }
    pub unsafe fn variable(
        &self,
        token: Token,
        host: usize,
        address: *const u8,
        name: *const u8,
        metadata: crate::registration_variables::VariableMetadata,
    ) -> Result<(), i32> {
        self.function_state(token)?;
        let variable = match unsafe {
            crate::registration_variables::prepare(host, address, name, metadata, self.limits.names)
        } {
            Ok(v) => v,
            Err(code) => return Err(self.fail_mapping(token, 0, code)),
        };
        #[cfg(test)]
        crate::registration_variables::PREPARE_BARRIER.with(|v| {
            if let Some((a, b)) = v.borrow_mut().take() {
                a.wait();
                b.wait();
            }
        });
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let index = inner
            .records
            .iter()
            .position(|r| r.identity() == token)
            .ok_or(98)?;
        match inner.records[index].state {
            Status::Building => {}
            Status::Failed(c) => return Err(c),
            Status::Retired => return Err(98),
            Status::Ready => {
                inner.records[index].state = Status::Failed(1);
                return Err(1);
            }
        }
        let r = &mut inner.records[index];
        if let Some(old) = r.variables.iter().find(|v| v.host == host) {
            if old.address == variable.address
                && old.name == variable.name
                && old.metadata == variable.metadata
            {
                return Ok(());
            }
            r.state = Status::Failed(1);
            return Err(1);
        }
        if r.variables.len() >= self.limits.variables
            || inner.variable_mappings >= self.limits.variable_mappings
        {
            inner.records[index].state = Status::Failed(801);
            return Err(801);
        }
        let r = &mut inner.records[index];
        if let Err(c) = reserve(&mut r.variables, 1) {
            r.state = Status::Failed(c);
            return Err(c);
        }
        r.variables.push(variable);
        r.variable_count += 1;
        inner.variable_mappings += 1;
        Ok(())
    }
    pub fn end(&self, token: Token) -> Result<(), i32> {
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let r = inner
            .records
            .iter_mut()
            .find(|r| r.identity() == token)
            .ok_or(98)?;
        match r.state {
            Status::Building => {
                let data = r.data.as_ref().ok_or(98)?;
                if data
                    .variables
                    .set(std::mem::take(&mut r.variables))
                    .is_err()
                {
                    r.state = Status::Failed(999);
                    return Err(999);
                }
                r.state = Status::Ready;
                Ok(())
            }
            Status::Ready => Ok(()),
            Status::Failed(c) => Err(c),
            Status::Retired => Err(98),
        }
    }
    pub fn retire(&self, token: Token) -> Result<(), i32> {
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let r = inner
            .records
            .iter_mut()
            .find(|r| r.identity() == token)
            .ok_or(98)?;
        if matches!(r.state, Status::Retired) {
            return Ok(());
        }
        r.state = Status::Retired;
        if let Some(data) = r.data.take() {
            data.retired.store(true, SeqCst);
        }
        let count = r.functions.len();
        r.functions = Vec::new();
        let variable_count = r.variable_count;
        r.variable_count = 0;
        r.variables = Vec::new();
        inner.variable_mappings -= variable_count;
        inner.live -= 1;
        inner.mappings -= count;
        Ok(())
    }
    pub fn lease(&self, host: usize) -> Result<LaunchLease, i32> {
        let inner = self.inner.lock().map_err(|_| 999)?;
        let mut found = None;
        for r in &inner.records {
            if matches!(r.state, Status::Retired) {
                continue;
            }
            if let Some(m) = r.functions.iter().find(|m| m.host == host) {
                if found.is_some() {
                    return Err(98);
                }
                found = Some((r, m));
            }
        }
        let (r, m) = found.ok_or(98)?;
        match r.state {
            Status::Ready => {}
            Status::Failed(c) => return Err(c),
            _ => return Err(98),
        }
        if m.error != 0 {
            return Err(m.error);
        }
        let data = r.data.as_ref().ok_or(98)?.clone();
        data.active.fetch_add(1, SeqCst);
        Ok(LaunchLease {
            data,
            symbol: m.symbol.clone(),
        })
    }
}

//! CPU-only compiler registration. No platform/Driver imports or native cleanup.
use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering::SeqCst};
use std::sync::{Arc, Mutex};

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
        }
    }
}
pub struct Image {
    pub bytes: Vec<u8>,
    budget: Arc<AtomicUsize>,
}
impl Drop for Image {
    fn drop(&mut self) {
        self.budget.fetch_sub(self.bytes.len(), SeqCst);
    }
}
pub struct RegistrationData {
    pub id: RegistrationId,
    pub image: Image,
    pub retired: AtomicBool,
    pub active: AtomicUsize,
}
pub struct LaunchLease {
    pub data: Arc<RegistrationData>,
    pub(crate) symbol: Arc<Vec<u8>>,
}
impl LaunchLease {
    pub fn image(&self) -> &[u8] {
        &self.data.image.bytes
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
}
pub struct Registry {
    inner: Mutex<Inner>,
    limits: Limits,
    raw_bytes: Arc<AtomicUsize>,
}

fn reserve<T>(v: &mut Vec<T>, count: usize) -> Result<(), i32> {
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
            }),
            limits,
            raw_bytes: Arc::new(AtomicUsize::new(0)),
        }
    }
    pub unsafe fn register(&self, wrapper: *const c_void) -> Result<Token, i32> {
        if wrapper.is_null() {
            return Err(1);
        }
        let w = unsafe { wrapper.cast::<Wrapper>().read_unaligned() };
        if w.magic != 0x466243b1 || w.data == 0 {
            return Err(1);
        }
        if w.version != 1 || w.extra != 0 {
            return Err(801);
        }
        let map = |e| match e {
            ct_fatbin::Error::Invalid => 218,
            ct_fatbin::Error::Unsupported => 801,
            ct_fatbin::Error::Allocation => 2,
        };
        let header = unsafe { std::slice::from_raw_parts(w.data as *const u8, 16) };
        let size = ct_fatbin::image_size(header).map_err(map)?;
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        if inner.live >= self.limits.live
            || inner.records.len() >= self.limits.lifetime
            || size
                > self
                    .limits
                    .raw_bytes
                    .saturating_sub(self.raw_bytes.load(SeqCst))
        {
            return Err(801);
        }
        reserve(&mut inner.records, 1)?;
        let mut bytes = Vec::new();
        reserve(&mut bytes, size)?;
        bytes.extend_from_slice(unsafe { std::slice::from_raw_parts(w.data as *const u8, size) });
        ct_fatbin::extract_candidates(&bytes).map_err(map)?;
        let id = inner.records.len() as u64 + 1;
        let token = Box::new(0u8);
        let identity = (&*token as *const u8) as usize;
        let data = Arc::new(RegistrationData {
            id,
            image: Image {
                bytes,
                budget: self.raw_bytes.clone(),
            },
            retired: AtomicBool::new(false),
            active: AtomicUsize::new(0),
        });
        self.raw_bytes.fetch_add(size, SeqCst);
        inner.records.push(Record {
            token,
            state: Status::Building,
            data: Some(data),
            functions: Vec::new(),
        });
        inner.live += 1;
        Ok(identity)
    }
    pub fn fail(&self, token: Token, code: i32) {
        if let Ok(mut inner) = self.inner.lock() {
            if let Some(r) = inner.records.iter_mut().find(|r| r.identity() == token) {
                if !matches!(r.state, Status::Retired) {
                    r.state = Status::Failed(code);
                }
            }
        }
    }
    pub unsafe fn function(
        &self,
        token: Token,
        host: usize,
        symbol: *const u8,
        metadata: FunctionMetadata,
    ) -> Result<(), i32> {
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
                self.fail(token, code);
                return Err(code);
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
    pub fn end(&self, token: Token) -> Result<(), i32> {
        let mut inner = self.inner.lock().map_err(|_| 999)?;
        let r = inner
            .records
            .iter_mut()
            .find(|r| r.identity() == token)
            .ok_or(98)?;
        match r.state {
            Status::Building => {
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
        r.functions.clear();
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

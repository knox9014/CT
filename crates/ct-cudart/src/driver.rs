pub type Context = usize;
pub type DriverResult<T> = Result<T, i32>;
pub trait DriverCalls: Send + Sync {
    fn init(&self) -> i32;
    fn count(&self) -> DriverResult<i32>;
    fn device(&self, ordinal: i32) -> DriverResult<i32>;
    // Preparation returns Runtime-domain errors; the query returns raw Driver errors.
    fn prepare_device_attribute(&self) -> Result<(), i32> {
        Ok(())
    }
    fn device_attribute(&self, _attribute: i32, _device: i32) -> DriverResult<i32> {
        Err(801)
    }
    fn prepare_host(&self) -> Result<(), i32> {
        Ok(())
    }
    fn allocate_host(&self, _size: usize) -> DriverResult<usize> {
        Err(801)
    }
    fn free_host(&self, _pointer: usize) -> i32 {
        801
    }
    fn prepare_events(&self) -> Result<(), i32> {
        Ok(())
    }
    fn event_create(&self) -> DriverResult<usize> {
        Err(801)
    }
    fn event_record(&self, _event: usize) -> i32 {
        801
    }
    fn event_synchronize(&self, _event: usize) -> i32 {
        801
    }
    fn event_destroy(&self, _event: usize) -> i32 {
        801
    }
    fn event_elapsed(&self, _start: usize, _end: usize) -> DriverResult<f32> {
        Err(801)
    }
    fn current(&self) -> DriverResult<Option<Context>>;
    fn context_device(&self) -> DriverResult<i32>;
    fn retain(&self, device: i32) -> DriverResult<Context>;
    fn release(&self, device: i32) -> i32;
    fn set_current(&self, context: Context) -> i32;
    fn synchronize(&self) -> i32;
    fn allocate(&self, bytes: usize) -> DriverResult<u64>;
    fn free(&self, pointer: u64) -> i32;
    unsafe fn copy_htod(&self, dst: u64, src: *const u8, bytes: usize) -> i32;
    unsafe fn copy_dtoh(&self, dst: *mut u8, src: u64, bytes: usize) -> i32;
    fn copy_dtod(&self, dst: u64, src: u64, bytes: usize) -> i32;
    fn fill8(&self, dst: u64, value: u8, bytes: usize) -> i32;
}

pub struct DriverBridge {
    #[cfg(windows)]
    pub(crate) _owned: crate::platform::windows::Owned,
    table: [usize; 15],
    attribute: std::sync::OnceLock<Result<usize, i32>>,
    host: std::sync::OnceLock<Result<[usize; 2], i32>>,
    events: std::sync::OnceLock<Result<[usize; 5], i32>>,
    pub(crate) kernel: std::sync::OnceLock<Result<[usize; 5], i32>>,
    pub(crate) global: std::sync::OnceLock<Result<usize, i32>>,
}
impl DriverBridge {
    fn event_table(&self) -> Result<&[usize; 5], i32> {
        crate::cached(&self.events, || {
            #[cfg(windows)]
            {
                crate::platform::resolve_events(
                    &crate::platform::windows::WinPlatform,
                    &self._owned,
                )
            }
            #[cfg(not(windows))]
            {
                Err(35)
            }
        })
    }
    fn host_table(&self) -> Result<&[usize; 2], i32> {
        crate::cached(&self.host, || {
            #[cfg(windows)]
            {
                crate::platform::resolve_host(&crate::platform::windows::WinPlatform, &self._owned)
            }
            #[cfg(not(windows))]
            {
                Err(35)
            }
        })
    }

    fn attribute_function(&self) -> Result<usize, i32> {
        crate::cached(&self.attribute, || {
            #[cfg(windows)]
            {
                crate::platform::resolve_device_attribute(
                    &crate::platform::windows::WinPlatform,
                    &self._owned,
                )
            }
            #[cfg(not(windows))]
            {
                Err(35)
            }
        })
        .copied()
    }

    pub fn open() -> Result<Self, i32> {
        #[cfg(windows)]
        {
            let (owned, table) =
                crate::platform::bootstrap(&crate::platform::windows::WinPlatform)?;
            Ok(Self {
                _owned: owned,
                table,
                attribute: std::sync::OnceLock::new(),
                host: std::sync::OnceLock::new(),
                events: std::sync::OnceLock::new(),
                kernel: std::sync::OnceLock::new(),
                global: std::sync::OnceLock::new(),
            })
        }
        #[cfg(not(windows))]
        {
            Err(35)
        }
    }
}
fn result(code: i32) -> Result<(), i32> {
    if code == 0 {
        Ok(())
    } else {
        Err(code)
    }
}
// Only a fully validated and pinned table can construct this bridge.
macro_rules! call {
    ($s:expr,$i:expr,$ty:ty,$($arg:expr),*) => {{
        let function: $ty = unsafe { std::mem::transmute($s.table[$i]) };
        unsafe { function($($arg),*) }
    }};
}
impl DriverCalls for DriverBridge {
    fn prepare_events(&self) -> Result<(), i32> {
        self.event_table().map(|_| ())
    }
    fn event_create(&self) -> DriverResult<usize> {
        let t = self.event_table().map_err(|_| 999)?;
        let f: unsafe extern "system" fn(*mut usize, u32) -> i32 =
            unsafe { std::mem::transmute(t[0]) };
        let mut out = 0;
        result(unsafe { f(&mut out, 0) })?;
        if out == 0 {
            Err(999)
        } else {
            Ok(out)
        }
    }
    fn event_record(&self, event: usize) -> i32 {
        let t = match self.event_table() {
            Ok(t) => t,
            Err(_) => return 999,
        };
        let f: unsafe extern "system" fn(usize, usize) -> i32 =
            unsafe { std::mem::transmute(t[1]) };
        unsafe { f(event, 0) }
    }
    fn event_synchronize(&self, event: usize) -> i32 {
        let t = match self.event_table() {
            Ok(t) => t,
            Err(_) => return 999,
        };
        let f: unsafe extern "system" fn(usize) -> i32 = unsafe { std::mem::transmute(t[2]) };
        unsafe { f(event) }
    }
    fn event_destroy(&self, event: usize) -> i32 {
        let t = match self.event_table() {
            Ok(t) => t,
            Err(_) => return 999,
        };
        let f: unsafe extern "system" fn(usize) -> i32 = unsafe { std::mem::transmute(t[3]) };
        unsafe { f(event) }
    }
    fn event_elapsed(&self, start: usize, end: usize) -> DriverResult<f32> {
        let t = self.event_table().map_err(|_| 999)?;
        let f: unsafe extern "system" fn(*mut f32, usize, usize) -> i32 =
            unsafe { std::mem::transmute(t[4]) };
        let mut out = 0.0;
        result(unsafe { f(&mut out, start, end) })?;
        Ok(out)
    }

    fn prepare_host(&self) -> Result<(), i32> {
        self.host_table().map(|_| ())
    }
    fn allocate_host(&self, size: usize) -> DriverResult<usize> {
        let table = self.host_table().map_err(|_| 999)?;
        let f: unsafe extern "system" fn(*mut usize, usize, u32) -> i32 =
            unsafe { std::mem::transmute(table[0]) };
        let mut out = 0;
        result(unsafe { f(&mut out, size, 0) })?;
        if out == 0 {
            Err(999)
        } else {
            Ok(out)
        }
    }
    fn free_host(&self, pointer: usize) -> i32 {
        let table = match self.host_table() {
            Ok(t) => t,
            Err(_) => return 999,
        };
        let f: unsafe extern "system" fn(usize) -> i32 = unsafe { std::mem::transmute(table[1]) };
        unsafe { f(pointer) }
    }

    fn prepare_device_attribute(&self) -> Result<(), i32> {
        self.attribute_function().map(|_| ())
    }
    fn device_attribute(&self, attribute: i32, device: i32) -> DriverResult<i32> {
        let address = self.attribute_function()?;
        let function: unsafe extern "system" fn(*mut i32, i32, i32) -> i32 =
            unsafe { std::mem::transmute(address) };
        let mut out = 0;
        result(unsafe { function(&mut out, attribute, device) })?;
        Ok(out)
    }

    fn init(&self) -> i32 {
        call!(self, 0, unsafe extern "system" fn(u32) -> i32, 0)
    }
    fn count(&self) -> DriverResult<i32> {
        let mut out = 0;
        result(call!(
            self,
            1,
            unsafe extern "system" fn(*mut i32) -> i32,
            &mut out
        ))?;
        Ok(out)
    }
    fn device(&self, ordinal: i32) -> DriverResult<i32> {
        let mut out = 0;
        result(call!(
            self,
            2,
            unsafe extern "system" fn(*mut i32, i32) -> i32,
            &mut out,
            ordinal
        ))?;
        Ok(out)
    }
    fn current(&self) -> DriverResult<Option<Context>> {
        let mut out = 0;
        result(call!(
            self,
            3,
            unsafe extern "system" fn(*mut usize) -> i32,
            &mut out
        ))?;
        Ok((out != 0).then_some(out))
    }
    fn context_device(&self) -> DriverResult<i32> {
        let mut out = 0;
        result(call!(
            self,
            4,
            unsafe extern "system" fn(*mut i32) -> i32,
            &mut out
        ))?;
        Ok(out)
    }
    fn set_current(&self, context: Context) -> i32 {
        call!(self, 5, unsafe extern "system" fn(usize) -> i32, context)
    }
    fn retain(&self, device: i32) -> DriverResult<Context> {
        let mut out = 0;
        result(call!(
            self,
            6,
            unsafe extern "system" fn(*mut usize, i32) -> i32,
            &mut out,
            device
        ))?;
        Ok(out)
    }
    fn release(&self, device: i32) -> i32 {
        call!(self, 7, unsafe extern "system" fn(i32) -> i32, device)
    }
    fn synchronize(&self) -> i32 {
        call!(self, 8, unsafe extern "system" fn() -> i32,)
    }
    fn allocate(&self, bytes: usize) -> DriverResult<u64> {
        let mut out = 0;
        result(call!(
            self,
            9,
            unsafe extern "system" fn(*mut u64, usize) -> i32,
            &mut out,
            bytes
        ))?;
        Ok(out)
    }
    fn free(&self, pointer: u64) -> i32 {
        call!(self, 10, unsafe extern "system" fn(u64) -> i32, pointer)
    }
    unsafe fn copy_htod(&self, dst: u64, src: *const u8, bytes: usize) -> i32 {
        call!(
            self,
            11,
            unsafe extern "system" fn(u64, *const u8, usize) -> i32,
            dst,
            src,
            bytes
        )
    }
    unsafe fn copy_dtoh(&self, dst: *mut u8, src: u64, bytes: usize) -> i32 {
        call!(
            self,
            12,
            unsafe extern "system" fn(*mut u8, u64, usize) -> i32,
            dst,
            src,
            bytes
        )
    }
    fn copy_dtod(&self, dst: u64, src: u64, bytes: usize) -> i32 {
        call!(
            self,
            13,
            unsafe extern "system" fn(u64, u64, usize) -> i32,
            dst,
            src,
            bytes
        )
    }
    fn fill8(&self, dst: u64, value: u8, bytes: usize) -> i32 {
        call!(
            self,
            14,
            unsafe extern "system" fn(u64, u8, usize) -> i32,
            dst,
            value,
            bytes
        )
    }
}

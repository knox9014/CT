pub type Context = usize;
pub type DriverResult<T> = Result<T, i32>;
pub trait DriverCalls: Send + Sync {
    fn init(&self) -> i32;
    fn count(&self) -> DriverResult<i32>;
    fn device(&self, ordinal: i32) -> DriverResult<i32>;
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
    _owned: crate::platform::windows::Owned,
    table: [usize; 15],
}
impl DriverBridge {
    pub fn open() -> Result<Self, i32> {
        #[cfg(windows)]
        {
            let (owned, table) =
                crate::platform::bootstrap(&crate::platform::windows::WinPlatform)?;
            Ok(Self {
                _owned: owned,
                table,
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

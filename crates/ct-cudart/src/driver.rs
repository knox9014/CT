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

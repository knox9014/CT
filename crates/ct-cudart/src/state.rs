use crate::driver::{Context, DriverCalls, DriverResult};
use std::collections::BTreeMap;
use std::sync::{Mutex, OnceLock};
#[derive(Clone, Copy)]
enum Slot {
    Ready(Context),
    Failed(i32),
}
pub struct Runtime<D: DriverCalls> {
    pub driver: D,
    initialized: OnceLock<i32>,
    slots: Mutex<BTreeMap<i32, Slot>>,
}
impl<D: DriverCalls> Runtime<D> {
    pub fn new(driver: D) -> Self {
        Self {
            driver,
            initialized: OnceLock::new(),
            slots: Mutex::new(BTreeMap::new()),
        }
    }
    pub fn initialize(&self) -> i32 {
        *self.initialized.get_or_init(|| self.driver.init())
    }
    fn initialized(&self) -> DriverResult<()> {
        let code = self.initialize();
        if code == 0 {
            Ok(())
        } else {
            Err(code)
        }
    }
    pub fn get_count(&self) -> DriverResult<i32> {
        self.initialized()?;
        self.driver.count()
    }
    pub fn get_device(&self) -> DriverResult<i32> {
        self.initialized()?;
        if self.driver.current()?.is_some() {
            self.driver.context_device()
        } else {
            self.driver.device(0)
        }
    }
    pub fn set_device(&self, ordinal: i32) -> i32 {
        self.select(ordinal).err().unwrap_or(0)
    }
    fn select(&self, ordinal: i32) -> DriverResult<Context> {
        self.initialized()?;
        let device = self.driver.device(ordinal)?;
        let mut slots = self.slots.lock().map_err(|_| 999)?;
        if let Some(slot) = slots.get(&device).copied() {
            return match slot {
                Slot::Failed(code) => Err(code),
                Slot::Ready(context) => {
                    let code = self.driver.set_current(context);
                    if code == 709 {
                        slots.insert(device, Slot::Failed(709));
                    }
                    if code == 0 {
                        Ok(context)
                    } else {
                        Err(code)
                    }
                }
            };
        }
        let context = self.driver.retain(device)?;
        let code = self.driver.set_current(context);
        if code != 0 {
            if self.driver.release(device) != 0 {
                slots.insert(device, Slot::Failed(999));
                return Err(999);
            }
            return Err(code);
        }
        slots.insert(device, Slot::Ready(context));
        Ok(context)
    }
    pub fn ensure_current(&self) -> DriverResult<Context> {
        self.initialized()?;
        match self.driver.current()? {
            Some(context) => Ok(context),
            None => self.select(0),
        }
    }
}

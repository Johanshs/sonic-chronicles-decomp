//! Leitura segura de inteiros little-endian (o DS é little-endian).
//! Toda leitura fora dos limites vira `Error::Truncated` em vez de pânico.

use crate::{Error, Result};

pub fn u8_at(d: &[u8], off: usize, what: &'static str) -> Result<u8> {
    d.get(off).copied().ok_or(Error::Truncated { what, offset: off })
}

pub fn u16_at(d: &[u8], off: usize, what: &'static str) -> Result<u16> {
    d.get(off..off + 2)
        .map(|b| u16::from_le_bytes([b[0], b[1]]))
        .ok_or(Error::Truncated { what, offset: off })
}

pub fn u32_at(d: &[u8], off: usize, what: &'static str) -> Result<u32> {
    d.get(off..off + 4)
        .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .ok_or(Error::Truncated { what, offset: off })
}

pub fn i32_at(d: &[u8], off: usize, what: &'static str) -> Result<i32> {
    u32_at(d, off, what).map(|v| v as i32)
}

pub fn slice<'a>(d: &'a [u8], off: usize, len: usize, what: &'static str) -> Result<&'a [u8]> {
    d.get(off..off.checked_add(len).ok_or(Error::Truncated { what, offset: off })?)
        .ok_or(Error::Truncated { what, offset: off + len })
}

pub fn expect_magic(d: &[u8], off: usize, magic: &[u8], what: &'static str) -> Result<()> {
    let found = slice(d, off, magic.len(), what)?;
    if found == magic {
        Ok(())
    } else {
        Err(Error::BadMagic { what, found: found.to_vec() })
    }
}

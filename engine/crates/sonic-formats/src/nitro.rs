//! Gráficos "Nitro" (formato padrão do NitroSDK).
//!
//! **NCLR** (paleta): cabeçalho `RLCN` (0x10 bytes) + seção `TTLP`:
//! ```text
//! 0x10 "TTLP"  0x14 tamanho  0x18 bpp (3 = 4bpp, 4 = 8bpp)
//! 0x20 tamanho dos dados  0x24 offset dos dados (relativo a 0x18)  -> cores BGR555
//! ```
//! **NCGR** (tiles): cabeçalho `RGCN` + seção `RAHC`:
//! ```text
//! 0x18 altura em tiles (u16)  0x1A largura em tiles (u16)  (0xFFFF = não informado)
//! 0x1C bpp (3 = 4bpp, 4 = 8bpp)   0x24 "tiled" (0 = blocos 8×8, 1 = linear)
//! 0x28 tamanho dos dados          0x2C offset dos dados (relativo a 0x18)
//! ```
//! No modo em blocos, a imagem é uma grade de tiles 8×8; cada tile tem seus
//! 64 pixels em sequência. O índice 0 da paleta é transparente.

use crate::bytes::{expect_magic, slice, u16_at, u32_at};
use crate::image::{bgr555, Rgba};
use crate::Result;

pub struct Palette {
    pub colors: Vec<[u8; 4]>,
}

impl Palette {
    pub fn parse(d: &[u8]) -> Result<Self> {
        expect_magic(d, 0, b"RLCN", "NCLR")?;
        expect_magic(d, 0x10, b"TTLP", "NCLR")?;
        let size = u32_at(d, 0x20, "NCLR")? as usize;
        let off = 0x18 + u32_at(d, 0x24, "NCLR")? as usize;
        // alguns arquivos declaram mais dados do que têm: limita ao que existe
        let size = size.min(d.len().saturating_sub(off));
        let raw = slice(d, off, size & !1, "NCLR")?;
        Ok(Palette { colors: raw.chunks_exact(2).map(|p| bgr555(u16::from_le_bytes([p[0], p[1]]))).collect() })
    }

    /// Paleta cinza de reserva (quando não sabemos qual é a certa).
    pub fn grayscale(n: usize) -> Self {
        Palette { colors: (0..n).map(|i| { let v = (i * 255 / (n - 1).max(1)) as u8; [v, v, v, 255] }).collect() }
    }

    fn color(&self, idx: usize, transparent_zero: bool) -> [u8; 4] {
        if transparent_zero && idx == 0 {
            return [0, 0, 0, 0];
        }
        self.colors.get(idx).copied().unwrap_or([255, 0, 255, 255]) // magenta = índice fora da paleta
    }
}

pub struct Tiles {
    pub width_tiles: Option<u16>,
    pub height_tiles: Option<u16>,
    pub bpp: u8,
    pub linear: bool,
    /// Um índice de cor por pixel, na ordem em que estão no arquivo.
    pub indices: Vec<u8>,
}

impl Tiles {
    pub fn parse(d: &[u8]) -> Result<Self> {
        expect_magic(d, 0, b"RGCN", "NCGR")?;
        expect_magic(d, 0x10, b"RAHC", "NCGR")?;
        let h = u16_at(d, 0x18, "NCGR")?;
        let w = u16_at(d, 0x1A, "NCGR")?;
        let bpp = if u32_at(d, 0x1C, "NCGR")? == 3 { 4 } else { 8 };
        let linear = u32_at(d, 0x24, "NCGR")? & 0xFF == 1;
        let size = u32_at(d, 0x28, "NCGR")? as usize;
        let off = 0x18 + u32_at(d, 0x2C, "NCGR")? as usize;
        let size = size.min(d.len().saturating_sub(off));
        let raw = slice(d, off, size, "NCGR")?;
        let indices = if bpp == 4 { raw.iter().flat_map(|b| [b & 0xF, b >> 4]).collect() } else { raw.to_vec() };
        let dim = |v: u16| (v != 0xFFFF && v != 0).then_some(v);
        Ok(Tiles { width_tiles: dim(w), height_tiles: dim(h), bpp, linear, indices })
    }

    /// Renderiza com a paleta dada. Sem dimensões no arquivo, usa 8 tiles de largura.
    pub fn render(&self, pal: &Palette, palette_bank: usize) -> Rgba {
        let n_tiles = self.indices.len() / 64;
        let wt = self.width_tiles.map(|v| v as usize).unwrap_or_else(|| n_tiles.clamp(1, 8));
        let ht = self.height_tiles.map(|v| v as usize).unwrap_or_else(|| n_tiles.div_ceil(wt).max(1));
        let mut img = Rgba::new((wt * 8) as u32, (ht * 8) as u32);
        let bank = palette_bank * if self.bpp == 4 { 16 } else { 256 };
        for (i, &v) in self.indices.iter().enumerate() {
            let (x, y) = if self.linear {
                (i % (wt * 8), i / (wt * 8))
            } else {
                let (tile, k) = (i / 64, i % 64);
                ((tile % wt) * 8 + k % 8, (tile / wt) * 8 + k / 8)
            };
            img.set(x as u32, y as u32, pal.color(bank + v as usize, true));
        }
        img
    }
}

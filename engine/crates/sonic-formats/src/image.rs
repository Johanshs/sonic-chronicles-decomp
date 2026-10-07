//! Imagem RGBA mínima + gravação em PNG. Também converte cores do DS.

use crate::Result;
use std::io::Write;

#[derive(Clone)]
pub struct Rgba {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<[u8; 4]>,
}

impl Rgba {
    pub fn new(width: u32, height: u32) -> Self {
        Rgba { width, height, pixels: vec![[0, 0, 0, 0]; (width * height) as usize] }
    }

    pub fn set(&mut self, x: u32, y: u32, c: [u8; 4]) {
        if x < self.width && y < self.height {
            self.pixels[(y * self.width + x) as usize] = c;
        }
    }

    pub fn get(&self, x: u32, y: u32) -> [u8; 4] {
        self.pixels[(y * self.width + x) as usize]
    }

    /// Cola `src` na posição (x, y).
    pub fn blit(&mut self, src: &Rgba, x: u32, y: u32) {
        for sy in 0..src.height {
            for sx in 0..src.width {
                self.set(x + sx, y + sy, src.get(sx, sy));
            }
        }
    }

    pub fn write_png<W: Write>(&self, w: W) -> Result<()> {
        let mut enc = png::Encoder::new(w, self.width, self.height);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(png::BitDepth::Eight);
        let mut wr = enc.write_header().map_err(|e| crate::Error::Invalid(format!("PNG: {e}")))?;
        let flat: Vec<u8> = self.pixels.iter().flatten().copied().collect();
        wr.write_image_data(&flat).map_err(|e| crate::Error::Invalid(format!("PNG: {e}")))?;
        Ok(())
    }

    pub fn save_png(&self, path: &std::path::Path) -> Result<()> {
        let f = std::io::BufWriter::new(std::fs::File::create(path)?);
        self.write_png(f)
    }
}

/// Cor do DS: 15 bits, `0bbbbbgggggrrrrr` (BGR555). Expande 5 → 8 bits
/// repetindo os bits altos (31 vira 255, não 248).
pub fn bgr555(c: u16) -> [u8; 4] {
    let x = |v: u16| {
        let v = (v & 31) as u8;
        (v << 3) | (v >> 2)
    };
    [x(c), x(c >> 5), x(c >> 10), 255]
}

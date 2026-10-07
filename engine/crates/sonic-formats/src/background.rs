//! Cenários pré-renderizados das áreas (formato próprio da BioWare, decifrado aqui).
//!
//! Cada área `X` tem quatro arquivos soltos no NitroFS:
//! - **`X.cbgt`**: índice de 4096 entradas `{u16 tamanho, u16 offset/512}` (16 KB),
//!   seguido dos tiles. Cada tile é LZ10 → 4096 bytes = 64×64 pixels, 8 bpp, em
//!   blocos de 8×8 (64 blocos, cada um com 64 pixels seguidos). Tiles em ordem
//!   linha a linha.
//! - **`X.pal`**: paletas de 256 cores BGR555 (512 bytes cada).
//! - **`X.2da`**: grade colunas × linhas dizendo a paleta de cada tile
//!   (`paletteNN.pal`). As paletas pertencem a blocos de 2×2 tiles, numerados
//!   coluna a coluna.
//! - **`X.cdpth`** (opcional): mesmo índice; tile LZ10 → 64×64 valores de 16 bits,
//!   em ordem LINEAR (diferente da cor!). É a profundidade de cada pixel, para o
//!   jogo saber o que fica na frente ou atrás dos personagens. `0x7FFF` = sem
//!   objeto; tamanho 0 no índice = tile inteiro sem profundidade.
//!
//! O índice 0 de toda paleta é magenta (`0x7C1F`): a cor-chave de transparência.
//!
//! Como foi descoberto: a ordem certa foi escolhida medindo a diferença de cor nas
//! bordas entre tiles vizinhos para cada hipótese (linha a linha deu 4,8; as
//! outras, 35 a 56).

use crate::bytes::u16_at;
use crate::compression::lz10_decompress;
use crate::image::{bgr555, Rgba};
use crate::twoda;
use crate::{Error, Result};

pub const TILE: u32 = 64;

/// Lê a grade de paletas do `.2da` da área: `grid[linha][coluna] = nº da paleta`.
pub fn palette_grid(twoda_bytes: &[u8]) -> Result<Vec<Vec<usize>>> {
    let t = twoda::read(twoda_bytes);
    let grid: Vec<Vec<usize>> = t
        .rows
        .iter()
        .map(|r| {
            r.iter()
                .skip(1) // primeira coluna = número da linha
                .filter(|c| !c.is_empty())
                .filter_map(|c| c.trim_start_matches(|ch: char| !ch.is_ascii_digit()).split('.').next()?.parse().ok())
                .collect()
        })
        .filter(|r: &Vec<usize>| !r.is_empty())
        .collect();
    if grid.is_empty() {
        return Err(Error::Invalid("mapa de paletas vazio".into()));
    }
    Ok(grid)
}

fn tile_bytes(cbgt: &[u8], i: usize) -> Result<Option<Vec<u8>>> {
    let size = u16_at(cbgt, 4 * i, "índice CBGT")? as usize;
    let off = u16_at(cbgt, 4 * i + 2, "índice CBGT")? as usize * 512;
    if size == 0 {
        return Ok(None);
    }
    let raw = crate::bytes::slice(cbgt, off, size, "tile CBGT")?;
    lz10_decompress(raw).map(Some)
}

/// Posição do pixel `n` dentro de um tile 64×64 guardado em blocos 8×8.
fn block_pos(n: usize) -> (u32, u32) {
    let (blk, k) = (n / 64, n % 64);
    (((blk % 8) * 8 + k % 8) as u32, ((blk / 8) * 8 + k / 8) as u32)
}

/// Monta o cenário completo.
pub fn render(cbgt: &[u8], pal: &[u8], grid: &[Vec<usize>]) -> Result<Rgba> {
    let rows = grid.len();
    let cols = grid.iter().map(Vec::len).max().unwrap_or(0);
    let mut img = Rgba::new(cols as u32 * TILE, rows as u32 * TILE);
    for (y, row) in grid.iter().enumerate() {
        for (x, &pi) in row.iter().enumerate() {
            let Some(t) = tile_bytes(cbgt, y * cols + x)? else { continue };
            let palette: Vec<[u8; 4]> = (0..256)
                .map(|k| u16_at(pal, pi * 512 + 2 * k, "paleta").map(bgr555).unwrap_or([255, 0, 255, 255]))
                .collect();
            for (n, &v) in t.iter().enumerate() {
                let (px, py) = block_pos(n);
                let c = if v == 0 { [0, 0, 0, 0] } else { palette[v as usize] }; // 0 = transparente
                img.set(x as u32 * TILE + px, y as u32 * TILE + py, c);
            }
        }
    }
    Ok(img)
}

pub const NO_DEPTH: u16 = 0x7FFF;

/// Mapa de profundidade em tons de cinza (claro = perto), normalizado pela área.
/// Pixels sem profundidade ficam transparentes.
pub fn render_depth(cdpth: &[u8], cols: usize, rows: usize) -> Result<Rgba> {
    let mut values = vec![None; cols * rows * (TILE * TILE) as usize];
    let (mut lo, mut hi) = (u16::MAX, 0u16);
    for i in 0..cols * rows {
        let Some(t) = tile_bytes(cdpth, i)? else { continue };
        for (n, p) in t.chunks_exact(2).enumerate() {
            let v = u16::from_le_bytes([p[0], p[1]]);
            if v == NO_DEPTH {
                continue;
            }
            let (px, py) = ((n % 64) as u32, (n / 64) as u32); // linear
            let (gx, gy) = ((i % cols) as u32 * TILE + px, (i / cols) as u32 * TILE + py);
            values[(gy * cols as u32 * TILE + gx) as usize] = Some(v);
            lo = lo.min(v);
            hi = hi.max(v);
        }
    }
    let mut img = Rgba::new(cols as u32 * TILE, rows as u32 * TILE);
    let span = (hi.saturating_sub(lo)).max(1) as u32;
    for (k, v) in values.iter().enumerate() {
        if let Some(v) = v {
            let g = (255 - ((*v - lo) as u32 * 255 / span)) as u8;
            img.pixels[k] = [g, g, g, 255];
        }
    }
    Ok(img)
}

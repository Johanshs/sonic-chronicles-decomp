//! Compressão.
//!
//! **LZ10** (tipo 0x10 da BIOS do DS/GBA): cabeçalho `0x10` + tamanho final (24 bits).
//! Blocos de 8 itens precedidos de 1 byte de flags (bit 7 primeiro):
//! bit 0 = byte literal; bit 1 = referência de 2 bytes `b0 b1` que copia
//! `3 + (b0 >> 4)` bytes de `((b0 & 0xF) << 8 | b1) + 1` bytes atrás.
//!
//! **`.small`** (contêiner da BioWare): `u32 = tipo | tamanho << 8`.
//! Tipo 0x00 = dados sem compressão; tipo 0x10 = LZ10.
//! O jogo procura `nome.ext.small` antes de `nome.ext`.

use crate::{Error, Result};

pub fn lz10_decompress(src: &[u8]) -> Result<Vec<u8>> {
    if src.len() < 4 || src[0] != 0x10 {
        return Err(Error::Invalid("LZ10: cabeçalho inválido".into()));
    }
    let size = u32::from_le_bytes([src[1], src[2], src[3], 0]) as usize;
    let mut out = Vec::with_capacity(size);
    let mut i = 4;
    let byte = |i: usize| src.get(i).copied().ok_or(Error::Truncated { what: "LZ10", offset: i });
    while out.len() < size {
        let flags = byte(i)?;
        i += 1;
        for bit in (0..8).rev() {
            if out.len() >= size {
                break;
            }
            if flags & (1 << bit) == 0 {
                out.push(byte(i)?);
                i += 1;
            } else {
                let (b0, b1) = (byte(i)? as usize, byte(i + 1)? as usize);
                i += 2;
                let len = 3 + (b0 >> 4);
                let dist = ((b0 & 0xF) << 8 | b1) + 1;
                if dist > out.len() {
                    return Err(Error::Invalid("LZ10: referência antes do início".into()));
                }
                // Byte a byte: a origem pode sobrepor o que está sendo escrito
                // (é assim que o LZ repete padrões curtos, ex.: "aaaaaa").
                for _ in 0..len {
                    out.push(out[out.len() - dist]);
                }
            }
        }
    }
    out.truncate(size);
    Ok(out)
}

/// Resultado de abrir um `.small`.
pub enum Small<'a> {
    Stored(&'a [u8]),
    Lz10(Vec<u8>),
}

impl Small<'_> {
    pub fn into_vec(self) -> Vec<u8> {
        match self {
            Small::Stored(s) => s.to_vec(),
            Small::Lz10(v) => v,
        }
    }
}

/// Tenta interpretar `blob` como `.small`. Devolve `None` se não parecer um.
pub fn open_small(blob: &[u8]) -> Option<Small<'_>> {
    if blob.len() <= 4 {
        return None;
    }
    let size = u32::from_le_bytes([blob[1], blob[2], blob[3], 0]) as usize;
    match blob[0] {
        0x00 if size == blob.len() - 4 && size > 0 => Some(Small::Stored(&blob[4..])),
        0x10 if size > 0 && size < 64 << 20 => match lz10_decompress(blob) {
            Ok(v) if v.len() == size => Some(Small::Lz10(v)),
            _ => None,
        },
        _ => None,
    }
}

/// Compressão LZ10 (compatível com a BIOS do DS). Gulosa: em cada posição, procura
/// a maior repetição nos últimos 4096 bytes (3 a 18 bytes, distância >= 2). Usa uma tabela de
/// "últimas posições" por trio de bytes para não comparar com a janela inteira.
pub fn lz10_compress(src: &[u8]) -> Vec<u8> {
    let mut out = vec![0x10];
    out.extend(&(src.len() as u32).to_le_bytes()[..3]);
    let mut chains: std::collections::HashMap<[u8; 3], Vec<usize>> = std::collections::HashMap::new();
    let mut i = 0;
    while i < src.len() {
        let flag_pos = out.len();
        out.push(0);
        let mut flags = 0u8;
        for bit in (0..8).rev() {
            if i >= src.len() {
                break;
            }
            let mut best = (0usize, 0usize); // (tamanho, distância)
            if i + 3 <= src.len() {
                if let Some(cands) = chains.get(&[src[i], src[i + 1], src[i + 2]]) {
                    for &p in cands.iter().rev() {
                        let dist = i - p;
                        if dist > 4096 {
                            break;
                        }
                        // distância 1 é proibida: a rotina da BIOS que escreve na VRAM
                        // grava 16 bits por vez e leria um byte que ainda não existe
                        if dist < 2 {
                            continue;
                        }
                        let max = (src.len() - i).min(18);
                        let mut len = 0;
                        while len < max && src[p + len] == src[i + len] {
                            len += 1;
                        }
                        if len > best.0 {
                            best = (len, dist);
                            if len == 18 {
                                break;
                            }
                        }
                    }
                }
            }
            let step = if best.0 >= 3 {
                flags |= 1 << bit;
                let (len, dist) = (best.0 - 3, best.1 - 1);
                out.push(((len << 4) | (dist >> 8)) as u8);
                out.push((dist & 0xFF) as u8);
                best.0
            } else {
                out.push(src[i]);
                1
            };
            for k in i..i + step {
                if k + 3 <= src.len() {
                    chains.entry([src[k], src[k + 1], src[k + 2]]).or_default().push(k);
                }
            }
            i += step;
        }
        out[flag_pos] = flags;
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

/// Embala `data` como `.small` do mesmo tipo do original (0x00 = sem compressão, 0x10 = LZ10).
pub fn make_small(data: &[u8], lz10: bool) -> Vec<u8> {
    if lz10 {
        lz10_compress(data)
    } else {
        let size = (data.len() as u32) << 8; // tipo 0x00 no byte baixo, tamanho << 8
        let mut out = size.to_le_bytes().to_vec();
        out.extend(data);
        out
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn lz10_ida_e_volta() {
        let data: Vec<u8> = (0..5000u32).map(|i| ((i * 7) % 13 + (i / 100)) as u8).collect();
        let c = super::lz10_compress(&data);
        assert!(c.len() < data.len());
        assert_eq!(super::lz10_decompress(&c).unwrap(), data);
    }

    use super::*;

    #[test]
    fn lz10_com_referencia_sobreposta() {
        // "abcabcabc": 3 literais + referência (tamanho 6, distância 3)
        let comp = [0x10, 9, 0, 0, 0b0001_0000, b'a', b'b', b'c', 0x30, 0x02];
        assert_eq!(lz10_decompress(&comp).unwrap(), b"abcabcabc");
    }

    #[test]
    fn small_sem_compressao() {
        let blob = [0x00, 3, 0, 0, 7, 8, 9];
        assert_eq!(open_small(&blob).unwrap().into_vec(), vec![7, 8, 9]);
    }
}

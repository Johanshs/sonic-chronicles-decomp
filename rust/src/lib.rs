//! Formatos do Sonic Chronicles, reimplementados em Rust.
//!
//! Cada função aqui corresponde a algo encontrado no código original (ARM9):
//! - [`hash_resource_name`] = `func_02009b78` (HashResourceName)
//! - [`lz10_decompress`]    = descompressão LZ77 da BIOS do DS (arquivos `.small`)
//! - [`Herf`]               = pacote de recursos `.herf`

use std::fmt;

/// Hash DJB2 usado no lugar dos nomes de arquivo dentro do HERF.
///
/// Fiel ao assembly: o caractere é lido **com sinal** (`ldrsb`), só bytes
/// 0..0x7F passam pela tabela de minúsculas, e bytes >= 0x80 entram negativos.
pub fn hash_resource_name(name: &[u8]) -> u32 {
    let mut hash: u32 = 5381; // ldr r4, =0x1505
    for &b in name {
        let c = b as i8 as i32; // ldrsb
        let c = if (0..0x80).contains(&c) {
            (c as u8).to_ascii_lowercase() as i32 // ldrb r5, [tabela, r5]
        } else {
            c
        };
        // lsl r7, r4, #5 ; add r4, r7 ; add r4, r5, r4   =>  hash*33 + c
        hash = hash.wrapping_mul(33).wrapping_add(c as u32);
    }
    hash
}

#[derive(Debug)]
pub enum Error {
    NotHerf(u32),
    Truncated(&'static str),
    BadLz10(&'static str),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::NotHerf(m) => write!(f, "não é HERF (magic {m:#010x})"),
            Error::Truncated(what) => write!(f, "arquivo truncado: {what}"),
            Error::BadLz10(why) => write!(f, "LZ10 inválido: {why}"),
        }
    }
}
impl std::error::Error for Error {}

fn read_u32(data: &[u8], off: usize, what: &'static str) -> Result<u32, Error> {
    data.get(off..off + 4)
        .map(|b| u32::from_le_bytes(b.try_into().unwrap()))
        .ok_or(Error::Truncated(what))
}

/// Uma entrada do índice do HERF.
#[derive(Debug, Clone, Copy)]
pub struct Entry {
    pub hash: u32,
    pub size: u32,
    pub offset: u32,
}

/// Pacote HERF: `u32 magic, u32 count, count × {hash, tamanho, offset}`.
/// Empresta (`&'a [u8]`) os dados em vez de copiar: ler um arquivo de 49 MB
/// não aloca nada além do índice.
pub struct Herf<'a> {
    data: &'a [u8],
    pub entries: Vec<Entry>,
}

impl<'a> Herf<'a> {
    pub const MAGIC: u32 = 0x00F1_A5C0;

    pub fn parse(data: &'a [u8]) -> Result<Self, Error> {
        let magic = read_u32(data, 0, "magic")?;
        if magic != Self::MAGIC {
            return Err(Error::NotHerf(magic));
        }
        let count = read_u32(data, 4, "contagem")? as usize;
        let entries = (0..count)
            .map(|i| {
                let base = 8 + 12 * i;
                Ok(Entry {
                    hash: read_u32(data, base, "índice")?,
                    size: read_u32(data, base + 4, "índice")?,
                    offset: read_u32(data, base + 8, "índice")?,
                })
            })
            .collect::<Result<Vec<_>, Error>>()?;
        Ok(Herf { data, entries })
    }

    /// Bytes brutos de uma entrada (ainda comprimidos, se for `.small`).
    pub fn raw(&self, e: &Entry) -> Result<&'a [u8], Error> {
        let (start, end) = (e.offset as usize, e.offset as usize + e.size as usize);
        self.data.get(start..end).ok_or(Error::Truncated("dados da entrada"))
    }

    /// Procura uma entrada pelo nome (calculando o hash, como o jogo faz).
    pub fn find(&self, name: &str) -> Option<&Entry> {
        let h = hash_resource_name(name.as_bytes());
        self.entries.iter().find(|e| e.hash == h)
    }
}

/// Descompressão LZ10 (tipo 0x10 da BIOS do Nintendo DS/GBA).
///
/// Cabeçalho: `0x10` + tamanho final em 24 bits. Depois, blocos de 8 itens
/// precedidos de 1 byte de flags (bit 7 primeiro): bit 0 = byte literal,
/// bit 1 = referência de 2 bytes => copia `3 + (b0 >> 4)` bytes de
/// `distância = ((b0 & 0xF) << 8 | b1) + 1` bytes atrás.
pub fn lz10_decompress(src: &[u8]) -> Result<Vec<u8>, Error> {
    if src.len() < 4 || src[0] != 0x10 {
        return Err(Error::BadLz10("cabeçalho"));
    }
    let size = u32::from_le_bytes([src[1], src[2], src[3], 0]) as usize;
    let mut out = Vec::with_capacity(size);
    let mut i = 4;
    while out.len() < size {
        let flags = *src.get(i).ok_or(Error::BadLz10("fim inesperado"))?;
        i += 1;
        for bit in (0..8).rev() {
            if out.len() >= size {
                break;
            }
            if flags & (1 << bit) == 0 {
                out.push(*src.get(i).ok_or(Error::BadLz10("literal"))?);
                i += 1;
            } else {
                let (b0, b1) = match (src.get(i), src.get(i + 1)) {
                    (Some(&a), Some(&b)) => (a as usize, b as usize),
                    _ => return Err(Error::BadLz10("referência")),
                };
                i += 2;
                let len = 3 + (b0 >> 4);
                let dist = ((b0 & 0xF) << 8 | b1) + 1;
                if dist > out.len() {
                    return Err(Error::BadLz10("distância antes do início"));
                }
                // byte a byte: a cópia pode sobrepor o que está sendo escrito
                for _ in 0..len {
                    out.push(out[out.len() - dist]);
                }
            }
        }
    }
    out.truncate(size);
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_bate_com_o_jogo() {
        // pares conferidos no test.herf original
        assert_eq!(hash_resource_name(b"areas.gda"), hash_resource_name(b"AREAS.GDA"));
        assert_eq!(hash_resource_name(b""), 5381);
    }

    #[test]
    fn lz10_simples() {
        // "abcabcabc": 3 literais + referência (len 6, dist 3)
        let comp = [0x10, 9, 0, 0, 0b0001_0000, b'a', b'b', b'c', 0x30, 0x02];
        assert_eq!(lz10_decompress(&comp).unwrap(), b"abcabcabc");
    }
}

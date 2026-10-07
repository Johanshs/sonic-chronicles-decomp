//! ROM do Nintendo DS (`.nds`).
//!
//! Cabeçalho (primeiros 0x200 bytes), campos usados aqui:
//! ```text
//! 0x00 título (12 bytes)   0x0C código do jogo (4)    0x10 código do fabricante (2)
//! 0x20 ARM9 offset  0x24 entrada  0x28 endereço na RAM  0x2C tamanho
//! 0x30 ARM7 offset  0x34 entrada  0x38 endereço na RAM  0x3C tamanho
//! 0x40 FNT offset   0x44 FNT tamanho   (tabela de nomes)
//! 0x48 FAT offset   0x4C FAT tamanho   (tabela de alocação: início/fim de cada arquivo)
//! ```
//! NitroFS: a FNT tem uma "tabela principal" com 8 bytes por pasta
//! `{u32 offset da sub-tabela, u16 id do 1º arquivo, u16 pai}`; cada sub-tabela é uma
//! sequência de `{u8 tamanho|0x80 se pasta, nome, [u16 id da pasta]}` terminada em 0.

use crate::bytes::{slice, u16_at, u32_at, u8_at};
use crate::{Error, Result};

pub struct Rom<'a> {
    data: &'a [u8],
    pub title: String,
    pub game_code: String,
    pub arm9: Region,
    pub arm7: Region,
    /// Todos os arquivos do NitroFS, com caminho completo ("pasta/arquivo").
    pub files: Vec<FileEntry>,
}

#[derive(Debug, Clone, Copy)]
pub struct Region {
    pub offset: u32,
    pub entry: u32,
    pub ram_address: u32,
    pub size: u32,
}

#[derive(Debug, Clone)]
pub struct FileEntry {
    pub id: u16,
    pub path: String,
    pub start: u32,
    pub end: u32,
}

impl<'a> Rom<'a> {
    pub fn parse(data: &'a [u8]) -> Result<Self> {
        let text = |off, len| -> Result<String> {
            Ok(String::from_utf8_lossy(slice(data, off, len, "cabeçalho")?)
                .trim_end_matches('\0')
                .to_string())
        };
        let region = |base: usize| -> Result<Region> {
            Ok(Region {
                offset: u32_at(data, base, "cabeçalho")?,
                entry: u32_at(data, base + 4, "cabeçalho")?,
                ram_address: u32_at(data, base + 8, "cabeçalho")?,
                size: u32_at(data, base + 12, "cabeçalho")?,
            })
        };
        let fnt = u32_at(data, 0x40, "cabeçalho")? as usize;
        let fat = u32_at(data, 0x48, "cabeçalho")? as usize;
        let fat_size = u32_at(data, 0x4C, "cabeçalho")? as usize;

        let mut files = Vec::new();
        walk_dir(data, fnt, fat, 0xF000, String::new(), &mut files, 0)?;
        // Arquivos sem nome (overlays) também estão na FAT, mas não nos interessam aqui.
        let _ = fat_size;
        Ok(Rom {
            data,
            title: text(0, 12)?,
            game_code: text(0x0C, 4)?,
            arm9: region(0x20)?,
            arm7: region(0x30)?,
            files,
        })
    }

    pub fn arm9(&self) -> Result<&'a [u8]> {
        slice(self.data, self.arm9.offset as usize, self.arm9.size as usize, "ARM9")
    }

    pub fn arm7(&self) -> Result<&'a [u8]> {
        slice(self.data, self.arm7.offset as usize, self.arm7.size as usize, "ARM7")
    }

    pub fn file_data(&self, f: &FileEntry) -> Result<&'a [u8]> {
        if f.end < f.start {
            return Err(Error::Invalid(format!("arquivo {} com fim antes do início", f.path)));
        }
        slice(self.data, f.start as usize, (f.end - f.start) as usize, "arquivo do NitroFS")
    }

    pub fn find(&self, path: &str) -> Option<&FileEntry> {
        self.files.iter().find(|f| f.path.eq_ignore_ascii_case(path))
    }
}

fn walk_dir(
    d: &[u8],
    fnt: usize,
    fat: usize,
    dir_id: u16,
    prefix: String,
    out: &mut Vec<FileEntry>,
    depth: usize,
) -> Result<()> {
    if depth > 32 {
        return Err(Error::Invalid("NitroFS: pastas aninhadas demais".into()));
    }
    let entry = fnt + 8 * (dir_id & 0x0FFF) as usize;
    let mut p = fnt + u32_at(d, entry, "FNT")? as usize;
    let mut file_id = u16_at(d, entry + 4, "FNT")?;
    loop {
        let len_byte = u8_at(d, p, "FNT")?;
        p += 1;
        if len_byte == 0 {
            break;
        }
        let is_dir = len_byte & 0x80 != 0;
        let len = (len_byte & 0x7F) as usize;
        let name = String::from_utf8_lossy(slice(d, p, len, "FNT")?).to_string();
        p += len;
        let path = if prefix.is_empty() { name } else { format!("{prefix}/{name}") };
        if is_dir {
            let sub = u16_at(d, p, "FNT")?;
            p += 2;
            walk_dir(d, fnt, fat, sub, path, out, depth + 1)?;
        } else {
            let fa = fat + 8 * file_id as usize;
            out.push(FileEntry {
                id: file_id,
                path,
                start: u32_at(d, fa, "FAT")?,
                end: u32_at(d, fa + 4, "FAT")?,
            });
            file_id += 1;
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Escrita: troca de arquivos do NitroFS com o mínimo de mudanças.
// ---------------------------------------------------------------------------

/// CRC16 do cabeçalho (polinômio 0xA001, início 0xFFFF), gravado em 0x15E
/// sobre os bytes 0x000..0x15D. Conferido com o valor original da ROM.
pub fn header_crc16(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for &b in data {
        crc ^= b as u16;
        for _ in 0..8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0xA001 } else { crc >> 1 };
        }
    }
    crc
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Placement {
    /// Coube no espaço do arquivo antigo.
    InPlace,
    /// Foi para o fim da área usada do cartucho.
    Appended,
}

/// Substitui o conteúdo do arquivo `file_id`. Se couber até o início do próximo
/// arquivo, fica no mesmo lugar; senão vai para o fim (alinhado em 0x200), e o
/// cartucho cresce para a próxima potência de 2 se preciso. Atualiza FAT,
/// tamanho usado (0x80), capacidade (0x14) e o CRC do cabeçalho.
pub fn replace_file(rom: &mut Vec<u8>, file_id: u16, new: &[u8]) -> Result<Placement> {
    let fat = u32_at(rom, 0x48, "cabeçalho")? as usize;
    let count = u32_at(rom, 0x4C, "cabeçalho")? as usize / 8;
    let id = file_id as usize;
    if id >= count {
        return Err(Error::Invalid(format!("arquivo {file_id} não existe na FAT")));
    }
    let ents: Vec<(u32, u32)> = (0..count).map(|i| Ok((u32_at(rom, fat + 8 * i, "FAT")?, u32_at(rom, fat + 8 * i + 4, "FAT")?))).collect::<Result<_>>()?;
    let used = u32_at(rom, 0x80, "cabeçalho")?;
    let (start, end) = ents[id];
    let limit = ents.iter().filter(|(s, _)| *s >= end && *s > start).map(|(s, _)| *s).min().unwrap_or(used).min(used.max(end));
    let (new_start, placement) = if start as usize + new.len() <= limit as usize {
        (start, Placement::InPlace)
    } else {
        ((used + 0x1FF) & !0x1FF, Placement::Appended)
    };
    let new_end = new_start as usize + new.len();
    if new_end > rom.len() {
        let cap = new_end.next_power_of_two();
        rom.resize(cap, 0xFF);
    }
    rom[new_start as usize..new_end].copy_from_slice(new);
    rom[fat + 8 * id..fat + 8 * id + 4].copy_from_slice(&new_start.to_le_bytes());
    rom[fat + 8 * id + 4..fat + 8 * id + 8].copy_from_slice(&(new_end as u32).to_le_bytes());
    if placement == Placement::Appended {
        rom[0x80..0x84].copy_from_slice(&(new_end as u32).to_le_bytes());
    }
    // capacidade do cartucho: 128 KB << n
    let mut n = 0u8;
    while (128 * 1024usize) << n < rom.len() {
        n += 1;
    }
    rom[0x14] = n;
    let crc = header_crc16(&rom[..0x15E]);
    rom[0x15E..0x160].copy_from_slice(&crc.to_le_bytes());
    Ok(placement)
}

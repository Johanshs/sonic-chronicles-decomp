//! Tabela de textos `.tlk` (GFF4 tipo `TLK `).
//! Raiz `TLK ` → lista 19001 de structs `STRN { 19002: id, 19003: texto }`.
//! Um arquivo por idioma: `strings.tlk` (EN), `strings_fr-fr.tlk`, `_de-de`, `_es-es`, `_it-it`.

use crate::bytes::u32_at;
use crate::gff4::{cp1252, Gff4};
use crate::{Error, Result};
use std::collections::{BTreeMap, HashMap};

pub fn read(data: &[u8]) -> Result<BTreeMap<u32, String>> {
    let root = Gff4::parse(data)?.root()?;
    let mut out = BTreeMap::new();
    if let Some(list) = root.get("19001").and_then(|v| v.as_array()) {
        for s in list {
            if let (Some(id), Some(text)) = (s.get("19002").and_then(|v| v.as_u64()), s.get("19003").and_then(|v| v.as_str())) {
                out.insert(id as u32, text.trim().to_string());
            }
        }
    }
    Ok(out)
}

/// Idiomas do jogo, na ordem do código (`OS_GetOwnerInfo`): o arquivo de cada um.
pub const LANGUAGES: &[(&str, &str)] = &[
    ("en", "strings.tlk"),
    ("fr", "strings_fr-fr.tlk"),
    ("de", "strings_de-de.tlk"),
    ("es", "strings_es-es.tlk"),
    ("it", "strings_it-it.tlk"),
];

// ---------------------------------------------------------------------------
// Modelo para edição. Descoberto lendo a função 0x020989fc do jogo:
// a lista de entradas é uma TABELA HASH com sondagem linear.
//   posição = hash(id) % total; se ocupada por outro id, tenta a próxima.
//   id 0xFFFFFFFF = posição vazia (a busca para ali).
// Layout dos dados: raiz {u32 rel(lista)=4}; lista {u32 n, n × {u32 id, u32 rel(texto)}};
// textos {u32 tamanho, bytes cp1252 com '\0'} sem repetição, na ordem da primeira
// posição que os usa, alinhados em 4 com 0xFF. Reproduz os 5 TLK byte a byte.
// ---------------------------------------------------------------------------

pub const EMPTY: u32 = 0xFFFF_FFFF;

/// Hash usado pelo jogo para posicionar o id na tabela (variante do hash de Thomas Wang).
pub fn slot_hash(id: u32) -> u32 {
    let mut u = (!id).wrapping_add(id.wrapping_mul(0x8000));
    u = ((u >> 12) ^ u).wrapping_mul(5);
    u = (u ^ (u >> 4)).wrapping_mul(0x809);
    (u >> 16) ^ u
}

#[derive(Clone)]
pub struct Tlk {
    header: Vec<u8>,
    /// Posições da tabela hash: (id, texto em bytes cp1252 com '\0').
    pub slots: Vec<(u32, Option<Vec<u8>>)>,
}

/// Texto Unicode -> cp1252 com '\0'. Caracteres sem equivalente viram '?'.
pub fn encode_text(s: &str) -> (Vec<u8>, bool) {
    let mut lossy = false;
    let mut v: Vec<u8> = s
        .chars()
        .map(|c| {
            if (c as u32) < 0x80 || ((c as u32) >= 0xA0 && (c as u32) <= 0xFF) {
                return c as u32 as u8;
            }
            match (0x80u8..=0x9F).find(|&b| cp1252(&[b]).starts_with(c)) {
                Some(b) => b,
                None => { lossy = true; b'?' }
            }
        })
        .collect();
    v.push(0);
    (v, lossy)
}

impl Tlk {
    pub fn parse(d: &[u8]) -> Result<Self> {
        let g = Gff4::parse(d)?;
        if g.file_type != "TLK" {
            return Err(Error::Invalid("não é um TLK".into()));
        }
        let data_off = g.data_offset;
        let lo = data_off + u32_at(d, data_off, "TLK")? as usize;
        let n = u32_at(d, lo, "TLK")? as usize;
        let mut slots = Vec::with_capacity(n);
        for i in 0..n {
            let id = u32_at(d, lo + 4 + 8 * i, "TLK")?;
            let rel = u32_at(d, lo + 8 + 8 * i, "TLK")?;
            let text = if rel == EMPTY {
                None
            } else {
                let so = data_off + rel as usize;
                let len = u32_at(d, so, "TLK")? as usize;
                Some(crate::bytes::slice(d, so + 4, len, "TLK")?.to_vec())
            };
            slots.push((id, text));
        }
        Ok(Tlk { header: d[..data_off].to_vec(), slots })
    }

    fn find(&self, id: u32) -> Option<usize> {
        let n = self.slots.len();
        let mut i = slot_hash(id) as usize % n;
        for _ in 0..n {
            match self.slots[i].0 {
                x if x == id => return Some(i),
                EMPTY => return None,
                _ => i = (i + 1) % n,
            }
        }
        None
    }

    pub fn get(&self, id: u32) -> Option<String> {
        self.find(id).and_then(|i| self.slots[i].1.as_ref()).map(|b| cp1252(b).trim_end_matches('\0').to_string())
    }

    /// Todos os textos, por id.
    pub fn texts(&self) -> BTreeMap<u32, String> {
        self.slots
            .iter()
            .filter(|(id, _)| *id != EMPTY)
            .map(|(id, t)| (*id, t.as_ref().map(|b| cp1252(b).trim_end_matches('\0').to_string()).unwrap_or_default()))
            .collect()
    }

    /// Troca o texto de um id existente ou cria um id novo. Devolve `true` se algum
    /// caractere não existe em cp1252 (virou '?').
    pub fn set(&mut self, id: u32, text: &str) -> Result<bool> {
        if id == EMPTY {
            return Err(Error::Invalid("id 4294967295 é reservado (posição vazia)".into()));
        }
        let (bytes, lossy) = encode_text(text);
        if let Some(i) = self.find(id) {
            self.slots[i].1 = Some(bytes);
            return Ok(lossy);
        }
        // id novo: se a tabela estiver cheia demais, aumenta e reinsere tudo
        let used = self.slots.iter().filter(|s| s.0 != EMPTY).count();
        if (used + 1) * 10 > self.slots.len() * 9 {
            self.rebuild(self.slots.len() * 5 / 4 + 1);
        }
        let n = self.slots.len();
        let mut i = slot_hash(id) as usize % n;
        while self.slots[i].0 != EMPTY {
            i = (i + 1) % n;
        }
        self.slots[i] = (id, Some(bytes));
        Ok(lossy)
    }

    /// Remove um id (a tabela é refeita para não quebrar cadeias de sondagem).
    pub fn remove(&mut self, id: u32) {
        if let Some(i) = self.find(id) {
            self.slots[i] = (EMPTY, None);
            self.rebuild(self.slots.len());
        }
    }

    fn rebuild(&mut self, size: usize) {
        let entries: Vec<(u32, Option<Vec<u8>>)> = self.slots.drain(..).filter(|s| s.0 != EMPTY).collect();
        self.slots = vec![(EMPTY, None); size];
        for (id, t) in entries {
            let mut i = slot_hash(id) as usize % size;
            while self.slots[i].0 != EMPTY {
                i = (i + 1) % size;
            }
            self.slots[i] = (id, t);
        }
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out: Vec<u8> = Vec::new();
        out.extend(4u32.to_le_bytes());
        out.extend((self.slots.len() as u32).to_le_bytes());
        let table = out.len();
        out.resize(table + 8 * self.slots.len(), 0);
        let mut seen: HashMap<&[u8], u32> = HashMap::new();
        for (i, (id, text)) in self.slots.iter().enumerate() {
            let rel = match text {
                None => EMPTY,
                Some(t) => match seen.get(t.as_slice()) {
                    Some(&r) => r,
                    None => {
                        while !out.len().is_multiple_of(4) {
                            out.push(0xFF);
                        }
                        let r = out.len() as u32;
                        out.extend((t.len() as u32).to_le_bytes());
                        out.extend(t);
                        seen.insert(t, r);
                        r
                    }
                },
            };
            out[table + 8 * i..table + 8 * i + 4].copy_from_slice(&id.to_le_bytes());
            out[table + 8 * i + 4..table + 8 * i + 8].copy_from_slice(&rel.to_le_bytes());
        }
        let mut file = self.header.clone();
        file.extend(out);
        file
    }
}

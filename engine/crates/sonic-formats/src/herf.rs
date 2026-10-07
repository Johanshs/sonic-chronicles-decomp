//! Pacote de recursos `.herf`.
//!
//! ```text
//! u32 magic = 0x00F1A5C0
//! u32 count
//! count × { u32 hash_do_nome, u32 tamanho, u32 offset }
//! ```
//! O nome não é guardado, só o hash ([`hash_resource_name`], função 0x02009b78 do
//! jogo). Mas o próprio pacote principal traz um arquivo **`erf.dict`** com os nomes:
//! ```text
//! u32 magic = 0x00F1A5C0, u32 count, count × { u32 hash, char nome[128] }
//! ```
//! [`parse_name_dict`] lê esse dicionário (e confere cada hash). Para pacotes sem
//! dicionário, [`NameRecovery`] faz um *ataque de dicionário*:
//! junta palavras que parecem nomes de arquivo (no código, nos próprios arquivos,
//! em ASCII e em UTF-16), gera variações de extensão e testa o hash de cada uma.

use crate::bytes::u32_at;
use crate::compression::open_small;
use crate::{Error, Result};
use std::collections::{BTreeSet, HashMap, HashSet};

pub const MAGIC: u32 = 0x00F1_A5C0;

/// DJB2 com tabela de minúsculas, fiel ao assembly (caractere lido com sinal).
pub fn hash_resource_name(name: &[u8]) -> u32 {
    let mut hash: u32 = 5381;
    for &b in name {
        let c = b as i8 as i32;
        let c = if (0..0x80).contains(&c) { (c as u8).to_ascii_lowercase() as i32 } else { c };
        hash = hash.wrapping_mul(33).wrapping_add(c as u32);
    }
    hash
}

#[derive(Debug, Clone, Copy)]
pub struct Entry {
    pub hash: u32,
    pub size: u32,
    pub offset: u32,
}

pub struct Herf<'a> {
    data: &'a [u8],
    pub entries: Vec<Entry>,
}

impl<'a> Herf<'a> {
    pub fn parse(data: &'a [u8]) -> Result<Self> {
        let magic = u32_at(data, 0, "HERF")?;
        if magic != MAGIC {
            return Err(Error::BadMagic { what: "HERF", found: data[..4].to_vec() });
        }
        let count = u32_at(data, 4, "HERF")? as usize;
        let entries = (0..count)
            .map(|i| {
                let b = 8 + 12 * i;
                Ok(Entry {
                    hash: u32_at(data, b, "índice HERF")?,
                    size: u32_at(data, b + 4, "índice HERF")?,
                    offset: u32_at(data, b + 8, "índice HERF")?,
                })
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Herf { data, entries })
    }

    pub fn raw(&self, e: &Entry) -> Result<&'a [u8]> {
        crate::bytes::slice(self.data, e.offset as usize, e.size as usize, "dados HERF")
    }

    /// Conteúdo pronto para uso: se for `.small`, já vem aberto.
    /// Devolve `(dados, era_small)`.
    pub fn contents(&self, e: &Entry) -> Result<(Vec<u8>, bool)> {
        let raw = self.raw(e)?;
        Ok(match open_small(raw) {
            Some(s) => (s.into_vec(), true),
            None => (raw.to_vec(), false),
        })
    }

    /// Procura como o jogo: primeiro `nome.small`, depois `nome`.
    pub fn find(&self, name: &str) -> Option<&Entry> {
        let small = hash_resource_name(format!("{name}.small").as_bytes());
        let plain = hash_resource_name(name.as_bytes());
        self.entries.iter().find(|e| e.hash == small).or_else(|| self.entries.iter().find(|e| e.hash == plain))
    }
}

/// Lê um `erf.dict`. Só aceita nomes cujo hash confere. `None` se não for um dicionário.
pub fn parse_name_dict(d: &[u8]) -> Option<HashMap<u32, String>> {
    const ENTRY: usize = 4 + 128;
    let magic = u32_at(d, 0, "").ok()?;
    let count = u32_at(d, 4, "").ok()? as usize;
    if magic != MAGIC || d.len() != 8 + ENTRY * count {
        return None;
    }
    let mut out = HashMap::new();
    for i in 0..count {
        let base = 8 + ENTRY * i;
        let hash = u32_at(d, base, "").ok()?;
        let raw = &d[base + 4..base + ENTRY];
        let name = &raw[..raw.iter().position(|&b| b == 0).unwrap_or(raw.len())];
        if !name.is_empty() && hash_resource_name(name) == hash {
            out.insert(hash, String::from_utf8_lossy(name).into_owned());
        }
    }
    Some(out)
}

/// Monta um pacote HERF. Reproduz o original byte a byte quando recebe as mesmas
/// entradas: índice ordenado por hash (o jogo usa busca binária), dados na mesma
/// ordem, cada um alinhado em 4 bytes com zeros, e o fim do arquivo também.
pub fn write(entries: &[(u32, Vec<u8>)]) -> Vec<u8> {
    let mut sorted: Vec<&(u32, Vec<u8>)> = entries.iter().collect();
    sorted.sort_by_key(|e| e.0);
    let n = sorted.len();
    let mut out = Vec::with_capacity(8 + 12 * n + entries.iter().map(|e| e.1.len() + 3).sum::<usize>());
    out.extend(MAGIC.to_le_bytes());
    out.extend((n as u32).to_le_bytes());
    out.resize(8 + 12 * n, 0);
    for (i, (hash, data)) in sorted.iter().enumerate() {
        while out.len() % 4 != 0 {
            out.push(0);
        }
        let off = out.len() as u32;
        out[8 + 12 * i..8 + 12 * i + 4].copy_from_slice(&hash.to_le_bytes());
        out[8 + 12 * i + 4..8 + 12 * i + 8].copy_from_slice(&(data.len() as u32).to_le_bytes());
        out[8 + 12 * i + 8..8 + 12 * i + 12].copy_from_slice(&off.to_le_bytes());
        out.extend(data);
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

/// Monta um `erf.dict` (dicionário de nomes), ordenado por hash.
pub fn write_name_dict(names: &[(u32, String)]) -> Vec<u8> {
    let mut v: Vec<&(u32, String)> = names.iter().collect();
    v.sort_by_key(|e| e.0);
    let mut out = MAGIC.to_le_bytes().to_vec();
    out.extend((v.len() as u32).to_le_bytes());
    for (h, n) in v {
        out.extend(h.to_le_bytes());
        let mut name = n.as_bytes().to_vec();
        name.resize(128, 0);
        out.extend(name);
    }
    out
}

/// Recupera os nomes de todos os pacotes de uma ROM: primeiro o `erf.dict`
/// oficial; o ataque de dicionário preenche o resto.
pub fn recover_names(rom: &crate::nds::Rom) -> Result<HashMap<u32, String>> {
    let mut dict = NameRecovery::default();
    dict.add_bytes(rom.arm9()?);
    let mut wanted = HashSet::new();
    let mut official = HashMap::new();
    for f in &rom.files {
        let data = rom.file_data(f)?;
        dict.add_word(&f.path);
        let l = f.path.to_ascii_lowercase();
        if l.ends_with(".2da") || l.ends_with(".gda") {
            dict.add_bytes(data);
        }
        if l.ends_with(".herf") {
            let h = Herf::parse(data)?;
            for e in &h.entries {
                wanted.insert(e.hash);
                let (c, _) = h.contents(e)?;
                if let Some(d) = parse_name_dict(&c) {
                    official.extend(d);
                }
                dict.add_bytes(&c);
            }
        }
    }
    let mut names = dict.resolve(&wanted);
    names.extend(official);
    Ok(names)
}

/// Extensões vistas no jogo, usadas para gerar candidatos a partir de nomes-base.
pub const EXTENSIONS: &[&str] = &[
    "gda", "gff", "gui", "are", "dlg", "ncgr", "nclr", "nscr", "ncer", "nanr", "nsbmd", "nsbtx",
    "nsbca", "nsbta", "nsbtp", "nsbma", "emit", "small", "tlk", "utc", "uti", "utp", "ute", "plo",
    "ptm", "cbgt", "pal", "cdpth", "txt",
];

/// Extrai de `bytes` tudo que parece nome de arquivo, em ASCII e em UTF-16LE.
/// Equivale à regex `[A-Za-z0-9_-]{2,48}(\.[A-Za-z0-9]{2,5})?`.
pub fn name_candidates(bytes: &[u8], out: &mut HashSet<String>) {
    scan(bytes, out);
    // UTF-16LE: pega só as unidades < 256 (texto latino), como "latin-1".
    let narrowed: Vec<u8> = bytes
        .chunks_exact(2)
        .filter_map(|p| {
            let u = u16::from_le_bytes([p[0], p[1]]);
            (u < 256).then_some(u as u8)
        })
        .collect();
    scan(&narrowed, out);
}

fn scan(s: &[u8], out: &mut HashSet<String>) {
    let word = |c: u8| c.is_ascii_alphanumeric() || c == b'_' || c == b'-';
    let mut i = 0;
    while i < s.len() {
        if !word(s[i]) {
            i += 1;
            continue;
        }
        let mut run = 0;
        while i + run < s.len() && word(s[i + run]) && run < 48 {
            run += 1;
        }
        if run < 2 {
            i += 1;
            continue;
        }
        let mut end = i + run;
        if end < s.len() && s[end] == b'.' {
            let mut k = 0;
            while end + 1 + k < s.len() && s[end + 1 + k].is_ascii_alphanumeric() && k < 5 {
                k += 1;
            }
            if k >= 2 {
                end += 1 + k;
            }
        }
        out.insert(String::from_utf8_lossy(&s[i..end]).into_owned());
        i = end;
    }
}

/// Gera variações: o próprio nome, `base.EXT`, `base.EXT.small`, `nome.small`.
fn expand(word: &str, mut f: impl FnMut(String)) {
    let stem = word.rsplit_once('.').map(|(s, _)| s).unwrap_or(word);
    f(word.to_string());
    for e in EXTENSIONS {
        f(format!("{stem}.{e}"));
        f(format!("{stem}.{e}.small"));
    }
    if !word.to_ascii_lowercase().ends_with(".small") {
        f(format!("{word}.small"));
    }
}

/// Ataque de dicionário para recuperar nomes a partir dos hashes.
#[derive(Default)]
pub struct NameRecovery {
    words: HashSet<String>,
}

impl NameRecovery {
    pub fn add_bytes(&mut self, bytes: &[u8]) {
        name_candidates(bytes, &mut self.words);
    }

    pub fn add_word(&mut self, w: &str) {
        self.words.insert(w.to_string());
    }

    /// Resolve os hashes pedidos. Determinístico: em colisão, vence o menor nome
    /// em ordem alfabética.
    pub fn resolve(&self, wanted: &HashSet<u32>) -> HashMap<u32, String> {
        let sorted: BTreeSet<&String> = self.words.iter().collect();
        let mut found: HashMap<u32, String> = HashMap::new();
        for w in sorted {
            expand(w, |cand| {
                let h = hash_resource_name(cand.as_bytes());
                if wanted.contains(&h) {
                    found.entry(h).and_modify(|old| {
                        if cand < *old {
                            *old = cand.clone();
                        }
                    }).or_insert(cand);
                }
            });
        }
        found
    }
}

/// Descobre a extensão pela assinatura quando o nome é desconhecido.
pub fn guess_extension(data: &[u8]) -> &'static str {
    match data.get(..4) {
        Some(b"GFF ") => "gff",
        Some(b"RGCN") => "ncgr",
        Some(b"RLCN") => "nclr",
        Some(b"RCSN") => "nscr",
        Some(b"RECN") => "ncer",
        Some(b"RNAN") => "nanr",
        Some(b"BMD0") => "nsbmd",
        Some(b"BTX0") => "nsbtx",
        Some(b"BCA0") => "nsbca",
        Some(b"BTA0") => "nsbta",
        Some(b"BTP0") => "nsbtp",
        Some(b"BMA0") => "nsbma",
        Some(b"2DA ") => "2da",
        Some(b"SDAT") => "sdat",
        _ => "bin",
    }
}

/// Uma entrada já resolvida: nome final (sem `.small`) e conteúdo aberto.
pub struct Resolved {
    pub hash: u32,
    pub name: String,
    pub named: bool,
    pub was_small: bool,
    pub data: Vec<u8>,
}

/// Abre todas as entradas, aplica os nomes recuperados e valida:
/// um `.small` só pode ter nome terminado em `.small` (senão foi colisão de hash).
pub fn resolve_all(herf: &Herf, names: &HashMap<u32, String>) -> Result<Vec<Resolved>> {
    herf.entries
        .iter()
        .map(|e| {
            let (data, was_small) = herf.contents(e)?;
            let mut name = names.get(&e.hash).cloned();
            if let Some(n) = &name {
                if was_small != n.to_ascii_lowercase().ends_with(".small") {
                    name = None; // colisão: o nome não condiz com o conteúdo
                }
            }
            let named = name.is_some();
            let name = match name {
                Some(n) if was_small => n[..n.len() - 6].to_string(),
                Some(n) => n,
                None => format!("_unk_{:08x}.{}", e.hash, guess_extension(&data)),
            };
            Ok(Resolved { hash: e.hash, name, named, was_small, data })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_ignora_maiusculas() {
        assert_eq!(hash_resource_name(b"areas.gda"), hash_resource_name(b"AREAS.GDA"));
        assert_eq!(hash_resource_name(b""), 5381);
    }

    #[test]
    fn candidatos_ascii_e_utf16() {
        let mut s = HashSet::new();
        name_candidates(b"..CBT_Ambush.ncgr\0x", &mut s);
        assert!(s.contains("CBT_Ambush.ncgr"));
        let utf16: Vec<u8> = "a1c2_knuckles".encode_utf16().flat_map(|u| u.to_le_bytes()).collect();
        name_candidates(&utf16, &mut s);
        assert!(s.contains("a1c2_knuckles"));
    }
}

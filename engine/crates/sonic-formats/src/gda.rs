//! Tabela binária GDA (GFF4 tipo `G2DA`).
//!
//! Raiz `gtop`: lista 10002 de `colm { 10001: hash do nome, 10999: tipo }` e
//! lista 10003 de `rows` com um campo por coluna, na mesma ordem.
//! O nome da coluna não está no arquivo: só `CRC32(nome.lower() em UTF-16LE)`.
//! Os nomes conhecidos vêm do xoreos (`data/gda_columns_xoreos.json`, GPLv3).

use crate::gff4::Gff4;
use crate::Result;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::OnceLock;

/// CRC32 (IEEE) do nome em minúsculas, codificado em UTF-16LE.
pub fn column_hash(name: &str) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for u in name.to_lowercase().encode_utf16() {
        for b in u.to_le_bytes() {
            crc ^= b as u32;
            for _ in 0..8 {
                crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
            }
        }
    }
    !crc
}

pub fn known_columns() -> &'static HashMap<u32, String> {
    static MAP: OnceLock<HashMap<u32, String>> = OnceLock::new();
    MAP.get_or_init(|| {
        let v: HashMap<String, String> = serde_json::from_str(include_str!("../data/gda_columns_xoreos.json")).unwrap_or_default();
        v.into_iter().filter_map(|(k, n)| k.parse().ok().map(|h| (h, n))).collect()
    })
}

pub struct Table {
    pub columns: Vec<String>,
    pub column_hashes: Vec<u32>,
    pub rows: Vec<Vec<Value>>,
}

pub fn is_gda(d: &[u8]) -> bool {
    d.len() > 16 && d.starts_with(b"GFF V4.0") && &d[12..16] == b"G2DA"
}

pub fn read(data: &[u8]) -> Result<Table> {
    let root = Gff4::parse(data)?.root()?;
    let known = known_columns();
    let column_hashes: Vec<u32> = root
        .get("10002")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|c| c.get("10001").and_then(|h| h.as_u64()).map(|h| h as u32)).collect())
        .unwrap_or_default();
    let columns = column_hashes.iter().map(|h| known.get(h).cloned().unwrap_or_else(|| format!("col_{h:08x}"))).collect();
    let rows = root
        .get("10003")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|r| r.as_object().map(|o| o.iter().filter(|(k, _)| *k != "_type").map(|(_, v)| v.clone()).collect()).unwrap_or_default())
                .collect()
        })
        .unwrap_or_default();
    Ok(Table { columns, column_hashes, rows })
}

// ---------------------------------------------------------------------------
// Modelo tipado: leitura E escrita. Reproduz o arquivo original byte a byte
// (verificado nas 229 tabelas do jogo), o que permite editar com segurança.
//
// Layout dos dados (a partir de data_offset):
//   raiz gtop: u32 rel(lista colm), u32 rel(lista rows)
//   colm: u32 n, n × { u32 hash, u8 tipo, 3 bytes 0xFF }
//   rows: u32 n, n × struct de tamanho fixo (template "rows"); bytes livres = 0xFF
//   strings (tipo 20, por referência): { u32 tamanho, bytes incluindo o '\0' },
//   sem repetição, alinhadas em 4 bytes com 0xFF, na ordem em que aparecem.
// ---------------------------------------------------------------------------

use crate::bytes::{slice, u32_at, u8_at};
use crate::Error;

const NULL_REF: u32 = 0xFFFF_FFFF;

/// Valor de uma célula. As tabelas do jogo só usam estes quatro tipos de campo.
#[derive(Clone, Debug, PartialEq)]
pub enum Cell {
    /// tipo 5: inteiro com sinal de 32 bits
    Int(i32),
    /// tipo 0: byte sem sinal
    Byte(u8),
    /// tipo 18: ponto fixo do DS (valor bruto; real = bruto / 4096)
    Fixed(i32),
    /// tipo 20 (referência): texto ASCII; `None` = sem texto
    Str(Option<Vec<u8>>),
}

#[derive(Clone, Debug)]
pub struct RowField {
    pub label: u32,
    pub type_flags: u32,
    pub offset: u32,
}

#[derive(Clone)]
pub struct Gda {
    /// Cabeçalho + templates (tudo antes de data_offset): não muda ao editar linhas.
    header: Vec<u8>,
    /// (hash do nome, tipo) de cada coluna.
    pub columns: Vec<(u32, u8)>,
    pub row_size: usize,
    pub fields: Vec<RowField>,
    pub rows: Vec<Vec<Cell>>,
}

impl Gda {
    pub fn parse(d: &[u8]) -> Result<Self> {
        if !is_gda(d) {
            return Err(Error::Invalid("não é uma tabela GDA".into()));
        }
        let data_off = u32_at(d, 0x18, "GDA")? as usize;
        let n_tmpl = u32_at(d, 0x14, "GDA")? as usize;
        let mut rows_tmpl = None;
        for i in 0..n_tmpl {
            let b = 0x1C + 16 * i;
            if slice(d, b, 4, "GDA")? == b"rows" {
                let nf = u32_at(d, b + 4, "GDA")? as usize;
                let fo = u32_at(d, b + 8, "GDA")? as usize;
                let size = u32_at(d, b + 12, "GDA")? as usize;
                let fields = (0..nf)
                    .map(|k| Ok(RowField { label: u32_at(d, fo + 12 * k, "GDA")?, type_flags: u32_at(d, fo + 12 * k + 4, "GDA")?, offset: u32_at(d, fo + 12 * k + 8, "GDA")? }))
                    .collect::<Result<Vec<_>>>()?;
                rows_tmpl = Some((size, fields));
            }
        }
        let (row_size, fields) = rows_tmpl.ok_or(Error::Invalid("GDA sem template 'rows'".into()))?;
        let colm_rel = u32_at(d, data_off, "GDA")? as usize;
        let rows_rel = u32_at(d, data_off + 4, "GDA")? as usize;
        let nc = u32_at(d, data_off + colm_rel, "GDA")? as usize;
        let columns = (0..nc)
            .map(|i| { let b = data_off + colm_rel + 4 + 8 * i; Ok((u32_at(d, b, "GDA")?, u8_at(d, b + 4, "GDA")?)) })
            .collect::<Result<Vec<_>>>()?;
        let nr = u32_at(d, data_off + rows_rel, "GDA")? as usize;
        let mut rows = Vec::with_capacity(nr);
        for r in 0..nr {
            let base = data_off + rows_rel + 4 + row_size * r;
            let mut row = Vec::with_capacity(fields.len());
            for f in &fields {
                let o = base + f.offset as usize;
                row.push(match f.type_flags & 0xFFFF {
                    5 => Cell::Int(u32_at(d, o, "GDA")? as i32),
                    0 => Cell::Byte(u8_at(d, o, "GDA")?),
                    18 => Cell::Fixed(u32_at(d, o, "GDA")? as i32),
                    20 => {
                        let rel = u32_at(d, o, "GDA")?;
                        if rel == NULL_REF {
                            Cell::Str(None)
                        } else {
                            let so = data_off + rel as usize;
                            let n = u32_at(d, so, "GDA")? as usize;
                            Cell::Str(Some(slice(d, so + 4, n, "GDA")?.to_vec()))
                        }
                    }
                    t => return Err(Error::Invalid(format!("GDA: tipo de campo {t} não suportado"))),
                });
            }
            rows.push(row);
        }
        Ok(Gda { header: d[..data_off].to_vec(), columns, row_size, fields, rows })
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        const PAD: u8 = 0xFF;
        let mut out: Vec<u8> = Vec::new();
        let colm_rel = 8u32;
        let rows_rel = colm_rel + 4 + 8 * self.columns.len() as u32;
        out.extend(colm_rel.to_le_bytes());
        out.extend(rows_rel.to_le_bytes());
        out.extend((self.columns.len() as u32).to_le_bytes());
        for (h, t) in &self.columns {
            out.extend(h.to_le_bytes());
            out.extend([*t, PAD, PAD, PAD]);
        }
        out.extend((self.rows.len() as u32).to_le_bytes());
        let rows_start = out.len();
        out.resize(rows_start + self.row_size * self.rows.len(), PAD);
        let mut seen: HashMap<Vec<u8>, u32> = HashMap::new();
        for (r, row) in self.rows.iter().enumerate() {
            for (f, cell) in self.fields.iter().zip(row) {
                let o = rows_start + self.row_size * r + f.offset as usize;
                match cell {
                    Cell::Int(v) | Cell::Fixed(v) => out[o..o + 4].copy_from_slice(&v.to_le_bytes()),
                    Cell::Byte(v) => out[o] = *v,
                    Cell::Str(None) => out[o..o + 4].copy_from_slice(&NULL_REF.to_le_bytes()),
                    Cell::Str(Some(s)) => {
                        let rel = match seen.get(s) {
                            Some(&rel) => rel,
                            None => {
                                while !out.len().is_multiple_of(4) {
                                    out.push(PAD);
                                }
                                let rel = out.len() as u32;
                                out.extend((s.len() as u32).to_le_bytes());
                                out.extend(s);
                                seen.insert(s.clone(), rel);
                                rel
                            }
                        };
                        out[o..o + 4].copy_from_slice(&rel.to_le_bytes());
                    }
                }
            }
        }
        let mut file = self.header.clone();
        file.extend(out);
        file
    }

    /// Nome legível de cada coluna (ou `col_<hash>` se desconhecido).
    pub fn column_names(&self) -> Vec<String> {
        let known = known_columns();
        self.columns.iter().map(|(h, _)| known.get(h).cloned().unwrap_or_else(|| format!("col_{h:08x}"))).collect()
    }

    /// Converte uma célula em texto para planilha. Textos perdem o '\0' final.
    pub fn cell_to_text(c: &Cell) -> String {
        match c {
            Cell::Int(v) => v.to_string(),
            Cell::Byte(v) => v.to_string(),
            Cell::Fixed(v) => format!("{}", *v as f64 / 4096.0),
            Cell::Str(None) => String::new(),
            Cell::Str(Some(s)) => String::from_utf8_lossy(s.strip_suffix(b"\0").unwrap_or(s)).into_owned(),
        }
    }

    /// Converte texto da planilha de volta para o tipo do campo `field`.
    pub fn cell_from_text(&self, field: usize, text: &str) -> std::result::Result<Cell, String> {
        let t = text.trim();
        let ty = self.fields.get(field).map(|f| f.type_flags & 0xFFFF).ok_or("coluna a mais")?;
        let num = |t: &str| -> std::result::Result<f64, String> {
            if t.is_empty() { return Ok(0.0); }
            t.replace(',', ".").parse::<f64>().map_err(|_| format!("'{t}' não é número"))
        };
        Ok(match ty {
            5 => Cell::Int(if t.is_empty() { 0 } else { t.parse::<i64>().map_err(|_| format!("'{t}' não é inteiro"))? as i32 }),
            0 => Cell::Byte(if t.is_empty() { 0 } else { t.parse::<u8>().map_err(|_| format!("'{t}' não é um byte (0-255)"))? }),
            18 => Cell::Fixed((num(t)? * 4096.0).round() as i32),
            20 => Cell::Str(if text.is_empty() {
                None
            } else {
                if !text.is_ascii() {
                    return Err(format!("'{text}': nomes de arquivo/identificadores precisam ser ASCII (sem acentos)"));
                }
                let mut v = text.as_bytes().to_vec();
                v.push(0);
                Some(v)
            }),
            _ => return Err(format!("tipo {ty} não suportado")),
        })
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn hash_de_coluna_bate_com_a_tabela_do_xoreos() {
        let known = super::known_columns();
        let h = super::column_hash("Name");
        assert_eq!(known.get(&h).map(String::as_str), Some("Name"));
    }
}

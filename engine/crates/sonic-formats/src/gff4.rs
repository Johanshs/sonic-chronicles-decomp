//! GFF V4.0 (BioWare, mesmo contêiner do Dragon Age: Origins) → `serde_json::Value`.
//!
//! ```text
//! "GFF " "V4.0" plataforma(4) tipo(4) versão_do_tipo(4)
//! u32 struct_count, u32 data_offset
//! templates: struct_count × { label(4), field_count, field_offset, struct_size }
//! campos:    field_count × { u32 label, u32 tipo | flags << 16, u32 offset }
//! dados a partir de data_offset; a struct raiz (template 0) está em data_offset.
//! ```
//! Campos têm NÚMEROS como rótulo (ex.: TLK: 19002 = id, 19003 = texto).
//! Flags: `0x8000` lista, `0x4000` struct (tipo = índice do template), `0x2000` referência.
//!
//! Particularidades do Sonic Chronicles (DS) em relação ao PC:
//! - strings `ECString` podem ser de 8 bits (TLK) ou UTF-16 (DLG/ARE);
//! - tipo 18 = ponto fixo do DS (20.12); tipo 20 = string ASCII inline.

use crate::bytes::{expect_magic, slice, u32_at};
use crate::{Error, Result};
use serde_json::{json, Map, Value};

const LIST: u32 = 0x8000;
const STRUCT: u32 = 0x4000;
const REF: u32 = 0x2000;
const NULL: u32 = 0xFFFF_FFFF;
const GENERIC: u32 = 0xFFFF;

pub struct Template {
    pub label: String,
    pub size: u32,
    pub fields: Vec<(u32, u32, u32)>, // (label, tipo|flags, offset)
}

pub struct Gff4<'a> {
    d: &'a [u8],
    pub file_type: String,
    pub type_version: String,
    pub data_offset: usize,
    pub templates: Vec<Template>,
}

fn simple_size(t: u32) -> Option<usize> {
    Some(match t {
        0 | 1 => 1,
        2 | 3 => 2,
        4 | 5 | 8 | 18 => 4,
        6 | 7 | 9 => 8,
        10 => 12,
        12 | 13 | 15 => 16,
        16 => 64,
        14 => 4,
        17 => 8,
        GENERIC => 8,
        _ => return None,
    })
}

impl<'a> Gff4<'a> {
    pub fn is_gff4(d: &[u8]) -> bool {
        d.starts_with(b"GFF V4.0")
    }

    pub fn parse(d: &'a [u8]) -> Result<Self> {
        expect_magic(d, 0, b"GFF V4.0", "GFF4")?;
        let txt = |o, n| -> Result<String> { Ok(String::from_utf8_lossy(slice(d, o, n, "GFF4")?).trim().to_string()) };
        let count = u32_at(d, 0x14, "GFF4")? as usize;
        let data_offset = u32_at(d, 0x18, "GFF4")? as usize;
        let mut templates = Vec::with_capacity(count);
        for i in 0..count {
            let b = 0x1C + 16 * i;
            let label = txt(b, 4)?;
            let nf = u32_at(d, b + 4, "GFF4")? as usize;
            let fo = u32_at(d, b + 8, "GFF4")? as usize;
            let size = u32_at(d, b + 12, "GFF4")?;
            let fields = (0..nf)
                .map(|k| Ok((u32_at(d, fo + 12 * k, "GFF4")?, u32_at(d, fo + 12 * k + 4, "GFF4")?, u32_at(d, fo + 12 * k + 8, "GFF4")?)))
                .collect::<Result<Vec<_>>>()?;
            templates.push(Template { label, size, fields });
        }
        Ok(Gff4 { d, file_type: txt(12, 4)?, type_version: txt(16, 4)?, data_offset, templates })
    }

    pub fn root(&self) -> Result<Value> {
        if self.templates.is_empty() {
            return Err(Error::Invalid("GFF4 sem templates".into()));
        }
        Ok(self.read_struct(0, self.data_offset, 0))
    }

    fn u32(&self, o: usize) -> Result<u32> {
        u32_at(self.d, o, "GFF4")
    }

    /// ECString: u32 tamanho + texto. Heurística: em UTF-16 de texto latino,
    /// quase todo byte ímpar é zero.
    fn string(&self, rel: u32) -> Value {
        if rel == NULL {
            return Value::Null;
        }
        let o = self.data_offset + rel as usize;
        let Ok(n) = self.u32(o) else { return Value::Null };
        let n = n as usize;
        if let Some(raw) = self.d.get(o + 4..o + 4 + 2 * n) {
            let zeros = raw.iter().skip(1).step_by(2).filter(|&&b| b == 0).count();
            if n > 0 && zeros * 10 >= n * 9 {
                let units: Vec<u16> = raw.chunks_exact(2).map(|p| u16::from_le_bytes([p[0], p[1]])).collect();
                return Value::String(String::from_utf16_lossy(&units).trim_end_matches('\0').to_string());
            }
        }
        match self.d.get(o + 4..o + 4 + n) {
            Some(b) => Value::String(cp1252(b).trim_end_matches('\0').to_string()),
            None => Value::Null,
        }
    }

    fn value(&self, t: u32, o: usize) -> Result<Value> {
        let d = self.d;
        let f32_at = |o| -> Result<f64> { Ok(f32::from_bits(u32_at(d, o, "GFF4")?) as f64) };
        Ok(match t {
            0 => json!(*d.get(o).ok_or(Error::Truncated { what: "GFF4", offset: o })?),
            1 => json!(*d.get(o).ok_or(Error::Truncated { what: "GFF4", offset: o })? as i8),
            2 => json!(u16::from_le_bytes(slice(d, o, 2, "GFF4")?.try_into().unwrap())),
            3 => json!(i16::from_le_bytes(slice(d, o, 2, "GFF4")?.try_into().unwrap())),
            4 => json!(self.u32(o)?),
            5 => json!(self.u32(o)? as i32),
            6 => json!(u64::from_le_bytes(slice(d, o, 8, "GFF4")?.try_into().unwrap())),
            7 => json!(i64::from_le_bytes(slice(d, o, 8, "GFF4")?.try_into().unwrap())),
            8 => json!(f32_at(o)?),
            9 => json!(f64::from_le_bytes(slice(d, o, 8, "GFF4")?.try_into().unwrap())),
            10 | 12 | 13 | 15 | 16 => {
                let n = simple_size(t).unwrap() / 4;
                Value::Array((0..n).map(|k| f32_at(o + 4 * k).map(|v| json!(v))).collect::<Result<_>>()?)
            }
            14 => self.string(self.u32(o)?),
            17 => {
                let rel = self.u32(o + 4)?;
                json!({ "tlk_id": self.u32(o)?, "text": if rel == 0 || rel == NULL { Value::Null } else { self.string(rel) } })
            }
            18 => json!(self.u32(o)? as i32 as f64 / 4096.0),
            20 => {
                let n = self.u32(o)? as usize;
                Value::String(cp1252(slice(d, o + 4, n, "GFF4")?).trim_end_matches('\0').to_string())
            }
            GENERIC => {
                let tf = self.u32(o)?;
                let rel = self.u32(o + 4)?;
                if rel == NULL {
                    Value::Null
                } else {
                    self.field(tf & 0xFFFF, tf >> 16, self.data_offset + rel as usize, 1)
                        .unwrap_or_else(|_| json!({ "generic_raw": [tf, rel] }))
                }
            }
            _ => json!({ "unknown_type": t }),
        })
    }

    fn read_struct(&self, idx: usize, o: usize, depth: usize) -> Value {
        let Some(t) = self.templates.get(idx) else { return json!({ "erro": "template inexistente" }) };
        let mut m = Map::new();
        m.insert("_type".into(), Value::String(t.label.clone()));
        for &(label, tf, fo) in &t.fields {
            let v = self
                .field(tf & 0xFFFF, tf >> 16, o + fo as usize, depth)
                .unwrap_or_else(|e| json!({ "erro": format!("tipo {tf:#x}: {e}") }));
            m.insert(label.to_string(), v);
        }
        Value::Object(m)
    }

    fn field(&self, t: u32, flags: u32, o: usize, depth: usize) -> Result<Value> {
        if depth > 32 {
            return Ok(Value::String("<profundidade>".into()));
        }
        let (is_list, is_struct, is_ref) = (flags & LIST != 0, flags & STRUCT != 0, flags & REF != 0);
        if is_list {
            let rel = self.u32(o)?;
            if rel == NULL {
                return Ok(Value::Array(vec![]));
            }
            let lo = self.data_offset + rel as usize;
            let n = self.u32(lo)? as usize;
            if n > 1_000_000 {
                return Err(Error::Invalid("lista grande demais".into()));
            }
            let mut items = Vec::with_capacity(n);
            let mut p = lo + 4;
            for _ in 0..n {
                if t == GENERIC && !is_struct {
                    items.push(self.value(t, p)?);
                    p += 8;
                } else if is_struct && !is_ref {
                    items.push(self.read_struct(t as usize, p, depth + 1));
                    p += self.templates.get(t as usize).map(|x| x.size as usize).unwrap_or(4);
                } else if is_struct || is_ref {
                    let r = self.u32(p)?;
                    items.push(if r == NULL {
                        Value::Null
                    } else if is_struct {
                        self.read_struct(t as usize, self.data_offset + r as usize, depth + 1)
                    } else {
                        self.value(t, self.data_offset + r as usize)?
                    });
                    p += 4;
                } else {
                    items.push(self.value(t, p)?);
                    p += simple_size(t).unwrap_or(4);
                }
            }
            return Ok(Value::Array(items));
        }
        if is_struct {
            if is_ref {
                let r = self.u32(o)?;
                return Ok(if r == NULL { Value::Null } else { self.read_struct(t as usize, self.data_offset + r as usize, depth + 1) });
            }
            return Ok(self.read_struct(t as usize, o, depth + 1));
        }
        if is_ref {
            let r = self.u32(o)?;
            return if r == NULL { Ok(Value::Null) } else { self.value(t, self.data_offset + r as usize) };
        }
        self.value(t, o)
    }
}

/// Windows-1252 → String (os acentos dos textos em francês/alemão/espanhol).
pub fn cp1252(b: &[u8]) -> String {
    const HIGH: [char; 32] = [
        '€', '\u{81}', '‚', 'ƒ', '„', '…', '†', '‡', 'ˆ', '‰', 'Š', '‹', 'Œ', '\u{8d}', 'Ž', '\u{8f}',
        '\u{90}', '‘', '’', '“', '”', '•', '–', '—', '˜', '™', 'š', '›', 'œ', '\u{9d}', 'ž', 'Ÿ',
    ];
    b.iter()
        .map(|&c| match c {
            0x80..=0x9F => HIGH[(c - 0x80) as usize],
            _ => c as char,
        })
        .collect()
}

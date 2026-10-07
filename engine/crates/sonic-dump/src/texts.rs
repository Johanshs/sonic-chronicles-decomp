//! Exportação de textos, diálogos, tabelas e GFF4 → JSON.

use crate::{write, Asset};
use rayon::prelude::*;
use serde_json::{json, Value};
use sonic_formats::{gda, gff4::Gff4, tlk, twoda};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

type Res<T> = Result<T, Box<dyn std::error::Error>>;

/// Campo CSV com aspas quando precisa (vírgula, aspas, quebra de linha).
pub fn csv_field(s: &str) -> String {
    if s.contains([',', '"', '\n', '\r']) {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

fn csv_line(fields: impl IntoIterator<Item = String>) -> String {
    fields.into_iter().map(|f| csv_field(&f)).collect::<Vec<_>>().join(",") + "\n"
}

fn value_to_cell(v: &Value) -> String {
    match v {
        Value::Null => String::new(),
        Value::String(s) => s.clone(),
        Value::Object(o) if o.contains_key("tlk_id") => o["tlk_id"].to_string(),
        other => other.to_string(),
    }
}

fn find<'a>(assets: &'a [Asset], name: &str) -> Option<&'a Asset> {
    assets.iter().find(|a| a.name.eq_ignore_ascii_case(name))
}

pub fn export_texts(loose: &[Asset], assets: &[Asset], out: &Path) -> Res<Value> {
    // 1. tabela com os 5 idiomas lado a lado
    let mut langs: Vec<(&str, BTreeMap<u32, String>)> = Vec::new();
    for (code, file) in tlk::LANGUAGES {
        if let Some(a) = find(loose, file) {
            langs.push((code, tlk::read(&a.data)?));
        }
    }
    let ids: BTreeSet<u32> = langs.iter().flat_map(|(_, m)| m.keys().copied()).collect();
    let mut csv = csv_line(std::iter::once("id".to_string()).chain(langs.iter().map(|(c, _)| c.to_string())));
    for id in &ids {
        csv += &csv_line(std::iter::once(id.to_string()).chain(langs.iter().map(|(_, m)| m.get(id).cloned().unwrap_or_default())));
    }
    write(&out.join("textos/textos_5_idiomas.csv"), csv.as_bytes())?;

    // 2. roteiro por idioma (estrutura dos nós NTRY descoberta na análise)
    //    12201 texto (id TLK) · 12202 retrato (quem fala + emoção) · 12400 próximos nós
    let dialogs: Vec<(&Asset, Value)> = assets
        .iter()
        .filter(|a| a.name.to_ascii_lowercase().ends_with(".dlg") && Gff4::is_gff4(&a.data))
        .filter_map(|a| Gff4::parse(&a.data).and_then(|g| g.root()).ok().map(|r| (a, r)))
        .collect();
    let mut lines_total = 0;
    for (code, table) in &langs {
        let mut txt = String::new();
        for (a, root) in &dialogs {
            let nodes = root.get("12002").and_then(Value::as_array).cloned().unwrap_or_default();
            let starts: Vec<String> = root.get("12000").and_then(Value::as_array).map(|v| v.iter().filter_map(|s| s.get("12001")).map(|x| x.to_string()).collect()).unwrap_or_default();
            txt += &format!("\n=== {}  ({} nós, entradas: [{}])\n", a.name, nodes.len(), starts.join(", "));
            for (i, nd) in nodes.iter().enumerate() {
                let Some(id) = nd.get("12201").and_then(|t| t.get("tlk_id")).and_then(Value::as_u64) else { continue };
                let Some(line) = table.get(&(id as u32)).filter(|s| !s.is_empty()) else { continue };
                let portrait = nd.get("12202").and_then(Value::as_str).unwrap_or("");
                let who = portrait.strip_prefix("prtl_").or_else(|| portrait.strip_prefix("PRTL_")).unwrap_or(if portrait.is_empty() { "?" } else { portrait });
                let links: Vec<String> = nd.get("12400").and_then(Value::as_array).map(|v| v.iter().map(|x| x.to_string()).collect()).unwrap_or_default();
                txt += &format!("[{i:3}] {who:>14}: {line}{}\n", if links.is_empty() { String::new() } else { format!("   -> [{}]", links.join(", ")) });
                if *code == "en" {
                    lines_total += 1;
                }
            }
        }
        write(&out.join(format!("textos/roteiro_{code}.txt")), txt.as_bytes())?;
    }
    Ok(json!({"idiomas": langs.len(), "ids_de_texto": ids.len(), "dialogos": dialogs.len(), "falas": lines_total}))
}

pub fn export_tables(loose: &[Asset], assets: &[Asset], out: &Path) -> Res<Value> {
    let mut n_gda = 0;
    let mut n_2da = 0;
    let mut hashes = BTreeSet::new();
    let mut named = BTreeSet::new();
    for a in assets.iter().chain(loose) {
        let stem = a.name.rsplit('/').next().unwrap_or(&a.name);
        let stem = stem.rsplit_once('.').map(|(s, _)| s).unwrap_or(stem);
        if gda::is_gda(&a.data) {
            let Ok(t) = gda::read(&a.data) else { continue };
            for (h, c) in t.column_hashes.iter().zip(&t.columns) {
                hashes.insert(*h);
                if !c.starts_with("col_") {
                    named.insert(*h);
                }
            }
            let mut csv = csv_line(t.columns.iter().cloned());
            for r in &t.rows {
                csv += &csv_line(r.iter().map(value_to_cell));
            }
            write(&out.join(format!("tabelas/gda/{stem}.csv")), csv.as_bytes())?;
            n_gda += 1;
        } else if twoda::is_2da(&a.data) {
            let t = twoda::read(&a.data);
            let mut csv = csv_line(std::iter::once(String::new()).chain(t.columns.iter().cloned()));
            for r in &t.rows {
                csv += &csv_line(r.iter().cloned());
            }
            let ext = a.name.rsplit_once('.').map(|(_, e)| e).unwrap_or("2da");
            write(&out.join(format!("tabelas/2da/{stem}.{ext}.csv")), csv.as_bytes())?;
            n_2da += 1;
        }
    }
    Ok(json!({"gda": n_gda, "2da": n_2da, "colunas_gda": hashes.len(), "colunas_com_nome": named.len()}))
}

pub fn export_gff_json(assets: &[Asset], out: &Path) -> Res<usize> {
    let done: Vec<bool> = assets
        .par_iter()
        .filter(|a| Gff4::is_gff4(&a.data))
        .map(|a| {
            let Ok(g) = Gff4::parse(&a.data) else { return false };
            let Ok(root) = g.root() else { return false };
            let v = json!({"tipo": g.file_type, "versao": g.type_version, "raiz": root});
            let path = out.join("json").join(&a.pack).join(format!("{}.json", a.name));
            serde_json::to_string_pretty(&v).ok().map(|s| write(&path, s.as_bytes()).is_ok()).unwrap_or(false)
        })
        .collect();
    Ok(done.iter().filter(|&&b| b).count())
}

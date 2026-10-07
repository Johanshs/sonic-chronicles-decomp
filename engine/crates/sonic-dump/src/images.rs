//! Exportação de imagens: sprites/interface (NCGR) e cenários das áreas.

use crate::{safe_name, write, Asset};
use rayon::prelude::*;
use serde_json::{json, Value};
use sonic_formats::{background, gff4::Gff4, image::Rgba, nitro};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

type Res<T> = Result<T, Box<dyn std::error::Error>>;

/// Resultado de uma imagem: (nome, método da paleta, paleta, (pacote, nome-base, imagem) se renderizou)
type Rendered = (String, String, Option<String>, Option<(String, String, Rgba)>);

fn lower(s: &str) -> String {
    s.to_ascii_lowercase()
}

fn stem(s: &str) -> &str {
    s.rsplit_once('.').map(|(a, _)| a).unwrap_or(s)
}

/// Prefixo de um nome para agrupar ("PRTL_TailsSca" -> "prtl", "a1_s1_mm" -> "a1").
fn prefix(s: &str) -> String {
    lower(s.split(['_', '-']).next().unwrap_or(s).trim_end_matches(|c: char| c.is_ascii_digit()))
}

/// Coleta pares (imagem, paleta) citados juntos num mesmo struct de qualquer GFF4
/// (as telas .gui usam struct `IMG ` com campo 60004 = ncgr e 60015 = nclr).
fn gui_pairs(assets: &[Asset]) -> HashMap<String, BTreeMap<String, usize>> {
    fn walk(v: &Value, out: &mut HashMap<String, BTreeMap<String, usize>>) {
        match v {
            Value::Object(o) => {
                let strs: Vec<&str> = o.values().filter_map(Value::as_str).collect();
                for g in strs.iter().filter(|s| lower(s).ends_with(".ncgr")) {
                    for p in strs.iter().filter(|s| lower(s).ends_with(".nclr")) {
                        *out.entry(lower(g)).or_default().entry(lower(p)).or_default() += 1;
                    }
                }
                o.values().for_each(|x| walk(x, out));
            }
            Value::Array(a) => a.iter().for_each(|x| walk(x, out)),
            _ => {}
        }
    }
    let mut out = HashMap::new();
    for a in assets.iter().filter(|a| Gff4::is_gff4(&a.data)) {
        if let Ok(r) = Gff4::parse(&a.data).and_then(|g| g.root()) {
            walk(&r, &mut out);
        }
    }
    out
}

/// Pares (nome-base, paleta) tirados das linhas das tabelas GDA: numa linha que
/// tem um valor `*.nclr`, os outros nomes da linha usam essa paleta.
/// Ex.: creatures.gda: `PRTL_TAILS` + `PRTL_Tal.nclr` -> retratos `PRTL_TAILS*`.
fn table_pairs(assets: &[Asset]) -> Vec<(String, String)> {
    let mut map: HashMap<String, BTreeMap<String, usize>> = HashMap::new();
    for a in assets.iter().filter(|a| sonic_formats::gda::is_gda(&a.data)) {
        let Ok(t) = sonic_formats::gda::read(&a.data) else { continue };
        for row in &t.rows {
            let strs: Vec<&str> = row.iter().filter_map(Value::as_str).collect();
            let Some(pal) = strs.iter().find(|s| lower(s).ends_with(".nclr")) else { continue };
            for s in strs.iter().filter(|s| !lower(s).ends_with(".nclr") && s.len() >= 5 && s.chars().any(|c| c.is_ascii_alphabetic())) {
                *map.entry(lower(stem(s))).or_default().entry(lower(pal)).or_default() += 1;
            }
        }
    }
    let mut v: Vec<(String, String)> = map
        .into_iter()
        .filter_map(|(b, ps)| ps.into_iter().max_by_key(|(_, n)| *n).map(|(p, _)| (b, p)))
        .collect();
    v.sort_by(|a, b| b.0.len().cmp(&a.0.len()).then(a.0.cmp(&b.0))); // mais longo primeiro
    v
}

pub fn export_sprites(assets: &[Asset], out: &Path) -> Res<HashMap<String, usize>> {
    let palettes: HashMap<String, nitro::Palette> = assets
        .iter()
        .filter(|a| a.data.starts_with(b"RLCN"))
        .filter_map(|a| nitro::Palette::parse(&a.data).ok().map(|p| (lower(&a.name), p)))
        .collect();
    let pairs = gui_pairs(assets);
    let tables = table_pairs(assets);

    // paleta mais usada por prefixo, aprendida dos pares confiáveis
    let mut by_prefix: HashMap<String, BTreeMap<String, usize>> = HashMap::new();
    for (g, ps) in &pairs {
        for (p, n) in ps {
            if palettes.contains_key(p) {
                *by_prefix.entry(prefix(g)).or_default().entry(p.clone()).or_default() += n;
            }
        }
    }
    let best = |m: &BTreeMap<String, usize>| m.iter().max_by_key(|(_, n)| **n).map(|(p, _)| p.clone());
    let gray = nitro::Palette::grayscale(256);

    let results: Vec<Rendered> = assets
        .par_iter()
        .filter(|a| a.data.starts_with(b"RGCN"))
        .map(|a| {
            let key = lower(&a.name);
            let same_name = format!("{}.nclr", lower(stem(&a.name)));
            let (method, pal_name) = if let Some(p) = pairs.get(&key).and_then(&best).filter(|p| palettes.contains_key(p)) {
                ("gui", Some(p))
            } else if let Some((_, p)) = tables.iter().find(|(b, p)| lower(stem(&a.name)).starts_with(b.as_str()) && palettes.contains_key(p)) {
                ("tabela", Some(p.clone()))
            } else if palettes.contains_key(&same_name) {
                ("mesmo_nome", Some(same_name))
            } else if let Some(p) = by_prefix.get(&prefix(&a.name)).and_then(&best) {
                ("prefixo", Some(p))
            } else {
                ("cinza", None)
            };
            let pal = pal_name.as_ref().and_then(|p| palettes.get(p)).unwrap_or(&gray);
            let rendered = nitro::Tiles::parse(&a.data).ok().and_then(|t| {
                let img = t.render(pal, 0);
                let path = out.join("imagens/sprites").join(&a.pack).join(format!("{}.png", safe_name(stem(&a.name))));
                (std::fs::create_dir_all(path.parent().unwrap()).is_ok() && img.save_png(&path).is_ok())
                    .then(|| (a.pack.clone(), stem(&a.name).to_string(), img))
            });
            (format!("{}/{}", a.pack, a.name), method.to_string(), pal_name, rendered)
        })
        .collect();

    // Retratos e ícones vêm em 4 peças 64×64 (`nome_0` .. `nome_3`) que formam
    // um quadro 128×128 em 2×2 (0 1 / 2 3). Montamos a imagem inteira.
    let mut groups: BTreeMap<(String, String), BTreeMap<u32, &Rgba>> = BTreeMap::new();
    for (_, _, _, r) in &results {
        let Some((pack, st, img)) = r else { continue };
        if let Some((base, n)) = st.rsplit_once('_') {
            if let Ok(n) = n.parse::<u32>() {
                groups.entry((pack.clone(), base.to_string())).or_default().insert(n, img);
            }
        }
    }
    let mut montages = 0;
    for ((pack, base), parts) in &groups {
        let quad = parts.len() == 4 && (0..4).all(|i| parts.get(&i).is_some_and(|p| p.width == 64 && p.height == 64));
        if !quad {
            continue;
        }
        let mut m = Rgba::new(128, 128);
        for (i, p) in parts {
            m.blit(p, (i % 2) * 64, (i / 2) * 64);
        }
        let path = out.join("imagens/montadas").join(pack).join(format!("{}.png", safe_name(base)));
        let _ = std::fs::create_dir_all(path.parent().unwrap());
        if m.save_png(&path).is_ok() {
            montages += 1;
        }
    }

    let mut stats: HashMap<String, usize> = HashMap::new();
    let mut report = serde_json::Map::new();
    stats.insert("montadas_2x2".into(), montages);
    for (name, method, pal, r) in results {
        let ok = r.is_some();
        *stats.entry(if ok { method.clone() } else { "falhou".into() }).or_default() += 1;
        report.insert(name, json!({"metodo": method, "paleta": pal, "ok": ok}));
    }
    write(&out.join("imagens/_paletas.json"), serde_json::to_string_pretty(&report)?.as_bytes())?;
    Ok(stats)
}

pub fn export_backgrounds(loose: &[Asset], out: &Path) -> Res<usize> {
    let by_name: HashMap<String, &Asset> = loose.iter().map(|a| (lower(&a.name), a)).collect();
    let areas: Vec<String> = loose.iter().filter(|a| lower(&a.name).ends_with(".cbgt")).map(|a| stem(&a.name).to_string()).collect();
    let done: Vec<bool> = areas
        .par_iter()
        .map(|area| {
            let get = |ext: &str| by_name.get(&lower(&format!("{area}.{ext}"))).map(|a| a.data.as_slice());
            // variantes como "a2_s2_i05_2" não têm .2da próprio: usam o da área base
            let base = area.rsplit_once('_').filter(|(_, n)| n.chars().all(|c| c.is_ascii_digit())).map(|(b, _)| b.to_string());
            let map = get("2da").or_else(|| base.as_ref().and_then(|b| by_name.get(&lower(&format!("{b}.2da"))).map(|a| a.data.as_slice())));
            let (Some(cbgt), Some(pal), Some(map)) = (get("cbgt"), get("pal"), map) else { return false };
            let Ok(grid) = background::palette_grid(map) else { return false };
            let dir = out.join("imagens/cenarios");
            let _ = std::fs::create_dir_all(&dir);
            let ok = background::render(cbgt, pal, &grid).and_then(|img| img.save_png(&dir.join(format!("{area}.png")))).is_ok();
            if let Some(depth) = get("cdpth") {
                let cols = grid.iter().map(Vec::len).max().unwrap_or(0);
                if let Ok(img) = background::render_depth(depth, cols, grid.len()) {
                    let _ = img.save_png(&dir.join(format!("{area}_profundidade.png")));
                }
            }
            ok
        })
        .collect();
    Ok(done.iter().filter(|&&b| b).count())
}

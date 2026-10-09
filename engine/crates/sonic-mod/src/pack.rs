//! pack: projeto editado + ROM original -> ROM modificada.
//!
//! Para cada coisa do projeto, gera o binário e compara com o original. Como os
//! escritores reproduzem os arquivos originais byte a byte, "não mudou" é
//! detectado com exatidão e só o que você editou é regravado.

use crate::{open_pack, stem_lower, Item, Res, LANG_FILES};
use sonic_formats::{compression, csv, gda::Gda, herf, nds, nds::Rom, tlk::Tlk};
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};

pub fn run(rom_path: &str, dir: &str, out_path: &str) -> Res<()> {
    let dir = Path::new(dir);
    if !dir.join("tabelas").exists() && !dir.join("textos").exists() && !dir.join("arquivos").exists() {
        return Err(format!("{} não parece um projeto do sonic-mod (rode unpack antes)", dir.display()).into());
    }
    let original = fs::read(rom_path)?;
    let rom = Rom::parse(&original)?;
    let names = herf::recover_names(&rom)?;
    let mut report: Vec<String> = Vec::new();
    let mut warnings: Vec<String> = Vec::new();
    let mut replaced: Vec<(u16, String, Vec<u8>)> = Vec::new();

    // ---- pacotes HERF: planilhas + arquivos
    for f in rom.files.iter().filter(|f| f.path.to_ascii_lowercase().ends_with(".herf")) {
        let pack = f.path.trim_end_matches(".herf").to_string();
        let mut items = open_pack(rom.file_data(f)?, &names)?;
        let by_stem: HashMap<String, usize> = items
            .iter()
            .enumerate()
            .filter(|(_, it)| Gda::parse(&it.content).is_ok())
            .map(|(i, it)| (stem_lower(&it.name), i))
            .collect();
        let mut changed = 0;
        let mut new_names: Vec<(u32, String)> = Vec::new();

        // planilhas
        for csv_path in files_in(&dir.join("tabelas").join(&pack), "csv") {
            let stem = stem_lower(&csv_path.file_name().unwrap().to_string_lossy());
            let Some(&idx) = by_stem.get(&stem) else {
                warnings.push(format!("{}: não existe tabela com esse nome no pacote {pack} (ignorado)", csv_path.display()));
                continue;
            };
            let mut g = Gda::parse(&items[idx].content)?;
            g.rows = read_table(&csv_path, &g)?;
            let bytes = g.to_bytes();
            if bytes != items[idx].content {
                warn_duplicate_ids(&csv_path, &g.rows);
                report.push(format!("tabela   {pack}/{} ({} linhas)", items[idx].name, g.rows.len()));
                set_content(&mut items[idx], bytes);
                changed += 1;
            }
        }

        // arquivos soltos: substituem (mesmo nome) ou são adicionados
        for path in files_in(&dir.join("arquivos").join(&pack), "") {
            let name = path.file_name().unwrap().to_string_lossy().to_string();
            let data = fs::read(&path)?;
            let found = items.iter().position(|it| it.name.eq_ignore_ascii_case(&name));
            match found {
                Some(i) if items[i].content == data => {}
                Some(i) => {
                    report.push(format!("arquivo  {pack}/{name} (substituído)"));
                    set_content(&mut items[i], data);
                    changed += 1;
                }
                None => {
                    if !name.is_ascii() {
                        return Err(format!("{}: o nome do arquivo precisa ser ASCII (sem acentos)", path.display()).into());
                    }
                    // Embala como os arquivos do mesmo tipo: o jogo procura os modelos e
                    // texturas 3D só como "nome.small" (comprimido); um .nsbmd solto não é achado.
                    let small = small_like(&items, &name);
                    let stored = if small.is_some() { format!("{name}.small") } else { name.clone() };
                    let hash = herf::hash_resource_name(stored.as_bytes());
                    if items.iter().any(|it| it.hash == hash) {
                        return Err(format!("{name}: o hash do nome colide com outro arquivo; escolha outro nome").into());
                    }
                    let raw = match small {
                        Some(lz) => compression::make_small(&data, lz),
                        None => data.clone(),
                    };
                    let how = match small {
                        Some(true) => ", guardado como .small LZ10",
                        Some(false) => ", guardado como .small",
                        None => "",
                    };
                    report.push(format!("arquivo  {pack}/{name} (NOVO{how})"));
                    new_names.push((hash, stored));
                    items.push(Item { hash, name, raw, small, content: data });
                    changed += 1;
                }
            }
        }

        if changed > 0 {
            // mantém o dicionário de nomes (erf.dict) em dia com os arquivos novos
            if !new_names.is_empty() {
                if let Some(d) = items.iter_mut().find(|it| herf::parse_name_dict(&it.content).is_some()) {
                    let mut all: Vec<(u32, String)> = herf::parse_name_dict(&d.content).unwrap().into_iter().collect();
                    all.extend(new_names);
                    let bytes = herf::write_name_dict(&all);
                    set_content(d, bytes);
                }
            }
            let entries: Vec<(u32, Vec<u8>)> = items.into_iter().map(|it| (it.hash, it.raw)).collect();
            replaced.push((f.id, f.path.clone(), herf::write(&entries)));
        }
    }

    // ---- textos
    for (code, file) in LANG_FILES {
        let csv_path = dir.join("textos").join(format!("{code}.csv"));
        let (Some(f), true) = (rom.find(file), csv_path.exists()) else { continue };
        let original_bytes = rom.file_data(f)?;
        let mut t = Tlk::parse(original_bytes)?;
        let before = t.texts();
        let (mut changed, mut added) = (0, 0);
        for (line, row) in csv::parse(&fs::read_to_string(&csv_path)?).into_iter().skip(1) {
            let id: u32 = row.first().and_then(|s| s.trim().parse().ok()).ok_or_else(|| format!("{}:{line}: id inválido", csv_path.display()))?;
            let text = row.get(1).cloned().unwrap_or_default();
            match before.get(&id) {
                Some(old) if *old == text => continue,
                Some(old) if !old.is_empty() => changed += 1,
                _ => added += 1,
            }
            if t.set(id, &text)? {
                warnings.push(format!("{}:{line}: caracteres sem equivalente no jogo viraram '?'", csv_path.display()));
            }
        }
        if changed + added > 0 {
            report.push(format!("textos   {code}: {changed} alterados, {added} novos"));
            replaced.push((f.id, f.path.clone(), t.to_bytes()));
        }
    }

    if replaced.is_empty() {
        eprintln!("nada mudou em relação à ROM original: nenhuma ROM gerada.");
        return Ok(());
    }

    // ---- grava a ROM
    let mut out = original.clone();
    for (id, path, data) in &replaced {
        let p = nds::replace_file(&mut out, *id, data)?;
        let where_ = if p == nds::Placement::InPlace { "no lugar" } else { "no fim do cartucho" };
        report.push(format!("rom      {path}: {} bytes, {where_}", data.len()));
    }

    // ---- confere: a ROM nova abre e devolve exatamente o que foi gravado
    let check = Rom::parse(&out)?;
    for (id, path, data) in &replaced {
        let f = check.files.iter().find(|f| f.id == *id).ok_or("arquivo sumiu")?;
        if check.file_data(f)? != data.as_slice() {
            return Err(format!("verificação falhou em {path}").into());
        }
    }
    fs::write(out_path, &out)?;
    for w in &warnings {
        eprintln!("aviso: {w}");
    }
    for r in &report {
        eprintln!("  {r}");
    }
    eprintln!("ROM modificada: {out_path} ({} MB)", out.len() / (1 << 20));
    Ok(())
}

/// Grava o conteúdo novo mantendo a embalagem original (.small LZ10, .small cru ou comum).
fn set_content(it: &mut Item, content: Vec<u8>) {
    it.raw = match it.small {
        Some(lz) => compression::make_small(&content, lz),
        None => content.clone(),
    };
    it.content = content;
}

/// Como o pacote guarda os arquivos com a mesma extensão de `name`: a embalagem da
/// maioria (`Some(true)` = .small LZ10, `Some(false)` = .small cru, `None` = comum).
fn small_like(items: &[Item], name: &str) -> Option<bool> {
    let ext = |n: &str| n.rsplit_once('.').map(|(_, e)| e.to_ascii_lowercase());
    let mine = ext(name)?;
    let (mut plain, mut raw, mut lz) = (0, 0, 0);
    for it in items.iter().filter(|it| ext(&it.name).as_deref() == Some(mine.as_str())) {
        match it.small {
            None => plain += 1,
            Some(false) => raw += 1,
            Some(true) => lz += 1,
        }
    }
    if plain >= raw + lz {
        None
    } else {
        Some(lz >= raw)
    }
}

fn files_in(dir: &Path, ext: &str) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir(dir)
        .map(|rd| rd.filter_map(|e| e.ok().map(|e| e.path())).filter(|p| p.is_file()).collect())
        .unwrap_or_default();
    if !ext.is_empty() {
        v.retain(|p| p.extension().is_some_and(|e| e.eq_ignore_ascii_case(ext)));
    }
    v.retain(|p| !p.file_name().unwrap().to_string_lossy().starts_with('.'));
    v.sort();
    v
}

/// Lê uma planilha usando os tipos das colunas da tabela original.
fn read_table(path: &Path, g: &Gda) -> Res<Vec<Vec<sonic_formats::gda::Cell>>> {
    let rows = csv::parse(&fs::read_to_string(path)?);
    let ncols = g.fields.len();
    let mut out = Vec::new();
    let names = g.column_names();
    for (line, row) in rows.into_iter().skip(1) {
        if row.iter().all(|c| c.trim().is_empty()) {
            continue;
        }
        if row.len() != ncols {
            return Err(format!("{}:{line}: a linha tem {} colunas, a tabela tem {ncols}", path.display(), row.len()).into());
        }
        let cells = row
            .iter()
            .enumerate()
            .map(|(i, v)| g.cell_from_text(i, v).map_err(|e| format!("{}:{line}, coluna {}: {e}", path.display(), names[i])))
            .collect::<Result<Vec<_>, _>>()?;
        out.push(cells);
    }
    Ok(out)
}

/// IDs repetidos costumam ser engano ao copiar linhas (só avisa em tabelas editadas:
/// algumas tabelas originais do jogo já têm repetições).
fn warn_duplicate_ids(path: &Path, rows: &[Vec<sonic_formats::gda::Cell>]) {
    let mut seen = BTreeMap::new();
    for (i, r) in rows.iter().enumerate() {
        if let Some(sonic_formats::gda::Cell::Int(id)) = r.first() {
            if let Some(prev) = seen.insert(*id, i) {
                eprintln!("aviso: {}: ID {id} aparece nas linhas de dados {} e {}", path.display(), prev + 1, i + 1);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(name: &str, small: Option<bool>) -> Item {
        Item { hash: 0, name: name.into(), raw: vec![], small, content: vec![] }
    }

    #[test]
    fn arquivo_novo_segue_a_embalagem_do_tipo() {
        let items = vec![
            item("FX_A.nsbtx", Some(true)),
            item("FX_B.nsbtx", Some(true)),
            item("FX_C.NSBTX", None),
            item("Item1.ITM", None),
            item("Item2.itm", None),
            item("x.gff", Some(false)),
        ];
        assert_eq!(small_like(&items, "FX_Novo.nsbtx"), Some(true));
        assert_eq!(small_like(&items, "Item288.ITM"), None);
        assert_eq!(small_like(&items, "novo.gff"), Some(false));
        assert_eq!(small_like(&items, "sem_tipo_conhecido.xyz"), None);
        assert_eq!(small_like(&items, "sem_extensao"), None);
    }
}

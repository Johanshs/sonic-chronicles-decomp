//! unpack: ROM -> projeto editável.

use crate::{open_pack, Res, LANG_FILES, PROJECT_README};
use sonic_formats::{csv, gda::Gda, herf, nds::Rom, tlk::Tlk};
use std::fs;
use std::path::Path;

pub fn run(rom_path: &str, dir: &str) -> Res<()> {
    let dir = Path::new(dir);
    if dir.join("tabelas").exists() {
        return Err(format!("{} já tem um projeto; use outra pasta (para não sobrescrever suas edições)", dir.display()).into());
    }
    let bytes = fs::read(rom_path)?;
    let rom = Rom::parse(&bytes)?;
    eprintln!("ROM: {} ({})", rom.title, rom.game_code);
    let names = herf::recover_names(&rom)?;

    let (mut n_tables, mut n_files) = (0, 0);
    for f in rom.files.iter().filter(|f| f.path.to_ascii_lowercase().ends_with(".herf")) {
        let pack = f.path.trim_end_matches(".herf");
        for it in open_pack(rom.file_data(f)?, &names)? {
            if let Ok(g) = Gda::parse(&it.content) {
                // tabela binária -> planilha
                let stem = it.name.rsplit_once('.').map(|(s, _)| s).unwrap_or(&it.name);
                let mut text = csv::line(g.column_names());
                for row in &g.rows {
                    text += &csv::line(row.iter().map(Gda::cell_to_text));
                }
                write(&dir.join("tabelas").join(pack).join(format!("{stem}.csv")), text.as_bytes())?;
                n_tables += 1;
            } else if it.content.starts_with(b"2DA ") {
                // tabelas em texto (.itm, .spl, ...): editáveis direto num editor de texto
                write(&dir.join("arquivos").join(pack).join(&it.name), &it.content)?;
                n_files += 1;
            }
        }
    }

    for (code, file) in LANG_FILES {
        let Some(f) = rom.find(file) else { continue };
        let t = Tlk::parse(rom.file_data(f)?)?;
        let mut text = csv::line(["id", "texto"]);
        for (id, s) in t.texts() {
            if !s.is_empty() {
                text += &csv::line([id.to_string(), s]);
            }
        }
        write(&dir.join("textos").join(format!("{code}.csv")), text.as_bytes())?;
    }

    write(&dir.join("LEIA-ME.md"), PROJECT_README.as_bytes())?;
    write(&dir.join(".sonic-mod"), format!("rom={}\ncodigo={}\ntamanho={}\n", rom.title, rom.game_code, bytes.len()).as_bytes())?;
    eprintln!("projeto criado em {}: {n_tables} planilhas, {n_files} arquivos de texto, 5 idiomas", dir.display());
    eprintln!("edite e depois rode: sonic-mod pack {rom_path} {} rom_modificada.nds", dir.display());
    Ok(())
}

fn write(path: &Path, data: &[u8]) -> std::io::Result<()> {
    if let Some(p) = path.parent() {
        fs::create_dir_all(p)?;
    }
    fs::write(path, data)
}

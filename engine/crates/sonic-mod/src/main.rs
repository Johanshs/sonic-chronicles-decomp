//! sonic-mod: modding do Sonic Chronicles.
//!
//!   sonic-mod unpack <rom.nds> <projeto>              cria o projeto editável
//!   sonic-mod pack   <rom.nds> <projeto> <saida.nds>  gera a ROM modificada
//!
//! O projeto tem planilhas CSV (tabelas do jogo), textos por idioma e arquivos
//! soltos. O `pack` compara cada coisa com a ROM original e só regrava o que mudou.

mod pack;
mod unpack;

use std::process;

pub const PROJECT_README: &str = include_str!("../PROJETO-LEIA-ME.md");

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("unpack") if args.len() == 3 => unpack::run(&args[1], &args[2]),
        Some("pack") if args.len() == 4 => pack::run(&args[1], &args[2], &args[3]),
        _ => {
            eprintln!(
                "sonic-mod {}: modding do Sonic Chronicles (DS)\n\n\
                 uso:\n  sonic-mod unpack <rom.nds> <projeto>\n  sonic-mod pack   <rom.nds> <projeto> <saida.nds>\n\n\
                 Edite as planilhas em <projeto>/tabelas, os textos em <projeto>/textos e\n\
                 coloque arquivos novos ou substitutos em <projeto>/arquivos. Veja <projeto>/LEIA-ME.md.",
                env!("CARGO_PKG_VERSION")
            );
            process::exit(2);
        }
    };
    if let Err(e) = result {
        eprintln!("\nerro: {e}");
        process::exit(1);
    }
}

pub type Res<T> = Result<T, Box<dyn std::error::Error>>;

/// Nome-base sem `.small` e sem extensão final, em minúsculas: "Items.GDA.small" -> "items".
pub fn stem_lower(name: &str) -> String {
    let n = name.strip_suffix(".small").unwrap_or(name);
    n.rsplit_once('.').map(|(s, _)| s).unwrap_or(n).to_ascii_lowercase()
}

/// Uma entrada de pacote com nome resolvido.
pub struct Item {
    pub hash: u32,
    pub name: String,
    pub raw: Vec<u8>,
    /// `Some(true)` = .small LZ10, `Some(false)` = .small sem compressão, `None` = arquivo comum
    pub small: Option<bool>,
    pub content: Vec<u8>,
}

/// Abre um HERF e devolve as entradas com nome e conteúdo já descomprimido.
pub fn open_pack(data: &[u8], names: &std::collections::HashMap<u32, String>) -> Res<Vec<Item>> {
    let h = sonic_formats::herf::Herf::parse(data)?;
    let mut out = Vec::new();
    for e in &h.entries {
        let raw = h.raw(e)?.to_vec();
        let (content, small) = match sonic_formats::compression::open_small(&raw) {
            Some(s) => {
                let lz = matches!(s, sonic_formats::compression::Small::Lz10(_));
                (s.into_vec(), Some(lz))
            }
            None => (raw.clone(), None),
        };
        let mut name = names.get(&e.hash).cloned().unwrap_or_else(|| format!("_unk_{:08x}", e.hash));
        if small.is_some() {
            name = name.strip_suffix(".small").map(str::to_string).unwrap_or(name);
        }
        out.push(Item { hash: e.hash, name, raw, small, content });
    }
    Ok(out)
}

/// Pacotes e textos editáveis da ROM.
pub const LANG_FILES: &[(&str, &str)] = sonic_formats::tlk::LANGUAGES;

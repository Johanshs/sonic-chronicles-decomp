//! sonic-dump: extrai todos os assets do Sonic Chronicles para formatos abertos.
//!
//! Uso: sonic-dump <rom.nds> <pasta_de_saida> [opções]
//!   --sem-imagens    não gera PNG de sprites/interface
//!   --sem-cenarios   não gera PNG dos cenários das áreas
//!   --sem-json       não converte GFF4 para JSON
//!   --sem-bruto      não copia os arquivos originais do NitroFS

mod images;
mod texts;

use sonic_formats::{herf, nds::Rom};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::time::Instant;
use std::{env, fs, process};

pub struct Opts {
    pub images: bool,
    pub backgrounds: bool,
    pub json: bool,
    pub raw: bool,
}

/// Um arquivo do jogo pronto para exportar: de onde veio + nome + conteúdo aberto.
pub struct Asset {
    pub pack: String,
    pub name: String,
    pub data: Vec<u8>,
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let pos: Vec<&String> = args.iter().skip(1).filter(|a| !a.starts_with("--")).collect();
    if pos.len() < 2 {
        eprintln!(
            "sonic-dump {}: extrai os assets do Sonic Chronicles (DS)\n\n\
             uso: sonic-dump <rom.nds> <pasta_de_saida> [--sem-imagens] [--sem-cenarios] [--sem-json] [--sem-bruto]",
            env!("CARGO_PKG_VERSION")
        );
        process::exit(2);
    }
    let flag = |f: &str| !args.iter().any(|a| a == f);
    let opts = Opts { images: flag("--sem-imagens"), backgrounds: flag("--sem-cenarios"), json: flag("--sem-json"), raw: flag("--sem-bruto") };
    if let Err(e) = run(Path::new(pos[0]), Path::new(pos[1]), &opts) {
        eprintln!("\nerro: {e}");
        process::exit(1);
    }
}

pub fn write(path: &Path, data: &[u8]) -> std::io::Result<()> {
    if let Some(p) = path.parent() {
        fs::create_dir_all(p)?;
    }
    fs::write(path, data)
}

/// Nomes de arquivo seguros no Windows também.
pub fn safe_name(n: &str) -> String {
    n.chars().map(|c| if r#"<>:"/\|?*"#.contains(c) || c.is_control() { '_' } else { c }).collect()
}

fn step(n: u32, msg: &str) {
    eprintln!("[{n}/7] {msg}");
}

fn run(rom_path: &Path, out: &Path, opts: &Opts) -> Result<(), Box<dyn std::error::Error>> {
    let t0 = Instant::now();
    let rom_bytes = fs::read(rom_path)?;
    let rom = Rom::parse(&rom_bytes)?;
    eprintln!("ROM: {} ({}) | {} arquivos no NitroFS", rom.title, rom.game_code, rom.files.len());
    if rom.game_code != "YWSE" && rom.game_code != "YWSP" && rom.game_code != "YWSJ" {
        eprintln!("aviso: código {} não é o Sonic Chronicles esperado (YWSE); tentando mesmo assim", rom.game_code);
    }
    fs::create_dir_all(out)?;

    // 1. arquivos originais
    step(1, "arquivos originais do NitroFS");
    let mut loose: Vec<Asset> = Vec::new();
    for f in &rom.files {
        let data = rom.file_data(f)?.to_vec();
        if opts.raw {
            write(&out.join("bruto").join(&f.path), &data)?;
        }
        loose.push(Asset { pack: "rom".into(), name: f.path.clone(), data });
    }
    if opts.raw {
        write(&out.join("bruto/arm9.bin"), rom.arm9()?)?;
        write(&out.join("bruto/arm7.bin"), rom.arm7()?)?;
    }

    // 2. pacotes HERF + recuperação de nomes
    step(2, "pacotes HERF: recuperando nomes por dicionário");
    let herfs: Vec<(&Asset, herf::Herf)> = loose
        .iter()
        .filter(|a| a.name.to_ascii_lowercase().ends_with(".herf"))
        .map(|a| herf::Herf::parse(&a.data).map(|h| (a, h)))
        .collect::<Result<_, _>>()?;
    let mut dict = herf::NameRecovery::default();
    dict.add_bytes(rom.arm9()?);
    for a in &loose {
        dict.add_word(&a.name);
        let l = a.name.to_ascii_lowercase();
        if l.ends_with(".2da") || l.ends_with(".gda") {
            dict.add_bytes(&a.data);
        }
    }
    let mut opened: Vec<Vec<(herf::Entry, Vec<u8>, bool)>> = Vec::new();
    for (_, h) in &herfs {
        let mut v = Vec::new();
        for e in &h.entries {
            let (d, small) = h.contents(e)?;
            dict.add_bytes(&d);
            v.push((*e, d, small));
        }
        opened.push(v);
    }
    let wanted: HashSet<u32> = herfs.iter().flat_map(|(_, h)| h.entries.iter().map(|e| e.hash)).collect();
    // fonte principal: o dicionário de nomes que o próprio jogo traz (erf.dict);
    // o ataque de dicionário só preenche o que faltar
    let mut names = dict.resolve(&wanted);
    let mut from_dict = 0;
    for (_, d, _) in opened.iter().flatten() {
        if let Some(official) = herf::parse_name_dict(d) {
            from_dict += official.len();
            names.extend(official);
        }
    }
    eprintln!("      erf.dict: {from_dict} nomes oficiais; total resolvido: {}/{}", names.len(), wanted.len());

    let mut assets: Vec<Asset> = Vec::new();
    let mut manifest = Vec::new();
    for ((src, h), _) in herfs.iter().zip(&opened) {
        let pack = src.name.trim_end_matches(".herf").to_string();
        let resolved = herf::resolve_all(h, &names)?;
        let named = resolved.iter().filter(|r| r.named).count();
        eprintln!("      {}: {} arquivos, {} nomes ({:.1}%)", src.name, resolved.len(), named, 100.0 * named as f64 / resolved.len().max(1) as f64);
        for r in resolved {
            let name = safe_name(&r.name);
            write(&out.join("herf").join(&pack).join(&name), &r.data)?;
            manifest.push(serde_json::json!({"pacote": pack, "hash": format!("{:08x}", r.hash), "nome": name,
                "nome_recuperado": r.named, "era_small": r.was_small, "bytes": r.data.len()}));
            assets.push(Asset { pack: pack.clone(), name, data: r.data });
        }
    }
    write(&out.join("herf/_manifesto.json"), serde_json::to_string_pretty(&manifest)?.as_bytes())?;
    drop(opened);

    // 3-5. textos, diálogos, tabelas, GFF -> JSON
    step(3, "textos (5 idiomas) e roteiro dos diálogos");
    let text_stats = texts::export_texts(&loose, &assets, out)?;
    step(4, "tabelas (GDA e 2DA -> CSV)");
    let table_stats = texts::export_tables(&loose, &assets, out)?;
    let json_count = if opts.json {
        step(5, "GFF4 -> JSON");
        texts::export_gff_json(&assets, out)?
    } else {
        0
    };

    // 6-7. imagens
    let sprite_stats = if opts.images {
        step(6, "gráficos Nitro (NCGR + NCLR -> PNG)");
        images::export_sprites(&assets, out)?
    } else {
        HashMap::new()
    };
    let bg_count = if opts.backgrounds {
        step(7, "cenários das áreas (CBGT + PAL + 2DA -> PNG)");
        images::export_backgrounds(&loose, out)?
    } else {
        0
    };

    let summary = serde_json::json!({
        "jogo": rom.title, "codigo": rom.game_code,
        "arquivos_nitrofs": rom.files.len(),
        "arquivos_herf": manifest.len(),
        "textos": text_stats, "tabelas": table_stats, "gff_json": json_count,
        "imagens_por_metodo_de_paleta": sprite_stats, "cenarios": bg_count,
        "segundos": t0.elapsed().as_secs_f32(),
    });
    write(&out.join("resumo.json"), serde_json::to_string_pretty(&summary)?.as_bytes())?;
    write(&out.join("LEIA-ME.txt"), README_OUT.as_bytes())?;
    eprintln!("\npronto em {:.1}s -> {}", t0.elapsed().as_secs_f32(), PathBuf::from(out).display());
    eprintln!("{}", serde_json::to_string_pretty(&summary)?);
    Ok(())
}

const README_OUT: &str = "\
Assets extraídos do Sonic Chronicles: The Dark Brotherhood (DS) por sonic-dump.
USO PESSOAL: este material pertence à SEGA/BioWare. Não redistribua.

bruto/             arquivos originais do NitroFS, sem alteração (+ arm9.bin, arm7.bin)
herf/<pacote>/     conteúdo dos pacotes .herf, já descomprimido e com nome recuperado
                   (_unk_<hash>.<ext> = nome não recuperado; extensão deduzida pela assinatura)
herf/_manifesto.json   hash, nome e tamanho de cada arquivo dos pacotes
textos/            textos_5_idiomas.csv e roteiro_<idioma>.txt (diálogos com personagem/emoção)
tabelas/           tabelas de jogo em CSV (gda/ = binárias, 2da/ = texto)
json/              todo arquivo GFF4 (diálogos, áreas, telas, plots...) convertido para JSON
imagens/sprites/   gráficos NCGR em PNG. imagens/_paletas.json diz qual paleta foi usada e como:
                   'gui' = indicada pelas telas do jogo; 'tabela' = indicada pelas tabelas
                   (retratos, itens) -> confiáveis; 'mesmo_nome' / 'prefixo' = palpite;
                   'cinza' = paleta desconhecida
imagens/montadas/  retratos e ícones montados (4 peças 64×64 -> 128×128)
imagens/cenarios/  cenário completo de cada área (+ _profundidade.png: o que fica na frente
                   dos personagens; claro = perto)

Não convertidos (ficam em bruto/ e herf/): modelos 3D .nsbmd/.nsbtx/.nsbca (use o apicula),
áudio sound_data.sdat (use o VGMTrans), vídeos .vx (codec Actimagine VX).
";

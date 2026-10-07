//! Teste de ida e volta com a ROM real: ler -> escrever -> comparar byte a byte.
//! Rode com:  SONIC_ROM=/caminho/rom.nds cargo test --release -- --nocapture
//! Sem a variável, o teste é pulado (a ROM não faz parte do repositório).

use sonic_formats::{compression, gda::Gda, herf, nds::Rom, tlk::Tlk};

fn rom_bytes() -> Option<Vec<u8>> {
    let path = std::env::var("SONIC_ROM").ok()?;
    std::fs::read(path).ok()
}

#[test]
fn tudo_volta_identico() {
    let Some(bytes) = rom_bytes() else {
        eprintln!("SONIC_ROM não definida: teste pulado");
        return;
    };
    let rom = Rom::parse(&bytes).unwrap();
    let (mut tlks, mut herfs, mut gdas, mut smalls) = (0, 0, 0, 0);
    for f in &rom.files {
        let data = rom.file_data(f).unwrap();
        let lower = f.path.to_ascii_lowercase();
        if lower.ends_with(".tlk") {
            let t = Tlk::parse(data).unwrap();
            assert_eq!(t.to_bytes(), data, "TLK {}", f.path);
            // toda entrada precisa ser achada pela busca do jogo
            for (id, _) in t.slots.iter().filter(|s| s.0 != sonic_formats::tlk::EMPTY) {
                assert!(t.get(*id).is_some() || t.slots.iter().any(|s| s.0 == *id && s.1.is_none()), "id {id} inacessível");
            }
            tlks += 1;
        }
        if lower.ends_with(".herf") {
            let h = herf::Herf::parse(data).unwrap();
            let entries: Vec<(u32, Vec<u8>)> = h.entries.iter().map(|e| (e.hash, h.raw(e).unwrap().to_vec())).collect();
            assert_eq!(herf::write(&entries), data, "HERF {}", f.path);
            herfs += 1;
            for e in &h.entries {
                let raw = h.raw(e).unwrap();
                let (content, _) = h.contents(e).unwrap();
                if Gda::parse(&content).map(|g| assert_eq!(g.to_bytes(), content)).is_ok() {
                    gdas += 1;
                }
                // recomprimir e descomprimir precisa devolver o mesmo conteúdo
                if raw.first() == Some(&0x10) && compression::open_small(raw).is_some() && smalls < 400 {
                    let again = compression::lz10_compress(&content);
                    assert_eq!(compression::lz10_decompress(&again).unwrap(), content);
                    smalls += 1;
                }
            }
        }
    }
    eprintln!("idênticos: {tlks} TLK, {herfs} HERF, {gdas} GDA; LZ10 ida e volta: {smalls}");
    assert_eq!((tlks, herfs), (5, 6));
    assert!(gdas >= 229);
}

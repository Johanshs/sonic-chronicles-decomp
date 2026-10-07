//! `herf list <arquivo.herf> [nomes.txt]`  — lista entradas (e nomes, se souber)
//! `herf get  <arquivo.herf> <nome> <saida>` — extrai um arquivo pelo nome
use sonic_chronicles_tools::{hash_resource_name, lz10_decompress, Herf};
use std::collections::HashMap;
use std::{env, fs, process};

fn main() {
    if let Err(e) = run() {
        eprintln!("erro: {e}");
        process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("list") if args.len() >= 3 => {
            let data = fs::read(&args[2])?;
            let herf = Herf::parse(&data)?;
            let names: HashMap<u32, String> = match args.get(3) {
                Some(p) => fs::read_to_string(p)?
                    .lines()
                    .map(|n| (hash_resource_name(n.as_bytes()), n.to_string()))
                    .collect(),
                None => HashMap::new(),
            };
            for e in &herf.entries {
                let name = names.get(&e.hash).map(String::as_str).unwrap_or("?");
                println!("{:08x} {:>9} {}", e.hash, e.size, name);
            }
            eprintln!("{} entradas", herf.entries.len());
        }
        Some("get") if args.len() >= 5 => {
            let data = fs::read(&args[2])?;
            let herf = Herf::parse(&data)?;
            // o jogo procura primeiro o nome comprimido (.small), depois o normal
            let small = format!("{}.small", args[3]);
            let (entry, compressed) = match herf.find(&small) {
                Some(e) => (e, true),
                None => (herf.find(&args[3]).ok_or("nome não encontrado no HERF")?, false),
            };
            let raw = herf.raw(entry)?;
            let bytes = if compressed { lz10_decompress(raw)? } else { raw.to_vec() };
            fs::write(&args[4], &bytes)?;
            eprintln!("{} bytes{} -> {}", bytes.len(), if compressed { " (descomprimido)" } else { "" }, args[4]);
        }
        _ => {
            eprintln!("uso:\n  herf list <arquivo.herf> [nomes.txt]\n  herf get <arquivo.herf> <nome> <saida>");
            process::exit(2);
        }
    }
    Ok(())
}

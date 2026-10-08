//! `sonic-mod menu`: põe o painel de controle (mod menu, pasta `modmenu/`) numa CÓPIA da
//! ROM. É o mesmo enxerto de `modmenu/ferramentas/enxertar.py`, aqui para quem só tem o
//! `sonic-mod` (sem Python): as duas versões geram a mesma ROM, byte a byte.
//!
//! O painel chega pronto, como o ELF que o `make` da pasta `modmenu/` gera
//! (`build/painel_jogo.elf`; o pacote de release o traz ao lado do `sonic-mod`). O que
//! muda na cópia (todos os endereços são do ARM9):
//!
//! 1. O código do painel vira um bloco de *autoload* novo: a lista que o início do
//!    programa (crt0 do NitroSDK) percorre para copiar blocos para a memória. O jogo já a
//!    usa para o ITCM e o DTCM; entra uma terceira entrada, "copie o painel para o fim do
//!    heap".
//! 2. O fim do heap (`OS_GetInitArenaHi`, literal em 0x020d8c9c) baixa para onde o
//!    painel começa. O começo não muda, então os objetos do jogo ficam nos mesmos
//!    endereços e os cheats que dependem deles continuam valendo.
//! 3. Em 0x02000d50, no laço principal, `bl func_02002708` (ler os botões) vira
//!    `bl gancho`. O gancho chama o painel e depois a função original.
//! 4. O ARM9 cresce; como o ARM7 vem logo depois na ROM, ele é mudado para o fim dos
//!    dados. O cabeçalho ganha os tamanhos novos e o CRC certo.
//!
//! Antes de mudar qualquer coisa, cada ponto é conferido contra o valor da versão YWSE.
//! Se algo não bater (outra versão, ROM já enxertada), nada é gravado.

use crate::Res;
use sonic_formats::nds::header_crc16;

const BASE: u32 = 0x0200_0000;
/// Parâmetros do módulo (NitroSDK `_start_ModuleParams`), relativos ao começo do ARM9.
const PARAMS: usize = 0xB9C;
/// `bl func_02002708` no `main`.
const CHAMADA: u32 = 0x0200_0D50;
const ALVO_ORIGINAL: u32 = 0x0200_2708;
/// `OS_GetInitArenaHi`, caso 0 (memória principal).
const LITERAL_ARENA_FIM: u32 = 0x020D_8C9C;
const ARENA_FIM_ORIGINAL: u32 = 0x023E_0000;
/// Assinatura dos 12 bytes que muitos jogos do NitroSDK têm depois do ARM9.
const NITROCODE: u32 = 0xDEC0_0621;

fn u32_em(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes(b[o..o + 4].try_into().unwrap())
}

fn por_u32(b: &mut [u8], o: usize, v: u32) {
    b[o..o + 4].copy_from_slice(&v.to_le_bytes());
}

/// O painel lido do ELF: onde ele mora, os bytes carregados e os símbolos que importam.
pub struct Painel {
    pub inicio: u32,
    pub bloco: Vec<u8>,
    /// Fim da memória do painel, BSS incluída (`__painel_fim`).
    pub fim: u32,
    /// Endereço do `gancho` (bit 0 = Thumb).
    pub gancho: u32,
}

/// Lê o ELF32 little-endian que o ld.lld gera: os bytes de `__painel_inicio` até
/// `__painel_fim_carregado` e os símbolos `__painel_fim` e `gancho`.
pub fn ler_elf(e: &[u8]) -> Res<Painel> {
    if e.len() < 0x34 || &e[..4] != b"\x7fELF" || e[4] != 1 || e[5] != 1 {
        return Err("o painel não é um ELF32 little-endian (é o build/painel_jogo.elf?)".into());
    }
    let curto = || -> Box<dyn std::error::Error> { "ELF do painel truncado".into() };
    let u16_em = |o: usize| u16::from_le_bytes([e[o], e[o + 1]]) as usize;
    let shoff = u32_em(e, 0x20) as usize;
    let (shentsize, shnum) = (u16_em(0x2E), u16_em(0x30));
    let mut secs = Vec::with_capacity(shnum);
    for i in 0..shnum {
        let o = shoff + i * shentsize;
        if o + 40 > e.len() {
            return Err(curto());
        }
        let campos: Vec<u32> = (0..10).map(|k| u32_em(e, o + 4 * k)).collect();
        secs.push(campos);
    }
    let mut simbolo = std::collections::HashMap::new();
    for s in secs.iter().filter(|s| s[1] == 2) {
        // SHT_SYMTAB: entradas de 16 bytes {nome, valor, tamanho, info...}
        let strtab = secs.get(s[6] as usize).ok_or_else(curto)?[4] as usize;
        let (ini, tam) = (s[4] as usize, s[5] as usize);
        if ini + tam > e.len() {
            return Err(curto());
        }
        for o in (ini..ini + tam).step_by(16) {
            let nome_ini = strtab + u32_em(e, o) as usize;
            let nome_fim = e[nome_ini..].iter().position(|&c| c == 0).ok_or_else(curto)? + nome_ini;
            if nome_fim > nome_ini {
                simbolo.insert(String::from_utf8_lossy(&e[nome_ini..nome_fim]).into_owned(), u32_em(e, o + 4));
            }
        }
    }
    let pegar = |n: &str| -> Res<u32> {
        simbolo.get(n).copied().ok_or_else(|| format!("o ELF do painel não tem o símbolo {n}").into())
    };
    let (inicio, fim_carregado) = (pegar("__painel_inicio")?, pegar("__painel_fim_carregado")?);
    let tamanho = fim_carregado.checked_sub(inicio).ok_or("ELF do painel com o fim antes do começo")?;
    let mut bloco = vec![0u8; tamanho as usize];
    for s in &secs {
        let (tipo, addr, off, tam) = (s[1], s[3], s[4] as usize, s[5] as usize);
        // SHT_PROGBITS dentro do bloco
        if tipo == 1 && (inicio..fim_carregado).contains(&addr) && tam > 0 {
            let destino = (addr - inicio) as usize;
            if destino + tam > bloco.len() || off + tam > e.len() {
                return Err(curto());
            }
            bloco[destino..destino + tam].copy_from_slice(&e[off..off + tam]);
        }
    }
    Ok(Painel { inicio, bloco, fim: pegar("__painel_fim")?, gancho: pegar("gancho")? })
}

/// A instrução BL do Thumb (dois meios-palavras) de `origem` para `destino`.
pub fn codificar_bl_thumb(origem: u32, destino: u32) -> Res<[u8; 4]> {
    let desl = destino as i64 - (origem as i64 + 4);
    if !(-0x40_0000..0x40_0000).contains(&desl) || desl & 1 != 0 {
        return Err(format!("bl de {origem:#x} para {destino:#x} fora do alcance").into());
    }
    let d = (desl as u32) & 0x7F_FFFF;
    let h1 = 0xF000 | (d >> 12) as u16;
    let h2 = 0xF800 | ((d >> 1) & 0x7FF) as u16;
    let mut b = [0u8; 4];
    b[..2].copy_from_slice(&h1.to_le_bytes());
    b[2..].copy_from_slice(&h2.to_le_bytes());
    Ok(b)
}

/// O destino de um BL do Thumb, ou `None` se os dois meios-palavras não forem um BL.
pub fn decodificar_bl_thumb(origem: u32, h1: u16, h2: u16) -> Option<u32> {
    if h1 & 0xF800 != 0xF000 || h2 & 0xF800 != 0xF800 {
        return None;
    }
    let mut desl = (((h1 & 0x7FF) as i64) << 12) | (((h2 & 0x7FF) as i64) << 1);
    if desl & 0x40_0000 != 0 {
        desl -= 0x80_0000;
    }
    Some((origem as i64 + 4 + desl) as u32)
}

/// Faz o enxerto e devolve a ROM nova e as linhas do relatório.
pub fn enxertar(rom_original: &[u8], painel: &Painel) -> Res<(Vec<u8>, Vec<String>)> {
    let mut rom = rom_original.to_vec();
    let mut relatorio = Vec::new();
    if rom.len() < 0x200 || &rom[0x0C..0x10] != b"YWSE" {
        return Err("este enxerto é só para o Sonic Chronicles dos EUA (código YWSE)".into());
    }
    if u16::from_le_bytes([rom[0x15E], rom[0x15F]]) != header_crc16(&rom[..0x15E]) {
        return Err("o CRC do cabeçalho não confere: a ROM está corrompida ou já foi mexida".into());
    }
    let (off9, ram9, tam9) = (u32_em(&rom, 0x20) as usize, u32_em(&rom, 0x28), u32_em(&rom, 0x2C) as usize);
    let (off7, tam7) = (u32_em(&rom, 0x30) as usize, u32_em(&rom, 0x3C) as usize);
    let mut usado = u32_em(&rom, 0x80) as usize;
    if off9 + tam9 + 12 > rom.len() || off7 + tam7 > rom.len() || tam9 < PARAMS + 12 {
        return Err("cabeçalho com ARM9 ou ARM7 fora da ROM".into());
    }
    let arm9 = rom[off9..off9 + tam9].to_vec();
    let rodape =
        if u32_em(&rom, off9 + tam9) == NITROCODE { rom[off9 + tam9..off9 + tam9 + 12].to_vec() } else { Vec::new() };

    let (lista, lista_fim) = (u32_em(&arm9, PARAMS), u32_em(&arm9, PARAMS + 4));
    let em9 = |a: u32| (a - BASE) as usize;
    let chamada = decodificar_bl_thumb(
        CHAMADA,
        u16::from_le_bytes([arm9[em9(CHAMADA)], arm9[em9(CHAMADA) + 1]]),
        u16::from_le_bytes([arm9[em9(CHAMADA) + 2], arm9[em9(CHAMADA) + 3]]),
    );
    let confere = [
        (ram9 == BASE, format!("ARM9 carregado em {ram9:#x}")),
        ((lista, lista_fim) == (0x0211_0F00, 0x0211_0F18), "lista de autoload fora do lugar".into()),
        (lista_fim.wrapping_sub(BASE) as usize == tam9, "a lista de autoload não termina no fim do ARM9".into()),
        (u32_em(&arm9, em9(LITERAL_ARENA_FIM)) == ARENA_FIM_ORIGINAL, "fim do heap diferente".into()),
        (chamada == Some(ALVO_ORIGINAL), format!("em {CHAMADA:#x} não está a chamada de func_02002708")),
    ];
    if let Some((_, msg)) = confere.iter().find(|(ok, _)| !ok) {
        return Err(format!("ROM inesperada: {msg}. Ela já foi enxertada ou é outra versão?").into());
    }

    let Painel { inicio, bloco, fim, gancho } = painel;
    if *fim > ARENA_FIM_ORIGINAL || inicio & 31 != 0 || fim < inicio || (*fim - inicio) < bloco.len() as u32 {
        return Err(format!("o painel ({inicio:#x}-{fim:#x}) precisa caber antes de {ARENA_FIM_ORIGINAL:#x}").into());
    }
    let bss = fim - inicio - bloco.len() as u32;
    relatorio.push(format!(
        "painel: {} bytes carregados + {bss} de BSS, em {inicio:#x}-{fim:#x}; o heap do jogo passa a terminar em {inicio:#x}",
        bloco.len()
    ));

    // 1. bloco novo antes da lista de autoload, e a entrada nova no fim da lista
    let corte = em9(lista);
    let mut novo9 = Vec::with_capacity(arm9.len() + bloco.len() + 12);
    novo9.extend_from_slice(&arm9[..corte]);
    novo9.extend_from_slice(bloco);
    novo9.extend_from_slice(&arm9[corte..]);
    for v in [*inicio, bloco.len() as u32, bss] {
        novo9.extend_from_slice(&v.to_le_bytes());
    }
    por_u32(&mut novo9, PARAMS, lista + bloco.len() as u32);
    por_u32(&mut novo9, PARAMS + 4, lista_fim + bloco.len() as u32 + 12);
    // 2. heap: termina onde o painel começa
    por_u32(&mut novo9, em9(LITERAL_ARENA_FIM), *inicio);
    // 3. gancho (o bit 0 do símbolo só diz que é Thumb)
    novo9[em9(CHAMADA)..em9(CHAMADA) + 4].copy_from_slice(&codificar_bl_thumb(CHAMADA, gancho & !1)?);

    // 4. montar a ROM: ARM9 no mesmo lugar; o ARM7 vai para o fim se não couber mais
    let fim9 = off9 + novo9.len() + rodape.len();
    let arm7 = rom[off7..off7 + tam7].to_vec();
    let novo_off7 = if fim9 > off7 {
        let o = (usado + 0x1FF) & !0x1FF;
        usado = o + tam7;
        relatorio.push(format!("ARM7 mudado de {off7:#x} para {o:#x} (o ARM9 cresceu até {fim9:#x})"));
        o
    } else {
        off7
    };
    if rom.len() < usado {
        rom.resize(usado, 0xFF);
    }
    if novo_off7 != off7 {
        rom[off7..off7 + tam7].fill(0xFF);
    }
    rom[off9..off9 + novo9.len()].copy_from_slice(&novo9);
    rom[off9 + novo9.len()..fim9].copy_from_slice(&rodape);
    rom[novo_off7..novo_off7 + tam7].copy_from_slice(&arm7);
    por_u32(&mut rom, 0x2C, novo9.len() as u32);
    por_u32(&mut rom, 0x30, novo_off7 as u32);
    por_u32(&mut rom, 0x80, usado as u32);
    let crc = header_crc16(&rom[..0x15E]);
    rom[0x15E..0x160].copy_from_slice(&crc.to_le_bytes());
    Ok((rom, relatorio))
}

/// Onde procurar o painel quando ele não é dado: ao lado do `sonic-mod` (o pacote de
/// release o traz ali).
fn painel_padrao() -> Res<std::path::PathBuf> {
    let exe = std::env::current_exe()?;
    Ok(exe.parent().ok_or("pasta do sonic-mod desconhecida")?.join("painel_jogo.elf"))
}

pub fn run(rom: &str, saida: &str, painel: Option<&str>) -> Res<()> {
    let (rom_canon, saida_canon) = (std::fs::canonicalize(rom)?, std::fs::canonicalize(saida).ok());
    if saida_canon.as_ref() == Some(&rom_canon) {
        return Err("a saída precisa ser outro arquivo: a ROM original nunca é alterada".into());
    }
    let caminho = match painel {
        Some(p) => std::path::PathBuf::from(p),
        None => painel_padrao()?,
    };
    let elf = std::fs::read(&caminho).map_err(|e| {
        format!(
            "não achei o painel em {} ({e}). Ele vem no pacote de release ao lado do sonic-mod, \
             ou é gerado por `make` na pasta modmenu/ (build/painel_jogo.elf)",
            caminho.display()
        )
    })?;
    let (nova, relatorio) = enxertar(&std::fs::read(rom)?, &ler_elf(&elf)?)?;
    for linha in relatorio {
        println!("{linha}");
    }
    std::fs::write(saida, nova)?;
    println!("gravado: {saida}");
    println!("No jogo, L + R + SELECT abre o painel. Guarde uma cópia do seu save antes de jogar.");
    Ok(())
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn bl_thumb_ida_e_volta() {
        for (de, para) in [(CHAMADA, ALVO_ORIGINAL), (CHAMADA, 0x023D_8000), (0x0200_4000, 0x0200_0100)] {
            let b = codificar_bl_thumb(de, para).unwrap();
            let h1 = u16::from_le_bytes([b[0], b[1]]);
            let h2 = u16::from_le_bytes([b[2], b[3]]);
            assert_eq!(decodificar_bl_thumb(de, h1, h2), Some(para));
        }
        // o BL original do jogo, lido no ARM9: 0x02000d50 -> func_02002708
        let b = codificar_bl_thumb(CHAMADA, ALVO_ORIGINAL).unwrap();
        assert_eq!(b, [0x01, 0xF0, 0xDA, 0xFC]);
        assert!(codificar_bl_thumb(CHAMADA, CHAMADA + 4 + 0x40_0000).is_err());
    }

    /// Um ELF32 mínimo com uma seção de código e a tabela de símbolos, como o ld.lld faria.
    fn elf_de_mentira(inicio: u32, codigo: &[u8], bss: u32, gancho: u32) -> Vec<u8> {
        let nomes = b"\0__painel_inicio\0__painel_fim_carregado\0__painel_fim\0gancho\0";
        // o nome inteiro, entre dois zeros ("__painel_fim" também aparece dentro de outro)
        let nome = |n: &str| {
            let alvo = [b"\0", n.as_bytes(), b"\0"].concat();
            nomes.windows(alvo.len()).position(|w| w == alvo).unwrap() as u32 + 1
        };
        let fim_carregado = inicio + codigo.len() as u32;
        let simbolos = [
            (0, 0),
            (nome("__painel_inicio"), inicio),
            (nome("__painel_fim_carregado"), fim_carregado),
            (nome("__painel_fim"), fim_carregado + bss),
            (nome("gancho"), gancho),
        ];
        let mut e = vec![0u8; 0x34];
        e[..6].copy_from_slice(b"\x7fELF\x01\x01");
        let off_codigo = e.len();
        e.extend_from_slice(codigo);
        let off_nomes = e.len();
        e.extend_from_slice(nomes);
        let off_sim = e.len();
        for (n, v) in simbolos {
            for x in [n, v, 0, 0] {
                e.extend_from_slice(&x.to_le_bytes());
            }
        }
        let shoff = e.len() as u32;
        // seções: 0 nula, 1 código (PROGBITS), 2 nomes (STRTAB), 3 símbolos (SYMTAB, link 2)
        let secoes: [[u32; 10]; 4] = [
            [0; 10],
            [0, 1, 6, inicio, off_codigo as u32, codigo.len() as u32, 0, 0, 4, 0],
            [0, 3, 0, 0, off_nomes as u32, nomes.len() as u32, 0, 0, 1, 0],
            [0, 2, 0, 0, off_sim as u32, 16 * simbolos.len() as u32, 2, 1, 4, 16],
        ];
        for s in secoes {
            for x in s {
                e.extend_from_slice(&x.to_le_bytes());
            }
        }
        por_u32(&mut e, 0x20, shoff);
        e[0x2E..0x30].copy_from_slice(&40u16.to_le_bytes());
        e[0x30..0x32].copy_from_slice(&4u16.to_le_bytes());
        e
    }

    /// Uma ROM de mentira com o que o enxerto confere nos lugares da YWSE.
    fn rom_de_mentira() -> Vec<u8> {
        let tam9 = 0x0011_0F18usize;
        let (off9, tam7) = (0x4000usize, 0x1000usize);
        let off7 = off9 + tam9 + 12 + 0x20; // pouco espaço: o ARM9 maior obriga a mudar o ARM7
        let mut rom = vec![0u8; off7 + tam7];
        rom[0x0C..0x10].copy_from_slice(b"YWSE");
        for (o, v) in [(0x20, off9 as u32), (0x28, BASE), (0x2C, tam9 as u32), (0x30, off7 as u32), (0x3C, tam7 as u32)] {
            por_u32(&mut rom, o, v);
        }
        por_u32(&mut rom, 0x80, (off7 + tam7) as u32);
        let a9 = |a: u32| off9 + (a - BASE) as usize;
        por_u32(&mut rom, off9 + PARAMS, 0x0211_0F00);
        por_u32(&mut rom, off9 + PARAMS + 4, 0x0211_0F18);
        por_u32(&mut rom, a9(LITERAL_ARENA_FIM), ARENA_FIM_ORIGINAL);
        rom[a9(CHAMADA)..a9(CHAMADA) + 4].copy_from_slice(&codificar_bl_thumb(CHAMADA, ALVO_ORIGINAL).unwrap());
        // as duas entradas de autoload do jogo (ITCM e DTCM), no fim do ARM9
        rom[off9 + tam9 - 24..off9 + tam9].iter_mut().enumerate().for_each(|(i, b)| *b = i as u8 + 1);
        por_u32(&mut rom, off9 + tam9, NITROCODE);
        rom[off7..].fill(0x77);
        let crc = header_crc16(&rom[..0x15E]);
        rom[0x15E..0x160].copy_from_slice(&crc.to_le_bytes());
        rom
    }

    #[test]
    fn enxerto_numa_rom_de_mentira() {
        let codigo: Vec<u8> = (0..64u8).collect();
        let painel = ler_elf(&elf_de_mentira(0x023D_8000, &codigo, 0x100, 0x023D_8001)).unwrap();
        assert_eq!((painel.inicio, painel.fim, painel.gancho), (0x023D_8000, 0x023D_8140, 0x023D_8001));
        assert_eq!(painel.bloco, codigo);

        let rom = rom_de_mentira();
        let (nova, _) = enxertar(&rom, &painel).unwrap();
        let off9 = u32_em(&nova, 0x20) as usize;
        let tam9 = u32_em(&nova, 0x2C) as usize;
        assert_eq!(tam9, 0x0011_0F18 + 64 + 12);
        let a9 = |a: u32| off9 + (a - BASE) as usize;
        // o bloco entra onde a lista de autoload estava; a lista anda e ganha uma entrada
        assert_eq!(&nova[a9(0x0211_0F00)..a9(0x0211_0F00) + 64], &codigo[..]);
        assert_eq!((u32_em(&nova, off9 + PARAMS), u32_em(&nova, off9 + PARAMS + 4)), (0x0211_0F40, 0x0211_0F64));
        assert_eq!(&nova[a9(0x0211_0F40)..a9(0x0211_0F40) + 24], &rom[a9(0x0211_0F00)..a9(0x0211_0F18)]);
        let entrada: Vec<u32> = (0..3).map(|k| u32_em(&nova, a9(0x0211_0F58) + 4 * k)).collect();
        assert_eq!(entrada, [0x023D_8000, 64, 0x100]);
        assert_eq!(u32_em(&nova, off9 + tam9), NITROCODE);
        // o heap termina no painel; o gancho chama o painel
        assert_eq!(u32_em(&nova, a9(LITERAL_ARENA_FIM)), 0x023D_8000);
        let h = |o: usize| u16::from_le_bytes([nova[o], nova[o + 1]]);
        assert_eq!(decodificar_bl_thumb(CHAMADA, h(a9(CHAMADA)), h(a9(CHAMADA) + 2)), Some(0x023D_8000));
        // o ARM7 mudou para o fim, inteiro, e o cabeçalho confere
        let (off7, tam7) = (u32_em(&nova, 0x30) as usize, u32_em(&nova, 0x3C) as usize);
        assert!(off7 >= off9 + tam9 + 12 && off7 % 0x200 == 0);
        assert!(nova[off7..off7 + tam7].iter().all(|&b| b == 0x77));
        assert_eq!(u16::from_le_bytes([nova[0x15E], nova[0x15F]]), header_crc16(&nova[..0x15E]));

        // enxertar de novo é recusado (o gancho e o heap já mudaram)
        assert!(enxertar(&nova, &painel).is_err());
        // outra versão do jogo também
        let mut outra = rom.clone();
        outra[0x0F] = b'P';
        assert!(enxertar(&outra, &painel).is_err());
        // um painel grande demais também
        let gordo = ler_elf(&elf_de_mentira(0x023D_8000, &codigo, 0x8000, 0x023D_8001)).unwrap();
        assert!(enxertar(&rom, &gordo).is_err());
    }
}

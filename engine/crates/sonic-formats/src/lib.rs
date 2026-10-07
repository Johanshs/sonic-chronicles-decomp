//! # sonic-formats
//!
//! Leitura dos formatos do **Sonic Chronicles: The Dark Brotherhood** (DS, BioWare 2008),
//! descobertos por engenharia reversa. Cada módulo documenta o layout binário.
//!
//! A biblioteca não depende de nada do jogo: tudo é lido da ROM do usuário.
//! É a base tanto da ferramenta de extração (`sonic-dump`) quanto de um futuro
//! executável que carregue os assets originais.
//!
//! | Módulo | Formato |
//! |---|---|
//! | [`nds`] | ROM `.nds`: cabeçalho, ARM9/ARM7, sistema de arquivos NitroFS |
//! | [`compression`] | LZ10 (BIOS do DS) e contêiner `.small` |
//! | [`herf`] | pacote de recursos `.herf` + recuperação de nomes por dicionário |
//! | [`gff4`] | GFF V4.0 (BioWare) → `serde_json::Value` |
//! | [`tlk`], [`gda`], [`twoda`] | textos, tabelas binárias, tabelas em texto |
//! | [`nitro`] | gráficos Nitro: paletas NCLR, tiles NCGR |
//! | [`background`] | cenários `.cbgt` + `.pal` + `.2da` e profundidade `.cdpth` |
//! | [`image`] | imagem RGBA simples + gravação PNG |
//! | [`csv`] | CSV para as planilhas de modding |
//!
//! Leitura **e escrita**: GDA, TLK, HERF, LZ10 e a ROM são reescritos byte a byte
//! idênticos ao original quando nada muda (teste `tests/roundtrip_rom.rs`).

pub mod background;
pub mod bytes;
pub mod compression;
pub mod csv;
pub mod gda;
pub mod gff4;
pub mod herf;
pub mod image;
pub mod nds;
pub mod nitro;
pub mod tlk;
pub mod twoda;

use std::fmt;

/// Erro único da biblioteca: diz o que estava sendo lido e o que deu errado.
#[derive(Debug)]
pub enum Error {
    /// O arquivo terminou antes do esperado.
    Truncated { what: &'static str, offset: usize },
    /// Assinatura ("magic") inesperada.
    BadMagic { what: &'static str, found: Vec<u8> },
    /// Dados inconsistentes.
    Invalid(String),
    Io(std::io::Error),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Truncated { what, offset } => write!(f, "{what}: arquivo termina antes do offset {offset:#x}"),
            Error::BadMagic { what, found } => write!(f, "{what}: assinatura inesperada {found:02x?}"),
            Error::Invalid(s) => write!(f, "{s}"),
            Error::Io(e) => write!(f, "E/S: {e}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

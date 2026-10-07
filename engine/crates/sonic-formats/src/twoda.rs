//! Tabela em texto `2DA V2.0` (formato clássico da BioWare, separado por TAB).
//! ```text
//! 2DA V2.0
//! <linha vazia ou valor padrão>
//! \tcol1\tcol2...
//! 0\tvalor\tvalor...
//! ```

pub struct TwoDa {
    pub columns: Vec<String>,
    pub rows: Vec<Vec<String>>,
}

pub fn is_2da(d: &[u8]) -> bool {
    d.starts_with(b"2DA ")
}

pub fn read(data: &[u8]) -> TwoDa {
    let text = String::from_utf8_lossy(data);
    let mut lines = text.lines().skip(1).filter(|l| !l.trim().is_empty());
    let columns = lines.next().map(|l| l.split('\t').map(|c| c.trim().to_string()).filter(|c| !c.is_empty()).collect()).unwrap_or_default();
    let rows = lines.map(|l| l.split('\t').map(|c| c.trim().to_string()).collect()).collect();
    TwoDa { columns, rows }
}

//! CSV mínimo (RFC 4180): aspas, aspas dobradas, quebras de linha dentro de aspas.
//! Na leitura aceita `,` ou `;` (detectado pela 1ª linha) e ignora o BOM do Excel.

/// Uma linha CSV com vírgulas, terminada em `\n`.
pub fn line<I, S>(fields: I) -> String
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let mut out = fields.into_iter().map(|f| field(f.as_ref())).collect::<Vec<_>>().join(",");
    out.push('\n');
    out
}

pub fn field(s: &str) -> String {
    if s.contains([',', ';', '"', '\n', '\r']) || s.starts_with(' ') || s.ends_with(' ') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

/// Lê o texto inteiro. Cada linha vem com o número da linha no arquivo (para erros).
pub fn parse(text: &str) -> Vec<(usize, Vec<String>)> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let first = text.lines().next().unwrap_or("");
    let sep = if first.matches(';').count() > first.matches(',').count() { ';' } else { ',' };
    let mut rows = Vec::new();
    let (mut row, mut cur) = (Vec::new(), String::new());
    let (mut quoted, mut line_no, mut row_start) = (false, 1usize, 1usize);
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' if quoted => {
                if chars.peek() == Some(&'"') {
                    cur.push('"');
                    chars.next();
                } else {
                    quoted = false;
                }
            }
            '"' if cur.is_empty() => quoted = true,
            c if c == sep && !quoted => row.push(std::mem::take(&mut cur)),
            '\r' if !quoted => {}
            '\n' if !quoted => {
                row.push(std::mem::take(&mut cur));
                if !(row.len() == 1 && row[0].is_empty()) {
                    rows.push((row_start, std::mem::take(&mut row)));
                } else {
                    row.clear();
                }
                line_no += 1;
                row_start = line_no;
            }
            '\n' => {
                cur.push('\n');
                line_no += 1;
            }
            c => cur.push(c),
        }
    }
    if !cur.is_empty() || !row.is_empty() {
        row.push(cur);
        rows.push((row_start, row));
    }
    rows
}

#[cfg(test)]
mod tests {
    #[test]
    fn ida_e_volta_com_aspas_e_quebra() {
        let l = super::line(["1", "Olá, \"mundo\"", "a\nb"]);
        let p = super::parse(&l);
        assert_eq!(p[0].1, vec!["1", "Olá, \"mundo\"", "a\nb"]);
    }

    #[test]
    fn ponto_e_virgula_e_bom() {
        let p = super::parse("\u{feff}id;texto\n5;oi, tudo\n");
        assert_eq!(p[1].1, vec!["5", "oi, tudo"]);
    }
}

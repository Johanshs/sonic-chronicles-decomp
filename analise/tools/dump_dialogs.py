"""Exporta todos os diálogos (.dlg) como roteiro legível, usando o TLK para o texto.

Campos descobertos no struct NTRY (nó de diálogo) — labels numéricos do GFF4:
  12201 texto (TlkString -> id no strings.tlk)   12202 retrato   12203 quem fala
  12208 condição (PLOT)   12209 ação (PLOT)       12400 links para os próximos nós
Lista 12000 = pontos de entrada (STRT, 12001 = índice do nó inicial).
Uso: python3 dump_dialogs.py dir_herf strings.tlk saida.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import gff4

def main(herf_dir, tlk, out):
    text = gff4.tlk_strings(tlk)
    lines, n_files, n_lines = [], 0, 0
    for f in sorted(os.listdir(herf_dir)):
        if not f.lower().endswith('.dlg'):
            continue
        root = gff4.GFF4(open(os.path.join(herf_dir, f), 'rb').read()).root()
        nodes = root.get('12002', [])
        starts = [s.get('12001') for s in root.get('12000', [])]
        lines.append(f'\n=== {f}  ({len(nodes)} nós, entradas: {starts})')
        n_files += 1
        for i, nd in enumerate(nodes):
            t = nd.get('12201') or {}
            fala = text.get(t.get('tlk_id'), t.get('text')) if isinstance(t, dict) else None
            if not fala:
                continue
            # 12203 é quase sempre 'PLAYER'; quem fala de fato aparece no retrato
            # (ex.: 'prtl_tailssca' -> 'tailssca'), então usamos ele.
            prt = nd.get('12202') or ''
            quem = prt[5:] if prt.lower().startswith('prtl_') else (prt or nd.get('12203') or '?')
            links = nd.get('12400') or []
            lines.append(f'[{i:3}] {quem:>14}: {fala.strip()}' + (f'   -> {links}' if links else ''))
            n_lines += 1
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'{n_files} dialogos, {n_lines} falas -> {out}')

if __name__ == '__main__':
    main(*sys.argv[1:4])

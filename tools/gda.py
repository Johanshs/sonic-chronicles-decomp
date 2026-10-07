"""Converte tabelas GDA (GFF4 do tipo 'G2DA') para CSV.

Estrutura:  raiz 'gtop'
  10002 lista de 'colm' { 10001: hash do nome da coluna, 10999: tipo }
  10003 lista de 'rows' { 10005, 10006, ... um campo por coluna, na mesma ordem }
O nome da coluna não está no arquivo: só CRC32(nome.lower() em UTF-16LE).
Os nomes vêm de (1) tabela pública do xoreos e (2) ataque de dicionário com
palavras encontradas no próprio jogo (ver recover_columns()).
Uso: python3 gda.py dir_herf saida_dir [arquivos_extras_para_dicionario...]
"""
import csv, json, os, re, sys, zlib
sys.path.insert(0, os.path.dirname(__file__))
import gff4

def col_hash(name):
    return zlib.crc32(name.lower().encode('utf-16-le'))

def load_known():
    p = os.path.join(os.path.dirname(__file__), 'gda_columns_xoreos.json')
    return {int(k): v for k, v in json.load(open(p)).items()}

def recover_columns(hashes, known, word_sources):
    words = set()
    for src in word_sources:
        txt = open(src, 'rb').read().decode('latin-1')
        words |= set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{1,40}', txt))
    # também combinações com sufixos numéricos comuns (Ability1, Stat_2...)
    extra = {f'{w}{i}' for w in list(words)[:20000] for i in range(10)}
    for w in words | extra:
        h = col_hash(w)
        if h in hashes and h not in known:
            known[h] = w
    return known

def main(herf_dir, outdir, *word_sources):
    os.makedirs(outdir, exist_ok=True)
    tables = {}
    for f in sorted(os.listdir(herf_dir)):
        p = os.path.join(herf_dir, f)
        if not f.lower().endswith('.gda') or open(p, 'rb').read(16)[12:16] != b'G2DA':
            continue
        tables[f] = gff4.GFF4(open(p, 'rb').read()).root()
    hashes = {c['10001'] for t in tables.values() for c in t.get('10002', [])}
    known = load_known()
    before = sum(1 for h in hashes if h in known)
    known = recover_columns(hashes, known, word_sources)
    after = sum(1 for h in hashes if h in known)
    for f, t in tables.items():
        cols = [known.get(c['10001'], f"col_{c['10001']:08x}") for c in t.get('10002', [])]
        rows = t.get('10003', [])
        with open(os.path.join(outdir, f.rsplit('.', 1)[0] + '.csv'), 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in rows:
                vals = [v for k, v in r.items() if k != '_type']
                w.writerow(['' if v is None else v for v in vals])
    print(f'{len(tables)} tabelas | colunas distintas: {len(hashes)} | '
          f'nomeadas: {before} (xoreos) -> {after} (+ dicionario) = {100 * after / len(hashes):.0f}%')

if __name__ == '__main__':
    main(*sys.argv[1:])

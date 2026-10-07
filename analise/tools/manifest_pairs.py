"""Imprime 'hash nome' para cada arquivo NOMEADO de um manifesto de HERF.
Aceita os dois formatos:
  - _manifest.json do tools/herf.py (Python)
  - _manifesto.json do sonic-dump (Rust; usa só o pacote 'test')
Para arquivos que eram '.small', recoloca o sufixo do nome original (é dele que vem o hash)."""
import json, sys
for e in json.load(open(sys.argv[1])):
    if 'nome' in e:                       # formato do sonic-dump
        if e.get('pacote') != 'test' or not e['nome_recuperado']:
            continue
        name, small = e['nome'], e['era_small']
    else:                                 # formato do herf.py
        if not e['named']:
            continue
        name, small = e['name'], e.get('compressed')
    if small and not name.lower().endswith('.small'):
        name += '.small'
    print(e['hash'], name)

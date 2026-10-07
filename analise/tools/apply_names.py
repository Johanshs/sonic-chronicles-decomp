"""Aplica project/symbols_manual.txt a um symbols.txt do dsd (nomes manuais vencem)."""
import re, sys
manual = {}
for line in open(sys.argv[1]):
    line = line.split('#')[0].strip()
    if line:
        a, n = line.split()[:2]
        manual[int(a, 16)] = n
out = []
for line in open(sys.argv[2]):
    m = re.match(r'(\S+)( kind:\S+ addr:(0x[0-9a-f]+).*)', line.rstrip('\n'))
    if m and int(m[3], 16) in manual:
        line = manual[int(m[3], 16)] + m[2] + '\n'
    out.append(line)
open(sys.argv[3], 'w').write(''.join(out))
print(f'{len(manual)} nomes manuais aplicados')

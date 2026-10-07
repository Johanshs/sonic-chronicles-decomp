"""Converte os symbols.txt do dsd (main + ITCM) no TSV lido por SetupSonic.java."""
import re, sys
for f in ('arm9/symbols.txt', 'arm9/itcm/symbols.txt'):
    for line in open(f'{sys.argv[1]}/{f}'):
        m = re.match(r'(\S+) kind:function\((\w+),size=(0x[0-9a-f]+)\S*\) addr:(0x[0-9a-f]+)', line)
        if m and int(m[3], 16) > 0:
            print(f'{m[4]}\t{m[1]}\t{m[2]}\t{m[3]}')

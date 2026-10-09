"""Compacta uma ROM de DS: tira o espaço morto entre os arquivos e corta no menor tamanho.

Uso: python3 compactar.py entrada.nds saida.nds

Por que existe: o `sonic-mod pack` grava cada pacote (HERF) alterado NO FIM da ROM e deixa
o antigo onde estava, sem uso. Com o conteúdo novo (PR #39), isso levou a ROM de 124 MB
usados para 172 MB, e o tamanho do cartão subiu de 128 para 256 MB, embora os arquivos
vivos continuem somando ~123 MB. Uma ROM de 256 MB ocupa o dobro no cartão SD e é uma
suspeita (não confirmada) no menu do R4 que ficou em branco.

Como: tudo antes do primeiro arquivo (cabeçalho, ARM9, tabelas de overlays, nomes e
FAT, banner) fica como está. Os arquivos da FAT são copiados um atrás do outro, na
ordem em que estavam, alinhados em 0x200 bytes (como no jogo original); o ARM7, se
estiver depois dos arquivos (o enxerto do painel o põe lá), vem em seguida. A FAT e o
cabeçalho (posição do ARM7, tamanho usado, capacidade, CRC) são corrigidos e o resto é
preenchido com 0xFF, até a menor capacidade em que tudo cabe.

No fim, o script confere byte a byte que cada arquivo, o ARM7 e o resto do começo da ROM
saíram iguais aos da entrada.
"""
import struct
import sys

ALINHAMENTO = 0x200


def crc16(dados):
    crc = 0xFFFF
    for b in dados:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def alinhar(x):
    return (x + ALINHAMENTO - 1) // ALINHAMENTO * ALINHAMENTO


def main(entrada, saida):
    rom = open(entrada, 'rb').read()
    cab = bytearray(rom[:0x200])
    fat, fat_tam = struct.unpack_from('<2I', cab, 0x48)
    arm7, _, _, arm7_tam = struct.unpack_from('<4I', cab, 0x30)
    entradas = [list(struct.unpack_from('<2I', rom, fat + i)) for i in range(0, fat_tam, 8)]
    vivos = [i for i, (ini, fim) in enumerate(entradas) if fim > ini]
    inicio = min(entradas[i][0] for i in vivos)
    if arm7 < inicio and arm7 + arm7_tam > inicio:
        raise SystemExit('o ARM7 cruza o começo dos arquivos: layout que não conheço')

    novo = bytearray(rom[:inicio])
    pos = inicio
    nova_fat = [e[:] for e in entradas]
    for i in sorted(vivos, key=lambda i: entradas[i][0]):
        ini, fim = entradas[i]
        pos = alinhar(pos)
        novo.extend(b'\xFF' * (pos - len(novo)))
        novo.extend(rom[ini:fim])
        nova_fat[i] = [pos, pos + (fim - ini)]
        pos += fim - ini
    # entradas vazias (início = fim) apontam para onde estão, sem dados: ficam como estavam
    arm7_novo = arm7
    if arm7 >= inicio:
        pos = alinhar(pos)
        novo.extend(b'\xFF' * (pos - len(novo)))
        novo.extend(rom[arm7:arm7 + arm7_tam])
        arm7_novo = pos
        pos += arm7_tam
    usado = pos

    for i, (ini, fim) in enumerate(nova_fat):
        struct.pack_into('<2I', novo, fat + 8 * i, ini, fim)
    # capacidade do cartão: 128 KB << n
    n = 0
    while (0x20000 << n) < usado:
        n += 1
    struct.pack_into('<I', novo, 0x30, arm7_novo)
    struct.pack_into('<I', novo, 0x80, usado)
    novo[0x14] = n
    struct.pack_into('<H', novo, 0x15E, crc16(novo[:0x15E]))
    novo.extend(b'\xFF' * ((0x20000 << n) - len(novo)))

    # conferência
    for i in vivos:
        a, b = entradas[i]
        c, d = nova_fat[i]
        assert rom[a:b] == novo[c:d], f'arquivo {i} diferente'
    assert rom[arm7:arm7 + arm7_tam] == novo[arm7_novo:arm7_novo + arm7_tam], 'ARM7 diferente'
    antes = bytearray(rom[0x200:inicio])
    depois = bytearray(novo[0x200:inicio])
    antes[fat - 0x200:fat - 0x200 + fat_tam] = depois[fat - 0x200:fat - 0x200 + fat_tam]
    assert antes == depois, 'o começo da ROM mudou fora da FAT'

    open(saida, 'wb').write(novo)
    print(f'{len(vivos)} arquivos; usado {struct.unpack_from("<I", rom, 0x80)[0] / 2**20:.1f} MB -> '
          f'{usado / 2**20:.1f} MB; cartão {len(rom) // 2**20} MB -> {len(novo) // 2**20} MB')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

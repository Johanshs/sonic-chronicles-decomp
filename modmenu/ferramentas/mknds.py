"""Monta um .nds mínimo a partir de dois binários nossos (ARM9 e ARM7).

Uso: python3 mknds.py arm9.bin arm7.bin saida.nds

Serve só para a ROM de teste do painel: nada do jogo entra aqui. O cabeçalho segue o
GBATEK ("DS Cartridge Header"). O logo da Nintendo fica zerado: o DeSmuME inicia a ROM
direto (sem firmware) e não confere o logo; um DS de verdade conferiria.
"""
import struct
import sys

ARM9_RAM = 0x02000000
ARM7_RAM = 0x037F8000


def crc16(dados):
    """CRC-16 do cabeçalho (o mesmo do NitroSDK e de engine/.../nds.rs)."""
    crc = 0xFFFF
    for b in dados:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def alinhar(dados, n=0x200):
    return dados + b'\0' * (-len(dados) % n)


def main(arm9_arq, arm7_arq, saida):
    arm9 = alinhar(open(arm9_arq, 'rb').read(), 4)
    arm7 = alinhar(open(arm7_arq, 'rb').read(), 4)
    off9 = 0x4000
    off7 = off9 + len(alinhar(arm9))
    fim = off7 + len(alinhar(arm7))

    h = bytearray(0x4000)
    h[0x000:0x00C] = b'PAINEL TESTE'
    h[0x00C:0x010] = b'####'  # código de jogo fictício
    h[0x010:0x012] = b'00'
    struct.pack_into('<IIII', h, 0x020, off9, ARM9_RAM, ARM9_RAM, len(arm9))
    struct.pack_into('<IIII', h, 0x030, off7, ARM7_RAM, ARM7_RAM, len(arm7))
    struct.pack_into('<I', h, 0x080, fim)       # tamanho usado da ROM
    struct.pack_into('<I', h, 0x084, 0x4000)    # tamanho do cabeçalho
    struct.pack_into('<H', h, 0x15E, crc16(h[:0x15E]))

    rom = bytes(h) + alinhar(arm9) + alinhar(arm7)
    open(saida, 'wb').write(rom)
    print(f'{saida}: {len(rom)} bytes (ARM9 {len(arm9)} bytes, ARM7 {len(arm7)} bytes)')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

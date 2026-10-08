"""Completa o CRC da "área segura" no cabeçalho da ROM reconstruída.

Por quê: os primeiros 16 KB do ARM9 (offset 0x4000 a 0x8000 da ROM) são a
"área segura". No cartucho ela fica criptografada (Blowfish/KEY1) e o
cabeçalho guarda, em 0x6C, um CRC16 dessa versão criptografada. A chave está
na BIOS do ARM7 do DS, que não podemos distribuir. Sem ela, o `dsd rom build`
grava 0 nesse campo, e por consequência o CRC do cabeçalho (0x15E) também muda.

Como resolve sem a BIOS: o CRC depende só dos bytes da área segura (e da
chave fixa). Se esses 16 KB da ROM reconstruída são idênticos aos da ROM
original, o CRC certo é o mesmo da original. O script confere isso byte a byte
e só então copia o valor; depois recalcula o CRC do cabeçalho. Se a área
segura mudou (alguém alterou o começo do ARM9), ele recusa: aí é preciso
passar a BIOS ao dsd (`dsd rom build --arm7-bios bios7.bin`).

Uso: python3 crc_area_segura.py rom_original.nds rom_reconstruida.nds
"""
import struct, sys


def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


orig_path, nova_path = sys.argv[1], sys.argv[2]
with open(orig_path, "rb") as f:
    orig = f.read(0x8000)
with open(nova_path, "r+b") as f:
    nova = bytearray(f.read(0x8000))
    if nova[0x4000:0x8000] != orig[0x4000:0x8000]:
        sys.exit("ERRO: a área segura (0x4000-0x8000) mudou; o CRC precisa ser "
                 "recalculado com a BIOS do ARM7 (dsd rom build --arm7-bios)")
    crc_orig = struct.unpack_from("<H", orig, 0x6C)[0]
    crc_nova = struct.unpack_from("<H", nova, 0x6C)[0]
    if crc_nova not in (0, crc_orig):
        sys.exit(f"ERRO: CRC da área segura inesperado: {crc_nova:#06x}")
    struct.pack_into("<H", nova, 0x6C, crc_orig)
    struct.pack_into("<H", nova, 0x15E, crc16(nova[:0x15E]))
    f.seek(0)
    f.write(nova[:0x200])
print(f"área segura idêntica; CRC {crc_orig:#06x} copiado e CRC do cabeçalho recalculado")

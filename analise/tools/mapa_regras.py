#!/usr/bin/env python3
"""Mapeia as 74 regras de combate para os endereços onde o jogo as guarda.

    python3 analise/tools/mapa_regras.py arm9.bin

`CRules_LoadCombatRules` (0x0201f270) lê cada linha de `combatrules.gda` com a
função 0x0201b3bc (tabela, linha, coluna, destino) e guarda o valor numa variável
global, às vezes convertido. Em vez de ler as 74 chamadas à mão, este script executa a
função no Unicorn:

- a leitura da tabela (0x0201b3bc) é trocada por uma função nossa que devolve um valor
  de teste e anota a linha pedida;
- as funções que abrem o arquivo (0x0201ef68, 0x02004e68, 0x0201ae10, 0x02004f70) não
  fazem nada;
- o divisor de hardware (0x04000280), usado nas regras com casas decimais, é imitado;
- cada escrita fora da pilha vira "a regra N mora em tal endereço".

Rodando duas vezes com valores de teste diferentes (100 e 0x1000 + N), dá para ver a
conversão: igual (inteiro), ×4096 (ponto fixo 20.12 do DS), 0/1 (booleano), ÷100 ou
÷1000 em ponto fixo. A saída é a tabela de docs/CHEATS.md e o dicionário REGRAS do
ar_codes.py. Requer: pip install unicorn
"""
import struct
import sys

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R3, UC_ARM_REG_SP

BASE = 0x02000000
INICIO, FIM_REGRAS = 0x0201F270, 0x0201F7DC   # depois da regra 73 a função lê outra tabela
LER_TABELA = 0x0201B3BC
NAO_FAZ_NADA = {0x0201EF68, 0x02004E68, 0x0201AE10, 0x02004F70}
PILHA = (0x023E0000, 0x02400000)
DIV = 0x04000280


def executar(arm9, teste):
    """Roda a função; devolve [(endereço, valor gravado, linha da tabela)]."""
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(BASE, 0x400000)
    mu.mem_write(BASE, arm9)
    mu.mem_map(0x04000000, 0x1000)
    volta = 0x02380000
    mu.mem_write(volta, b"\xfe\xe7")  # b . (laço infinito onde a função retorna)
    mu.reg_write(UC_ARM_REG_SP, 0x023F0000)
    mu.reg_write(UC_ARM_REG_R0, 0x02300000)
    mu.reg_write(UC_ARM_REG_LR, volta | 1)
    estado = {"linha": None}
    escritas = []

    def codigo(uc, end, tam, _):
        if end in (volta, FIM_REGRAS):
            uc.emu_stop()
            return
        if end == LER_TABELA or end in NAO_FAZ_NADA:
            if end == LER_TABELA:
                linha, dest = uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R3)
                estado["linha"] = linha
                uc.mem_write(dest, struct.pack("<I", teste(linha)))
                if not PILHA[0] <= dest < PILHA[1]:
                    escritas.append((dest, teste(linha), linha))
            uc.reg_write(UC_ARM_REG_R0, 1)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def escrita(uc, acesso, end, tam, valor, _):
        if not PILHA[0] <= end < PILHA[1] and not 0x04000000 <= end < 0x04001000:
            escritas.append((end, valor & 0xFFFFFFFF, estado["linha"]))

    def divisor(uc, acesso, end, tam, valor, _):
        if 0x040002A0 <= end < 0x040002B0:
            modo = uc.mem_read(DIV, 4)[0] & 3
            n = struct.unpack("<q", uc.mem_read(0x04000290, 8))[0]
            d = struct.unpack("<q", uc.mem_read(0x04000298, 8))[0]
            if modo == 0:
                n = struct.unpack("<i", uc.mem_read(0x04000290, 4))[0]
            if modo in (0, 1):
                d = struct.unpack("<i", uc.mem_read(0x04000298, 4))[0]
            q = int(n / d) if d else 0
            uc.mem_write(0x040002A0, struct.pack("<qq", q, n - q * d))

    mu.hook_add(UC_HOOK_CODE, codigo)
    mu.hook_add(UC_HOOK_MEM_WRITE, escrita)
    mu.hook_add(UC_HOOK_MEM_READ, divisor, begin=DIV, end=0x040002B0)
    mu.emu_start(INICIO | 1, volta, count=500000)
    return escritas


def formato(v100, v_teste, linha):
    if v100 == 100 and v_teste == 0x1000 + linha:
        return "int"
    if v100 == 100 << 12:
        return "fx"          # ponto fixo: valor × 4096
    if v100 in (0, 1):
        return "bool"
    if v100 == 0x1000:
        return "fx/100"      # valor/100 em ponto fixo
    if v100 == 0x199:
        return "fx/1000"     # valor/1000 em ponto fixo
    return "?"


def mapa(arm9):
    a = executar(arm9, lambda n: 100)
    b = executar(arm9, lambda n: 0x1000 + n)
    regras = {}
    for (end, v1, linha), (end2, v2, _) in zip(a, b):
        assert end == end2
        regras[linha] = (end, formato(v1, v2, linha))
    return regras


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    arm9 = open(sys.argv[1], "rb").read()
    for linha, (end, fmt) in sorted(mapa(arm9).items()):
        print(f"{linha:2}  0x{end:08X}  {fmt}")


if __name__ == "__main__":
    main()

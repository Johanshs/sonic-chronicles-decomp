"""Enxerta o painel na SUA cópia do Sonic Chronicles (EUA, YWSE) e grava outra ROM.

Uso: python3 enxertar.py rom_original.nds build/painel_jogo.elf saida.nds

A ROM original não é alterada. O que muda na cópia (todos os endereços são do ARM9):

1. O código do painel vira um bloco de "autoload" novo. Autoload é a lista que o
   próprio início do programa (crt0 do NitroSDK) percorre para copiar blocos do
   arquivo do ARM9 para outros lugares da memória; o jogo já a usa para o ITCM e o
   DTCM. Acrescentamos uma terceira entrada: "copie o painel para 0x023D8000".
2. O heap do jogo ia até 0x023E0000 (OS_GetInitArenaHi, literal em 0x020d8c9c). Ele
   passa a terminar onde o painel começa, para o jogo nunca usar a nossa memória. O
   começo do heap não muda, então os objetos do heap ficam nos mesmos endereços do
   jogo original e os cheats que dependem deles continuam valendo.
3. Em 0x02000d50, no laço principal, `bl func_02002708` (ler os botões) vira
   `bl gancho`. O gancho chama o painel e depois a função original.
4. O ARM9 cresce. Na ROM ele é seguido de perto pelo ARM7, então o ARM7 é mudado para o
   fim dos dados da ROM (o cabeçalho diz onde ele está, então basta atualizar o
   endereço). O cabeçalho ganha os tamanhos novos e o CRC certo.

Antes de mudar qualquer coisa, o script confere que cada ponto tem o valor esperado da
versão YWSE. Se não tiver (outra versão, ROM já modificada), ele para sem gravar nada.
"""
import struct
import sys

BASE = 0x02000000
PARAMS = 0xB9C                     # parâmetros do módulo (NitroSDK _start_ModuleParams)
CHAMADA = 0x02000D50               # bl func_02002708 no main
ALVO_ORIGINAL = 0x02002708
LITERAL_ARENA_FIM = 0x020D8C9C     # OS_GetInitArenaHi, caso 0 (memória principal)
ARENA_FIM_ORIGINAL = 0x023E0000
NITROCODE = 0xDEC00621


class Erro(Exception):
    pass


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def crc16(dados):
    crc = 0xFFFF
    for b in dados:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def ler_elf(caminho):
    """Lê do ELF do painel: os bytes carregados (de .text até __painel_fim_carregado),
    o endereço inicial e os símbolos. ELF32 little-endian, o que o ld.lld gera."""
    e = open(caminho, 'rb').read()
    if e[:4] != b'\x7fELF' or e[4] != 1 or e[5] != 1:
        raise Erro(f'{caminho} não é um ELF32 little-endian')
    shoff, = struct.unpack_from('<I', e, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', e, 0x2E)
    secs = [struct.unpack_from('<10I', e, shoff + i * shentsize) for i in range(shnum)]
    simbolos = {}
    for s in secs:
        if s[1] == 2:  # SHT_SYMTAB
            strtab = secs[s[6]]
            for o in range(s[4], s[4] + s[5], 16):
                nome_off, valor = struct.unpack_from('<II', e, o)
                nome = e[strtab[4] + nome_off:e.index(b'\0', strtab[4] + nome_off)].decode()
                if nome:
                    simbolos[nome] = valor
    inicio, fim = simbolos['__painel_inicio'], simbolos['__painel_fim_carregado']
    dados = bytearray(fim - inicio)
    for s in secs:
        tipo, addr, off, tam = s[1], s[3], s[4], s[5]
        if tipo == 1 and inicio <= addr < fim and tam:  # SHT_PROGBITS dentro do bloco
            dados[addr - inicio:addr - inicio + tam] = e[off:off + tam]
    return inicio, bytes(dados), simbolos


def codificar_bl_thumb(origem, destino):
    """Instrução BL do Thumb (dois meios-palavras) de `origem` para `destino`."""
    desl = destino - (origem + 4)
    if not -0x400000 <= desl < 0x400000 or desl & 1:
        raise Erro(f'bl de {origem:#x} para {destino:#x} fora do alcance')
    desl &= 0x7FFFFF
    return struct.pack('<HH', 0xF000 | (desl >> 12), 0xF800 | ((desl >> 1) & 0x7FF))


def decodificar_bl_thumb(origem, h1, h2):
    if h1 & 0xF800 != 0xF000 or h2 & 0xF800 != 0xF800:
        return None
    desl = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
    if desl & 0x400000:
        desl -= 0x800000
    return origem + 4 + desl


def enxertar(rom, painel_elf):
    rom = bytearray(rom)
    if rom[0x0C:0x10] != b'YWSE':
        raise Erro(f'código do jogo {rom[0x0C:0x10]!r}: este enxerto é só para YWSE (EUA)')
    if struct.unpack_from('<H', rom, 0x15E)[0] != crc16(rom[:0x15E]):
        raise Erro('CRC do cabeçalho não confere: a ROM está corrompida ou já foi mexida')

    off9, entrada9, ram9, tam9 = struct.unpack_from('<4I', rom, 0x20)
    off7, entrada7, ram7, tam7 = struct.unpack_from('<4I', rom, 0x30)
    usado = u32(rom, 0x80)
    arm9 = bytearray(rom[off9:off9 + tam9])
    # Muitos jogos do NitroSDK têm 12 bytes depois do ARM9 (assinatura 0xDEC00621 e o
    # endereço dos parâmetros). Eles vão junto.
    rodape = rom[off9 + tam9:off9 + tam9 + 12] if u32(rom, off9 + tam9) == NITROCODE else b''

    lista, lista_fim, dados_autoload = struct.unpack_from('<3I', arm9, PARAMS)
    confere = [
        (ram9 == BASE, f'ARM9 carregado em {ram9:#x}'),
        ((lista, lista_fim) == (0x02110F00, 0x02110F18), 'lista de autoload fora do lugar'),
        (lista_fim - BASE == tam9, 'a lista de autoload não termina no fim do ARM9'),
        (u32(arm9, LITERAL_ARENA_FIM - BASE) == ARENA_FIM_ORIGINAL, 'fim do heap diferente'),
        (decodificar_bl_thumb(CHAMADA, *struct.unpack_from('<HH', arm9, CHAMADA - BASE))
         == ALVO_ORIGINAL, f'em {CHAMADA:#x} não está a chamada de func_02002708'),
    ]
    for ok, msg in confere:
        if not ok:
            raise Erro(f'ROM inesperada: {msg}. Ela já foi enxertada ou é outra versão?')

    inicio, bloco, sim = ler_elf(painel_elf)
    fim_bss = sim['__painel_fim']
    if fim_bss > ARENA_FIM_ORIGINAL or inicio & 31:
        raise Erro(f'o painel ({inicio:#x}-{fim_bss:#x}) precisa caber antes de {ARENA_FIM_ORIGINAL:#x}')
    print(f'painel: {len(bloco)} bytes carregados + {fim_bss - inicio - len(bloco)} de BSS, '
          f'em {inicio:#x}-{fim_bss:#x}; o heap do jogo passa a terminar em {inicio:#x}')

    # 1. bloco novo antes da lista de autoload, e a entrada nova no fim da lista
    corte = lista - BASE
    tabela = arm9[corte:]
    entrada = struct.pack('<3I', inicio, len(bloco), fim_bss - inicio - len(bloco))
    novo9 = arm9[:corte] + bloco + tabela + entrada
    struct.pack_into('<2I', novo9, PARAMS, lista + len(bloco), lista_fim + len(bloco) + 12)
    # 2. heap: termina onde o painel começa
    struct.pack_into('<I', novo9, LITERAL_ARENA_FIM - BASE, inicio)
    # 3. gancho
    novo9[CHAMADA - BASE:CHAMADA - BASE + 4] = codificar_bl_thumb(CHAMADA, sim['gancho'] & ~1)  # bit 0 = Thumb

    # 4. montar a ROM: ARM9 no mesmo lugar; ARM7 vai para o fim se não couber mais
    novo_tam9 = len(novo9)
    fim9 = off9 + novo_tam9 + len(rodape)
    arm7 = rom[off7:off7 + tam7]
    if fim9 > off7:
        novo_off7 = (usado + 0x1FF) & ~0x1FF
        usado = novo_off7 + tam7
        print(f'ARM7 mudado de {off7:#x} para {novo_off7:#x} (o ARM9 cresceu até {fim9:#x})')
    else:
        novo_off7 = off7
    if len(rom) < usado:
        rom += b'\xFF' * (usado - len(rom))
    if novo_off7 != off7:
        rom[off7:off7 + tam7] = b'\xFF' * tam7
    rom[off9:fim9] = novo9 + rodape
    rom[novo_off7:novo_off7 + tam7] = arm7
    struct.pack_into('<I', rom, 0x2C, novo_tam9)
    struct.pack_into('<I', rom, 0x30, novo_off7)
    struct.pack_into('<I', rom, 0x80, usado)
    struct.pack_into('<H', rom, 0x15E, crc16(rom[:0x15E]))
    return bytes(rom)


def main(orig, elf, saida):
    if orig == saida:
        raise SystemExit('a saída precisa ser outro arquivo: a ROM original nunca é alterada')
    try:
        nova = enxertar(open(orig, 'rb').read(), elf)
    except Erro as e:
        raise SystemExit(f'erro: {e}')
    open(saida, 'wb').write(nova)
    print(f'gravado: {saida}')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

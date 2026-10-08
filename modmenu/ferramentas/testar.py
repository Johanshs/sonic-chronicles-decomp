"""Testa o painel na ROM de teste, no DeSmuME, sem janela.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 testar.py painel_teste.nds pasta_capturas

O que confere (cada item imprime OK ou FALHOU; o código de saída é 1 se algo falhar):
  1. O painel fica fechado e não atrapalha o "jogo" (o contador de quadros sobe).
  2. L + R + SELECT abre o painel: a tela de baixo muda e o contador PARA (jogo pausado).
  3. Mudar valores no painel escreve na RAM nos endereços do jogo, com os limites.
  4. Ao fechar, os registradores, a paleta e a VRAM da tela de baixo voltam idênticos,
     byte a byte, e o contador volta a subir.
  5. Abrir e fechar 100 vezes também devolve tudo idêntico (critério da fase B2).
Capturas das duas telas ficam em pasta_capturas.
"""
import os
import sys

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

CONTADOR = 0x02100000
R44, R45, R7, R71, NIVEL = 0x020F64C0, 0x020F64BC, 0x020F6470, 0x021A57C0, 0x02160E54
CARTEIRA = 0x02111000 + 0x114             # o esquadrão de mentira da ROM de teste
ATRIB_SONIC, ATRIB_AMY = 0x02110200, 0x02110600  # os atributos dos dois personagens
HP_INIMIGO = 0x02112200                      # o inimigo de mentira

TECLAS = {
    'A': Keys.KEY_A, 'B': Keys.KEY_B, 'L': Keys.KEY_L, 'R': Keys.KEY_R,
    'START': Keys.KEY_START, 'SELECT': Keys.KEY_SELECT,
    'CIMA': Keys.KEY_UP, 'BAIXO': Keys.KEY_DOWN, 'ESQ': Keys.KEY_LEFT, 'DIR': Keys.KEY_RIGHT,
}

falhas = []


def confere(cond, msg):
    print(('  OK      ' if cond else '  FALHOU  ') + msg)
    if not cond:
        falhas.append(msg)


class Emu:
    def __init__(self, rom):
        self.emu = DeSmuME()
        self.emu.open(rom)
        self.emu.volume_set(0)
        self.mem = self.emu.memory

    def quadros(self, n):
        for _ in range(n):
            self.emu.cycle(with_joystick=False)

    def apertar(self, *nomes, quadros=3):
        """Aperta as teclas juntas por alguns quadros e solta."""
        for n in nomes:
            self.emu.input.keypad_add_key(keymask(TECLAS[n]))
        self.quadros(quadros)
        for n in nomes:
            self.emu.input.keypad_rm_key(keymask(TECLAS[n]))
        self.quadros(3)

    def u32(self, a):
        return self.mem.unsigned.read_long(a)

    def s32(self, a):
        return self.mem.signed.read_long(a)

    def s8(self, a):
        return self.mem.signed.read_byte(a)

    def tela_de_baixo(self):
        """Tudo o que o painel promete devolver intacto."""
        m = self.mem.unsigned
        return {
            'DISPCNT_B': self.u32(0x04001000),
            'BG0CNT_B': m.read_short(0x04001008),
            'BLDCNT_B': m.read_short(0x04001050),
            'MASTER_BRIGHT_B': m.read_short(0x0400106C),
            'paleta': bytes(m[0x05000400:0x05000600]),
            'vram': bytes(m[0x06200000:0x06208000]),  # os 32 KB inteiros
        }

    def captura(self, pasta, nome):
        self.emu.screenshot().save(os.path.join(pasta, nome + '.png'))


def diferencas(a, b):
    return [k for k in a if a[k] != b[k]]


def main(rom, pasta):
    os.makedirs(pasta, exist_ok=True)
    e = Emu(rom)
    e.quadros(30)

    print('1. painel fechado')
    c0 = e.u32(CONTADOR)
    e.quadros(10)
    confere(e.u32(CONTADOR) - c0 == 10, f'o jogo roda: contador subiu {e.u32(CONTADOR) - c0} em 10 quadros')
    antes = e.tela_de_baixo()
    e.captura(pasta, '1_jogo')

    print('2. abrir com L + R + SELECT')
    e.apertar('L', 'R', 'SELECT')
    e.quadros(5)
    c1 = e.u32(CONTADOR)
    e.quadros(30)
    confere(e.u32(CONTADOR) == c1, 'jogo pausado: o contador não sobe com o painel aberto')
    confere(e.u32(0x04001000) == 0x10100, f'DISPCNT_B é o do painel ({e.u32(0x04001000):#x})')
    e.captura(pasta, '2_painel_inicio')

    print('3. editar valores')
    e.apertar('A')                       # entra em "Regras de combate (74)"
    for _ in range(44):
        e.apertar('BAIXO', quadros=1)    # desce até a regra 44 (a lista rola)
    for _ in range(5):
        e.apertar('DIR')                 # R44: 110 -> 115
    e.apertar('R')                       # +10 -> 125
    confere(e.s32(R44) == 125, f'R44 = {e.s32(R44)} (esperado 125)')
    e.apertar('BAIXO')
    for _ in range(7):
        e.apertar('L')                   # R45: 60 -> -10 (as regras aceitam negativos)
    confere(e.s32(R45) == -10, f'R45 = {e.s32(R45)} (esperado -10: 60 - 70)')
    confere(e.s32(R7) == 7, f'R7 não mudou ({e.s32(R7)})')
    e.captura(pasta, '3_regras')
    for _ in range(26):
        e.apertar('BAIXO', quadros=1)    # regra 71, formato fx/100 (0,90 guardado x 4096)
    for _ in range(5):
        e.apertar('ESQ')                 # 90 -> 85 na tela
    confere(e.s32(R71) == (85 * 41943 + 512) >> 10,
            f'R71 guardada = {e.s32(R71)} (esperado {(85 * 41943 + 512) >> 10}, ou 0,85 x 4096)')
    e.captura(pasta, '3b_regra71')
    e.apertar('B')                       # volta à tela inicial
    e.apertar('BAIXO')
    e.apertar('A')                       # entra em "Dificuldade dinamica"
    for _ in range(6):
        e.apertar('ESQ')                 # nível: 0 -> -4, sem passar do mínimo
    confere(e.s8(NIVEL) == -4, f'nível = {e.s8(NIVEL)} (esperado -4, byte com sinal)')
    e.captura(pasta, '4_dificuldade')
    e.apertar('B')
    e.apertar('BAIXO')
    e.apertar('A')                       # "Aneis" (a carteira, no esquadrão)
    e.apertar('R')                       # 8 -> 18
    confere(e.s32(CARTEIRA) == 18, f'carteira = {e.s32(CARTEIRA)} (esperado 18)')
    for _ in range(3):
        e.apertar('ESQ')                 # 18 -> 15
    confere(e.s32(CARTEIRA) == 15, f'carteira = {e.s32(CARTEIRA)} (esperado 15)')
    e.apertar('B')
    e.apertar('BAIXO')
    antes_grupo = bytes(e.mem.unsigned[0x02110000:0x02111000])
    e.apertar('A')                       # "Grupo": a lista de personagens
    e.captura(pasta, '4b_grupo')
    e.apertar('BAIXO')                   # o segundo da lista: a Amy (posição 3)
    e.apertar('A')
    e.apertar('BAIXO')
    e.apertar('BAIXO')                   # PP (ponto fixo)
    e.apertar('DIR')
    e.apertar('DIR')                     # 8 -> 10
    confere(e.s32(ATRIB_AMY + 0xB0) == 10 << 12, f'PP da Amy = {e.s32(ATRIB_AMY + 0xB0)} (esperado 10 x 4096)')
    confere(e.s32(ATRIB_SONIC + 0xB0) == 7 << 12, 'PP do Sonic não mudou')
    e.captura(pasta, '4c_membro_amy')
    e.apertar('B')                       # volta à lista
    e.apertar('BAIXO')                   # dá a volta: o Sonic de novo
    e.apertar('A')
    e.apertar('R')                       # HP 33 -> 43
    confere(e.s32(ATRIB_SONIC) == 43, f'HP do Sonic = {e.s32(ATRIB_SONIC)} (esperado 43)')
    depois_grupo = bytearray(e.mem.unsigned[0x02110000:0x02111000])
    esperado = bytearray(antes_grupo)
    esperado[0x200:0x204] = (43).to_bytes(4, 'little')
    esperado[0x6B0:0x6B4] = (10 << 12).to_bytes(4, 'little')
    confere(depois_grupo == esperado,
            'só o HP do Sonic e o PP da Amy mudaram (nada escrito no "não criatura" nem no lixo)')
    e.apertar('B')                       # volta à lista do grupo
    e.apertar('B')                       # volta à tela inicial
    e.apertar('BAIXO')
    e.apertar('A')                       # "Inimigos"
    e.apertar('A')                       # o primeiro (e único)
    e.apertar('L')                       # HP 340 -> 330
    confere(e.s32(HP_INIMIGO) == 330, f'HP do inimigo = {e.s32(HP_INIMIGO)} (esperado 330)')
    e.captura(pasta, '4d_inimigo')
    e.apertar('B')
    e.apertar('B')
    e.apertar('BAIXO')
    e.apertar('A')                       # "Acoes rapidas"
    e.apertar('A')                       # curar o grupo
    confere((e.s32(ATRIB_SONIC), e.s32(ATRIB_SONIC + 0xB0), e.s32(ATRIB_AMY), e.s32(ATRIB_AMY + 0xB0))
            == (33, 9 << 12, 23, 9 << 12), 'curar: HP e PP cheios no Sonic e na Amy')
    e.apertar('BAIXO')
    e.apertar('A')                       # inimigos com HP 1
    confere(e.s32(HP_INIMIGO) == 1, f'inimigos com HP 1: {e.s32(HP_INIMIGO)}')
    e.apertar('BAIXO')
    e.apertar('A')                       # nocautear: aqui não há a função do jogo
    confere(e.s32(HP_INIMIGO) == 1 and e.u32(0x04001000) == 0x10100,
            'nocautear sem a função do jogo: o painel recusa, não mexe no HP e continua de pé')
    e.captura(pasta, '4e_acoes')
    e.apertar('B')
    e.apertar('BAIXO')
    e.apertar('A')                       # "Itens"
    c_antes = e.u32(CONTADOR)
    e.apertar('A')                       # "dar item": aqui não há a função do jogo
    confere(e.u32(CONTADOR) == c_antes and e.u32(0x04001000) == 0x10100,
            'dar item sem a função do jogo: o painel recusa e continua de pé')
    e.captura(pasta, '4d_itens')
    e.apertar('BAIXO')                   # pilha 1: item 6, 87 unidades
    e.apertar('A')                       # "tirar 1": aqui não há a função do jogo
    confere(e.mem.unsigned.read_byte(0x02111ABB) == 87 and e.u32(0x04001000) == 0x10100,
            'tirar item sem a função do jogo: o painel recusa, não mexe na pilha e continua de pé')
    e.apertar('DIR')
    e.apertar('DIR')                     # 89
    confere(e.mem.unsigned.read_byte(0x02111ABB) == 89, f'pilha 1: {e.mem.unsigned.read_byte(0x02111ABB)} (esperado 89)')
    e.apertar('R')                       # 99, o máximo
    confere(e.mem.unsigned.read_byte(0x02111ABB) == 99, 'pilha 1 para em 99')
    e.apertar('BAIXO')                   # pilha 2: item 3, 2 unidades
    for _ in range(3):
        e.apertar('ESQ')                 # não desce de 1
    confere(e.mem.unsigned.read_byte(0x02111BBB) == 1, 'pilha 2 para em 1 (pilha vazia não)')

    print('4. fechar com START')
    e.apertar('START')
    e.quadros(5)
    depois = e.tela_de_baixo()
    d = diferencas(antes, depois)
    confere(not d, 'tela de baixo igual a antes, byte a byte' + (f' (diferem: {d})' if d else ''))
    c2 = e.u32(CONTADOR)
    e.quadros(10)
    confere(e.u32(CONTADOR) - c2 == 10, 'o jogo voltou a rodar')
    e.captura(pasta, '5_fechado')

    print('5. abrir e fechar 100 vezes')
    for i in range(100):
        e.apertar('L', 'R', 'SELECT')
        e.apertar('B' if i % 2 else 'START')
    e.quadros(5)
    d = diferencas(antes, e.tela_de_baixo())
    confere(not d, '100 ciclos sem corromper a tela' + (f' (diferem: {d})' if d else ''))

    print(f'\n{"TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"}; capturas em {pasta}')
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

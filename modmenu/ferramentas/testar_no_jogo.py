"""Testa o painel DENTRO do jogo, numa ROM já enxertada, no DeSmuME sem janela.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_no_jogo.py rom_com_painel.nds pasta_capturas

Começa um jogo novo (o roteiro de toques passa pelas telas de abertura até a primeira
exploração do capítulo 1) e confere:
  1. o enxerto está lá: o começo do heap mudou e o gancho roda uma vez por volta do laço;
  2. L + R + SELECT abre o painel (a tela do motor B passa a ser a do painel);
  3. a página "Grupo: membro 1" acha o Sonic (HP 33/33, Luck 3 no começo do jogo) e
     mudar o Luck muda o atributo de verdade;
  4. depois de 5 segundos com o painel aberto, o relógio do jogo NÃO dá o salto (o
     tempo medido na volta seguinte é o de uma volta normal);
  5. depois de fechar, a tela do motor B volta a ser a do jogo.
Leva uns 2 minutos. As capturas ficam em pasta_capturas.
"""
import os
import sys

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

GANCHO = 0x021B9500
LITERAL_ARENA = 0x020D8D10
TIME_DELTA = 0x02109B60 + 0x30     # objeto Time: tempo da última volta
LISTA_DO_GRUPO = 0x02160B28

TECLAS = {'A': Keys.KEY_A, 'B': Keys.KEY_B, 'L': Keys.KEY_L, 'R': Keys.KEY_R,
          'START': Keys.KEY_START, 'SELECT': Keys.KEY_SELECT,
          'CIMA': Keys.KEY_UP, 'BAIXO': Keys.KEY_DOWN, 'DIR': Keys.KEY_RIGHT}
falhas = []


def confere(cond, msg):
    print(('  OK      ' if cond else '  FALHOU  ') + msg)
    if not cond:
        falhas.append(msg)


def main(rom, pasta):
    os.makedirs(pasta, exist_ok=True)
    e = DeSmuME()
    e.open(rom)
    e.volume_set(0)
    m = e.memory.unsigned

    def quadros(n):
        for _ in range(n):
            e.cycle(with_joystick=False)

    def tocar(x, y):
        e.input.touch_set_pos(x, y)
        quadros(6)
        e.input.touch_release()
        quadros(2)

    def apertar(*nomes, n=6):
        for k in nomes:
            e.input.keypad_add_key(keymask(TECLAS[k]))
        quadros(n)
        for k in nomes:
            e.input.keypad_rm_key(keymask(TECLAS[k]))
        quadros(4)

    def captura(nome):
        e.screenshot().save(os.path.join(pasta, nome + '.png'))

    print('0. começar um jogo novo e chegar à exploração')
    for i in range(12):
        quadros(150)
        if i >= 4:
            tocar(128, 96)        # "Touch to Start", "start your Adventure", diálogos
    quadros(200)
    captura('1_exploracao')

    print('1. o enxerto')
    confere(m.read_long(LITERAL_ARENA) > 0x021B9500,
            f'heap do jogo começa em {m.read_long(LITERAL_ARENA):#x}, depois do painel')
    voltas = [0]
    e.memory.register_exec(GANCHO, lambda a, s: voltas.__setitem__(0, voltas[0] + 1))
    quadros(60)
    confere(voltas[0] in (30, 60), f'o gancho rodou {voltas[0]} vezes em 60 quadros (30 ou 60 por segundo)')

    print('2. abrir')
    disp_jogo = m.read_long(0x04001000)
    apertar('L', 'R', 'SELECT', n=8)
    quadros(6)
    confere(m.read_long(0x04001000) == 0x10100, 'a tela do motor B é a do painel')
    captura('2_painel')

    print('3. página do grupo')
    for _ in range(3):
        apertar('BAIXO')
    apertar('A')                           # "Grupo: membro 1"
    lista = m.read_long(LISTA_DO_GRUPO)
    sonic = next(c for c in (m.read_long(lista + 4 * i) for i in range(8))
                 if 0x02000000 <= c < 0x02400000 and m.read_long(c) == 0x020F9200)
    atributos = m.read_long(sonic + 0x1C)
    confere((m.read_long(atributos), m.read_long(atributos + 0xA0), m.read_long(atributos + 0xAC)) == (33, 33, 3),
            'Sonic no começo do jogo: HP 33/33, Luck 3')
    for _ in range(9):
        apertar('BAIXO')                   # Luck
    apertar('R')                           # +10
    confere(m.read_long(atributos + 0xAC) == 13, f'Luck = {m.read_long(atributos + 0xAC)} (esperado 13)')
    captura('3_grupo')

    print('4. relógio')
    quadros(300)                           # 5 segundos com o painel aberto
    apertar('START')
    deltas = []
    for _ in range(4):
        quadros(1)
        deltas.append(m.read_long(TIME_DELTA))
    confere(max(deltas) < 0x100, f'tempo por volta depois de fechar: {[hex(d) for d in deltas]} (normal ~0x21)')

    print('5. fechar')
    quadros(10)
    confere(m.read_long(0x04001000) != 0x10100, f'a tela do motor B voltou a ser a do jogo ({m.read_long(0x04001000):#x}; antes {disp_jogo:#x})')
    captura('4_fechado')

    print(f'\n{"TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"}; capturas em {pasta}')
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

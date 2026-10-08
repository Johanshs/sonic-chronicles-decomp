"""Testa o painel DENTRO do jogo, numa ROM já enxertada, no DeSmuME sem janela.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_no_jogo.py rom_com_painel.nds pasta_capturas

Começa um jogo novo (o roteiro de toques passa pelas telas de abertura até a primeira
exploração do capítulo 1) e confere:
  1. o enxerto está lá: o fim do heap baixou para o começo do painel, o começo NÃO mudou
     e o esquadrão está no mesmo endereço que no jogo original (0x022261E0: os cheats que
     usam endereços do heap continuam valendo), e o gancho roda uma vez por volta do laço;
  2. L + R + SELECT abre o painel (a tela do motor B passa a ser a do painel);
  3. a página "Aneis" muda a carteira (esquadrão + 0x114), a página "Grupo" acha o
     Sonic (HP 33/33, Luck 3 no começo do jogo) e mudar o Luck muda o atributo de verdade,
     e a página "Itens" dá um POW Candy pela função do próprio jogo;
  4. depois de 5 segundos com o painel aberto, o relógio do jogo NÃO dá o salto (o
     tempo medido na volta seguinte é o de uma volta normal);
  5. depois de fechar, a tela do motor B volta a ser a do jogo.
Leva uns 2 minutos. As capturas ficam em pasta_capturas.
"""
import os
import sys

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

GANCHO = 0x023D8000                # o painel mora no fim do heap (jogo/painel.ld)
LITERAL_ARENA_INICIO = 0x020D8D10  # OS_GetInitArenaLo
LITERAL_ARENA_FIM = 0x020D8C9C     # OS_GetInitArenaHi
GLOBAL_ESQUADRAO = 0x02160C18
ESQUADRAO_NO_ORIGINAL = 0x022261E0 # onde o jogo sem painel põe o esquadrão neste ponto
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
    # O DeSmuME guarda o save do cartão por nome de ROM (~/.config/desmume/*.dsv). Se
    # esta ROM já rodou com um save, o jogo mostraria os slots em vez de um jogo novo.
    # Por isso começamos com um save vazio (64 KB de 0xFF, a memória de um cartão novo).
    vazio = os.path.join(pasta, 'save_vazio.sav')
    with open(vazio, 'wb') as f:
        f.write(b'\xFF' * 65536)
    if not e.backup.import_file(vazio):
        raise SystemExit('não consegui zerar o save do emulador')
    e.reset()
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
    confere(m.read_long(LITERAL_ARENA_FIM) == GANCHO,
            f'heap do jogo termina em {m.read_long(LITERAL_ARENA_FIM):#x}, onde o painel começa')
    confere(m.read_long(LITERAL_ARENA_INICIO) == 0x021B9500,
            f'começo do heap igual ao original ({m.read_long(LITERAL_ARENA_INICIO):#x})')
    esquadrao = m.read_long(m.read_long(GLOBAL_ESQUADRAO))
    confere(esquadrao == ESQUADRAO_NO_ORIGINAL,
            f'esquadrão em {esquadrao:#x}, o mesmo endereço do jogo original')
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

    print('3. carteira e grupo')
    for _ in range(2):
        apertar('BAIXO')
    apertar('A')                           # "Aneis"
    carteira = m.read_long(esquadrao + 0x114)
    apertar('R')
    confere(m.read_long(esquadrao + 0x114) == carteira + 10,
            f'carteira {carteira} -> {m.read_long(esquadrao + 0x114)} (esperado +10)')
    apertar('B')
    apertar('BAIXO')
    apertar('A')                           # "Grupo": a lista de personagens
    captura('3a_grupo')
    apertar('A')                           # o primeiro: o Sonic
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

    print('3b. itens: dar 1 POW Candy (item 3) com a função do jogo')
    def inventario():
        inv = m.read_long(esquadrao + 0x40)
        n, dados = m.read_long(inv + 0x2C), m.read_long(inv + 0x34)
        pilhas = [m.read_long(dados + 4 * k) for k in range(n)]
        return {m.read_short(p + 0xB8): m.read_byte(p + 0xBB) for p in pilhas}
    antes = inventario()
    apertar('B')
    apertar('B')                           # tela inicial
    for _ in range(3):
        apertar('BAIXO')                   # Inimigos, Acoes rapidas, Itens
    apertar('A')                           # "Itens"
    for _ in range(3):
        apertar('DIR')                     # item 3
    apertar('A')
    depois = inventario()
    confere(depois.get(3, 0) == antes.get(3, 0) + 1,
            f'POW Candy: {antes.get(3, 0)} -> {depois.get(3, 0)} (esperado +1); pilhas {len(antes)} -> {len(depois)}')
    # O texto do painel está no mapa da BG0 do motor B (0x06207800): cada posição guarda
    # o número do caractere menos 0x20 nos 12 bits de baixo. A linha 20 mostra o nome que
    # o JOGO deu ao item escolhido (lido do texto do jogo, não do nosso código).
    def linha(n):
        return ''.join(chr((m.read_short(0x06207800 + 2 * (32 * n + c)) & 0xFFF) + 0x20) for c in range(32))
    confere('POW Candy' in linha(20), f'nome do item 3 pelo jogo: "{linha(20).strip()}"')
    captura('3b_itens')

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

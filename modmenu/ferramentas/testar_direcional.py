"""Confere o truque "Andar pelo direcional" num save, no DeSmuME sem janela.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_direcional.py rom_com_painel.nds seu.sav [pasta_capturas]

Carrega o PRIMEIRO slot do save (o .sav do cartão, cortado ou não; ele é copiado para o
emulador, o arquivo não muda), espera a exploração e, para cada seta e para uma diagonal,
segura a tecla meio segundo e mede quanto o grupo andou no mapa (esquadrão + 0x34: X em
+4 e Y em +8, pixels x 4096). Também confere que sem tecla nada anda e que a caneta
continua funcionando. Feito com o save do Capítulo 10 (Nocturne).
"""
import os
import sys

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

GLOBAL_ESQUADRAO = 0x02160C18
SETAS = {'DIR': Keys.KEY_RIGHT, 'ESQ': Keys.KEY_LEFT, 'BAIXO': Keys.KEY_DOWN, 'CIMA': Keys.KEY_UP}
falhas = []


def confere(cond, msg):
    print(('  OK      ' if cond else '  FALHOU  ') + msg)
    if not cond:
        falhas.append(msg)


def main(rom, save, pasta='capturas_direcional'):
    os.makedirs(pasta, exist_ok=True)
    # O emulador quer 64 KB; o .sav do R4 tem 512 KB com o resto em branco.
    corte = os.path.join(pasta, 'save_64k.sav')
    with open(save, 'rb') as f, open(corte, 'wb') as g:
        g.write(f.read(65536))
    e = DeSmuME()
    e.open(rom)
    e.volume_set(0)
    if not e.backup.import_file(corte):
        raise SystemExit('o emulador recusou o save')
    e.reset()
    m = e.memory.unsigned

    def quadros(n):
        for _ in range(n):
            e.cycle(with_joystick=False)

    def tocar(x, y, n=6):
        e.input.touch_set_pos(x, y)
        quadros(n)
        e.input.touch_release()
        quadros(2)

    print('0. carregar o save')
    for i in range(8):
        quadros(150)
        if i >= 4:
            tocar(128, 96)
    quadros(240)
    tocar(128, 22)          # o primeiro slot
    quadros(300)
    tocar(180, 175)         # "Start Game"
    quadros(900)
    tocar(128, 96)
    quadros(200)

    esquadrao = m.read_long(m.read_long(GLOBAL_ESQUADRAO))

    def lugar():
        o = m.read_long(esquadrao + 0x34)
        return [(v - (1 << 32) if v >= 1 << 31 else v) / 4096 for v in (m.read_long(o + 4), m.read_long(o + 8))]

    print('1. a troca')
    bl = (m.read_short(0x0204D174), m.read_short(0x0204D176))
    confere(bl != (0xF7B5, 0xFAF8), f'a chamada em 0x0204d174 foi trocada ({bl[0]:04X} {bl[1]:04X})')

    print('2. andar')
    parado = lugar()
    quadros(30)
    confere(lugar() == parado, f'sem tecla, o grupo fica parado em {parado}')
    andou = {}
    for nome, eixo, sinal in (('DIR', 0, 1), ('BAIXO', 1, 1), ('ESQ', 0, -1), ('CIMA', 1, -1)):
        antes = lugar()
        e.input.keypad_add_key(keymask(SETAS[nome]))
        quadros(30)
        e.input.keypad_rm_key(keymask(SETAS[nome]))
        quadros(15)
        depois = lugar()
        andou[nome] = round((depois[eixo] - antes[eixo]) * sinal)
    confere(sum(d > 16 for d in andou.values()) >= 3,
            f'pixels andados no sentido de cada seta (3 de 4 bastam, pode haver parede): {andou}')
    antes = lugar()
    for k in ('DIR', 'BAIXO'):
        e.input.keypad_add_key(keymask(SETAS[k]))
    quadros(30)
    for k in ('DIR', 'BAIXO'):
        e.input.keypad_rm_key(keymask(SETAS[k]))
    quadros(15)
    depois = lugar()
    dx, dy = depois[0] - antes[0], depois[1] - antes[1]
    confere(dx > 10 and dy > 10, f'diagonal DIR + BAIXO: andou ({dx:.0f}, {dy:.0f})')
    e.screenshot().save(os.path.join(pasta, 'direcional.png'))

    print('3. a caneta continua valendo')
    antes = lugar()
    tocar(200, 96, n=30)
    quadros(15)
    depois = lugar()
    confere(depois != antes, f'tocar a tela moveu o grupo: {antes} -> {depois}')

    print(f'\n{"TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"}; capturas em {pasta}')
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

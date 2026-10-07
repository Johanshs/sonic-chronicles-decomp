"""Roda a ROM no DeSmuME sem janela e executa um roteiro de ações.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 emu_run.py rom.nds pasta_saida "roteiro"

Roteiro: ações separadas por ';'
  w N          espera N quadros (60 quadros = 1 segundo)
  p TECLA [N]  aperta a tecla por N quadros (padrão 6) e solta. Teclas: A B X Y L R START SELECT UP DOWN LEFT RIGHT
  t X Y [N]    toca a tela de baixo em (X, Y) por N quadros (padrão 6)
  s NOME       salva captura das duas telas em pasta_saida/NOME.png
  save ARQ     salva o estado do emulador (savestate)
  load ARQ     carrega um estado salvo
Exemplo: "w 600; s inicio; p START; w 120; t 128 96; w 60; s depois"
Requer: pip install py-desmume
"""
import os
import sys

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

KEYS = {
    'A': Keys.KEY_A, 'B': Keys.KEY_B, 'X': Keys.KEY_X, 'Y': Keys.KEY_Y, 'L': Keys.KEY_L, 'R': Keys.KEY_R,
    'START': Keys.KEY_START, 'SELECT': Keys.KEY_SELECT,
    'UP': Keys.KEY_UP, 'DOWN': Keys.KEY_DOWN, 'LEFT': Keys.KEY_LEFT, 'RIGHT': Keys.KEY_RIGHT,
}


def main(rom, outdir, script):
    os.makedirs(outdir, exist_ok=True)
    emu = DeSmuME()
    emu.open(rom)
    emu.volume_set(0)

    def run(n):
        for _ in range(n):
            emu.cycle(with_joystick=False)

    for action in [a.strip() for a in script.split(';') if a.strip()]:
        cmd, *args = action.split()
        if cmd == 'w':
            run(int(args[0]))
        elif cmd == 'p':
            k = keymask(KEYS[args[0].upper()])
            emu.input.keypad_add_key(k)
            run(int(args[1]) if len(args) > 1 else 6)
            emu.input.keypad_rm_key(k)
            run(2)
        elif cmd == 't':
            emu.input.touch_set_pos(int(args[0]), int(args[1]))
            run(int(args[2]) if len(args) > 2 else 6)
            emu.input.touch_release()
            run(2)
        elif cmd == 's':
            emu.screenshot().save(os.path.join(outdir, args[0] + '.png'))
        elif cmd == 'save':
            emu.savestate.save_file(args[0])
        elif cmd == 'load':
            emu.savestate.load_file(args[0])
        else:
            raise SystemExit(f'ação desconhecida: {action}')
    print('ok')


if __name__ == '__main__':
    main(*sys.argv[1:4])

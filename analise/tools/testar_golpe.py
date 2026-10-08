"""Mostra, no DeSmuME sem janela, qual linha de `combo.gda` o jogo usa num golpe POW.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_golpe.py rom_mod.nds estado.dst LINHA pasta_capturas [QUADROS]

  estado.dst  um savestate do DeSmuME parado no momento em que o golpe foi escolhido
              (a tela "Choose a target" ou o começo do minijogo)
  LINHA       a linha de `combo.gda` esperada (ex.: 155 para um golpe novo)

O que faz:
  - fica de olho em `Combat_PowDamage` (0x02010810) e anota o 3º argumento, que é a
    linha de `combo.gda` do golpe: é a prova de que o jogo leu a linha nova;
  - joga o minijogo de toque: a cada quadro procura o anel VERDE (o jogo pinta o anel
    de verde no momento em que o toque conta) e toca no centro do maior grupo verde.

Atenção: este jogador automático acerta poucos anéis. Com poucos acertos o jogo marca
"Missed!" e o dano sai 0, mesmo com o golpe tendo sido escolhido e calculado. Para medir
o dano de verdade ainda é preciso jogar o minijogo à mão.
"""
import sys

from desmume.emulator import DeSmuME

POW_DAMAGE = 0x02010810          # Combat_PowDamage(this, alvo, linha_de_combo, ...)
VERDE = lambda r, g, b: g > 190 and g > r + 80 and g > b + 80


def grupos(pts, dist=10):
    """Separa os pontos em grupos ligados (dois pontos no mesmo grupo se distam < dist)."""
    restantes, saida = set(pts), []
    while restantes:
        fila, g = [restantes.pop()], []
        while fila:
            p = fila.pop()
            g.append(p)
            for q in [q for q in restantes
                      if abs(q[0] - p[0]) <= dist and abs(q[1] - p[1]) <= dist]:
                restantes.discard(q)
                fila.append(q)
        saida.append(g)
    return saida


def main(rom, estado, linha, pasta, quadros=700):
    linha, quadros = int(linha), int(quadros)
    e = DeSmuME()
    e.open(rom)
    e.volume_set(0)
    e.savestate.load_file(estado)
    reg = e.memory.register_arm9
    chamadas = []
    e.memory.register_exec(POW_DAMAGE, lambda a, s: chamadas.append(reg.r2))

    toques, q, livre = [], 0, 0
    while q < quadros:
        e.cycle(with_joystick=False)
        q += 1
        if q < livre:
            continue
        px = e.screenshot().crop((0, 192, 256, 384)).convert('RGB').load()
        pts = [(x, y) for y in range(0, 192, 2) for x in range(0, 256, 2) if VERDE(*px[x, y])]
        if len(pts) < 20:
            continue
        g = max(grupos(pts), key=len)
        if len(g) < 20:
            continue
        xs, ys = [p[0] for p in g], [p[1] for p in g]
        e.input.touch_set_pos((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
        e.cycle(with_joystick=False)
        q += 1
        e.input.touch_release()
        toques.append(q)
        livre = q + 8
    e.screenshot().save(f'{pasta}/golpe_fim.png')
    print(f'anéis acertados: {len(toques)} (quadros {toques})')
    print(f'Combat_PowDamage chamada {len(chamadas)} vez(es), linha de combo.gda: {chamadas}')
    certo = chamadas and all(c == linha for c in chamadas)
    print('  OK      ' if certo else '  FALHOU  ', f'o jogo usou a linha {linha}')
    sys.exit(0 if certo else 1)


if __name__ == '__main__':
    if not 5 <= len(sys.argv) <= 6:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

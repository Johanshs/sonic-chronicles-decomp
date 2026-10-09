"""Mostra, no DeSmuME sem janela, qual linha de `combo.gda` o jogo usa num golpe POW
e quais efeitos visuais (linhas de `VFX.gda`) ele pede.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_golpe.py rom_mod.nds estado.dst LINHA pasta [QUADROS] [--vfx N] [--auto]

  estado.dst  um savestate do DeSmuME feito COM ESTA MESMA ROM, depois de escolher o golpe
              (e as ações dos outros), antes do golpe começar. Atenção: o jogo lê as
              tabelas quando liga, então um savestate de outra ROM ainda usa as antigas.
  LINHA       a linha de `combo.gda` esperada (ex.: 155 para um golpe novo)
  --vfx N     confere também que o jogo pediu o efeito visual N (ex.: 467)
  --auto      faz como se o personagem tivesse o Chao 38 ("POW sempre perfeito"): o
              minijogo de toque se resolve sozinho. Só na memória do emulador, a ROM
              não muda.

O que faz:
  - fica de olho em `Combat_PowDamage` (0x02010810) e anota o 3º argumento, que é a
    linha de `combo.gda` do golpe: é a prova de que o jogo leu a linha nova;
  - fica de olho na função que cria um efeito visual (0x0202f47c; r1 = linha de
    `VFX.gda`, chamada pelo evento 46 de `AnimationEvents.gda`);
  - salva a tela de baixo (onde fica a batalha) a cada 2 quadros em pasta/q00000.png...;
  - sem --auto, joga o minijogo: a cada quadro procura o anel VERDE (o jogo pinta o anel
    de verde no momento em que o toque conta) e toca no centro do maior grupo verde.
    Esse jogador acerta poucos anéis; para medir dano, use --auto.
"""
import os
import sys

from desmume.emulator import DeSmuME

POW_DAMAGE = 0x02010810          # Combat_PowDamage(this, resultado, linha_de_combo, ...)
CRIA_VFX = 0x0202F47C            # cria um efeito visual: r1 = linha de VFX.gda
CHAO38_TESTE = 0x0207B884        # "ble" depois de perguntar a habilidade 0 (POW perfeito)
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


def main(rom, estado, linha, pasta, quadros=700, vfx=None, auto=False):
    linha, quadros = int(linha), int(quadros)
    os.makedirs(pasta, exist_ok=True)
    e = DeSmuME()
    e.open(rom)
    e.volume_set(0)
    e.savestate.load_file(estado)
    reg = e.memory.register_arm9
    q = 0
    chamadas, efeitos = [], []
    e.memory.register_exec(POW_DAMAGE, lambda a, s: chamadas.append(reg.r2))
    e.memory.register_exec(CRIA_VFX, lambda a, s: efeitos.append((q, reg.r1)))
    if auto:
        # o jogo pergunta "o personagem tem a habilidade 0?" e pula se não tiver;
        # trocar o pulo (0xDD00, ble) por um nop (0x46C0) faz a resposta ser sempre "sim"
        # (0x46C0 = o savestate já foi feito com --auto ligado)
        assert e.memory.unsigned.read_short(CHAO38_TESTE) in (0xDD00, 0x46C0), 'código diferente do esperado'
        e.memory.write_short(CHAO38_TESTE, 0x46C0)

    def quadro():
        nonlocal q
        e.cycle(with_joystick=False)
        q += 1
        if q % 2 == 0:
            e.screenshot().crop((0, 192, 256, 384)).save(f'{pasta}/q{q:05d}.png')

    toques, livre = [], 0
    while q < quadros:
        quadro()
        if auto or q < livre:
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
        quadro()
        e.input.touch_release()
        toques.append(q)
        livre = q + 8
    if not auto:
        print(f'anéis acertados: {len(toques)} (quadros {toques})')
    print(f'Combat_PowDamage chamada {len(chamadas)} vez(es), linha de combo.gda: {chamadas}')
    print(f'efeitos visuais pedidos (quadro, linha de VFX.gda): {efeitos}')
    certo = bool(chamadas) and all(c == linha for c in chamadas)
    print('  OK      ' if certo else '  FALHOU  ', f'o jogo usou a linha {linha}')
    if vfx is not None:
        pedidos = [f for f, v in efeitos if v == vfx]
        certo = certo and bool(pedidos)
        print('  OK      ' if pedidos else '  FALHOU  ', f'o jogo pediu o efeito {vfx}'
              + (f' (quadro {pedidos[0]}: veja {pasta}/q{pedidos[0] + pedidos[0] % 2:05d}.png e seguintes)'
                 if pedidos else ''))
    sys.exit(0 if certo else 1)


if __name__ == '__main__':
    args, vfx, auto = sys.argv[1:], None, False
    if '--auto' in args:
        args.remove('--auto')
        auto = True
    if '--vfx' in args:
        i = args.index('--vfx')
        vfx = int(args[i + 1])
        del args[i:i + 2]
    if not 4 <= len(args) <= 5:
        raise SystemExit(__doc__)
    main(*args, vfx=vfx, auto=auto)

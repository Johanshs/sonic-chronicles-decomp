"""Conta quantas vezes cada função do jogo roda, para achar onde pôr o gancho (fase B1).

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 contar_funcoes.py rom.nds estado.dst symbols.txt [quadros] [saida.json]

- estado.dst: um savestate do DeSmuME no momento do jogo que se quer medir (exploração,
  diálogo, combate, menu...).
- symbols.txt: a lista de funções do dsd (work/config/arm9/symbols.txt, gerada pelo
  analise/run_all.sh); os nomes do RTTI ajudam a ler o resultado.

Como funciona: o DeSmuME avisa quando o processador executa um endereço. Pedimos um
aviso no começo de cada uma das ~10 mil funções e contamos durante N quadros (padrão
120, 2 segundos). Uma função que rodou N vezes roda uma vez por quadro; N/2, uma vez a
cada dois quadros (o jogo roda a 30 quadros por segundo na exploração). Com milhares de
avisos o emulador fica lento: 120 quadros levam uns 3 minutos.

Foi assim que o gancho foi escolhido: o laço principal (main, 0x02000c8e) chama
func_02002708 (a leitura dos botões, do objeto Input) exatamente uma vez por volta, tanto
na exploração (60 em 120 quadros, 30 por segundo) quanto no diálogo (120 em 120).
"""
import collections
import json
import re
import sys

from desmume.emulator import DeSmuME


def ler_funcoes(caminho):
    funcs = {}
    for linha in open(caminho):
        m = re.match(r'(\S+) kind:function\((\w+),size=(0x[0-9a-f]+)\S*\) addr:(0x[0-9a-f]+)', linha)
        if m:
            funcs[int(m.group(4), 16)] = m.group(1)
    return funcs


def main(rom, estado, simbolos, quadros=120, saida=None):
    quadros = int(quadros)
    funcs = ler_funcoes(simbolos)
    emu = DeSmuME()
    emu.open(rom)
    emu.volume_set(0)
    emu.savestate.load_file(estado)
    emu.cycle(with_joystick=False)

    cont = collections.Counter()

    def aviso(endereco, _tamanho):
        cont[endereco] += 1

    for a in funcs:
        emu.memory.register_exec(a, aviso)
    for _ in range(quadros):
        emu.cycle(with_joystick=False)

    print(f'{len(cont)} funções rodaram em {quadros} quadros. Uma vez por volta do laço:')
    for a in sorted(cont):
        if cont[a] in (quadros, quadros // 2):
            print(f'  {a:#010x} {cont[a]:5d}  {funcs[a]}')
    if saida:
        json.dump({'quadros': quadros, 'contagem': {hex(a): c for a, c in cont.items()}},
                  open(saida, 'w'), indent=1)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

"""Grava em WAV o som que o jogo faz no DeSmuME, a partir de um savestate.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 gravar_som.py rom.nds estado.dst saida.wav [QUADROS]

QUADROS: quanto tempo gravar (60 quadros = 1 segundo; padrão 2400 = 40 s). Salva também
uma captura das telas a cada 10 s (saida.wav.N.png), para saber o que estava na tela.

Por que funciona: a biblioteca do DeSmuME exporta WAV_Begin, que grava a saída do chip
de som (o "núcleo" do SPU) sincronizada com a emulação. Não depende de placa de som nem
de tempo real: o emulador pode rodar mais rápido que o DS e a gravação sai certa.

O savestate guarda a RAM, onde o jogo deixou a tabela de arquivos do sound_data.sdat
quando ligou. Por isso o savestate só serve para outra ROM se o SDAT dela tiver os
arquivos nas mesmas posições (o `som.py trocar` grava no lugar quando cabe, para isso).
Requer: pip install py-desmume
"""
import ctypes
import os
import sys

import desmume
from desmume.emulator import DeSmuME

_LIB = ctypes.CDLL(os.path.join(os.path.dirname(desmume.__file__), 'libdesmume.so'))
_wav_begin = getattr(_LIB, '_Z9WAV_BeginPKc7WAVMode')   # WAV_Begin(const char*, WAVMode)
_wav_begin.argtypes, _wav_begin.restype = [ctypes.c_char_p, ctypes.c_int], ctypes.c_bool
_wav_end = getattr(_LIB, '_Z7WAV_Endv')                    # WAV_End()
WAVMODE_CORE = 0


def gravar(emu, arquivo, quadros, capturas=None):
    if not _wav_begin(arquivo.encode(), WAVMODE_CORE):
        raise SystemExit(f'não consegui abrir {arquivo} para gravar')
    for q in range(quadros):
        emu.cycle(with_joystick=False)
        if capturas and q % 600 == 599:
            emu.screenshot().save(f'{capturas}.{q + 1}.png')
    _wav_end()


def main(rom, estado, saida, quadros='2400'):
    emu = DeSmuME()
    emu.open(rom)
    emu.volume_set(0)          # só o alto-falante; a gravação do núcleo não depende dele
    emu.savestate.load_file(estado)
    gravar(emu, saida, int(quadros), capturas=saida)
    print(f'{saida}: {int(quadros) / 60:.1f} s')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:5])

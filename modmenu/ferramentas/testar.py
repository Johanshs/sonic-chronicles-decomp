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
ANEIS, ATRIBUTOS = 0x02160EB0, 0x02110200  # o grupo de mentira da ROM de teste

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
    e.apertar('A')                       # "Aneis"
    e.apertar('R')                       # 8 -> 18
    confere(e.s32(ANEIS) == 18, f'anéis = {e.s32(ANEIS)} (esperado 18)')
    e.apertar('B')
    e.apertar('BAIXO')
    e.apertar('A')                       # "Grupo: membro 1"
    e.apertar('BAIXO')
    e.apertar('BAIXO')                   # PP (ponto fixo)
    e.apertar('DIR')
    e.apertar('DIR')                     # 7 -> 9
    confere(e.s32(ATRIBUTOS + 0xB0) == 9 << 12, f'PP guardado = {e.s32(ATRIBUTOS + 0xB0)} (esperado 9 x 4096)')
    e.captura(pasta, '4b_membro1')
    antes_grupo = bytes(e.mem.unsigned[0x02110000:0x02110300])
    e.apertar('B')
    e.apertar('BAIXO')
    e.apertar('A')                       # "Grupo: membro 2", que está vazio
    e.apertar('DIR')
    e.apertar('R')
    confere(bytes(e.mem.unsigned[0x02110000:0x02110300]) == antes_grupo,
            'membro vazio: o painel não escreveu nada')
    e.captura(pasta, '4c_membro_vazio')

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

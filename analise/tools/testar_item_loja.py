"""Prova, no DeSmuME sem janela, que um item novo à venda numa loja funciona de verdade.

Uso: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
     python3 testar_item_loja.py rom_mod.nds save.sav ITEM LOJA PRECO CURA pasta_capturas

  ITEM   id do item novo em Items.gda (ex.: 288)
  LOJA   linha de stores.gda (0 Central City ... 4 The Overmart)
  PRECO  preço de compra na tabela StoreN (ex.: 15)
  CURA   quanto o .ITM cura (HealHP), para conferir o efeito (ex.: 321)

O roteiro:
  1. carrega o save (o slot 1, que precisa ser um jogo já em exploração) e espera o mapa;
  2. abre a loja LOJA com o tratador de evento do PRÓPRIO jogo (ver abrir_loja abaixo);
  3. toca a primeira linha da lista e "Buy Item": confere no inventário (RAM) que o ITEM
     entrou e que os anéis caíram exatamente PRECO;
  4. sai da loja, abre o menu > inventário > Consumables, e usa o primeiro item no Sonic.
     Antes, o HP do Sonic vai para 100 de 999 (só para medir: com o HP máximo normal
     a cura bateria no teto); confere que o HP subiu exatamente CURA e que o item saiu.
Leva uns 2 minutos. As capturas de cada etapa ficam em pasta_capturas.

O save não é modificado (o emulador trabalha numa cópia de 64 KB: o jogo só usa os
primeiros 64 KB do chip de 512 KB, e o DeSmuME só lê o save cortado nesse tamanho).
"""
import os
import struct
import sys

from desmume.emulator import DeSmuME

MODE_SWITCHER = 0x02109BA0     # objeto global que troca os modos de jogo
LACO_CHAMADA = 0x02000F1A      # no laço principal: "bl func_020310b8" (processa o modo pendente)
LACO_ORIGINAL = 0x020310B8
EVENTO_LOJA = 0x0207BE48       # tratador do evento 40 (o da conversa kron_store): r3 = loja
AREA_LIVRE = 0x023F7B00        # RAM só com zeros durante o jogo
GLOBAL_ESQUADRAO = 0x02160C18
LISTA_DO_GRUPO = 0x02160B28
VTABLE_PERSONAGEM = 0x020F9200

falhas = []


def confere(cond, msg):
    print(('  OK      ' if cond else '  FALHOU  ') + msg)
    if not cond:
        falhas.append(msg)


def bl(origem, destino):
    """Codifica um BL do Thumb (dois meios-words) de origem para destino."""
    off = (destino - (origem + 4)) >> 1
    return struct.pack('<HH', 0xF000 | ((off >> 11) & 0x7FF), 0xF800 | (off & 0x7FF))


def abrir_loja(e, indice):
    """Abre a loja `indice` chamando o tratador do jogo, o mesmo do evento 40.

    O tratador grava o índice em GameModeStateStore+4 (ModeSwitcher+0x40) e pede o
    modo 11 (loja). Para chamar uma função do jogo de fora, por poucos quadros o
    "bl" do laço principal passa a chamar um trampolim nosso, que chama o tratador
    com r3 = indice e segue para a função original com os registradores de antes.
    Depois o "bl" volta ao normal e o trampolim é apagado."""
    trampolim = struct.pack('<8H',
        0xB501,                 # push {r0, lr}
        0x2300 | indice,        # movs r3, #indice
        0x4A02,                 # ldr r2, [pc, #8]   (pc = +8) -> EVENTO_LOJA|1
        0x4790,                 # blx r2
        0xBC03,                 # pop {r0, r1}       (r0 = ModeSwitcher, r1 = lr de antes)
        0x468E,                 # mov lr, r1
        0x4A01,                 # ldr r2, [pc, #4]   (pc = +16) -> LACO_ORIGINAL|1
        0x4710)                 # bx r2
    trampolim += struct.pack('<II', EVENTO_LOJA | 1, LACO_ORIGINAL | 1)
    m = e.memory.unsigned
    antes = bytes(m[LACO_CHAMADA:LACO_CHAMADA + 4])
    assert antes == bl(LACO_CHAMADA, LACO_ORIGINAL), 'o laço principal não é o esperado'
    assert bytes(m[AREA_LIVRE:AREA_LIVRE + 32]) == bytes(32), 'a área do trampolim não está livre'
    chamou = []
    e.memory.register_exec(EVENTO_LOJA, lambda a, s: chamou.append(1))
    for i, b in enumerate(trampolim):
        e.memory.write_byte(AREA_LIVRE + i, b)
    for i, b in enumerate(bl(LACO_CHAMADA, AREA_LIVRE)):
        e.memory.write_byte(LACO_CHAMADA + i, b)
    for _ in range(10):
        e.cycle(with_joystick=False)
        if chamou:
            break
    for i, b in enumerate(antes):
        e.memory.write_byte(LACO_CHAMADA + i, b)
    for i in range(32):
        e.memory.write_byte(AREA_LIVRE + i, 0)
    e.memory.register_exec(EVENTO_LOJA, None)
    return bool(chamou), m.read_long(m.read_long(MODE_SWITCHER + 0x40) + 4)


def main(rom, save, item, loja, preco, cura, pasta):
    item, loja, preco, cura = int(item), int(loja), int(preco), int(cura)
    os.makedirs(pasta, exist_ok=True)
    e = DeSmuME()
    e.open(rom)
    e.volume_set(0)
    copia = os.path.join(pasta, 'save_64k.sav')
    with open(save, 'rb') as f, open(copia, 'wb') as g:
        g.write(f.read(65536))
    if not e.backup.import_file(copia):
        raise SystemExit('não consegui carregar o save')
    e.reset()
    m = e.memory.unsigned

    def quadros(n):
        for _ in range(n):
            e.cycle(with_joystick=False)

    def tocar(x, y, espera=30):
        e.input.touch_set_pos(x, y)
        quadros(6)
        e.input.touch_release()
        quadros(espera)

    def captura(nome):
        e.screenshot().save(os.path.join(pasta, nome + '.png'))

    def esquadrao():
        return m.read_long(m.read_long(GLOBAL_ESQUADRAO))

    def inventario():
        inv = m.read_long(esquadrao() + 0x40)
        n, dados = m.read_long(inv + 0x2C), m.read_long(inv + 0x34)
        pilhas = [m.read_long(dados + 4 * k) for k in range(n)]
        return {m.read_short(p + 0xB8): m.read_byte(p + 0xBB) for p in pilhas}

    def sonic_atributos():
        lista = m.read_long(LISTA_DO_GRUPO)
        for i in range(8):
            c = m.read_long(lista + 4 * i)
            if 0x02000000 <= c < 0x02400000 and m.read_long(c) == VTABLE_PERSONAGEM:
                return m.read_long(c + 0x1C)    # o primeiro do grupo é o Sonic

    print('0. carregar o slot 1 do save e chegar à exploração')
    quadros(1420)
    tocar(128, 96, 300)           # pula a abertura: "Touch to Start"
    tocar(128, 96, 200)           # a lista de slots
    tocar(128, 22, 120)           # slot 1: "The Story So Far"
    tocar(180, 175, 900)          # "Start Game"
    captura('0_exploracao')

    print(f'1. abrir a loja {loja} pelo tratador do jogo')
    chamou, indice = abrir_loja(e, loja)
    confere(chamou and indice == loja, f'tratador do evento 40 chamado; GameModeStateStore+4 = {indice}')
    quadros(300)
    captura('1_loja')

    print('2. comprar')
    antes, aneis = inventario(), m.read_long(esquadrao() + 0x114)
    tocar(160, 45)                # primeira linha da lista
    tocar(190, 176, 60)           # "Buy Item"
    depois, aneis2 = inventario(), m.read_long(esquadrao() + 0x114)
    captura('2_comprado')
    confere(depois.get(item, 0) == antes.get(item, 0) + 1,
            f'item {item} no inventário: {antes.get(item, 0)} -> {depois.get(item, 0)}')
    confere(aneis - aneis2 == preco, f'anéis {aneis} -> {aneis2} (esperado -{preco})')

    print('3. usar no Sonic pelo inventário')
    tocar(12, 176, 200)           # sair da loja
    at = sonic_atributos()
    e.memory.write_long(at, 100)
    e.memory.write_long(at + 0xA0, 999)
    tocar(10, 182, 90)            # abre o menu
    tocar(66, 151, 180)           # inventário
    tocar(205, 16, 60)            # aba "Consumables"
    captura('3_inventario')
    tocar(160, 45, 20)            # primeira linha
    tocar(190, 176, 90)           # "Use Item"
    captura('4_usado')
    hp = m.read_long(at)
    confere(hp - 100 == cura, f'HP do Sonic 100 -> {hp} (esperado +{cura})')
    confere(inventario().get(item, 0) == depois.get(item, 0) - 1, f'o item {item} foi gasto')

    print('\nRESULTADO:', 'tudo certo' if not falhas else f'{len(falhas)} falha(s)')
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    if len(sys.argv) != 8:
        raise SystemExit(__doc__)
    main(*sys.argv[1:8])

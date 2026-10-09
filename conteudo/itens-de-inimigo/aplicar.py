"""Cria acessórios que dão aos heróis habilidades que no jogo só os inimigos têm.

Uso: python3 aplicar.py PROJETO

  PROJETO  a pasta criada por `sonic-mod unpack` (pode já ter outros mods)

Itens novos (Type 1 = equipamento, EquipSlot 2 = acessório, qualquer herói pode usar):

  289 Phase Shifter   habilidade 25, Phased: todo ataque erra, até os "Can't miss"
  290 Evasion Band    habilidade 26, Agile ("Evading"): erra todo ataque que não seja Can't miss
  291 Repair Module   habilidade 27, auto-reparo (10%): nos inimigos, recupera HP a cada
                      rodada; num herói, ainda não visto agindo
  292 Immunity Core   habilidade 31, "Immunity" (100), a dos chefes; o efeito exato
                      ainda não foi lido no código (ver docs/COMBATE.md seção 11)

Por que funciona: a habilidade de um equipamento vem das colunas `col_ab33ab1a`
(código) e `col_dee49bb0` (valor) de Items.gda. Os inimigos ganham Phased e afins
"equipando" itens escondidos (211–230, 277–285) com esses códigos. Aqui fazemos o mesmo
com itens que um herói pode equipar.

Também: um .ITM para cada item (como o do Refresher, sem efeito extra), nome e descrição
em textos/en.csv (ids 990300–990307) e os 4 itens à venda nas 5 lojas por 50 anéis.
Pode rodar de novo: as linhas que este script cria são refeitas, não duplicadas.
"""
import csv
import os
import sys

MOLDE = '63'          # Refresher: acessório comum, que já usa a coluna de habilidade
PRECO = '50'
ITENS = [
    # id, nome do .ITM, habilidade, valor, nome, descrição
    ('289', 'PhaseShifter', '25', '1', 'Phase Shifter',
     'Bends light around the wearer. Every attack passes right through. (Phased)'),
    ('290', 'EvasionBand', '26', '1', 'Evasion Band',
     'Reflexes of a Nocturne soldier. Dodges any attack that can be dodged. (Evading)'),
    ('291', 'RepairModule', '27', '10', 'Repair Module',
     'Gizoid nanites repair the wearer, restoring 10% HP every round. (Self Repair)'),
    ('292', 'ImmunityCore', '31', '100', 'Immunity Core',
     'The core that shields the strongest foes. (Immunity)'),
]
ITM = """2DA V2.0
\t\t\tID \tEffectId  \tData\t\tSData1\tSData2\t\tSData3\t\t\tPulse
SpellData\t\t0  \t1\t\t{nome}\t0\t0\t\tICN_S_MEDKIT.NCGR\t***
CollectionData_Equip\t1  \t0\t\t2\t\t0\t-1\t\t1\t\t\t0x00000000
CollectionData_Use\t2  \t0\t\t0\t\t0\t-1\t\t-1\t\t\t0x00000000
"""


def ler(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


def gravar(p, linhas):
    with open(p, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f, lineterminator='\n').writerows(linhas)


def main(projeto):
    t = os.path.join(projeto, 'tabelas', 'test')
    ids = {i[0] for i in ITENS}

    itens = ler(os.path.join(t, 'Items.csv'))
    h = itens[0]
    molde = next(r for r in itens[1:] if r[0] == MOLDE)
    itens = [r for r in itens if r[0] not in ids]
    if int(itens[-1][0]) + 1 != int(ITENS[0][0]):
        raise SystemExit(f'Items.csv deveria terminar no item {int(ITENS[0][0]) - 1}; termina no {itens[-1][0]}')
    for k, (iid, arq, hab, valor, nome, desc) in enumerate(ITENS):
        novo = list(molde)
        novo[0] = iid
        novo[h.index('Name')] = str(990300 + 2 * k)
        novo[h.index('Description')] = str(990301 + 2 * k)
        novo[h.index('BaseItem1')] = f'Item{iid}.ITM'
        novo[h.index('MinimumCost')] = PRECO
        novo[h.index('col_ab33ab1a')] = hab
        novo[h.index('col_dee49bb0')] = valor
        itens.append(novo)
        with open(os.path.join(projeto, 'arquivos', 'test', f'Item{iid}.ITM'), 'w', encoding='utf-8') as f:
            f.write(ITM.format(nome=arq))
    gravar(os.path.join(t, 'Items.csv'), itens)

    tp = os.path.join(projeto, 'textos', 'en.csv')
    textos = ler(tp)
    novos = {}
    for k, (_, _, _, _, nome, desc) in enumerate(ITENS):
        novos[str(990300 + 2 * k)] = nome
        novos[str(990301 + 2 * k)] = desc
    textos = [r for r in textos if not r or r[0] not in novos] + [[i, s] for i, s in novos.items()]
    gravar(tp, textos)

    for n in range(1, 6):
        p = os.path.join(t, f'Store{n}.csv')
        loja = ler(p)
        loja = [loja[0]] + [r for r in loja[1:] if r[1] not in ids]
        for iid, *_ in ITENS:
            loja.append([str(int(loja[-1][0]) + 1), iid, PRECO, str(int(PRECO) // 2)])
        gravar(p, loja)
    print(f'itens {", ".join(i[0] for i in ITENS)} criados e à venda nas 5 lojas por {PRECO} anéis')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

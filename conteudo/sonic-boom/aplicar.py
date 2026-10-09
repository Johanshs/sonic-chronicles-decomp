"""Põe o golpe POW novo "Sonic Boom", com efeito visual próprio, num projeto do sonic-mod.

Uso: python3 aplicar.py PROJETO PASTA_ORIGINAIS [ESCALA] [--no-lugar-do axe-kick|whirlwind]

  PROJETO          a pasta criada por `sonic-mod unpack` (pode já ter outros mods)
  PASTA_ORIGINAIS  a pasta `herf/test` de um `sonic-dump` da sua ROM
  ESCALA           tamanho do efeito (padrão 2, o mesmo da fumaça do jogo)
  --no-lugar-do    qual golpe do Sonic sai para o Sonic Boom entrar (padrão: axe-kick)

Como um POW funciona (ver docs/DIARIO.md seção 23):
  - todo herói tem 6 VAGAS de POW (`Combo1`…`Combo6` em creatures.csv). Nenhum tem 7, a
    ficha do herói guarda o nível de só 6, e com um 7º golpe a tela "POW Moves" do
    perfil trava. Então o Sonic Boom entra NO LUGAR de um golpe;
  - cada vaga tem a sua coreografia: a linha de animations.csv da 1ª vaga é a 21, da 2ª a
    12, depois 23, 24, 25 e 26 (para todos os heróis). AnimationEvents.csv diz, quadro a
    quadro, o que acontece nela para cada herói (Skeleton 0 = Sonic): início e fim do
    minijogo (10003/10004), cada acerto (10001), o fim do golpe (10006), sons, câmera e
    efeitos (46 = criar o efeito da linha EventData de VFX.csv). Uma linha que não é vaga
    de POW (ex.: a 13) não serve: o golpe se repete sem parar ou o Sonic fica parado.

O que muda:
  1. combo.csv, linha 155: cópia do Axe Kick (linha 0) com 3 PP, dano 150/175/200 por
     acerto (2 acertos), Inescapable, dano elemental, textos novos (990200 a 990204) e a
     coreografia da vaga escolhida (col_9185ff28);
  2. creatures.csv, Sonic: o golpe 155 entra na vaga escolhida;
  3. AnimationEvents.csv: na coreografia dessa vaga, o efeito do Sonic (evento 46) passa a
     ser o 467. Só o Sonic usa esses eventos (Skeleton 0), e o golpe que saiu não aparece
     mais para ele;
  4. VFX.csv, linha 467, e arquivos/test/FX_SonicBoom.nsbmd/.nsbtx/.nsbtp: o efeito novo
     (montar_vfx.py usa o FX_SmokePuff do jogo como molde e troca só o desenho pelos
     quadros de sprites/; ver docs/DIARIO.md seção 22).
Pode rodar de novo, e também num projeto onde uma versão antiga deste script já rodou: as
linhas que ele cria são refeitas, não duplicadas.
"""
import csv
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MONTAR_VFX = os.path.join(AQUI, '..', '..', 'analise', 'tools', 'montar_vfx.py')
GOLPE = '155'          # linha de combo.gda do Sonic Boom
MOLDE_GOLPE = '0'      # Axe Kick
# golpe que sai: (vaga em creatures.csv, coreografia = linha de animations.csv, efeito do Sonic nela)
VAGAS = {'axe-kick': ('Combo1', '21', '89'),     # 89 = FX_Son_Shock
         'whirlwind': ('Combo2', '12', '85')}    # 85 = FX_SON_Whirl
MUDANCAS = {'Cost': '3', 'Damage1': '150', 'Damage2': '175', 'Damage3': '200',
            'NameStrRef': '990200', 'DescriptionStrRef': '990201',
            'DamageStrRef1': '990202', 'DamageStrRef2': '990203', 'DamageStrRef3': '990204',
            'EffectStrRef1': '23556', 'EffectStrRef2': '23556', 'EffectStrRef3': '23556',
            'Inescapable': '1', 'ElementalDamage': '1048576'}
TEXTOS = {'990200': 'Sonic Boom',
          '990201': 'Sonic breaks the sound barrier and hits a single foe with a shockwave.',
          '990202': '2x 300% of Attack damage',
          '990203': '2x 350% of Attack damage',
          '990204': '2x 400% of Attack damage'}
VFX_NOVO = '467'
NOME = 'FX_SonicBoom'


def ler(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


def gravar(p, linhas):
    with open(p, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f, lineterminator='\n').writerows(linhas)


def main(projeto, originais, escala='2', vaga='axe-kick'):
    t = os.path.join(projeto, 'tabelas', 'test')
    slot, anim, vfx_velho = VAGAS[vaga]

    combo = ler(os.path.join(t, 'combo.csv'))
    h = combo[0]
    combo = [r for r in combo if r[0] != GOLPE]
    if int(combo[-1][0]) + 1 != int(GOLPE):
        raise SystemExit(f'combo.csv deveria terminar na linha {int(GOLPE) - 1}; termina na {combo[-1][0]}')
    linha = list(next(r for r in combo[1:] if r[0] == MOLDE_GOLPE))
    linha[0] = GOLPE
    for col, v in MUDANCAS.items():
        linha[h.index(col)] = v
    linha[h.index('col_9185ff28')] = anim
    combo.append(linha)
    gravar(os.path.join(t, 'combo.csv'), combo)

    tp = os.path.join(projeto, 'textos', 'en.csv')
    textos = ler(tp)
    textos = [r for r in textos if not r or r[0] not in TEXTOS] + [[i, x] for i, x in TEXTOS.items()]
    gravar(tp, textos)

    cr = ler(os.path.join(t, 'creatures.csv'))
    sonic = cr[1]
    assert sonic[0] == '0', 'a linha 0 de creatures.csv devia ser o Sonic'
    for n in range(1, 11):          # tira o golpe de onde estiver (ex.: de um Combo7 antigo)
        if sonic[cr[0].index(f'Combo{n}')] == GOLPE:
            sonic[cr[0].index(f'Combo{n}')] = '-1'
    sonic[cr[0].index(slot)] = GOLPE
    gravar(os.path.join(t, 'creatures.csv'), cr)

    ev = ler(os.path.join(t, 'AnimationEvents.csv'))
    # versões antigas deste script copiavam eventos para a animação 13 (que só tinha o 10005)
    ev = [ev[0]] + [r for r in ev[1:] if not (r[1] == '13' and r[2] == '0' and r[4] != '10005')]
    trocados = 0
    for r in ev[1:]:
        if r[2] != '0' or r[4] != '46':
            continue
        if r[1] == anim and r[5] == vfx_velho:          # evento 46 = criar efeito visual
            r[5] = VFX_NOVO
            trocados += 1
        elif r[5] == VFX_NOVO and r[1] != anim:         # rodou antes com outra vaga: desfaz
            r[5] = next(v for _, a, v in VAGAS.values() if a == r[1])
    if trocados == 0 and not any(r[1] == anim and r[2] == '0' and r[5] == VFX_NOVO for r in ev[1:]):
        raise SystemExit(f'não achei o efeito {vfx_velho} na animação {anim} do Sonic')
    gravar(os.path.join(t, 'AnimationEvents.csv'), ev)

    vfx = ler(os.path.join(t, 'VFX.csv'))
    vfx = [r for r in vfx if r[0] != VFX_NOVO]
    if len(vfx) - 1 != int(VFX_NOVO):
        raise SystemExit(f'VFX.csv deveria ter as linhas 0 a {int(VFX_NOVO) - 1}; tem {len(vfx) - 1}')
    # ID, Type, modelo, animação, textura, troca de textura, anim. de textura, LifeTime,
    # Target, ?, Scale, OffsetX/Y/Z, Facing, FaceCamera, SoundID, CameraOffset, ?
    vfx.append([VFX_NOVO, '3', NOME + '.nsbmd', '', NOME + '.nsbtx', NOME + '.nsbtp', '',
                '300', '0', '0', escala, '0', '0', '0', '0', '0', '-1', '0', '0'])
    gravar(os.path.join(t, 'VFX.csv'), vfx)

    subprocess.run([sys.executable, MONTAR_VFX, originais, os.path.join(AQUI, 'sprites'),
                    os.path.join(projeto, 'arquivos', 'test'), NOME], check=True)
    print(f'golpe {GOLPE} no {slot} do Sonic (sai o {vaga}); coreografia {anim}; VFX {VFX_NOVO} = {NOME} (escala {escala})')


if __name__ == '__main__':
    args, vaga = sys.argv[1:], 'axe-kick'
    if '--no-lugar-do' in args:
        i = args.index('--no-lugar-do')
        vaga = args[i + 1]
        del args[i:i + 2]
    if len(args) not in (2, 3) or vaga not in VAGAS:
        raise SystemExit(__doc__)
    main(*args, vaga=vaga)

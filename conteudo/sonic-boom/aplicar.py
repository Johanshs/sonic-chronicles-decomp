"""Coloca o efeito visual novo do Sonic Boom num projeto do sonic-mod.

Uso: python3 aplicar.py PROJETO PASTA_ORIGINAIS [ESCALA]

  PROJETO          a pasta criada por `sonic-mod unpack` (já com o golpe 155, Sonic Boom:
                   ver a receita "Adicionar um golpe POW novo" em docs/MODDING.md)
  PASTA_ORIGINAIS  a pasta `herf/test` de um `sonic-dump` da sua ROM
  ESCALA           tamanho do efeito (padrão 2, o mesmo da fumaça do jogo)

O que muda (e por quê, ver docs/DIARIO.md seção 22):
  1. arquivos/test/FX_SonicBoom.nsbmd/.nsbtx/.nsbtp: o efeito, com os quadros de sprites/
     (montar_vfx.py usa o FX_SmokePuff do jogo como molde e troca só o desenho);
  2. VFX.csv, linha 467: o efeito novo (tipo 3 = modelo 3D com textura);
  3. AnimationEvents.csv: o golpe passa a tocar a animação 13 (SON_CB_PAttack02, um
     ataque do Sonic que nenhum POW usava) com os eventos do Axe Kick (animação 21,
     esqueleto 0) copiados para ela, trocando o efeito 89 (FX_Son_Shock) pelo 467;
  4. combo.csv, linha 155: a coluna da animação (col_9185ff28) passa de 21 para 13.
O Axe Kick continua igual: a animação 21 e os eventos dela não são tocados.
Pode rodar de novo: as linhas que este script cria são refeitas, não duplicadas.
"""
import csv
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MONTAR_VFX = os.path.join(AQUI, '..', '..', 'analise', 'tools', 'montar_vfx.py')
GOLPE = '155'          # linha de combo.gda do Sonic Boom
ANIM_MODELO = '21'     # animação do Axe Kick, de onde vêm os eventos
ANIM_NOVA = '13'       # SON_CB_PAttack02
VFX_VELHO = '89'       # FX_Son_Shock
VFX_NOVO = '467'
NOME = 'FX_SonicBoom'


def ler(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


def gravar(p, linhas):
    with open(p, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f, lineterminator='\n').writerows(linhas)


def main(projeto, originais, escala='2'):
    t = os.path.join(projeto, 'tabelas', 'test')

    combo = ler(os.path.join(t, 'combo.csv'))
    linha = next((r for r in combo[1:] if r[0] == GOLPE), None)
    if linha is None:
        raise SystemExit(f'combo.csv não tem a linha {GOLPE}: crie o golpe antes (docs/MODDING.md)')
    linha[combo[0].index('col_9185ff28')] = ANIM_NOVA
    gravar(os.path.join(t, 'combo.csv'), combo)

    ev = ler(os.path.join(t, 'AnimationEvents.csv'))
    ev = [ev[0]] + [r for r in ev[1:] if not (r[1] == ANIM_NOVA and r[2] == '0' and r[4] != '10005')]
    prox = max(int(r[0]) for r in ev[1:]) + 1
    for r in [r for r in ev[1:] if r[1] == ANIM_MODELO and r[2] == '0']:
        novo = [str(prox), ANIM_NOVA] + r[2:]
        if novo[4] == '46' and novo[5] == VFX_VELHO:      # evento 46 = criar efeito visual
            novo[5] = VFX_NOVO
        ev.append(novo)
        prox += 1
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
    print(f'combo {GOLPE}: animação {ANIM_NOVA}; VFX {VFX_NOVO} = {NOME} (escala {escala})')


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])

# Chronicles Studio: Framework de Assets do Sonic Chronicles

Ferramenta completa para criação, conversão, validação e injeção de assets estilizados e compatíveis com a engine do jogo **Sonic Chronicles: The Dark Brotherhood** (Nintendo DS / BioWare Aurora Engine).

---

## 1. Instalação e Requisitos

- Python 3.10 ou superior.
- Dependências Python:
  ```bash
  pip install pillow ndspy
  ```

---

## 2. Comandos da CLI (`chronicles-studio`)

Execute pelo módulo Python:
```bash
python -m tools.asset_pipeline.cli <subcomando> [opções]
```
Ou pelo script auxiliar no Windows:
```cmd
chronicles-studio.bat <subcomando> [opções]
```

### 2.1 Ícones e Sprites 2D

#### Converter imagem PNG para formatos nativos do DS (NCGR + NCLR)
Quantiza para o espaço de cores BGR555 de 15 bits, gerando blocos de 8×8 tiles com o índice 0 reservado para transparência:
```bash
python -m tools.asset_pipeline.cli icon-encode meu_icone.png ITM_Item.ncgr ITM_Item.nclr --bpp 4
```

#### Decodificar NCGR + NCLR de volta para PNG (Visualização)
```bash
python -m tools.asset_pipeline.cli icon-decode ITM_Item.ncgr ITM_Item.nclr visualizacao.png
```

---

### 2.2 Retratos de Diálogo e Imagens Compostas 2×2 (128×128)

No Sonic Chronicles, os retratos de diálogos e ícones grandes são gravados em 4 peças de 64×64 pixels (`_0`, `_1`, `_2`, `_3`):

#### Fatiar retrato de 128×128 em 4 peças NCGR e 1 NCLR compartilhado
```bash
python -m tools.asset_pipeline.cli portrait-split retrato_128.png saida_retratos/ PRTL_SonicGlad --bpp 4
```
Arquivos gerados:
- `PRTL_SonicGlad.nclr` (Paleta compartilhada)
- `PRTL_SonicGlad_0.ncgr` (Superior esquerdo)
- `PRTL_SonicGlad_1.ncgr` (Superior direito)
- `PRTL_SonicGlad_2.ncgr` (Inferior esquerdo)
- `PRTL_SonicGlad_3.ncgr` (Inferior direito)

#### Remontar as 4 peças em um PNG contínuo de 128×128
```bash
python -m tools.asset_pipeline.cli portrait-merge _0.ncgr _1.ncgr _2.ncgr _3.ncgr paleta.nclr retrato_final.png
```

---

### 2.3 Modelos 3D (Nintendo NitroSystem G3D)

#### Inspecionar e validar modelos `.nsbmd` ou texturas `.nsbtx`
Verifica contagem de polígonos, vértices, materiais, caixas de colisão e alerta sobre violações de limites de hardware do DS (limite de 1.536 polígonos e 2.048 vértices por quadro):
```bash
python -m tools.asset_pipeline.cli model-inspect modelo.nsbmd
```

#### Converter malha Wavefront `.obj` (Blender) para Nitro Intermediate `.imd`
```bash
python -m tools.asset_pipeline.cli obj-to-imd modelo.obj modelo.imd --texture-name minha_tex --palette-name minha_pal
```

---

### 2.4 Gameplay Studio: Criação Automática de Itens e Golpes POW

#### Criar um Novo Item no Projeto (`item-new`)
Automatiza a linha em `Items.csv`, gera o script de efeito 2DA em `Item<ID>.ITM`, insere os textos no TLK (`textos/en.csv`) e converte o ícone 32×32:
```bash
python -m tools.asset_pipeline.cli item-new \
  --project-dir ./meu_mod \
  --name "Chili Dog" \
  --desc "Recupera 150 de HP com sabor inigualavel." \
  --cost 200 \
  --heal-hp 150 \
  --icon-png chidog.png \
  --store Store1
```

#### Criar um Novo Golpe POW no Projeto (`pow-new`)
Cria a entrada em `combo.csv`, o script de efeito `Spell_<Nome>.SPL`, atribui ao personagem em `creatures.csv` no slot livre (`Combo1..Combo10`), insere textos e badge:
```bash
python -m tools.asset_pipeline.cli pow-new \
  --project-dir ./meu_mod \
  --name "Sonic Wind" \
  --desc "Furacao que ignora armadura do inimigo." \
  --owner 0 \
  --cost 5 \
  --dmg1 130 --dmg2 170 --dmg3 220 \
  --armor-pierce \
  --all-enemies \
  --icon-png sonic_wind_badge.png
```

---

### 2.5 VFX e Efeitos Visuais

#### Listar presets de partículas
```bash
python -m tools.asset_pipeline.cli vfx --list
```

#### Exportar preset de emissor de partículas para `.json` e binário `.emit`
```bash
python -m tools.asset_pipeline.cli vfx --export-preset chaos_energy --name "EfeitoChaos"
```

---

## 3. Diretrizes de Arte e Prompts de IA

Consulte a pasta [`style_guide/`](style_guide/):
- **[`art_style_guide.md`](style_guide/art_style_guide.md)**: Especificação estética do estilo comic book ocidental / BioWare 2008, regras de contorno, paletas e proporções.
- **[`ai_asset_prompts.md`](style_guide/ai_asset_prompts.md)**: Templates prontos para gerar retratos, ícones e texturas 3D via Midjourney, DALL-E e Stable Diffusion sem ruído de conversão.

---

## 4. Testes Automatizados

Para executar toda a suíte de testes unitários:
```bash
python -m unittest discover -s tools/asset_pipeline/tests -t . -p "test_*.py" -v
```

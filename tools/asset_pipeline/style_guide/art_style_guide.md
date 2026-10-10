# Guia de Direção de Arte: Sonic Chronicles: The Dark Brotherhood

## 1. Visão Geral e Identidade Estética

A arte visual de **Sonic Chronicles: The Dark Brotherhood** (BioWare / SEGA, 2008) é única em toda a franquia Sonic, combinando:
1. **Estilo Quadrinhos Ocidental (Comic Book / Graphic Novel)**: Fortemente inspirado nos traços das histórias em quadrinhos da Archie Comics (eras Patrick Spaziante e Tracy Yardley), com expressividade acentuada, linhas dinâmicas e painéis com bordas pretas angulares.
2. **Cel-Shading em 3 Níveis**: Renderização de superfícies com divisões marcadas entre Luz Alta (*Highlight*), Tom Médio (*Base*) e Sombra Projetada (*Shadow*), sem gradientes suaves analógicos.
3. **Contornos Pesados em Nanquim (Heavy Ink Outlines)**: Bordas pretas ou azul-escuras sólidas em volta dos personagens e objetos, garantindo legibilidade imediata na tela de baixa resolução (256×192) do Nintendo DS.

---

## 2. Especificações de Resolução e Formato

| Categoria | Dimensões | Formato DS | Paleta | Detalhes |
|---|---|---|---|---|
| **Retratos de Diálogo** | 128×128 | 4 peças NCGR (64×64) + NCLR | 16 cores (4bpp) ou 256 (8bpp) BGR555 | Cortado em 2×2 (`_0`, `_1`, `_2`, `_3`). Emoções nomeadas por sufixo (`_Glad`, `_Sca`, `_Ang`, `_Sad`). |
| **Ícones de Itens** | 32×32 | NCGR + NCLR | 16 cores (4bpp) | Moldura fina de 1 pixel ou silhueta destacada. Fundo transparente (índice 0). |
| **Badges de Golpes POW** | 24×24 ou 32×32 | NCGR + NCLR | 16 cores (4bpp) | Símbolo de ação energético (vento, fogo, impacto, engrenagem, estrela) com borda arredondada/hexagonal. |
| **Modelos 3D (Combate)** | 300–700 tris | NSBMD (`BMD0`) + NSBTX (`BTX0`) | Textura 64×64 ou 128×128 BGR555 | Cel-shading via *Toon Table* de hardware do DS; traços pretos nas bordas dos polígonos. |
| **Cenários de Exploração** | Mosaicos | `.cbgt` + `.pal` + `.2da` | Múltiplas paletas de 256 cores BGR555 | Blocos de 8×8 tiles com iluminação pintada à mão e mapa de profundidade `.cdpth`. |

---

## 3. Regras de Design: Sprites e Ícones

### 3.1 Contorno e Linhas
- **Espessura do Traço**: Contornos externos devem ter 1 a 2 pixels de espessura sólida (`#000000` ou cor escura correspondente, como azul marinho para o Sonic).
- **Linhas Internas**: Linhas de expressão faciais e dobras de luvas/sapatos devem ter 1 pixel. Evite linhas interrompidas que gerem ruído visual ("pixel noise").
- **Evitar Dithering**: O estilo BioWare Chronicles **não usa dithering clássico de 16-bits**. As sombras são aplicadas em blocos sólidos e uniformes (*flat cell shading*).

### 3.2 Paleta de Cores do Nintendo DS (BGR555)
- O hardware do DS utiliza 5 bits por canal (0–31). Cores com diferenças sutis em RGB de 8 bits são truncadas na conversão.
- Use cores altamente saturadas para compensar as telas LCD reflexivas originais do DS:
  - **Sonic Azul**: Base `#1040D0` (R:2, G:8, B:26), Sombra `#082070`, Brilho `#3070FF`.
  - **Knuckles Vermelho**: Base `#E01818` (R:28, G:3, B:3), Sombra `#800808`, Brilho `#FF5050`.
  - **Tails Amarelo/Laranja**: Base `#FFA000`, Sombra `#C06000`, Brilho `#FFD040`.
  - **Eggman/Tecnologia**: Tons metálicos frios `#8090A0` e amarelo de perigo `#F0D000`.

---

## 4. Modelagem 3D para o Hardware Nitro

### 4.1 Topologia e Geometria
- Orçamento máximo por personagem: **700 triângulos**.
- Otimização:
  - Elimine polígonos invisíveis (ex.: parte inferior dos calçados dentro do chão, topo da cabeça coberto por espinhos).
  - Use quads e triângulos uniformes; evite faces longas e extremamente estreitas (causam artefatos de interpolação no rasterizador do DS).
  - Vértices alinhados à escala de ponto fixo (1.0 = 4096 unidades).

### 4.2 Mapeamento UV e Texturização
- Uma única folha de textura (Texture Atlas) de **128×128** por personagem ou **64×64** para itens/acessórios.
- UVs espelhadas permitidas para braços, pernas e luvas para economizar espaço de VRAM.
- A textura deve conter sombras de oclusão e detalhes pintados (*baked shading*), pois o cálculo de iluminação em tempo real do DS é limitado a 4 luzes direcionais básicas.

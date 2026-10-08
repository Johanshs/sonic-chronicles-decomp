# Templates de Prompts de IA: Assets para Sonic Chronicles

Este guia contém fórmulas e templates de prompts otimizados para ferramentas de geração de imagens por inteligência artificial (Midjourney v6, DALL-E 3, Stable Diffusion XL, Flux, etc.).

Os prompts foram projetados especificamente para gerar artes que reproduzem o estilo **BioWare / Archie Sonic Comics de 2008** e que podem ser convertidas pelo nosso pipeline para os formatos nativos do Nintendo DS (`NCGR`, `NCLR`, `NSBMD`, `NSBTX`) sem degradação ou ruído visual.

---

## 1. Retratos de Diálogos (Portraits 128×128)

Os retratos no jogo utilizam close-ups dinâmicos do busto/rosto com fundo transparente ou vinheta sutil, com forte expressão facial.

### Fórmula Base
```text
close-up character portrait of [CHARACTER/SPECIES], [EMOTION/EXPRESSION], Sonic Chronicles The Dark Brotherhood art style, 2008 BioWare video game graphic novel style, Archie Sonic comics aesthetics by Patrick Spaziante, sharp heavy black ink contour outlines, bold 3-tone cel shading, clean flat vibrant colors, dynamic comic book angle, transparent background, isolated, high contrast, crisp edges, no gradients, no photorealism --ar 1:1 --style raw
```

### Exemplos Prontos

#### Sonic Confiante / Sorridente (`PRTL_SonicGlad`)
```text
close-up character portrait of Sonic the Hedgehog, confident smirk, cocky wink, Sonic Chronicles The Dark Brotherhood art style, 2008 BioWare RPG comic dialogue portrait, Archie Sonic art style, sharp thick black ink lineart, vibrant royal blue fur, flat cel-shading, comic book hatching accents, clean transparent background, isolated, crisp vector-like edges --ar 1:1
```

#### Tails Preocupado / Focado (`PRTL_TailsWorried`)
```text
close-up character portrait of Miles Tails Prower, determined yet concerned expression, ears slightly tilted back, Sonic Chronicles BioWare RPG dialogue portrait style, thick bold ink contour lines, bright warm orange-yellow fur, solid cel-shading blocks, isolated on white/transparent background, no blur --ar 1:1
```

#### Shadow Intenso / Sério (`PRTL_ShadowFierce`)
```text
close-up character portrait of Shadow the Hedgehog, intense fierce scowl, glowing crimson red eyes, crossed arms pose visible in lower frame, Sonic Chronicles BioWare comic dialogue portrait, heavy dark inking, deep black and crimson cel-shading, high contrast highlights, isolated background --ar 1:1
```

---

## 2. Ícones de Itens de Inventário (32×32)

Ícones de itens necessitam de silhuetas reconhecíveis com alto contraste para permanecerem legíveis quando reduzidos a uma grade de 32×32 pixels e quantizados para 16 cores.

### Fórmula Base
```text
game inventory icon of [ITEM DESCRIPTION], Sonic Chronicles RPG style, 2008 Nintendo DS RPG UI asset, bold dark silhouette outline, solid cel-shaded vibrant colors, clear readable shape, minimal detail, isolated on pure white background, flat lighting, clean comic graphic style --ar 1:1
```

### Exemplos Prontos

#### Semente Curativa Mística (`ITM_ChaoSeed`)
```text
game inventory icon of a glowing celestial Chao Fruit seed, radiant turquoise and gold tones, leafy stem, Sonic Chronicles BioWare RPG item icon, Nintendo DS UI asset, bold black outline, bright solid cel-shading, high contrast, isolated on white background, 32x32 pixel art readability --ar 1:1
```

#### Anel de Energia Elemental (`ITM_PlasmaRing`)
```text
game inventory icon of a futuristic metallic ring pulsing with electric cyan plasma energy, Sonic Chronicles RPG accessory icon, bold thick dark outline, glowing core, high contrast, clean comic illustration, isolated on pure white background --ar 1:1
```

#### Poção / Tônico Restaurador (`ITM_Tonic`)
```text
game inventory icon of a glass flask bottle filled with bubbling luminous purple elixir, cork stopper, brass band, Sonic Chronicles RPG medicine item, bold black ink outline, vibrant saturated colors, flat cel shading, white background --ar 1:1
```

---

## 3. Badges de Golpes POW (24×24 ou 32×32)

Os ícones de habilidades especiais (POW Moves) no menu de combate usam símbolos heráldicos de ação com bordas hexagonais ou circulares.

### Fórmula Base
```text
combat action skill badge icon, [ACTION/ELEMENT GLYPH], hexagonal emblem border, Sonic Chronicles Nintendo DS RPG combat menu icon, bold graphic comic iconography, high contrast silhouette, flat 3-color palette, vector emblem style, isolated on solid white background --ar 1:1
```

### Exemplos Prontos

#### Golpe de Impacto Sônico (`POW_SonicBoom`)
```text
combat action skill badge icon, sonic speed soundwave shockwave breaking through sound barrier, circular golden emblem frame, royal blue and white core glyph, Sonic Chronicles battle menu icon, bold black graphic silhouette, flat cel-shading, high contrast, white background --ar 1:1
```

#### Quebra de Defesa / Armadura (`POW_ArmorPierce`)
```text
combat action skill badge icon, fractured metal shield pierced by an energy punch fist, crimson and bronze emblem, Sonic Chronicles combat move icon, bold graphic comic art style, solid colors, sharp clean vectors, isolated on white background --ar 1:1
```

---

## 4. Texturas para Modelos 3D (Texture Atlas 128×128)

Texturas para o motor G3D do Nintendo DS devem conter iluminação cel-shading desenhada diretamente na textura (*baked shadows*), sem reflexos especulares em degradê analógico.

### Fórmula Base
```text
game texture atlas for low poly 3D character, [CHARACTER/PROPS], UV unwrap layout view, flat ambient lighting, Sonic Chronicles 2008 Nintendo DS texture style, hand-painted comic cel-shading, solid color zones with inked seam lines, square aspect ratio, 128x128 resolution style --ar 1:1
```

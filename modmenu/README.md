# Painel de controle (mod menu)

Código C nosso que roda **dentro** do Sonic Chronicles: aperta-se L + R + SELECT, o jogo
pausa e a tela de baixo vira um painel para ler e mudar valores do jogo ao vivo. O plano
completo está em [`docs/PLANO-MOD-MENU.md`](../docs/PLANO-MOD-MENU.md) (caminho B).

**Situação (08/10/2026):** o painel funciona numa **ROM de teste nossa**, no emulador. Ele
ainda **não está dentro do jogo**: falta achar a função do jogo que roda uma vez por
quadro (fase B1) e enxertar o código na ROM (fase B8). Nada aqui vem do jogo.

```
include/ds.h           registradores do DS que usamos (sem libnds, sem NitroSDK)
src/menu.c             o painel: páginas, campos, teclado, pausa
src/console.c          texto na tela de baixo, salvando e restaurando tudo o que toca
src/fonte.c            fonte 8x8 de domínio público (font8x8, de Daniel Hepper)
teste/                 a ROM de teste: um "jogo de mentira" que chama o painel
ferramentas/mknds.py   monta o .nds da ROM de teste
ferramentas/testar.py  roda a ROM de teste no DeSmuME e confere 10 itens
```

## Compilar e testar

Precisa de `clang` e `ld.lld` (LLVM 14 ou mais novo), `python3` e `pip install py-desmume`.
Não precisa de devkitARM: o clang já gera código para o ARM9 do DS.

```bash
cd modmenu
make            # build/painel_teste.nds e o tamanho do painel
make testar     # roda no DeSmuME sem janela; capturas em build/capturas/
```

A ROM de teste também abre no melonDS ou no DeSmuME com janela: segure L + R + SELECT.

## Como funciona, em quatro ideias

1. **Uma chamada por quadro.** O jogo vai chamar `modmenu_quadro()` uma vez por quadro
   (60 vezes por segundo). Fechado, o painel só lê os botões e volta: custa quase nada.
2. **Pausar é não devolver o controle.** Quando o combo é apertado, `modmenu_quadro()`
   entra no próprio laço (espera o quadro, lê botões, desenha) e só retorna ao fechar.
   O jogo para porque está esperando a nossa função terminar. As interrupções do jogo e
   o ARM7 (som) continuam.
3. **A tela é emprestada.** Antes de desenhar, o console copia para a RAM os
   registradores da tela de baixo, a paleta e os 5 KB de VRAM onde ficam a fonte e o mapa
   de letras. Ao fechar, copia tudo de volta. O teste confere isso byte a byte nos 32 KB
   inteiros, inclusive depois de abrir e fechar 100 vezes. Para provar que o teste pega
   erro, a restauração da paleta foi desligada de propósito uma vez: o teste falhou,
   como devia.
4. **Escrever na RAM do jogo.** Cada campo é um endereço, um tamanho (1, 2 ou 4 bytes),
   se tem sinal e os limites. A página mostra se o endereço já foi conferido no emulador
   (`emu`) ou só na análise estática (`est`).

## Tamanho

`make tamanho`: hoje são ~3,2 KB de código e dados e ~5,5 KB de BSS (quase tudo é a cópia
da tela do jogo). Isso importa porque o código precisa de um lugar livre na memória do
jogo; ver "Próximos passos".

## Limites conhecidos

- A rolagem da camada BG0 da tela de baixo (registradores BG0HOFS/VOFS) é só de escrita:
  não dá para salvá-la. Ao fechar, ela volta a 0. Só o teste no jogo dirá se isso aparece.
- Se o jogo não tiver VRAM de fundo ligada ao motor B no momento, o painel não abre (ele
  confere antes de mexer em qualquer coisa).
- X e Y não são usados: no DS só o ARM7 lê esses dois botões.
- Textos sem acento (a fonte só tem ASCII por enquanto).

## Próximos passos

- **B1, achar o gancho** (precisa da ROM): no py-desmume, contar quantas vezes cada
  função candidata roda por quadro e escolher uma que rode exatamente 1 vez em
  exploração, combate, menus e diálogo.
- **B8, pôr no jogo**: um patch que copia o painel para uma área livre da RAM e troca
  uma instrução da função escolhida por um desvio para `modmenu_quadro()`.
- Mais páginas conforme a fase A2 achar endereços (HP, PP, anéis, itens).

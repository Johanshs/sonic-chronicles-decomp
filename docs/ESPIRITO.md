# O espírito do projeto

Este projeto começou com uma pergunta simples: *"dá para abrir um jogo de DS e entender
como ele funciona?"* Este documento diz como trabalhamos e por quê.

## 1. Aprender é o objetivo, não um efeito colateral
Cada ferramenta é escrita para ser **lida**, não só usada. O código é comentado
explicando o *porquê* de cada byte; os formatos estão documentados em
[`FORMATOS.md`](FORMATOS.md); a história de como cada coisa foi descoberta está em
[`DIARIO.md`](DIARIO.md). Se você não entende uma parte, isso é um bug na documentação.

## 2. Nada vale até ser conferido contra o jogo
Uma hipótese que "parece certa" não é uma descoberta. Exemplos do que isso significa aqui:

- **Formatos:** todo escritor tem que reproduzir o arquivo original **byte a byte**
  quando nada muda (229 tabelas, 5 TLKs, 6 pacotes: todos idênticos).
- **Funções reescritas:** `HashResourceName` em C recalcula os 8.690 nomes do jogo e
  acerta todos.
- **Imagens:** a ordem dos tiles dos cenários foi escolhida *medindo* a continuidade
  das bordas (4,8 contra 35 a 56 nas outras hipóteses), não no olho.
- **Mods:** abertos no emulador e conferidos pela captura de tela.

## 3. Erros são registrados, não escondidos
Várias hipóteses estavam erradas: os "construtores" que não eram construtores, os
destrutores na posição errada da vtable, os 12 nomes falsos aceitos por colisão de
hash, os retratos pintados com a paleta do Tails. Cada um está no
[`DIARIO.md`](DIARIO.md) com a evidência que derrubou a hipótese. Isso vale mais do
que fingir que acertamos de primeira.

## 4. Honestidade sobre o que não funciona
O README e os documentos dizem claramente o que está pronto, o que é experimental e o
que é só plano. "Testado no emulador" quer dizer que foi testado no emulador. "Não
testado" fica escrito.

## 5. Nada do jogo no repositório
O jogo pertence à SEGA e à BioWare. Aqui só há **conhecimento e ferramentas**: código
escrito por nós, documentação e metadados (endereços, nomes). Tudo que deriva do jogo,
como ROM, assets, assembly e pseudo-C, é gerado localmente a partir da cópia de quem usa
e fica fora do Git (`work/`, `saida/`, `.gitignore`). Essa é a mesma postura de projetos
como o [pret](https://github.com/pret).

## 6. Ferramentas reutilizáveis
A biblioteca `sonic-formats` não sabe nada de disco nem de linha de comando: só lê e
escreve formatos. Assim, as mesmas peças servem ao extrator, ao modding e, um dia, a um
executável nativo do jogo.

## 7. Passos pequenos e verificáveis
O [plano de decompilação](PLANO-DECOMPILACAO.md) é dividido em partes de 1 a 5 dias,
cada uma com um critério de "pronto" objetivo. Um PR pequeno e conferido vale mais do
que um grande e duvidoso.

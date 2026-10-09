@ Depois de trocar instruções do jogo na RAM (os truques liga/desliga do painel), o
@ processador precisa ver o código novo. O ARM946E-S do DS tem duas memórias cache:
@   - a de DADOS: as escritas do painel podem ficar só nela, sem chegar à RAM;
@   - a de INSTRUÇÕES: ela pode guardar a instrução velha e continuar executando-a.
@ Por isso: (1) "limpar" cada linha de 32 bytes da cache de dados no trecho mudado
@ (grava na RAM o que estava só na cache), (2) esperar o buffer de escrita esvaziar e
@ (3) invalidar a cache de instruções inteira (a próxima busca lê da RAM).
@ São instruções do coprocessador 15 (mcr p15), que só existem no modo ARM, por isso
@ esta função é ARM e não Thumb como o resto do painel. O emulador não simula as caches;
@ no DS elas existem, e sem isto um truque poderia não pegar (ou pegar pela metade).
@
@ void sincronizar_codigo(u32 inicio, u32 fim)
    .syntax unified
    .arm
    .section .text.sincronizar_codigo, "ax"
    .global sincronizar_codigo
    .type sincronizar_codigo, %function
sincronizar_codigo:
    bic     r0, r0, #31
1:  mcr     p15, 0, r0, c7, c10, 1  @ limpa a linha da cache de dados (pelo endereço)
    add     r0, r0, #32
    cmp     r0, r1
    blo     1b
    mov     r0, #0
    mcr     p15, 0, r0, c7, c10, 4  @ espera o buffer de escrita
    mcr     p15, 0, r0, c7, c5, 0   @ invalida toda a cache de instruções
    bx      lr
    .size sincronizar_codigo, . - sincronizar_codigo

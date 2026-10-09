@ O gancho: a ponte entre o laço principal do jogo e o painel.
@
@ No laço principal (main, 0x02000c8e), o jogo chama a atualização dos botões
@ (func_02002708, do objeto Input) UMA vez por volta do laço. O enxerto troca essa chamada
@ (0x02000d50) por "bl gancho". O gancho:
@   1. chama o painel (que só volta quando estiver fechado);
@   2. se o painel abriu, acerta o relógio do jogo (ver abaixo);
@   3. pula para a função original, com o mesmo r0 e o mesmo endereço de volta.
@ Assim o jogo lê os botões DEPOIS do painel fechar e não vê as teclas usadas nele.
@
@ O relógio: o objeto Time (0x02109b60) mede o tempo real entre duas voltas do laço
@ com OS_GetTick (0x020d92d0) e guarda a última leitura em +0x20/+0x24 (64 bits). O jogo
@ move as coisas por esse tempo. Sem o acerto, depois de um minuto com o painel aberto o
@ jogo acharia que passou um minuto e daria um salto (visto no emulador: o Sonic andando
@ chegou ao destino num instante). Gravando ali o tick de agora, a próxima volta mede
@ só o tempo de uma volta normal.
    .syntax unified
    .thumb
    .section .text.gancho, "ax"
    .global gancho
    .type gancho, %function
gancho:
    push    {r0, lr}            @ r0 = o objeto Input; lr = a volta para o main
    bl      modmenu_quadro
    cmp     r0, #0
    beq     1f
    ldr     r3, =0x020d92d1     @ OS_GetTick (Thumb: endereço + 1); devolve r0:r1
    blx     r3
    ldr     r2, =0x02109b60     @ objeto Time
    str     r0, [r2, #0x20]
    str     r1, [r2, #0x24]
1:  pop     {r0, r3}
    mov     lr, r3
    ldr     r3, =0x02002709     @ func_02002708 (Thumb: endereço + 1)
    bx      r3
    .pool

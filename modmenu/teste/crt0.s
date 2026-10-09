@ Entrada da ROM de teste (ARM9). O DeSmuME carrega o binário em 0x02000000 e pula para
@ cá. Só preparamos a pilha, zeramos o BSS e chamamos o main da ROM de teste.
    .section .crt0, "ax"
    .arm
    .global _start
_start:
    ldr     sp, =__pilha_fim
    ldr     r0, =__bss_inicio
    ldr     r1, =__bss_fim
    mov     r2, #0
1:  cmp     r0, r1
    strlo   r2, [r0], #4
    blo     1b
    ldr     r0, =teste_main
    blx     r0
2:  b       2b
    .pool

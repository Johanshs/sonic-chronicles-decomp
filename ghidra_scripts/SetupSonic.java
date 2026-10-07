// Prepara o programa no Ghidra: cria a ITCM e as funções a partir do dsd.
// Arquivo de símbolos: TSV "endereco  nome  arm|thumb  tamanho"
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.math.BigInteger;
import java.nio.file.*;

public class SetupSonic extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String tsv = args[0];
        Memory mem = currentProgram.getMemory();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();

        // ITCM: o NitroSDK copia 0x6de0 bytes do fim do arm9.bin (offset 0x1090e0)
        // para 0x01ff8000 na inicialização ("autoload"). Recriamos essa cópia.
        byte[] itcm = new byte[0x6de0];
        mem.getBytes(sp.getAddress(0x021090e0L), itcm);
        MemoryBlock b = mem.createInitializedBlock("ITCM", sp.getAddress(0x01ff8000L),
                new ByteArrayInputStream(itcm), itcm.length, monitor, false);
        b.setExecute(true); b.setRead(true); b.setWrite(true);
        // DTCM e BSS: memória sem conteúdo inicial
        mem.createUninitializedBlock("DTCM", sp.getAddress(0x027e0000L), 0x4000, false).setWrite(true);
        mem.createUninitializedBlock("BSS", sp.getAddress(0x02110f18L), 0x021b9500L - 0x02110f18L, false).setWrite(true);

        // .text/.rodata (0x02000000-0x020f5260) nunca mudam em tempo de execução.
        // Marcando como somente-leitura, o decompilador passa a tratar os
        // "literal pools" como constantes: mostra 5381 em vez de DAT_02009bb4.
        MemoryBlock main = mem.getBlock(sp.getAddress(0x02000000L));
        mem.split(main, sp.getAddress(0x020f5260L));
        mem.getBlock(sp.getAddress(0x02000000L)).setWrite(false);
        mem.getBlock(sp.getAddress(0x02000000L)).setName("text_rodata");
        mem.getBlock(sp.getAddress(0x020f5260L)).setName("data");

        Register tmode = currentProgram.getRegister("TMode");
        java.util.List<String[]> rows = new java.util.ArrayList<>();
        for (String line : Files.readAllLines(Paths.get(tsv))) rows.add(line.split("\t"));

        // Passo 1: marcar o modo (ARM=0 / Thumb=1) de TODAS as funções antes de
        // desmontar qualquer coisa. Se desmontarmos uma por vez, o fluxo de uma
        // função pode "vazar" para a seguinte no modo errado e travar o contexto.
        for (String[] p : rows) {
            Address a = sp.getAddress(Long.decode(p[0]));
            Address end = a.add(Long.decode(p[3]) - 1);
            try {
                currentProgram.getProgramContext().setValue(tmode, a, end,
                        p[2].equals("thumb") ? BigInteger.ONE : BigInteger.ZERO);
            } catch (Exception e) { println("contexto falhou em " + a + ": " + e.getMessage()); }
        }
        // Passo 2: desmontar e criar as funções com os nomes recuperados.
        int n = 0;
        for (String[] p : rows) {
            Address a = sp.getAddress(Long.decode(p[0]));
            try {
                disassemble(a);
                Function f = getFunctionAt(a);
                if (f == null) f = createFunction(a, p[1]);
                if (f != null) { f.setName(p[1], SourceType.USER_DEFINED); n++; }
            } catch (Exception e) { println("funcao falhou em " + a + ": " + e.getMessage()); }
        }
        println("Funcoes criadas: " + n);
    }
}

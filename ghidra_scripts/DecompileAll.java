// Decompila todas as funções e grava um .c por classe (prefixo antes de "__").
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.util.*;

public class DecompileAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        File outDir = new File(getScriptArgs()[0]);
        outDir.mkdirs();
        DecompInterface di = new DecompInterface();
        // Respeitar memória somente-leitura: valores no .text/.rodata viram constantes
        DecompileOptions opts = new DecompileOptions();
        opts.grabFromProgram(currentProgram);
        opts.setRespectReadOnly(true);
        di.setOptions(opts);
        di.openProgram(currentProgram);
        Map<String, StringBuilder> files = new TreeMap<>();
        int ok = 0, fail = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (monitor.isCancelled()) break;
            String name = f.getName();
            String group = name.contains("__") ? name.substring(0, name.indexOf("__"))
                    : String.format("unsorted_%s", f.getEntryPoint().toString().substring(0, 5));
            DecompileResults r = di.decompileFunction(f, 60, monitor);
            StringBuilder sb = files.computeIfAbsent(group, k -> new StringBuilder());
            sb.append("// ").append(f.getEntryPoint()).append("\n");
            if (r != null && r.decompileCompleted()) {
                sb.append(r.getDecompiledFunction().getC()).append("\n");
                ok++;
            } else {
                sb.append("// falha ao decompilar\n\n");
                fail++;
            }
        }
        for (Map.Entry<String, StringBuilder> e : files.entrySet()) {
            try (Writer w = new FileWriter(new File(outDir, e.getKey() + ".c"))) {
                w.write(e.getValue().toString());
            }
        }
        println("Decompiladas: " + ok + " | falhas: " + fail + " | arquivos: " + files.size());
    }
}

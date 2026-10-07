# Contribuindo

Obrigado pelo interesse! Leia antes o [espírito do projeto](docs/ESPIRITO.md).

## Regras que não se negociam
1. **Nada do jogo no Git:** nada de ROM, assets, PNG/CSV extraídos, assembly ou pseudo-C
   gerado. Isso fica em `work/` / `saida/` (já no `.gitignore`). Endereços, nomes de
   funções/classes e descrições de formato podem entrar.
2. **Toda mudança em formato precisa manter a ida e volta byte a byte**:
   `SONIC_ROM=rom.nds cargo test --release` tem que passar.
3. **Toda descoberta vem com a evidência** (endereço da função, contagem que bate,
   captura do emulador). Nome dado à mão vai em `analise/symbols_manual.txt` com um
   comentário dizendo por quê.

## Branches
- **`main`**: estável. Só recebe código pronto, por pull request vindo da `dev`, com a CI verde.
  As releases saem daqui.
- **`dev`**: onde o trabalho do dia a dia acontece. Para algo maior, crie uma branch a partir
  dela (`dev` → `fase0/delink`, `modding/item-novo`...) e abra o PR de volta para a `dev`.

```
git switch dev && git pull
git switch -c fase0/delink        # opcional, para tarefas maiores
# ... trabalho, commits ...
git push -u origin fase0/delink   # PR para a dev; quando a dev estiver pronta, PR dev -> main
```

## Fluxo
- Escolha uma *issue* (o backlog segue o [plano](docs/PLANO-DECOMPILACAO.md)).
- Mencione a issue no commit ou no PR (`#12`), e use `Closes #12` quando ele a concluir.
- Um PR por assunto, pequeno. Descreva o que mudou e como verificou.
- Antes do PR:
  ```
  cd engine && cargo fmt && cargo clippy --release && cargo test --release
  SONIC_ROM=/caminho/rom.nds cargo test --release
  ```
- Erros e hipóteses descartadas também são contribuições: registre no
  [diário](docs/DIARIO.md).

## Estilo
- Código e comentários em português, explicando o *porquê* (formatos: o layout em
  comentário no topo do módulo).
- Rust: sem `unwrap()` em dados vindos da ROM; erros com contexto (`Error::Truncated { what, offset }`).
- Mensagens de commit no imperativo, em português.

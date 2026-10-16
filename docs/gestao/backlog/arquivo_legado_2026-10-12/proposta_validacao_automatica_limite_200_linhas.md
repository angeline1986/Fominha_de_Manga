# Proposta — Validação automática do limite de 200 linhas por arquivo

**Projeto:** Fominha_de_Manga  
**Status:** Proposta para avaliação futura — **não implementada**  
**Data:** 11/10/2026

## 1. Contexto e motivação

O projeto adota uma regra arquitetural: **arquivos de código não podem ultrapassar 200 linhas; arquivos `.md` são exceção**. Durante a integração do Laboratório L3 da Central V2, foram identificados arquivos que já ultrapassavam esse limite e continuavam recebendo novas responsabilidades. Conferências manuais ou revisões de diff não garantiram o cumprimento da regra.

A proposta é automatizar a verificação para detectar violações cedo, reduzir refatorações tardias e tornar a conformidade auditável, sem interferir nos algoritmos de processamento.

## 2. Objetivo

Implementar uma verificação reproduzível, executável localmente e na integração contínua, capaz de:

- Contar **linhas físicas** dos arquivos de código versionados no escopo configurado.
- Sinalizar arquivos com **mais de 200 linhas** (200 é permitido; 201 é violação).
- Isentar arquivos `.md`.
- Informar caminho, total de linhas, limite e excedente.
- Diferenciar novas violações de débitos preexistentes durante a adoção gradual.
- Impedir que novos commits/PRs ampliem o débito ou introduzam arquivos acima do limite.

## 3. Escopo e definições a validar

**Proposta inicial:** aplicar aos arquivos-fonte versionados do projeto, incluindo Python, JavaScript e outros formatos de código identificados em inventário. É necessário definir explicitamente a lista de extensões consideradas código antes da implementação; não pressupor que qualquer arquivo que não seja `.md` deva passar pela contagem (imagens, JSON de dados, binários e locks exigem política própria).

Exclusões previstas: dependências de terceiros, `.venv`, `node_modules`, caches, artefatos de execução, código gerado e submódulos, quando aplicável. As exclusões devem ser **documentadas e explícitas**, não baseadas apenas no tamanho dos arquivos. O submódulo `download/mangago_downloader` deve ter política própria, sem modificar seu conteúdo automaticamente.

**Critério:** contar quebras de linha físicas, incluindo linhas em branco e comentários. Fixar convenção para arquivos sem newline final e normalização CRLF; o script e a CI devem produzir o mesmo resultado.

## 4. Arquitetura proposta

### 4.1 Script central de verificação

Local sugerido: `dev/scripts/check_file_size.py`.

Responsabilidades:

1. Descobrir os arquivos versionados elegíveis (preferencialmente via Git, respeitando renomeações e caminhos).
2. Contar linhas e comparar com o limite de 200.
3. Aplicar exclusões justificadas.
4. Comparar com baseline de débitos legados, se habilitado.
5. Exibir diagnóstico legível e retornar código de saída não zero quando houver violação bloqueante.

Exemplo ilustrativo de saída:

```text
VIOLAÇÃO DO CONTRATO ARQUITETURAL — LIMITE: 200 LINHAS
Arquivo                                         Linhas  Excesso
central_v2/frontend/.../laboratorio/index.js     535      335
central_v2/backend/routes/router.py              237       37

Resultado: 2 violações bloqueantes.
```

### 4.2 Hook local pre-commit

Antes de criar um commit, executar o verificador contra o conteúdo **staged** (índice Git), e não apenas contra o workspace, para evitar discrepâncias. Um hook que consulta somente o disco pode validar uma versão diferente da que será commitada.

A instalação local de hooks exige configuração documentada; como hooks locais podem ser contornados, esta camada melhora a experiência do desenvolvedor, mas **não é a autoridade final**.

### 4.3 GitHub Actions

Executar a mesma verificação nos eventos de Pull Request e push relevantes. Configurar proteção de branch / required status check para bloquear o **merge** quando a verificação falhar. Um workflow isolado não impede automaticamente todo `git push` direto; isso depende das regras de proteção do repositório e das permissões configuradas.

## 5. Adoção gradual sem paralisar o desenvolvimento

### Fase 1 — Inventário (somente leitura)

- Levantar extensões e arquivos-fonte sob controle de versão.
- Listar os arquivos que hoje excedem 200 linhas.
- Identificar o débito preexistente, especialmente em módulos da Central V2.
- Registrar exceções justificadas e decidir o tratamento de arquivos gerados e submódulos.
- Não alterar código de produção.

**Entrega:** relatório de inventário e proposta de configuração.

### Fase 2 — Bloqueio de novas violações

- Arquivo novo: máximo de 200 linhas.
- Arquivo existente com até 200 linhas: não pode exceder 200.
- Arquivo legado com mais de 200 linhas: não pode crescer em relação ao baseline; reduções parciais são permitidas.
- Evitar uma exceção permanente que permita voltar a aumentar um arquivo já reduzido: atualizar o baseline de modo monotônico ou comparar com uma referência controlada.
- Hook local e CI apresentam mensagens claras e falham diante de violações novas.

**Entrega:** política anti-regressão ativa e documentada.

### Fase 3 — Regularização do legado

- Modularizar arquivos maiores em etapas pequenas, **por responsabilidades coesas**, não apenas cortando a cada 200 linhas.
- Preservar interfaces, comportamento e testes funcionais.
- Remover gradualmente entradas do baseline.
- Após eliminar o débito, aplicar regra rígida de 200 linhas a todos os arquivos elegíveis.

**Entrega:** conformidade integral sem baseline de exceções.

## 6. Critérios de aceite sugeridos

1. Arquivo novo com 201 linhas falha; arquivo com 200 passa.
2. Arquivo `.md` com mais de 200 linhas passa.
3. Um legado acima do limite pode diminuir de tamanho sem bloquear o trabalho; aumentar deve falhar.
4. Validador identifica a versão staged, inclusive em staging parcial.
5. Renomeação, remoção, CRLF e ausência de newline final são tratados consistentemente.
6. Arquivos gerados e dependências excluídas não provocam falsos positivos.
7. O mesmo conjunto de arquivos produz o mesmo resultado localmente e na CI.
8. Mensagem de falha informa arquivo e excesso, sem modificar arquivos automaticamente.
9. Suítes existentes e operações do Git não são afetadas quando não há violações.
10. Proteção do repositório efetivamente impede merge com check obrigatório falhando.

## 7. Riscos e decisões pendentes

| Tema | Decisão necessária |
|---|---|
| Tipos de arquivos | Quais extensões são consideradas código? |
| Legado | Como registrar e reduzir o baseline sem perpetuar exceções? |
| Arquivos gerados | Como reconhecê-los por regras explícitas? |
| Submódulos | Validar separadamente ou deixar fora do escopo inicial? |
| Hooks | Usar pre-commit framework ou hook Git simples? |
| CI / Branch | Existem proteções que tornam o status check obrigatório? |
| Testes | Como confirmar que a regra não bloqueia indevidamente mudanças legítimas? |

## 8. Sequência de implementação futura (somente após aprovação)

1. Fazer inventário e apresentar o relatório, sem alterações.
2. Aprovar extensões, exclusões e política de baseline.
3. Implementar o script de verificação e seus testes isolados.
4. Integrar ao hook local.
5. Integrar ao GitHub Actions e configurar proteção da branch quando autorizada.
6. Validar falsos positivos e começar a redução gradual do débito.

Cada fase deverá ser autorizada separadamente. **Não criar hooks, workflows ou alterações na base de código a partir deste documento sem nova autorização.**

## 9. Fora do escopo desta proposta

- Alterar os algoritmos Degradê, Artístico e Suave.
- Refatorar imediatamente todos os arquivos acima do limite.
- Alterar as venvs, imagens, manifestações de processamento ou resultados experimentais.
- Modificar `laboratorio_one/` ou o submódulo `mangago_downloader`.
- Fazer commit ou push.

---

**Status final:** documento de discussão para validação posterior. Nenhuma implementação autorizada ou executada.

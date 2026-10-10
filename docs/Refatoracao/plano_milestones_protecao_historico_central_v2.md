# Central V2 — Plano de correção: proteção entre fluxos e histórico do Auto-Cleaner Check

**Status:** planejamento técnico; nenhuma alteração aplicada.
**Referência:** branch `develop` do repositório `angeline1986/Fominha_de_Manga`, auditada em 09/10/2026.
**Escopo:** fluxo 04 — Auto-Cleaner Check; fluxo 05 — Auto-Cleaner: Transparência (Básica); contratos compartilhados necessários à segurança da pipeline.

## 1. Problemas que iremos atacar

### P1 — Balões estilizados são limpos pela Transparência Básica

- **Sintoma:** regiões classificadas manualmente como **Balão estilizado** no Auto-Cleaner Check foram limpas pela Transparência Básica, com perda da aparência desejada.
- **Causa confirmada no código:** `central_v2/backend/orchestration/textoff_merged/level2_manual_protection.py` define `PROTECTED_FROM_LEVEL2 = frozenset({"residuo_degrade", "residuo_gradiente"})`. O tipo `balao_estilizado` é ignorado na leitura das ocorrências e na construção da máscara protetora.
- **Evidência:** o Check persistiu ocorrências com `tipo = "balao_estilizado"`; o relatório da Transparência registrou `protected_occurrences = 0`, `protected_pixels = 0`, `protected_types = []`. Na página `page-082-086.png`, houve `171298` pixels alterados — número da página inteira, **não** contagem comprovada de alterações dentro do balão específico.
- **Impacto:** classificação manual registrada sem autoridade efetiva sobre o tratamento posterior.

### P2 — Retornar ao Check mostra imagem alterada por etapa posterior

- **Sintoma:** ao voltar ao Auto-Cleaner Check depois da Transparência Básica, a visualização passou a mostrar o balão já limpo.
- **Causa confirmada no código:** `central_v2/backend/orchestration/textoff_merged/comparison.py`, em `comparison_pairs(..., check=True)`, define `after = consolidated_image(manga, chapter, name)`. A função em `consolidated_artifacts.py` seleciona a imagem vigente do consolidado (Nível I ou II), não um resultado histórico imutável do Check.
- **Teste que formaliza o comportamento atual:** `dev/tests/test_auto_cleaner_check_consolidated_image.py` espera que o Check acompanhe a seleção atual do Consolidado.
- **Impacto:** impossível revisar com confiança o estado da página no momento em que a classificação foi feita.

### P3 — Política de proteção dispersa/incompleta

- **Sintoma:** os tipos de ocorrência estão registrados, mas nem todos possuem contratos explícitos de tratamento e bloqueio entre fluxos.
- **Evidência:** `residue_model.js` define sete tipos; `level2_manual_protection.py` protege somente dois deles.
- **Risco:** novas etapas podem ignorar classificações já aprovadas.
- **Decisão de projeto:** IDs textuais dos tipos continuam estáveis; a política por fluxo deve ser declarada centralmente e reutilizada. **Não** proteger indiscriminadamente todos os tipos.

## 2. Contratos desejados

1. **Proteção efetiva:** `balao_estilizado` é protegido na Transparência Básica; `residuo_degrade` e `residuo_gradiente` mantêm a proteção existente. Os demais tipos passam por decisão explícita de produto/engenharia.
2. **Autoridade do Check:** ocorrência aprovada e válida é aplicada à etapa posterior, identificada por página e coordenadas; o número visual `numero` não serve como ID global do balão.
3. **Segurança por padrão:** se o manifesto obrigatório estiver ilegível, incompatível, ausente em situação que exija proteção ou desatualizado, a etapa não deve promover resultado potencialmente destrutivo.
4. **Preservação verificável:** após a composição final, `changed_inside_protection = 0` para todos os pixels protegidos; não basta subtrair pixels da máscara antes do inpainting.
5. **Histórico de leitura:** reabrir o Check mostra exatamente a versão da imagem referenciada quando aquela revisão foi concluída, mesmo após executar o Nível II.
6. **Atualização explícita:** se for necessário rever decisões sobre uma nova imagem, isso deve ocorrer por ação identificável, não por substituição silenciosa da imagem histórica.

## 3. Plano em milestones

### M0 — Baseline e caracterização do defeito

**Objetivo:** documentar o comportamento atual antes de modificar a implementação.

**Entregas:**
- Localizar os consumidores de `load_level1_protection`, `protect_level2_masks`, `comparison_pairs(check=True)` e `consolidated_image`.
- Criar testes mínimos que reproduzam: (a) `balao_estilizado` ignorado; (b) Check exibindo Nível II após atualização do Consolidado.
- Delimitar qual artefato representa a imagem *no momento do Check* e se essa referência é estável hoje.

**Aceite:** testes de regressão reproduzem os dois defeitos no estado inicial e documentam os caminhos de execução. Nenhuma mutação de dados de produção.

### M1 — Registro central de tipos e políticas de proteção

**Objetivo:** eliminar divergência entre classificação da UI e autorização do backend.

**Entregas:**
- Formalizar os sete IDs atuais: `residuo_transparencia`, `residuo_degrade`, `residuo_gradiente`, `balao_estilizado`, `fragmento_balao`, `texto_residual`, `outro`.
- Criar uma definição de política backend por fluxo/tratamento, com validação e testes de contrato em relação à lista do frontend.
- Na **Transparência Básica**, proteger ao menos `balao_estilizado`, `residuo_degrade`, `residuo_gradiente`.
- Decidir explicitamente os comportamentos dos outros quatro tipos antes de estender a proteção.

**Aceite:** o Check persiste `balao_estilizado` e o backend o carrega como ocorrência protegida; testes demonstram mapeamento estável e nenhuma regressão para os dois tipos já protegidos.

### M2 — Máscaras seguras e garantia pós-composição

**Objetivo:** impedir alteração real das áreas protegidas, inclusive nas bordas.

**Entregas:**
- Validar associação de `page`, `box_normalized`, dimensões reais e máscara automática.
- Excluir regiões protegidas **após expansões/dilatações** da máscara.
- Garantir que a composição final reponha integralmente os pixels protegidos da imagem de entrada da etapa, independentemente do inpainting.
- Implementar falha segura para manifestos inválidos e métricas diferenciadas: `loaded_protected_occurrences`, `intersecting_occurrences`, `protected_pixels`, `changed_inside_protection`.
- Avaliar margem de segurança configurável para caixas de texto que não cobrem todo o balão; não expandir cegamente para regiões adjacentes.

**Aceite:** em testes sintéticos e em página real, nenhum pixel dentro da proteção é alterado; outras regiões autorizadas continuam sendo limpas. `changed_inside_protection == 0` em todos os casos de sucesso.

### M3 — Histórico imutável do Auto-Cleaner Check

**Objetivo:** desacoplar a visualização histórica do estado acumulado atual.

**Entregas:**
- Definir fonte de imagem do Check no instante da revisão: snapshot físico ou referência imutável verificável com SHA-256, sem cópias desnecessárias quando possível.
- Associar versão/snapshot às decisões aprovadas; explicitar quando uma revisão precisa ser refeita.
- Fazer `/api/textoff/comparison` em `comparisonMode=check` resolver esse estado histórico, e não a seleção mais recente do Consolidado.
- Atualizar `test_auto_cleaner_check_consolidated_image.py` e testes de navegação para validar a nova semântica.

**Aceite:** abrir Check → classificar balão → executar Transparência Básica → voltar ao Check mostra **os mesmos pixels** vistos na aprovação; visualização de estado atual permanece disponível apenas onde apropriado.

### M4 — Integração, testes e documentação

**Objetivo:** provar os dois contratos funcionando juntos.

**Entregas:**
- Reexecutar **somente o capítulo experimental**, seguindo Auto-Cleaner, Mapear, Sommelier, Check e Transparência Básica, quando necessários ao cenário.
- Cobrir pelo menos: balão estilizado protegido; degradê/gradiente protegidos; área comum não protegida limpa; marcações manuais múltiplas; navegação de ida e volta; reexecução da etapa posterior.
- Registrar no relatório de execução origem do manifesto, versão, tipos carregados e contagem de pixels efetivamente protegidos.
- Atualizar documentação de contratos e decisões arquiteturais.

**Aceite:** testes automatizados verdes, conferência visual do balão usado na investigação e `git diff` limitado aos arquivos planejados.

## 4. Ordem e governança

**Ordem obrigatória:** M0 → M1 → M2 → M3 → M4.
**Regra de execução:** um milestone por alteração/commit lógico; conferir `git diff` e testes antes de avançar.
**Fora do escopo:** modificar pesos/modelos, venvs, Cleaner/Patch Artístico validado, código/branch protegida da V1, reordenar os cinco fluxos, recuperar artefatos experimentais antigos ou redesenhar a UI.

## 5. Riscos e decisões pendentes

- **Caixa manual ≠ balão completo:** a região anotada geralmente cobre texto, não todo o balão. Definir proteção exata e margens conforme risco de dano visual.
- **Fonte histórica:** decidir entre snapshot próprio do Check e referência imutável a artefato existente; validar no código o momento exato em que a revisão fica persistida.
- **Ausência de manifesto:** distinguir capítulo sem revisão registrada de erro no carregamento de revisão existente; bloquear somente situações inseguras, sem impedir execução legítima.
- **Impacto em reprocessamento:** garantir que reexecuções não sobrescrevam snapshots históricos ligados a decisões aprovadas.
- **Semântica das categorias:** confirmar a política de `fragmento_balao`, `texto_residual`, `residuo_transparencia` e `outro` antes de utilizá-las para bloquear limpezas.

## 6. Estado do plano

- **Diagnóstico P1:** confirmado por inspeção de código e manifestos.
- **Diagnóstico P2:** confirmado por inspeção de código e teste existente.
- **Implementação:** não iniciada.
- **Próxima ação exata:** começar M0, caracterizando os defeitos com testes e mapeando os consumidores das máscaras e das imagens do Check, **sem corrigir o código nessa etapa**.

---

## Encerramento da validação integrada — M4

**Status:** APROVADO

**Cenário:** comix / Gazing at you_centrav2 / capítulo 1.

### Resultados

- M1: registro centralizado das políticas de proteção.
- M2: seis ocorrências protegidas (quatro balões estilizados e dois resíduos de degradê).
- M2: 215.853 pixels excluídos da máscara automática.
- M2: zero pixels modificados dentro das seis regiões protegidas.
- M2: 199.747 pixels modificados fora das regiões protegidas nas quatro páginas auditadas.
- M2: 438.910 pixels modificados no capítulo, conforme relatório.
- M2: integridade do processamento confirmada (`integrity_ok=true`).
- M3: 18 de 18 snapshots históricos íntegros após execução do Nível II.
- M4: validação integrada aprovada para o cenário experimental.

### Commits de implementação

- `c1cbe970` — políticas centralizadas.
- `2e400613` — proteção de ocorrências especiais no Nível II.
- `ca9e0252` — snapshots históricos do Auto-Cleaner Check.

### Limites da validação

A aprovação corresponde ao capítulo experimental auditado.
Não representa validação de todas as obras ou categorias de ocorrência.

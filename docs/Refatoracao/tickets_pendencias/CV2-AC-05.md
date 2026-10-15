# CV2-AC-05 — Investigar falha inicial no carregamento de imagens do Auto-Cleaner Check

- **Prioridade:** P2
- **Status:** TODO
- **Categoria:** Bug · Frontend · Visualização de imagens
- **Escopo:** Central V2 — Auto-Cleaner Check
- **Responsável:** A definir

**Problema observado:** Ao abrir uma página para comparação no Auto-Cleaner Check, a interface pode mostrar “Não foi possível carregar as 2 imagens. Tente novamente.” As imagens aparecem depois de navegar para outra página e voltar. Exemplo relatado: capítulo 1, `page-009-013.png`.

**Objetivo:** Identificar a causa da falha na primeira abertura e garantir o carregamento correto das imagens ORIGINAL e PROCESSADA sem exigir navegação adicional ou recarregamento manual.

**Diretrizes para investigação:**
- Inspecionar a inicialização do visualizador e o carregamento assíncrono das imagens.
- Comparar seleção da página, resolução das URLs, requisições HTTP e disponibilidade dos artefatos na primeira abertura e no retorno à página.
- Verificar `AbortController`, estados de carregamento, invalidação de requisições, cache, pré-carregamento e reutilização de imagens.
- Tratar condição de corrida como hipótese, não como causa confirmada.

**Critérios de Aceite:**
- [ ] Identificar e registrar a causa reproduzível da falha inicial antes de propor implementação.
- [ ] Confirmar que ORIGINAL e PROCESSADA carregam na primeira tentativa.
- [ ] Preservar a navegação entre páginas e capítulos sem requisições duplicadas desnecessárias.
- [ ] Não apresentar erro definitivo enquanto requisições válidas ainda estiverem em andamento.
- [ ] Verificar Antes & Depois e outros visualizadores que compartilhem o mecanismo, quando aplicável.
- [ ] Preservar imagens, manifestos e algoritmos de processamento.

**Restrições:** Não assumir condição de corrida sem evidência. Não alterar imagens, manifestos ou algoritmos de processamento durante a investigação.

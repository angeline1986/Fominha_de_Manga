# CV2-LAB-02 — Mostrar no Laboratório as páginas “Outro” do Check

- **Prioridade:** P2
- **Status:** DONE
- **Área:** Limpeza de Balões · Laboratório
- **Relação:** [BL-15](BL-15.md), origem Glass padrão no Laboratório

## Objetivo

Ao selecionar um capítulo no Laboratório, permitir encontrar diretamente as páginas que têm pelo menos uma ocorrência salva como **“Outro / não identificado”** no Auto-Cleaner Check.

## Fonte dos dados

Usar somente as decisões persistidas no manifesto oficial do Check para a obra e o capítulo selecionados. A classificação corresponde a `tipo: outro`. Essas decisões referenciam páginas MERGE. A saída persistida do Glass Básica usa o mesmo nome com sufixo `_clean.png`; essa é a correspondência usada para a origem padrão. A origem CHECK usa a imagem de revisão salva pelo Check, com verificação de integridade do snapshot.

## Critérios de aceite

- [x] Ao escolher um capítulo na origem Glass, mostrar somente imagens Glass das páginas com ao menos uma ocorrência `outro` salva no Check, cada página uma única vez.
- [x] Exibir estado vazio claro quando o capítulo não tiver ocorrências `outro` salvas; não apresentar sugestões ainda não aprovadas como marcações do Check.
- [x] Ao trocar de obra, capítulo ou origem, atualizar a lista sem reaproveitar classificações do contexto anterior.
- [x] Selecionar uma página da lista carrega a imagem Glass correspondente e conserva os controles do Laboratório.
- [x] Abrir o Laboratório na origem Glass; manter a troca manual para IMG, MERGE e o explorador de arquivos.
- [x] Apresentar as origens na ordem IMG, MERGE, GLASS, CHECK, ocupando o cabeçalho sem título adicional.
- [x] Na origem CHECK, listar uma vez cada página com pelo menos uma ocorrência `outro` aprovada e carregar a imagem revisada salva pelo Check.

## Limites

Consulta somente leitura. Não alterar ocorrências do Check, imagens, tratamentos, artefatos ou resultados do Laboratório.

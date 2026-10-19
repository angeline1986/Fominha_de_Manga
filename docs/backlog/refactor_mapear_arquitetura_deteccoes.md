# Backlog técnico: refatoração da arquitetura de detecções do Mapear

**Tipo:** dívida técnica / refatoração arquitetural
**Prioridade sugerida:** média
**Status:** backlog; implementação não autorizada
**Escopo:** Central V2; proposta futura para integração de detecções

## Objetivo

Registrar uma proposta de refatoração do Auto-Cleaner Mapear para tornar seus resultados e os de outros detectores reutilizáveis por consumidores autorizados, por meio de contratos explícitos e versionados. A refatoração deve reduzir processamento redundante, divergências de classificação, duplicidade de ocorrências e perda de proveniência, preservando os algoritmos e o comportamento validado dos fluxos existentes.

O reconhecimento imediato de balões transparentes é uma iniciativa independente. Seu desenvolvimento não deve aguardar nem depender desta proposta.

## Contexto e motivação

O Nível I identifica balões e classifica transparência; o Mapear identifica candidatos estilizados e características de balões sobre imagens consolidadas; o Bubble Sommelier realiza análise própria; o Auto-Cleaner Check recebe sugestões de fontes selecionadas; e o Combo Turbo precisa consumir decisões aprovadas pelo Check. Hoje, os resultados do Mapear não constituem um contrato geral de classificação para outras etapas. A ausência de um contrato comum também pode manter detecção, sugestão e execução excessivamente acopladas.

Um modelo compartilhado poderia permitir reaproveitamento rastreável e integração mais uniforme. Adaptadores leves podem oferecer esses benefícios com menos risco do que migrar todos os fluxos; essa opção deve ser avaliada antes de qualquer extração ampla.

## Evidências e questões a investigar

### Modelo e inferências

Nível I e Mapear usam o mesmo modelo YOLO, `huyvux3005/manga109-segmentation-bubble`, arquivo `best.pt`, revisão `f9a4108c4955136a810e5e92207972f3fb3a65fd`, com parâmetros distintos:

| Fluxo | Confiança | IoU |
|---|---:|---:|
| Nível I | 0.25 | 0.45 |
| Mapear | 0.15 | 0.45 |

As detecções não são, portanto, automaticamente equivalentes. O Nível I segmenta para classificação e novamente para produzir ou validar máscaras de transparência; o Mapear executa segmentação própria. Investigar reutilização somente quando imagem, parâmetros, finalidade, geometria e integridade forem compatíveis.

### Resultados do Mapear

O Mapear já produz `balloon_analysis` e `styled_balloon_candidates`. Investigar como disponibilizá-los em formato reutilizável sem alterar suas classificações ou algoritmos.

### Proveniência

O Mapear recebe imagens do consolidado, mas o relatório do worker declara `input_stage = "MERGE"`, enquanto o manifesto operacional registra origem consolidada. Investigar a correção e a compatibilidade com leitores e manifests existentes; não reescrever históricos sem estratégia explícita.

### Consumidores e geometria

O Check consome atualmente `mapear`, `sommelier` e `residue_occurrences`; a classificação automática de transparência do Nível I não integra diretamente essa lista. Avaliar um modelo padronizado de publicação de detecções para o Check e outros consumidores.

Análises podem usar imagens MERGE ou consolidadas e parâmetros diferentes. Não há equivalência garantida entre identificadores, caixas, polígonos ou máscaras de processos distintos. Qualquer correspondência precisa validar página, dimensões, referencial geométrico, origem e hashes.

## Arquitetura conceitual

```text
Fontes de imagens
        ↓
Camada de análise → detectores e classificadores existentes
        ↓
Contrato versionado de detecções
        ↓
Mapear / Check / outros consumidores autorizados
        ↓
Decisões aprovadas pelo Check
        ↓
Processamentos
```

Este desenho é uma possibilidade a avaliar, não uma ordem de migração. Estudar se adaptadores compatíveis aos formatos atuais atendem aos mesmos casos com menor risco de regressão.

## Diretrizes e contrato a estudar

Separar obtenção e validação de imagens, segmentação, classificação, normalização de geometria, consolidação, persistência de relatórios, publicação de sugestões, progresso e orquestração. Priorizar responsabilidades coesas e contratos explícitos.

O formato versionado deve avaliar campos para obra, capítulo e página; identificador estável; classe e classificação de origem; caixa e/ou máscara; sistema de coordenadas; modelo, revisão e parâmetros; identidade e hashes da imagem; métricas e justificativas; e referências aos artefatos originais.

O contrato deve distinguir claramente:

- detecção automática;
- sugestão para revisão;
- decisão humana persistida;
- autorização para processamento.

Novas sugestões não podem se tornar autorizações automaticamente. Ao integrar fontes ao Check, preservar aprovações, descartes, identidades de ocorrências, histórico de fontes e políticas de proteção existentes.

Padronizar a proveniência de MERGE, NÍVEL I, NÍVEL II e CONSOLIDADO sem invalidar manifests históricos. Registrar em experimentos controlados duração por etapa, quantidade de inferências, carregamento dos modelos, pico de memória, volume de imagens, artefatos reutilizados e falhas com seus motivos. Manter logs operacionais objetivos e detalhes por página em DEBUG quando adequado.

## Riscos e restrições

- Resultados divergentes caso parâmetros, imagem ou referencial geométrico sejam tratados como equivalentes sem comprovação.
- Regressões nos algoritmos ou resultados atuais do Mapear, Nível I ou Glass.
- Duplicidade de ocorrências, perda de rastreabilidade ou migração incorreta de aprovações e descartes no Check.
- Proveniência contraditória entre relatórios, manifests e artefatos.
- Aumento de acoplamento ou dependência circular entre detectores, consumidores e orquestração.
- Reuso indevido de inferência quando imagem, parâmetros, geometria ou integridade não forem equivalentes.

Restrições obrigatórias para eventual implementação:

- Não alterar algoritmos ou thresholds aprovados sem evidência experimental e aprovação específica.
- Não comprometer resultados validados do Mapear, nem modificar o comportamento do Nível I, Glass ou Central V1.
- Não invalidar manifests históricos, remover mecanismos de proteção ou fazer migração destrutiva de artefatos.
- Não misturar detecção com autorização de limpeza nem introduzir dependência circular.
- Não criar telas ou popups sem aprovação.
- Respeitar o limite de 200 linhas por arquivo de código e implementar incrementalmente, com regressão e rollback por etapa.

## Fases futuras sugeridas

1. **Baseline:** mapear contratos, dependências, artefatos e testes atuais; fixar resultados de referência por capítulo e página.
2. **Contratos:** definir formatos versionados reutilizáveis e adaptadores compatíveis com os formatos existentes.
3. **Extração gradual:** isolar responsabilidades em incrementos, evitando reescrever a esteira.
4. **Integração:** conectar consumidores ao contrato sem exigir migração simultânea dos fluxos.
5. **Validação:** comparar detecções, classificações, geometrias, proveniência, tempo e memória; preservar rollback por etapa.

## Dependências e pendências

- Inventariar contratos e leitores atuais de relatórios e manifests do Mapear, Nível I, Sommelier e Check.
- Identificar a origem efetiva das imagens em cada fluxo e definir compatibilidade de hashes, dimensões e coordenadas.
- Confirmar estabilidade e ciclo de vida dos identificadores de ocorrências e das decisões do Check.
- Definir casos de referência por obra, capítulo e página e obter baseline reproduzível.
- Determinar como corrigir a divergência `MERGE`/consolidado sem quebrar leitores históricos.
- Medir se há inferências reutilizáveis com imagem e parâmetros compatíveis; não presumir ganho.
- Avaliar adaptadores leves antes de definir extrações ou migração ampla.
- Priorizar e autorizar a implementação em item próprio antes de iniciar mudanças.

## Critérios de aceite futuros

- [ ] Comportamento funcional existente preservado.
- [ ] Nenhum algoritmo ou threshold alterado sem aprovação e evidência.
- [ ] Classificações reproduzíveis nos casos de referência.
- [ ] Proveniência consistente e compatível com manifests históricos.
- [ ] Contratos versionados e documentados.
- [ ] Resultados reutilizáveis por consumidores autorizados.
- [ ] Nenhuma dependência circular.
- [ ] Inferências comprovadamente compatíveis reutilizadas sem duplicação desnecessária.
- [ ] Aprovações, descartes, identidades e proteções do Check preservados; sugestões não autorizam processamento.
- [ ] Testes de regressão aprovados e rollback documentado.
- [ ] Performance medida antes e depois.

## Decisão registrada

Manter esta refatoração como dívida técnica para priorização futura. Não executar a refatoração, alterar arquivos operacionais ou realizar tratamentos como parte do registro. A iniciativa imediata de reconhecimento de balões transparentes permanece independente.

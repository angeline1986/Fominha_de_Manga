# Arquitetura de Interface --- Refactor V4

## Diretrizes

-   `interface_web/` será organizado por item de menu e, abaixo dele,
    por grupo/página.
-   O alvo é manter a maioria dos arquivos em aproximadamente 200 linhas
    ou menos.
-   Ao ultrapassar \~200 linhas, a unidade entra obrigatoriamente em
    revisão arquitetural; havendo mais de uma responsabilidade, deve ser
    decomposta.
-   O limite não autoriza divisão arbitrária: SRP, coesão e contratos
    prevalecem.
-   Evitar nomes redundantes com o contexto da pasta; usar nomes
    compostos e abreviações claras.
-   Componentes recorrentes (`table`, `zoom`, `viewer`, `pager`,
    `toolbar`, `filter`, `focus`, `modal`, `feedback`) ficam em
    `_shared/`.
-   `_shared/` também deve permanecer modular; não criar um novo arquivo
    central monolítico.
-   Páginas compõem/configuram componentes compartilhados e mantêm
    localmente apenas comportamento específico.
-   A mesma regra vale para CSS: tokens/layout/componentes
    compartilhados + CSS específico mínimo.
-   `orquestracao/` coordena; `processamento/` mantém os domínios de
    execução. Evitar `orquestracao/processamento/` para não repetir
    nomes e responsabilidades.

## Navegação-alvo

### Visão Geral

-   Resumo
-   Validar imagens

### Processamento

-   Auto Merge
    -   Nível I
    -   Nível II
    -   Nível III
    -   Nível IV
    -   Nível V
-   Revisão
    -   Revisão Merge
    -   Revisão Merge V2
-   Merge Manual
    -   Validar
    -   Novos Merges

### Balanceamento

-   Validar
-   Novos Cortes

### Gerar PDF

-   Original
-   Merge

### Texto Off

-   Original
-   Merged
-   Comparar resultados
-   Correção assistida
-   Especiais

### Exportar arquivos

-   Exportar

## Convenção de nomes

Exemplos: - `am3_page.js`: Auto-Merge Nível III. - `rvw_page.js`:
Review. - `mm_val_page.js`: Merge Manual / Validar. -
`bal_cut_editor.js`: Balanceamento / Novos Cortes / editor. -
`to_cmp_view.js`: Texto Off / Comparar / visualização. -
`pdf_mrg_page.js`: PDF / Merge. - `exp_preview.js`: Exportação / prévia.

A abreviação deve continuar reconhecível dentro do contexto da pasta e
não repetir desnecessariamente todo o caminho.

## Princípio de evolução

Não mover tudo de uma vez. Caracterizar → mapear → proteger → extrair
uma responsabilidade → delegar → validar → só então avançar.

# M1 — Matriz de diretórios e caminhos

## Caminhos operacionais

Os caminhos de estágio abaixo são relativos a `output/<provider>/<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/`. Inputs MERGE residem em `FLUXO_SECUNDARIO/02_MERGE/`; originais em `output/<provider>/<obra>/IMG/`. Previews experimentais ficam no repositório ignorado em `reports/experimentos/textoff_especiais_v2/`.

| Contrato/caminho | Presença observada | Papel e observação | Classificação inicial |
|---|---:|---|---|
| `TO_MERGED_NIVEL_I/<cap>/` | 4 obras | Saída legada Nível I; `clean/`, `mask/`, `json/` | migrar estado/referências; preservar binários referenciados |
| `01_AUTO_CLEANER/<cap>/` | 4 obras | Destino paralelo do registry | shadow; não equivalência aprovada |
| `TO_MERGED_NIVEL_III/<cap>/` | 4 obras | Mapear legado, relatórios/análise | migrar referências/relatórios conforme consumidores |
| `02_MAPEAR/<cap>/` | 4 obras | Destino paralelo do Mapear | shadow |
| `TO_MERGED_CONSOLIDADO/<cap>/` | 4 obras | Consolidação lógica; pode conter imagens e máscaras selecionadas | migrar seleção e referências; preservar compatibilidade |
| `02_MAPEAR/INPUT_CONSOLIDADO/<cap>/` | 4 obras | Destino paralelo do input intermediário do Mapear | shadow; não confundir com final |
| `TO_MERGED_NIVEL_II/<cap>/` | 4 obras | Glass/Nível II legado | migrar estado/referências e auxiliares necessários |
| `05_AUTO_CLEANER_TRANSPARENCIA/BASICA/<cap>/` | 4 obras | Destino paralelo do Glass | shadow |
| `BUBBLE_SOMMELIER/<cap>/` | 4 obras | Nome legado/caminho de compatibilidade | compatibilidade |
| `03_BUBBLE_SOMMELIER/<cap>/` | 4 obras | Destino paralelo reportado no registry | shadow |
| `04_AUTO_CLEANER_CHECK/<cap>/` | 4 obras | Check, imagens congeladas, manifest de decisões | estado operacional |
| `RESIDUE_OCCURRENCES/<cap>/` | 2 obras | Manifestos de ocorrências residuais | estado/decisões auxiliares |
| `05_AUTO_CLEANER_SOLIDOS/<cap>/` | 2 obras | Sólidos e manifest de saída | preview/execução; validar continuidade com Glass |
| `06_PINCEL/{DEGRADE,ARTISTICO,SUAVE}/<cap>/` | 3 obras | Artefatos dos tratamentos especiais | resultado/revisão; caminho tem migração legada adicional |
| `SPECIAL_TREATMENTS/<cap>/` | 4 obras | Manifesto agregador de tratamentos, snapshots/histórico | estado/auditoria |
| `07_CONSOLIDADO_FINAL/<cap>/` | 4 obras | Imagens físicas finais mais `final-manifest.json` | preservar até migração dos leitores |
| `COMBO_TURBO/` e `runs/` | caminhos existentes em código | Execuções, publicação e área/workspace de combo | Combo está no escopo da Onda 1; destino do estado transitório precisa decisão |
| `ORIGINAL/`, `MERGED/`, `NIVEL3/` | presentes em parte do acervo | 24 JSONs em ORIGINAL sem leitor confirmado; 8 manifests MERGED e 7 JSONs de fluxo NIVEL3 legado | preservar e rastrear readers/writers; NIVEL3 legado não equivale a Mapear V2 |
| `02_RECONHECER_TRANSPARENTES/`, `BACKUP_PREVIAS_SOLIDOS/`, `Patch degrade/` | presentes em parte do acervo | reconhecimento consumido por Check; 2 backups de Sólidos e 1 manifest de teste | preservar; definir autoridade e retenção por papel |
| `FLUXO_SECUNDARIO/02_MERGE/` | cinco obras | 147 manifests `merge-manifest.json` catalogados como inputs imediatos | manter vínculo e proveniência; não migrar como autoridade TextOff sem validação |
| `IMG/` | cinco obras | fontes originais incluídas na varredura de SHA-256 | preservar referências de origem/página/revisão |
| `reports/experimentos/textoff_especiais_v2/` | 11 runs no staging ignorado | 70 JSONs e 74 PNGs; payload, resultado e progresso de workers | decidir quais dados são transitórios, evidência e retenção |

Os quatro nomes `TO_MERGED_*` aparecem em quatro árvores, total 16 diretórios. O quinto diretório TextOff, `mangago/Teste Candy YumYum`, contém poucos artefatos de experimento e nenhum `TO_*` encontrado. A presença/pasta não prova que cada página tenha saída válida.

As quatro obras com as 16 pastas são `mangago/Candy YumYum (Yaoi)`, `mangago/Benevolent Violence (Yaoi)`, `comix/Gazing at you` e `comix/Gazing at you_v2`; em cada uma há exatamente um diretório de cada nome `TO_MERGED_NIVEL_I`, `TO_MERGED_NIVEL_II`, `TO_MERGED_NIVEL_III` e `TO_MERGED_CONSOLIDADO` sob `FLUXO_SECUNDARIO/04_TEXTO_OFF/`.

## Caminhos paralelos do registry

| `stage_id` | Legado | Destino | Authority atual | Dual write | Validação |
|---|---|---|---|---|---|
| `auto_cleaner` | `TO_MERGED_NIVEL_I` | `01_AUTO_CLEANER` | `legacy` | sim | não validado |
| `mapear` | `TO_MERGED_NIVEL_III` | `02_MAPEAR` | `legacy` | sim | não validado |
| `mapear_input_consolidado` | `TO_MERGED_CONSOLIDADO` | `02_MAPEAR/INPUT_CONSOLIDADO` | `legacy` | sim | não validado |
| `bubble_sommelier` | `BUBBLE_SOMMELIER` | `03_BUBBLE_SOMMELIER` | `legacy` | sim | não validado |
| `auto_cleaner_transparencia_basica` | `TO_MERGED_NIVEL_II` | `05_AUTO_CLEANER_TRANSPARENCIA/BASICA` | `legacy` | sim | não validado |

## Pastas candidatas a mudança futura

“Candidata” significa apenas que seu contrato pode ser substituído depois de rastrear leitores, hashes, proveniência e restauração. Não há candidatos autorizados para exclusão nesta fase:

- Pastas shadow paralelas criadas por `dual_write`, quando o contrato migrado tiver leitor e escritor no banco/Artifact Store.
- Aliases `MERGED_NIVEL_*` e caminhos `TO_*`, depois de desativar todos os leitores legados e completar período de observação.
- Diretórios gerados intermediários duplicados, somente quando comprovados como redundantes para o mesmo papel, revisão e consumidores.

`TO_MERGED_CONSOLIDADO` não pode ser tratado como cópia dispensável do `07_CONSOLIDADO_FINAL`: o primeiro seleciona logicamente fontes; o segundo fornece arquivos físicos a consumidores de tratamentos e exportação.

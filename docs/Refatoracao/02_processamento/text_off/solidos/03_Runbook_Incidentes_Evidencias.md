# Central V2 — Runbook de recuperação, diagnóstico e rastreabilidade

**Referência de código:** `develop@1af79b5c` (2026-10-15). **Escopo:** Auto-Cleaner Check, Laboratório Sólidos, etapa 05, visualização e Curadoria. Instruções conservadoras: não apagar, sobrescrever ou promover arquivos para “resolver” um incidente sem capturar evidências.

## 1. Matriz de versões

| Commit | Conteúdo | Comprovação disponível |
|---|---|---|
| `a0749ef7` | Novo tipo de ocorrência sólida branca, filtro Sólidos no Lab, etapa 05 inicial, navegação e docs de pendências | Commit/push registrado; Laboratório aprovado visualmente anteriormente |
| `934a3f4e` | Viewer compartilhado para Sólidos, backend comparação, UI de filtros e tabela | Commit/push registrado; viewer visto em integração mas homologação integral não demonstrada |
| `1af79b5c` | Marcar todos na Curadoria | Commit/push registrado; sem teste de regressão sistemático informado |

**Observação:** backups `.lab_solidos_backup/`, `.solid_stage_backup/`, `.solid_ui_backup/`, `.solid_eye_backup/`, `.solid_compare_backup/`, `.sommelier_selection_backup/` são diretórios locais de instaladores, não parte do Git. **Não depender deles como única fonte de recuperação**; o código consolidado está versionado no commit indicado.

## 2. Locais de saída

Substituir `<OUTPUT_ROOT>/<provider>/<obra>` pela base da instalação. Não inventar o caminho real sem verificar configuração `config/data_paths.py`.

```text
<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/
├── 01_AUTO_CLEANER/<capítulo>/clean/<stem>_clean.png
├── 04_AUTO_CLEANER_CHECK/<capítulo>/auto-cleaner-check-manifest.json
└── 05_AUTO_CLEANER_SOLIDOS/<capítulo>/
    ├── clean/<stem>_clean.png
    ├── mask/<stem>_mask.png
    └── solid-white-manifest.json

<OUTPUT_ROOT>/_laboratorio_solidos_previews/<run_id>/
├── preview.png
├── mask.png
└── manifest.json
```

`01_AUTO_CLEANER` pode ter alias de etapa dependente da configuração de saída; resolver via `stage_chapter(..., LEVEL1, ...)`, não forçar string em scripts de recuperação.

## 3. Diagnóstico por sintoma

| Sintoma | Causa a investigar | Verificação não destrutiva |
|---|---|---|
| Capítulo não aparece na etapa 05 | Check sem `approved_occurrences` do tipo Sólidos, tipo divergente ou manifesto ausente/incompatível | Ler Check e contar tipos, validar documento e IDs |
| Capítulo aparece pendente após tentativa | Falha de job, destino não publicado ou frontend usando outra obra/contexto | Consultar job/status, existência de pasta `05...`, logs do servidor |
| “Prévia já existente” ao executar | Pasta destino já existe; política intencional de não sobrescrever | Inspecionar diretório e manifest; **não remover** |
| Botão olho desabilitado | `processed=false` no GET overview | Verificar existência do `solid-white-manifest.json` |
| Botão olho habilitado mas imagem falha | Manifest existe mas hash/arquivo mudou, versão do viewer obsoleta ou origem AC1 divergiu | Comparar SHA-256 manifesto e arquivos; endpoint `/api/textoff/comparison` e imagem |
| Comparação não abre | Trio `step/scope/comparisonMode` ou chamada do viewer incorreta | Inspecionar network: todos iguais a `solid` |
| Imagens desalinhadas | Dimensões naturais diferentes | Checar PNG before/after; slider intencionalmente bloqueia |
| Região preservada sem limpar | `white_fraction < .70`, máscara insegura, componentes rejeitados ou nenhum pixel elegível | Ver `regions[].status/reason/white_fraction/components/changed_pixels` |
| Filtro “Concluídos” não representa aprovação | `processed` é arquivo de prévia existente | Não usar `processed` como atestado de revisão visual |
| Seleção parcial Curadoria não aparece | Divergência da renderização do checkbox no `header()` ou estado de Set | Comparar `checked`/`indeterminate`, conferir `page.rows` |

## 4. Comandos de auditoria seguros no Mac

```bash
cd ~/Documents/TI/Projetos/Fominha_de_Manga || exit 1
git status --short --branch
git --no-pager log -3 --oneline
git submodule status
git diff --check

# Conferir thresholds atuais SEM alterá-los:
grep -nE '245|205|\\.70|\\.20|\\.80|\\.30|253|dilate|connectedComponents' \
  central_v2/backend/routes/laboratorio_solidos.py

# Ver todos os arquivos tocados pelos commits de referência:
git --no-pager show --stat --oneline a0749ef7
git --no-pager show --stat --oneline 934a3f4e
git --no-pager show --stat --oneline 1af79b5c
```

Para checar manifests, use script Python **somente de leitura** apontando explicitamente para o arquivo real, e não alterações diretas do JSON:

```bash
python3 - /caminho/real/05_AUTO_CLEANER_SOLIDOS/1/solid-white-manifest.json <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
raw=p.read_bytes()
m=json.loads(raw)
print('arquivo:',p)
print('sha256:',hashlib.sha256(raw).hexdigest())
print('schema:',m.get('schema'),'preview_only:',m.get('preview_only'))
print('provider:',m.get('provider'),'manga:',m.get('manga'),'chapter:',m.get('chapter'))
print('paginas:',len(m.get('pages',[])),'regioes:',len(m.get('regions',[])))
for r in m.get('regions',[]):
    print(r.get('id'),r.get('page'),r.get('status'),r.get('reason',''),
          'changed_pixels:',r.get('changed_pixels'))
PY
```

## 5. Evidência mínima antes de modificar o algoritmo

Reunir: hash commit, branch e status de trabalho; Python e pacotes (`cv2`, `numpy`, `Pillow`), sem reinstalar dependências; source/Check/manifest e respectivos hashes; IDs e `box_pixels` das ROIs aprovadas; `audit` por ROI (`status`, `reason`, `components`, `white_fraction`, `changed_pixels`); PNG before/after/mask sem regravar; logs de job e erros de rota; capturas do viewer com zoom e capítulo/página; tipo de alteração pretendida (motor, API, UI ou documentação). Guardar antes de propor threshold novo.

## 6. Procedimento de recuperação (não destrutivo)

1. Congelar código e dados: anotar commit atual, status Git, etapa, capítulo e provider. Não executar mais jobs.
2. Inspecionar Check, AC1, estágio 05, SHA-256 e retorno da API. Se o problema é UI, **não mexer no motor**.
3. Reproduzir em cópia isolada dos arquivos afetados, sem trocar origem AC1 por outro arquivo.
4. Comparar os parâmetros da seção técnica 01 **um a um**, procurando divergência real e não suposições.
5. Se um patch for indispensável, manter contrato `preview_only`, publicar em nova pasta/teste isolado com manifest/hash e backup; só depois propor fluxo de invalidação versionado.
6. Validar visualmente pelo viewer compartilhado, verificando se bordas e elementos não textuais foram preservados.
7. Rodar testes do módulo e de regressão UI/rotas; não declarar “testado” se não foi executado.
8. Registrar delta exato, commit, hashes antes/depois, outputs e responsável pela validação no diário de evidências.

## 7. Riscos e lacunas reais

- `white_fraction` não avalia reconhecimento semântico de “texto”. Falsos positivos/negativos possíveis, sobretudo ilustrações escuras dentro da ROI.
- `processed` no overview é **presença** de arquivo manifest, não validação completa de seus hashes. Validar pelo endpoint de imagem antes de aprovar.
- `candidates` retornado por `execute_chapter` soma pixels mudados, apesar do nome. Evitar usar como contagem de balões.
- `createSolidTable` não possui estado `indeterminate` explícito; diferente da Curadoria. Documentar/testar antes de unificar.
- A UI aceita seleção múltipla e o job é executado por capítulo; investigar falha intermediária e a semântica de retomada, sem assumir atomicidade do lote inteiro.
- Não existe procedimento validado no código consultado para reprocessar resultado da etapa 05 já publicado. Criar somente com contrato de rastreabilidade e aprovação explícita.
- Não há evidência nesta revisão de que o Glass consuma o resultado da etapa 05; **não escrever em documentação que existe promoção operacional**.
- Documentos existentes de Auto-Cleaner, Merge e Glass continuam fontes próprias: este pacote registra somente as implementações e integrações vistas nesta fase. Revisão profunda de parâmetros de todo o pipeline antigo requer levantamento adicional independente.

## 8. Checklist de aceite de uma manutenção futura

- [ ] Identificação do problema com arquivos, páginas e ROI
- [ ] Captura dos hashes antes de processar
- [ ] Comportamento e parâmetros atuais reproduzidos em cópia
- [ ] Uma única ação/hipótese por patch, sem alteração lateral
- [ ] Resultado visual avaliado na resolução integral
- [ ] Integridade de Check, AC1, máscaras e manifests conservada
- [ ] Prévia isolada, sem overwrite de outputs anteriores
- [ ] Registros de erro e regressão anexados
- [ ] Commit e versão das dependências documentados
- [ ] Status homologado/pending registrado com data e responsável

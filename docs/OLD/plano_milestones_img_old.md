# Continuidade — Fominha_de_Manga — IMG + `_old`

## Contexto do projeto

**Projeto:** `Fominha_de_Manga`  
**Diretório:** `/Users/alinesouza/Documents/TI/Projetos/Fominha_de_Manga`  
**Branch de desenvolvimento:** `recovery/merge-stable-baseline`  
**Último commit remoto antes desta implementação:** `cddc3ed — Add image validation workflow before merge`

O sistema processa capítulos de mangá/webtoon armazenados em imagens. Fluxo geral:

```text
Download
→ Validação de imagens
→ Auto-Merge
→ Tratamento de merges pendentes
→ PDF
→ Limpeza de balões / Texto Off
```

`IMG/<capítulo>/` deve ser a fonte oficial das imagens.

### Restrição crítica

Não alterar os algoritmos de:

```text
Auto-Merge Nível I
Auto-Merge Nível II
```

Eles estão estáveis. Esta implementação atua somente na correção física das imagens e na descoberta das imagens ativas.

---

# Arquitetura definida

Problema real: algumas imagens isoladas possuem largura diferente da dominante do capítulo.

Exemplo:

```text
Cap. 63
page-115.png  940x490
page-116.png  940x277

Largura dominante: 760px
```

Resultado esperado:

```text
page-115_old.png  940x490
page-115.png      760x396

page-116_old.png  940x277
page-116.png      760x224
```

Regra global:

```text
IMG = fonte única
*_old.* = backup físico ignorado pelo processamento
arquivo sem _old = imagem ativa
```

A arquitetura substitui o modelo baseado em:

```text
CORRIGIDAS/
COMPOSICAO_FINAL/
```

## Regras obrigatórias

- preservar sempre o original como `<nome>_old.<ext>`;
- nunca sobrescrever `_old`;
- nunca criar `_old_old`;
- preservar proporção;
- `_old` deve ser invisível aos processamentos;
- execução repetida deve ser segura;
- após correção, reanalisar `IMG`;
- estado deve refletir o conteúdo real de `IMG`;
- não apagar automaticamente estruturas antigas;
- validar antes de commit;
- nunca usar `git add .`.

---

# Milestone 1 — Ignorar backups `_old`

**STATUS: CONCLUÍDO LOCALMENTE — ainda não commitado.**

## Alterações realizadas

### `processamento/validacao_imagens/analisador_dimensoes.py`

`iter_images()` agora contém:

```python
and not p.stem.lower().endswith("_old")
```

### `interface_web/processing_web.py`

Criada:

```python
def is_active_image(path):
    return (
        path.is_file()
        and path.suffix.lower() in IMAGE_EXTS
        and not path.stem.lower().endswith("_old")
    )
```

Aplicada em:

- descoberta de capítulos;
- enumeração da correção de dimensões;
- contagem de páginas;
- limpeza de balões executada pelo backend web.

### `processamento/pdf_original/pdf_batch_validation.py`

`list_supported_images()` agora ignora `_old`.

### `processamento/limpeza_baloes/bubble_cleaner_flow.py`

Ajustados:

- descoberta de capítulos;
- enumeração das imagens processadas.

Ambos ignoram `_old`.

## Auto-Merge auditado

`processamento/unificacao_imagens/image_stitcher.py` usa:

```python
PAGE_RE = re.compile(r"^page-(\d+)\.[^.]+$", re.IGNORECASE)
```

Logo `page-115_old.png` já é ignorado.

Os `glob("*.png")` auditados em diretórios de merge operam sobre artefatos gerados, não sobre imagens-fonte de `IMG`.

**Não alterar Auto-Merge.**

## Aceite

```text
_old não entra em análise
_old não entra em contagem
_old não entra em PDF Original
_old não entra na limpeza
_old não entra no Auto-Merge
```

---

# Milestone 2 — Corrigir diretamente em `IMG`

**STATUS: EM ANDAMENTO.**

## Auditoria já concluída

A implementação antiga de `do_dimension_correct()` fazia:

```text
IMG
→ CORRIGIDAS
→ COMPOSICAO_FINAL
→ dimension-correction-manifest.json
```

O frontend também foi auditado e ainda depende de:

```text
CORRIGIDO
correction_applied
corrected_count
COMPOSICAO_FINAL
```

`loadDimensionAnalysis()` apenas recarrega o estado do backend.

O job `dimension_correct` chama diretamente:

```python
do_dimension_correct(...)
```

## Alteração já aplicada localmente

`do_dimension_correct()` foi substituída por uma primeira implementação do modelo:

```text
imagem divergente ativa
→ verificar backup _old
→ gerar imagem corrigida temporária
→ original vira *_old
→ temporária assume nome original
→ reanalisar capítulo
```

A nova função:

- trabalha diretamente em `IMG`;
- usa somente imagens ativas;
- calcula altura proporcional à largura dominante;
- cria backup com:
  `source.with_name(f"{source.stem}_old{source.suffix}")`;
- bloqueia se `_old` já existir;
- nunca sobrescreve backup;
- usa arquivo temporário antes de renomear o original;
- tenta restaurar o original se a troca falhar;
- registra imagens `corrected` e `blocked`;
- chama `_dimension_payload(..., persist=True)` novamente após correção.

A aplicação retornou:

```text
OK: do_dimension_correct agora corrige diretamente em IMG com backup _old
```

### PONTO EXATO ONDE A SESSÃO PAROU

**O diff dessa nova função ainda NÃO foi revisado.**

Próximo comando obrigatório:

```bash
cd "/Users/alinesouza/Documents/TI/Projetos/Fominha_de_Manga" && git diff -- interface_web/processing_web.py
```

Não fazer outra alteração antes de revisar esse diff.

## Ainda falta no Milestone 2

- revisar o diff;
- validar sintaxe;
- validar segurança do temporário;
- validar comportamento quando `_old` já existe;
- somente depois testar em dados reais.

## Aceite

```text
page-115.png
↓
page-115_old.png
page-115.png corrigida
```

Sem sobrescrever backup, sem `_old_old` e com proporção preservada.

---

# Milestone 3 — Remover arquitetura antiga

**STATUS: NÃO INICIADO.**

Eliminar dependência operacional de:

```text
CORRIGIDAS/
COMPOSICAO_FINAL/
dimension-correction-manifest.json
```

## Backend já identificado

`_dimension_correction_state()` procura manifesto em `COMPOSICAO_FINAL`.

`dimension_state()` usa esse manifesto para sintetizar:

```text
CORRIGIDO
correction_applied
corrected_count
```

Essa lógica deverá ser removida/substituída.

## Frontend já identificado

`interface_web/app.js` possui referências a:

```text
CORRIGIDO
correction_applied
corrected_count
COMPOSICAO_FINAL
```

A Etapa 2 ainda afirma que `IMG` permanecerá intacto. Isso deverá mudar para explicar:

```text
original → *_old
corrigida → nome original
```

A Etapa 3 ainda se chama `Composição final` e aponta para `COMPOSICAO_FINAL`; deverá ser readequada.

**Não apagar automaticamente pastas antigas existentes.**

## Aceite

Nenhum fluxo depende de `CORRIGIDAS`, `COMPOSICAO_FINAL` ou do manifesto de correção.

---

# Milestone 4 — Estado pós-correção

**STATUS: NÃO INICIADO.**

Fluxo desejado:

```text
REQUER_ANALISE
→ corrigir
→ reanalisar IMG
→ OK
```

Não sintetizar `CORRIGIDO` por manifesto.

A autoridade passa a ser:

```text
IMG + análise atual
```

## Aceite

Após correção, `_old` é ignorado e:

```text
status = OK
exceptions = 0
```

quando todas as imagens ativas estiverem dentro da tolerância.

---

# Milestone 5 — Validação integrada

**STATUS: NÃO INICIADO.**

Teste inicial controlado:

```text
Obra: Gazing at you
Capítulo: 63
```

Antes:

```text
page-115.png  940x490
page-116.png  940x277
```

Esperado:

```text
page-115_old.png  940x490
page-115.png      760x396

page-116_old.png  940x277
page-116.png      760x224
```

Validar:

- backups preservados;
- ativas corrigidas;
- análise = `OK`;
- `_old` não entra na contagem;
- Auto-Merge ignora `_old`;
- PDF Original ignora `_old`;
- limpeza ignora `_old`;
- nenhuma regressão em Auto-Merge I ou II.

Testar primeiro apenas um capítulo, não em lote.

---

# Milestone 6 — Fechamento

**STATUS: NÃO INICIADO.**

Fazer nova auditoria por leitores diretos de imagens.

Critério final:

```text
IMG = fonte única
*_old = backup invisível
arquivo sem _old = imagem ativa
```

Depois:

1. validar funcionalmente;
2. validar visualmente;
3. revisar `git diff`;
4. verificar `git status`;
5. stage somente dos arquivos intencionais;
6. commit;
7. push em `recovery/merge-stable-baseline`.

---

# Arquivos envolvidos

Já modificados/intencionais:

```text
processamento/validacao_imagens/analisador_dimensoes.py
interface_web/processing_web.py
processamento/pdf_original/pdf_batch_validation.py
processamento/limpeza_baloes/bubble_cleaner_flow.py
```

Provável alteração futura:

```text
interface_web/app.js
```

Não modificar `image_stitcher.py` nem algoritmos de Auto-Merge sem nova necessidade comprovada.

---

# Estado Git / artefatos locais

Antes das alterações, a branch estava sincronizada:

```text
recovery/merge-stable-baseline...origin/recovery/merge-stable-baseline
```

Artefatos locais conhecidos que não devem ser commitados:

```text
? download/mangago_downloader
?? gui_config.json
```

As alterações IMG + `_old` ainda não foram commitadas.

## Segurança Git

Nunca usar:

```text
git clean
git reset --hard
git add .
```

Não remover artefatos locais sem solicitação explícita.

---

# Forma de trabalho obrigatória

A implementação está sendo feita em passos pequenos:

```text
1 comando por vez
→ aguardar saída
→ analisar
→ fornecer próximo comando
```

Não enviar vários comandos independentes de uma vez.

Não avançar milestone sem validar o atual.

Não fazer refatorações paralelas.

---

# Próximo passo exato ao retomar

Não reiniciar o trabalho.

Milestone 1 está concluído. Milestone 2 já possui a nova `do_dimension_correct()` aplicada localmente.

Executar primeiro:

```bash
cd "/Users/alinesouza/Documents/TI/Projetos/Fominha_de_Manga" && git diff -- interface_web/processing_web.py
```

Objetivo:

```text
revisar a nova do_dimension_correct()
antes de qualquer nova alteração
```

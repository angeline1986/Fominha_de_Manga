# Fluxo Narrativo — Plano de Implementação

## Objetivo

Criar uma etapa editorial entre o `MERGE` consolidado e a geração do PDF para validar se o processamento preservou:

- continuidade visual;
- ordem de leitura;
- compreensão narrativa.

A página deve consumir apenas o resultado final de `MERGE/<cap>/`.

Não deve alterar Auto-Merge Nível I, II ou III.

---

## Princípios

- Começar simples: OpenCV + NumPy + frontend já existente.
- Não introduzir LayoutParser, NetworkX, Fabric.js ou Konva.js na V1.
- Não alterar pixels dos arquivos em `MERGE`.
- Persistir apenas dados de análise e decisões humanas.
- Revisar manualmente apenas casos ambíguos.
- Evitar lógica duplicada com os fluxos de merge.

---

# Milestone 1 — Contrato funcional

## Entrega

Definir o contrato mínimo da etapa.

### Entrada

```text
MERGE/<cap>/*.png
```

### Saída

```text
FLUXO_NARRATIVO/<cap>/analysis.json
```

### Estados

```text
seguro
revisar
aprovado
```

### Conteúdo mínimo do analysis.json

- capítulo;
- imagem;
- perfil de leitura;
- painéis detectados;
- ordem proposta;
- nível de confiança;
- motivo quando marcado para revisão;
- decisão humana, quando existir.

## Critério de conclusão

Contrato documentado e leitura dos arquivos de `MERGE` funcionando.

---

# Milestone 2 — Detecção simples de painéis

## Entrega

Criar um analisador isolado usando:

- OpenCV;
- NumPy.

Responsabilidades:

1. carregar uma imagem do `MERGE`;
2. detectar regiões candidatas a painéis;
3. gerar bounding boxes;
4. calcular centroides;
5. devolver JSON.

Não gerar nova imagem física com setas.

## Critério de conclusão

Para um pequeno conjunto real de imagens, o sistema retorna bounding boxes coerentes sem alterar o `MERGE`.

---

# Milestone 3 — Ordem de leitura

## Entrega

Criar perfis simples:

```text
WEBTOON_VERTICAL
MANGA_RTL
COMIC_LTR
```

A ordenação deve considerar:

- posição vertical;
- sobreposição entre painéis;
- alinhamento;
- posição horizontal;
- distância entre regiões.

Não usar somente `sorted(Y, X)` como regra definitiva.

## Critério de conclusão

A ordem proposta funciona corretamente nos layouts simples e identifica layouts ambíguos.

---

# Milestone 4 — Confiança e fila de revisão

## Entrega

Classificar cada análise em:

```text
SEGURO
PROVÁVEL
REVISAR
```

Somente itens `REVISAR` devem entrar na fila humana por padrão.

Motivos devem ser objetivos, por exemplo:

```text
painéis sobrepostos
ordem horizontal ambígua
layout irregular
baixa confiança
```

## Critério de conclusão

O sistema consegue separar casos evidentes dos casos que realmente precisam de inspeção.

---

# Milestone 5 — Página Fluxo Narrativo

## Entrega

Criar a nova página sem editor gráfico complexo.

Estrutura mínima:

```text
FLUXO NARRATIVO

[ Capítulos / fila ]

Imagem analisada
+ overlay dos bounding boxes
+ números da ordem
+ linhas/setas entre os painéis

Ordem proposta:
[ 1 ] [ 2 ] [ 3 ] [ 4 ]

[ Aprovar ] [ Corrigir ordem ]
```

A correção da ordem deve usar reordenação simples dos itens.

Não implementar desenho manual de setas na V1.

## Critério de conclusão

O usuário consegue visualizar, aprovar e corrigir a ordem proposta.

---

# Milestone 6 — Persistência da validação

## Entrega

Salvar a decisão humana no `analysis.json`.

Exemplo:

```json
{
  "status": "aprovado",
  "original_order": ["p1", "p2", "p3"],
  "approved_order": ["p1", "p3", "p2"],
  "reviewed": true
}
```

A página deve conseguir reabrir o capítulo preservando o estado anterior.

## Critério de conclusão

A aprovação ou correção sobrevive ao reinício da aplicação.

---

# Milestone 7 — Gate para PDF

## Entrega

Usar o Fluxo Narrativo como condição editorial antes do PDF.

Regra inicial:

```text
todos seguros/aprovados
        ↓
PDF liberado

existe item REVISAR
        ↓
PDF bloqueado
```

Não alterar o conteúdo do `MERGE`.

## Critério de conclusão

O PDF só é liberado quando o capítulo não possui pendências narrativas.

---

# Fora da V1

Não implementar antes de existir necessidade comprovada:

- LayoutParser;
- NetworkX;
- Fabric.js;
- Konva.js;
- modelos de IA adicionais;
- OCR;
- análise de balões;
- inferência semântica de diálogos;
- correção automática da imagem;
- editor visual complexo.

Esses recursos só devem ser avaliados se os casos reais mostrarem que OpenCV + geometria não são suficientes.

---

# Ordem recomendada

```text
M1 Contrato
↓
M2 Detecção
↓
M3 Ordem
↓
M4 Confiança
↓
M5 Página
↓
M6 Persistência
↓
M7 Gate PDF
```

Cada milestone deve ser fechado e validado antes do próximo.

Evitar refatorações paralelas e mudanças nos fluxos de merge durante esta implementação.

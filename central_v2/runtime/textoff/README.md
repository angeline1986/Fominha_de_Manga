# Runtimes TextOff da Central V2

Cada feature usa seu próprio Python em `<feature>/.venv/`. Não mover nem
atualizar os ambientes existentes em `processamento/limpeza_baloes/`; eles
continuam atendendo à Central V1 e às ferramentas atuais.

## Ambientes provisionados

| Feature | Ambiente | Lock |
|---|---|---|
| Merged Nível I | `merged_nivel_i/.venv` | `merged_nivel_i/requirements.lock.txt` |
| Merged Nível II | `merged_nivel_ii/.venv` | `merged_nivel_ii/requirements.lock.txt` |

Merged Nível III usa o ambiente isolado de `merged_nivel_i`: ele analisa somente imagens limpas de `TO_MERGED_CONSOLIDADO`, em recortes verticais sobrepostos com o segmentador fixado para manter detalhes de contorno em páginas longas. Registra candidatos de cor decorativa, gradiente e contorno irregular em `TO_MERGED_NIVEL_III`. A etapa é experimental, não altera imagens, pode demorar mais que uma passada em página inteira, e vincula seu manifesto aos hashes dos manifestos Nível I, Nível II (quando disponível) e consolidado. Candidatos de contorno irregular podem incluir falsos positivos e requerem revisão visual.
| Patch Balão Transparente | `especiais/balao_transparente/.venv` | `especiais/balao_transparente/requirements.lock.txt` |
| Balão Transparente — Legado | `especiais/balao_transparente_legado/.venv` | `especiais/balao_transparente_legado/requirements.lock.txt` |

O Nível I usa o snapshot do Cleaner V2 mais Ultralytics para autorização de
balões. O Nível II usa o snapshot Regional como baseline, instalado em uma
venv independente. Modelos permanecem fora do repositório nos caches já
configurados pelo projeto.

Reconstrução e proveniência completas estão em
`docs/Refatoracao/01_ambientes_virtuais.md`, seção 15. Para recriar, use
Python 3.12.7 e o lock da feature. Os locks atuais foram validados em macOS
arm64. Não versionar diretórios `.venv` nem trocar o runtime de uma feature
antes de validar seus workers.

Casos Especiais possui executor próprio de prévia, sem promoção. Os dois
ambientes têm instalação independente e não lançam o Python da V1.
Detalhes, reconstrução e comandos de comparação: [especiais/README.md](especiais/README.md).

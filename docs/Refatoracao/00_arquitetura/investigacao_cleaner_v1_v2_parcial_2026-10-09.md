# Investigação forense do Cleaner — V1 × Central V2

**Registro parcial de evidências — 09/10/2026**  
**Estado:** investigação em andamento; documento de consolidação incremental.  
**Escopo:** Patch Estilizado, obra *Gazing at you*, capítulo 1, `page-082-086.png`.  
**Política:** apenas leitura e testes isolados; não alterar V1 congelada, branch protegida, arquivos oficiais, venvs ou modelos.

## 1. Objetivo

Determinar, com evidências reproduzíveis, qual modelo, backend, dispositivo, ambiente Python e configuração o Cleaner utilizou quando produziu o resultado histórico da V1; identificar o primeiro ponto de divergência na reprodução da Central V2; tentar reproduzir **exatamente** as saídas V1 (pixels e hashes), sem alterar componentes protegidos.

## 2. Identificação dos experimentos

- **V1 referência:** run `26830ad956b24b0ea6d933df7f6164ac`, diretório `~/Documents/TI/Projetos/Fominha_V1_Benchmark/reports/experimentos/textoff_especiais/26830ad956b24b0ea6d933df7f6164ac/`.
- **V2 reprodução isolada:** run `e74860f77ba04a78bc009dd67c4e0ba8`, diretório `/private/tmp/fominha-v1-v2-estilizado-26830-cache-fc_kqmpx/staging/e74860f77ba04a78bc009dd67c4e0ba8/`.
- **Comparativo:** `/private/tmp/fominha-v1-v2-estilizado-26830-cache-fc_kqmpx/comparison/`, com `metrics.json`, `relatorio.md` e `roi_resultados_v1_v2.png`.
- **Arquivo de entrada:** 940 × 7306 pixels, RGB, SHA-256 `10815c4dab99aef52bde65e84e8ab3048b20dae654f6f36ee17b8cc635abf77f` (igual nos dois runs).
- **ROI:** `[279,3583,435,104]`; algoritmo declarado `textoff_special_roi_styled_v1`; composição `source_without_official_base`.

### Artefatos de referência

| Artefato | V1 (SHA-256) | V2 (SHA-256) |
|---|---|---|
| Máscara original Cleaner | `d269bb1dd2be55d27dcd77dcb2cd5b3f6433bda18ae2f7c131c037db75d6a480` | `2569e0a1dfaf81a9f189c5e09504c48f31f970ea54db56b1efd6d5da57847cda` |
| Saída limpa Cleaner | `cc0005152379fb878bf03fcd9e57f6880b331d061ddf40b8448241c60aee33a4` | `c78551a942cd0758d2d6d4ef8d3d217ef55770c88414999041a4b93208c1aefb` |
| Máscara autorizada na ROI | `ffeca365c3247da21bac5940b9bf759635e02d1d93404e319ceb4ff6824a1f0f` | `7e3d1147a8d4f2830a19601b44bf835063dc14dca78b25a3b06113b68a626d2b` |
| Resultado `01_local_heal.png` | `1a666dd2715a0e158cf723fb77ef06d96422b9e7bef155267da5084689ead0b3` | `21f382911104e3ce85dffe216cd447c30520e5500b01fa24d8209554d2fe02c2` |

- Máscara autorizada ROI: **52.274 px V1** versus **49.280 px V2**; máscaras ROI diferem em **12.002 px**.
- Máscaras originais Cleaner diferem em **61.641 px**; resultados finais diferem em **50.274 px** (diferença máxima de canal reportada: 15).
- A divergência já existe nos artefatos **`source_mask` e `source_clean`** do Cleaner, antes da etapa de preenchimento local. Não atribuir causalidade somente à máscara: **ambos** diferem.
- A implementação comparada do patch e parâmetros principais eram iguais: `PATCH_RADIUS=4`, `SEARCH_RADIUS=70`, `SEARCH_STEP=2`, `MIN_CONTEXT=12`, `SOURCE_VALID=0.92`.

## 3. Baseline histórica preservada

**Arquivo físico (HD externo):**

`/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/venvs/fominha_venvs_complete_20260924_231843.tar.gz`

- Tamanho aproximado: **1,4 GB**.
- SHA-256 verificado: `60d88422fcd94a59a368df92a8ce41f7142436396e3ac374de8496479772d188`.
- `gzip -t`: **OK**.
- Contém a `.venv` de `processamento/limpeza_baloes/cleaner_v2` e o pacote `pcleaner-2.11.11`.
- Inventário da fase zero: `docs/Refatoracao/00_arquitetura/01_ambientes_virtuais.md`; evidências em `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/`.
- **Limite histórico:** a baseline é um snapshot de 24–25/09; é necessário estabelecer com evidência a data e as condições do run específico V1 para afirmar que o snapshot reflete exatamente sua execução.

### Dependências identificadas no inventário

- Python **3.12.7**, `pcleaner==2.11.11`, `numpy==2.5.3`, `opencv-python==5.0.0.93`, `torch==2.14.0`, `torchvision==0.29.0`, `pillow==12.3.0`, `manga-ocr==0.1.16`, `transformers==5.17.0`.
- Modelos preservados no HD e correspondentes ao cache atual do Pcleaner:
  - `comictextdetector.pt` — SHA-256 `1f90fa60aeeb1eb82e2ac1167a66bf139a8a61b8780acd351ead55268540cccb`;
  - `anime-manga-big-lama.pt` — SHA-256 `479d3afdcb7ed2fd944ed4ebcc39ca45b33491f0f2e43eb1000bd623cfb41823`.
- `anime-manga-big-lama.pt` está preservado, mas **o perfil analisado desabilita inpainting**; não presumir seu uso no run do Estilizado.
- O backup inclui também outros modelos de outras funcionalidades. Arquivos `._*` no HD são metadados AppleDouble do macOS, não pesos alternativos do detector.

### Comparações de código

- Comparação de `.py` do Pcleaner entre backup de 24/09 e venv geral atual: **109 arquivos reais iguais por SHA-256; zero diferentes**. Os 109 registros `AUSENTE` eram sidecars `._*` do macOS, sem equivalência a módulos executados.
- Seis módulos entre venv geral e venv dedicada do Estilizado V2: `main.py`, `config.py`, `ctd_interface.py`, `preprocessor.py`, `comic_text_detector/inference.py`, `model_downloader.py`: **idênticos por SHA-256**.
- Isso confirma identidade dos arquivos comparados, **não** identidade total do runtime nativo nem do estado da execução.

## 4. Perfil e cadeia de execução

**Perfil real:** `processamento/limpeza_baloes/cleaner_v2/preserve-colors.ini`, SHA-256 `e090cb53eac1f78ca5e876d092f15ed6cc29ed98c99ad93cb269c243169a5ae0` na verificação atual.

Parâmetros relevantes: `model_path` vazio (modelo escolhido pelo Pcleaner); `input_height_lower_target=1000`; `input_height_upper_target=4000`; `split_long_strips=True`; `preferred_split_height=2000`; `split_tolerance_margin=500`; `merge_after_split=True`; `allow_colored_masks=True`; `mask_growth_step_pixels=2`; `mask_growth_steps=11`; `min_mask_thickness=4`; `mask_max_standard_deviation=15`; `mask_selection_fast=False`; `denoising_enabled=True`; **`inpainting_enabled=False`**.

**Seleção de modelo no `pcleaner/main.py`:**

```python
gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
if torch.backends.mps.is_available():
    initialize_ocr_model()
model_path = config.get_model_path(gpu)
```

- Com GPU reconhecida: seleção preferencial do modelo `.pt` PyTorch; sem GPU: modelo OpenCV `.onnx` (salvo override explícito).
- O `ctd_interface.py` registra `Using device for text detection model: <device>` e seleciona `mps` caso MPS esteja disponível **naquele processo**.
- `TextDetector` escolhe backend pela extensão do modelo: `.onnx` -> `cv2.dnn.readNetFromONNX(...)` (OpenCV); outro formato -> `TextDetBase(...)` (PyTorch). **A linha de log `device: cpu` sozinha não prova o formato do modelo.**
- `onnxruntime` não está instalado nas duas venvs examinadas. Isso não inviabiliza ONNX via OpenCV DNN.
- O perfil padrão `outlined-text.ini` de outras rotinas **não** deve ser confundido com o `preserve-colors.ini` deste tratamento.

**Cadeia V2 efetiva verificada no código:**

1. `textoff_special/process.py` lança o worker com a venv dedicada `central_v2/runtime/textoff/especiais/patch_estilizado/.venv/bin/python`, herdando ambiente e adicionando `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `PYTHONUNBUFFERED=1`.
2. O worker chama a rotina de tratamento.
3. `patch_degrade_experimento.py` invoca `processamento/limpeza_baloes/cleaner_v2/.venv/bin/python` para executar `cleaner_v2/main.py` com `--profile preserve-colors.ini --timeout 900` — **o Cleaner roda na venv geral**, não na dedicada.
4. O wrapper executa `python -u -m pcleaner.main clean ...` num subprocesso, com o ambiente herdado; `--offline` não consta da chamada específica do Patch Estilizado verificada.

## 5. O que o benchmark V2 realmente registrou

**Run:** `e74860f77ba04a78bc009dd67c4e0ba8`  
**Log:** `.../logs/worker.log`, em 09/10/2026 ~15:58, horário local do arquivo.

Registro literal:

```text
Running text detection AI model...
Using device for text detection model: cpu
Using 1 processes for text detection.
```

- **CPU na detecção V2: confirmado diretamente pelo log.**
- **ONNX na detecção V2: não confirmado diretamente** por esse log; pode ser ONNX/OpenCV ou PyTorch/CPU, dependendo do caminho carregado.
- `runtime.json` informa Python `3.12.7 | packaged by Anaconda, Inc.`, executável da **venv dedicada**, `macOS-26.6.2-arm64-arm-64bit`, versões dos pacotes e hashes de arquivos de código.
- `manifest.json` contém `models: []`: o mecanismo de proveniência **não registrou o modelo interno do Pcleaner**; não significa que nenhum modelo foi carregado.
- O log contém erros repetidos `OSError` em `psutil.swap_memory()` (`pcleaner.helpers.sys_swap_memory_total`), mas o processamento prosseguiu e concluiu (~32,3 s); **sem evidência de relação causal com a divergência visual**.
- A divisão da imagem em partes é consistente com as `4/4` etapas de detecção e máscaras registradas; confirmar regras exatas da divisão no código se necessário.

## 6. Testes de MPS executados em 09/10

- Venv **dedicada**: Torch 2.14.0; `mps.is_built()=True`, `mps.is_available()=True`, `cuda.is_available()=False`.
- Subprocesso iniciado pela venv dedicada: MPS **True**, exit code `0`.
- Venv **geral** (Python real invocado pelo Patch): MPS **True**, CUDA **False**, seleção lógica GPU **True**.
- Configuração persistida `~/Library/Application Support/pcleaner/pcleanerconfig.ini` (mtime 19/09/2026): `default_torch_model_path=~/Library/Caches/pcleaner/model/comictextdetector.pt`; `default_cv2_model_path` vazio/`None`; perfil ativo sem override.
- **Previsão de seleção HOJE na venv geral:** `comictextdetector.pt` via PyTorch/MPS. Essa previsão **não** constitui prova de qual modelo/dispositivo o run V1 usou, nem de por que o run V2 registrou CPU.
- O código examinando `run_worker` **não força CPU explicitamente**. Investigar contexto original da execução; MPS pode ter sido indisponível naquele momento ou pode haver outras condições não registradas. Nenhuma causa provada ainda.

## 7. Evidências negativas e limitações

- `run.json` e `roi_report.json` do run V1 não trouxeram, na pesquisa feita, campos ou logs de modelo/provider/dispositivo. **Não existe ainda confirmação histórica direta de MPS na V1.**
- `models: []` no run V2 evidencia **lacuna da instrumentação de proveniência**.
- O diagnóstico inicial descreveu V2 como ONNX/CPU; **corrigir o status**: CPU comprovada, ONNX ainda requer evidência de carregamento e SHA do modelo.
- A verificação de hash do perfil em caminho `central_v2/runtime/textoff/especiais/patch_estilizado/preserve-colors.ini` falhou porque o arquivo não existe nesse caminho; isso **não comprova** ausência do perfil usado: a chamada real aponta para o perfil em `cleaner_v2`.
- As evidências atuais não autorizam afirmar que o backend é a causa da diferença de pixels. Não alterar implementações para tratar hipótese como fato.

## 8. Próximo experimento — protocolo proposto, **ainda não executado**

1. Preservar cópia/hash de entrada e referências V1; criar área temporária isolada fora das obras e repositórios.
2. Instrumentar de modo externo/não invasivo ou capturar logs detalhados para registrar **Python efetivo, MPS no subprocesso Cleaner, caminho exato/SHA do modelo, backend e formato** usados na nova execução.
3. Executar o **mesmo Cleaner** em condições controladas com PyTorch/MPS, mesma imagem e `preserve-colors.ini`, sem escrever nos ambientes/artefatos originais. Não forçar backend no código do projeto.
4. Comparar SHA-256 e pixels de `source_mask.png` **e** `source_clean.png` separadamente com a V1; confirmar que a máscara final autorizada coincide, sem aceitar somente aparência semelhante.
5. Se ambos os insumos coincidirem, executar o Patch Estilizado completo no staging isolado e conferir SHA do resultado `01_local_heal.png`. Se não coincidirem, localizar o primeiro estágio divergente e comparar metadados do detector, segmentação/redimensionamento, OCR, máscara e denoiser.
6. Se necessário, testar combinações controladas **máscara V1/V2 × clean V1/V2** em área temporária, para quantificar o peso de cada entrada. Não tratar máscara como única variável.

### Critério de conclusão

Somente considerar a reprodução **exata** da V1 quando imagens/artefatos coincidirem por conteúdo e pixels (e quando apropriado SHA de arquivo); registrar o que é comprovado, inferido e ainda desconhecido. Nunca usar o run original como área de escrita.

## 9. Localização dos relatórios parciais recebidos

Arquivos produzidos no Desktop do usuário e analisados na conversa:

- `diagnostico_backup_v1.txt`
- `comparacao_pcleaner_v1_v2.txt`
- `diagnostico_runtime_estilizado.txt`
- `selecao_modelo_cleaner.txt`
- `config_modelos_pcleaner.txt`
- `decisao_efetiva_modelo.txt`
- `evidencias_modelo_runs_v1_v2.txt`
- `localizacao_benchmark_v2.txt`
- `auditoria_execucao_real_v2.txt`
- `diagnostico_selecao_cpu.txt`
- `contexto_worker_estilizado.txt`

**Nota operacional:** estes relatórios permanecem na área do usuário e nas mensagens da investigação. Este documento é apenas um resumo forense incremental, não substitui os logs ou manifests originais.

## 10. Controle de continuidade

- **Próxima ação:** preparar e revisar um comando **único**, de baixo risco, para teste isolado do Cleaner com captura de backend/modelo e comparação das saídas contra V1.
- **Sem autorização para:** editar código, modelos, venvs, branch protegida, imagens oficiais, efetivar patch, commit ou push.
- **Versão deste registro:** parcial 1 — 09/10/2026.

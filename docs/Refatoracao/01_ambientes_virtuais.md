# Ambientes Virtuais e Modelos — Fominha_de_Manga

> **Documento operacional de referência**
>
> Este documento explica por que o projeto possui ambientes virtuais Python separados, qual fluxo utiliza cada ambiente, quais dependências precisam ser preservadas e como recuperar os ambientes em caso de troca de máquina, corrupção da `.venv` ou entrada de uma nova pessoa no projeto.
>
> **Baseline documentada:** 25/09/2026  
> **Python das três venvs:** 3.12.7

---

## 1. Objetivo

O `Fominha_de_Manga` utiliza processamento de imagens e modelos de IA com dependências pesadas e, em alguns casos, sensíveis a versão.

Por isso, os ambientes de processamento **não devem ser tratados como uma única `.venv` genérica do projeto**.

Atualmente existem três ambientes críticos:

| Ambiente | Localização | Papel |
|---|---|---|
| **Cleaner V2** | `processamento/limpeza_baloes/cleaner_v2/.venv` | Ambiente principal do fluxo de limpeza de balões / Texto Off baseado no `pcleaner` e modelos associados |
| **Gradiente Suave** | `processamento/limpeza_baloes/gradiente_suave/.venv` | Ambiente isolado do tratamento por gradiente suave |
| **Level 3 Regional** | `processamento/limpeza_baloes/level3_regional/.venv` | Ambiente do processamento regional do Nível III, com OCR, segmentação/inpainting e dependências adicionais de visão computacional |

As `.venv` **não são versionadas no Git**.

Isso é intencional: elas contêm muitos arquivos, bibliotecas binárias e dependências específicas da plataforma. O que deve ser preservado no repositório é a informação necessária para entender e reconstruir os ambientes.

---

## 2. Regra de manutenção

Não instalar, atualizar ou remover bibliotecas dessas venvs de forma indiscriminada.

Antes de alterar dependências de qualquer um desses ambientes:

1. identificar qual fluxo depende da biblioteca;
2. registrar o estado atual;
3. fazer a alteração somente na venv correspondente;
4. validar o fluxo funcional afetado;
5. atualizar o snapshot lógico e esta documentação quando a alteração for aceita.

Não usar `pip install -U`, recriar uma `.venv` ou substituir versões em massa apenas para “atualizar o ambiente”.

Os snapshots existentes representam ambientes que estavam funcionando no momento da baseline e devem servir como referência de recuperação.

---

# 3. Cleaner V2

## 3.1 Localização

```text
processamento/limpeza_baloes/cleaner_v2/.venv
```

Python validado:

```text
Python 3.12.7
```

## 3.2 Finalidade

É o ambiente mais sensível dos três.

Ele suporta o fluxo de limpeza de balões / Texto Off associado ao Cleaner V2 e reúne bibliotecas de OCR, visão computacional, processamento de imagens, interface e modelos de detecção/inpainting.

Entre as dependências registradas na baseline estão:

```text
pcleaner==2.11.11
manga-ocr==0.1.16
simple-lama-inpainting==0.1.0
torch==2.14.0
torchvision==0.29.0
opencv-python==5.0.0.93
numpy==2.5.3
transformers==5.17.0
PySide6==6.11.2
```

O snapshot completo possui **71 pacotes**.

O `requirements.txt` original do módulo contém apenas:

```text
pcleaner==2.11.11
```

Portanto, **não considerar esse `requirements.txt` sozinho como reprodução exata do ambiente operacional**.

Para reprodução fiel, consultar o snapshot lógico da baseline.

## 3.3 Configuração operacional preservada

Além das versões dos pacotes, o Cleaner possui configuração operacional preservada em:

```text
docs/Refatoracao/environment_baseline/2026-09-25/cleaner_v2_outlined-text.ini
```

Esse arquivo corresponde à configuração validada no ambiente funcional no momento da baseline.

## 3.4 Modelos utilizados

Dois modelos do `pcleaner` foram explicitamente preservados e validados.

### Comic Text Detector

Arquivo:

```text
comictextdetector.pt
```

Local operacional conhecido:

```text
~/Library/Caches/pcleaner/model/comictextdetector.pt
```

SHA-256:

```text
1f90fa60aeeb1eb82e2ac1167a66bf139a8a61b8780acd351ead55268540cccb
```

### Anime/Manga Big LaMa

Arquivo:

```text
anime-manga-big-lama.pt
```

Local operacional conhecido:

```text
~/Library/Caches/pcleaner/model/anime-manga-big-lama.pt
```

SHA-256:

```text
479d3afdcb7ed2fd944ed4ebcc39ca45b33491f0f2e43eb1000bd623cfb41823
```

Os hashes portáteis estão registrados em:

```text
docs/Refatoracao/environment_baseline/2026-09-25/cleaner_v2_models_SHA256SUMS.txt
```

---

# 4. Gradiente Suave

## 4.1 Localização

```text
processamento/limpeza_baloes/gradiente_suave/.venv
```

Python validado:

```text
Python 3.12.7
```

## 4.2 Finalidade

Ambiente isolado do processamento de **gradiente suave**.

É propositalmente pequeno e reduz o acoplamento desse tratamento com as bibliotecas mais pesadas utilizadas nos demais fluxos.

Na baseline atual existem somente dois pacotes instalados além das ferramentas básicas da venv:

```text
numpy==2.5.3
opencv-python-headless==5.0.0.93
```

O `requirements.txt` versionado registra:

```text
numpy
opencv-python-headless
```

Observe que esse arquivo **não fixa as versões**.

Para saber exatamente quais versões estavam funcionando na baseline de 25/09/2026, utilizar:

```text
docs/Refatoracao/environment_baseline/2026-09-25/gradiente_suave_pip_freeze.txt
```

---

# 5. Level 3 Regional

## 5.1 Localização

```text
processamento/limpeza_baloes/level3_regional/.venv
```

Python validado:

```text
Python 3.12.7
```

## 5.2 Finalidade

Ambiente utilizado pelo processamento regional relacionado ao **Nível III**.

Ele possui dependências de OCR, visão computacional, inpainting e modelos de detecção, sendo significativamente maior que o ambiente de Gradiente Suave.

O snapshot atual contém **62 pacotes**.

O `requirements.txt` do módulo possui 30 dependências fixadas, incluindo:

```text
easyocr==1.7.2
numpy==2.5.3
opencv-python==5.0.0.93
opencv-python-headless==5.0.0.93
scikit-image==0.26.0
scipy==1.18.1
simple-lama-inpainting==0.1.0
torch==2.14.0
torchvision==0.29.0
```

Entretanto, a venv operacional possui pacotes adicionais que não aparecem como dependências diretas nesse `requirements.txt`.

Entre os pacotes identificados como instalados diretamente estão:

```text
easyocr==1.7.2
huggingface_hub==2.0.0
simple-lama-inpainting==0.1.0
ultralytics==8.4.162
```

Isso significa que **o `requirements.txt` atual não deve ser considerado, sozinho, uma receita completa de reconstrução exata dessa venv**.

A fonte de verdade da baseline é:

```text
docs/Refatoracao/environment_baseline/2026-09-25/level3_regional_pip_freeze.txt
```

---

# 6. Baseline lógica versionável

A baseline consolidada dos ambientes está em:

```text
docs/Refatoracao/environment_baseline/2026-09-25/
```

Ela contém os registros necessários para consultar o estado exato das três venvs sem versionar os diretórios `.venv`.

Estrutura esperada:

```text
environment_baseline/
└── 2026-09-25/
    ├── cleaner_v2_baseline_SHA256SUMS.txt
    ├── cleaner_v2_models_SHA256SUMS.txt
    ├── cleaner_v2_outlined-text.ini
    ├── cleaner_v2_packages.json
    ├── cleaner_v2_pip_freeze.txt
    ├── cleaner_v2_python.txt
    ├── gradiente_suave_direct_packages.txt
    ├── gradiente_suave_pip_freeze.txt
    ├── gradiente_suave_python.txt
    ├── gradiente_suave_SHA256SUMS.txt
    ├── level3_regional_direct_packages.txt
    ├── level3_regional_pip_freeze.txt
    ├── level3_regional_python.txt
    └── level3_regional_SHA256SUMS.txt
```

### O que cada tipo de arquivo representa

`*_python.txt`
: versão do Python usada pela venv.

`*_pip_freeze.txt`
: conjunto exato de pacotes e versões instalado no ambiente funcional.

`*_direct_packages.txt`
: pacotes identificados pelo `pip` como não requeridos por outros pacotes; ajuda a distinguir dependências diretamente instaladas de dependências transitivas.

`*_SHA256SUMS.txt`
: hashes para verificar que o conteúdo da baseline não foi alterado.

`cleaner_v2_packages.json`
: inventário adicional dos pacotes do Cleaner V2.

`cleaner_v2_outlined-text.ini`
: configuração operacional preservada do Cleaner V2.

`cleaner_v2_models_SHA256SUMS.txt`
: identidade criptográfica dos modelos externos utilizados pelo Cleaner V2.

---

# 7. Backup físico externo

Além da baseline lógica, existe um backup físico das venvs em HD externo.

Local conhecido:

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/
```

## 7.1 Backup das venvs

Arquivo:

```text
venvs/fominha_venvs_complete_20260924_231843.tar.gz
```

SHA-256:

```text
60d88422fcd94a59a368df92a8ce41f7142436396e3ac374de8496479772d188
```

O arquivo foi validado com `gzip -t`.

Na verificação realizada, o arquivo possuía aproximadamente **1,4 GB** e **93.103 entradas**.

Ele contém, entre outros ambientes:

```text
download/mangago_downloader/.venv
processamento/limpeza_baloes/cleaner_v2/.venv
processamento/limpeza_baloes/gradiente_suave/.venv
processamento/limpeza_baloes/level3_regional/.venv
reports/experimentos/candy-ch4-pages-051-053/patchmatch/.venv
```

Os três ambientes documentados neste arquivo estão, portanto, protegidos também por uma cópia física.

> O `.tar.gz` é um recurso de recuperação, não substitui a documentação nem a baseline lógica.

## 7.2 Backup dos modelos

Os modelos são armazenados separadamente das venvs em:

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/models/
```

A separação é intencional: **os modelos não estão dentro do arquivo de backup das venvs**.

A estrutura conhecida é:

```text
models/
├── SHA256SUMS.txt
├── README_RECOVERY.txt
├── lama/
│   └── anime-manga-big-lama.pt
├── manga109-segmentation-bubble/
│   └── best.pt
├── bubble-cleaner-v3/
│   └── yolo26n.pt
└── pcleaner/
    └── comictextdetector.pt
```

Todos os quatro modelos presentes no manifesto externo foram validados por SHA-256.

### Hashes conhecidos

```text
anime-manga-big-lama.pt
479d3afdcb7ed2fd944ed4ebcc39ca45b33491f0f2e43eb1000bd623cfb41823

manga109-segmentation-bubble/best.pt
4028152940f7c910f40192f46ede3b3f6c7129e5c76849c324d3564f8ac50198

bubble-cleaner-v3/yolo26n.pt
29dbed070efdfa9b2b9f0b6a393bd9d02b86876ab54976fdf0a5cbd28b5c4334

pcleaner/comictextdetector.pt
1f90fa60aeeb1eb82e2ac1167a66bf139a8a61b8780acd351ead55268540cccb
```

O backup externo também possui:

```text
models/README_RECOVERY.txt
models/SHA256SUMS.txt
```

Esses arquivos devem ser consultados durante uma recuperação física dos modelos.

---

# 8. Estratégia de recuperação

Existem duas formas de recuperar os ambientes.

## 8.1 Estratégia preferencial — reconstrução lógica

Usar quando for necessário configurar uma máquina nova ou reconstruir uma venv de maneira limpa.

Fluxo recomendado:

```text
baseline documentada
        ↓
identificar a venv necessária
        ↓
confirmar versão do Python
        ↓
criar nova venv
        ↓
instalar as versões registradas no pip freeze
        ↓
restaurar/configurar modelos externos
        ↓
restaurar configuração específica, quando aplicável
        ↓
validar o fluxo funcional
```

Não substituir uma venv operacional existente antes da validação da nova.

A reconstrução deve ser feita inicialmente em ambiente separado.

## 8.2 Estratégia de contingência — backup físico

Usar quando for necessário recuperar rapidamente o estado físico conhecido das venvs.

Fonte:

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/venvs/
```

Antes de utilizar o arquivo:

1. validar seu SHA-256;
2. validar a integridade do `.tar.gz`;
3. não extrair diretamente sobre uma venv funcional existente;
4. restaurar inicialmente em local temporário;
5. verificar caminhos e compatibilidade da máquina;
6. somente depois promover o ambiente recuperado.

Venvs Python podem conter caminhos internos associados ao local onde foram criadas. Por isso, o backup físico deve ser tratado como **contingência**, enquanto os snapshots lógicos são a referência para reconstrução limpa.

---

# 9. Recuperação dos modelos

Modelos de IA não devem ser tratados como simples dependências do `pip`.

Ao recuperar uma máquina, verificar primeiro:

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/models/
```

Depois conferir:

```text
SHA256SUMS.txt
README_RECOVERY.txt
```

Para os modelos do `pcleaner`, o local operacional conhecido é:

```text
~/Library/Caches/pcleaner/model/
```

A identidade do arquivo deve ser confirmada pelo SHA-256 antes de considerar a recuperação concluída.

Não substituir um modelo apenas porque possui o mesmo nome.

---

# 10. Verificação da baseline

Para validar os manifests das venvs que possuem arquivos SHA portáteis:

```bash
cd docs/Refatoracao/environment_baseline/2026-09-25

shasum -a 256 -c gradiente_suave_SHA256SUMS.txt
shasum -a 256 -c level3_regional_SHA256SUMS.txt
shasum -a 256 -c cleaner_v2_baseline_SHA256SUMS.txt
```

O resultado esperado é `OK` para todos os arquivos listados.

Os hashes dos modelos do Cleaner V2 são um inventário de identidade. Como os modelos ficam fora desse diretório, sua validação deve ser feita apontando para os arquivos físicos correspondentes.

---

# 11. O que NÃO fazer

Não:

- versionar os diretórios `.venv`;
- assumir que o `requirements.txt` simplificado do Cleaner V2 reproduz todo o ambiente;
- assumir que o `requirements.txt` do Level 3 Regional representa todos os pacotes diretamente instalados;
- atualizar `torch`, `opencv`, `numpy`, `pcleaner`, OCR ou bibliotecas relacionadas sem validação do fluxo;
- apagar caches de modelos sem verificar se existe backup válido;
- substituir modelos apenas pelo nome do arquivo;
- restaurar o `.tar.gz` diretamente sobre ambientes funcionais;
- misturar dependências das três venvs para “simplificar” o projeto sem uma análise técnica específica.

A separação dos ambientes existe para limitar impacto entre fluxos diferentes.

---

# 12. Procedimento para uma nova pessoa no projeto

Ao trabalhar pela primeira vez com os módulos de processamento de imagens:

1. leia este documento antes de instalar dependências;
2. identifique qual módulo será alterado;
3. utilize a venv específica desse módulo;
4. consulte o `pip freeze` da baseline para conhecer o ambiente funcional;
5. verifique se o fluxo depende de modelos externos;
6. não altere versões como efeito colateral de outra tarefa;
7. se precisar reconstruir o ambiente, faça isso separadamente e valide antes de substituir o existente.

Para manutenção cotidiana, a regra é simples:

> **Uma feature não deve modificar a venv de outro fluxo sem justificativa técnica explícita.**

---

# 13. Fontes de verdade

Para evitar ambiguidades, utilizar esta ordem de consulta:

### Entender o ambiente

```text
Este documento
```

### Saber as versões exatas instaladas na baseline

```text
docs/Refatoracao/environment_baseline/2026-09-25/*_pip_freeze.txt
```

### Saber quais pacotes parecem ter sido instalados diretamente

```text
docs/Refatoracao/environment_baseline/2026-09-25/*_direct_packages.txt
```

No Cleaner V2, consultar também:

```text
cleaner_v2_packages.json
```

### Saber a configuração operacional preservada do Cleaner V2

```text
cleaner_v2_outlined-text.ini
```

### Confirmar integridade da baseline

```text
*_SHA256SUMS.txt
```

### Recuperar fisicamente as venvs

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/venvs/
```

### Recuperar modelos

```text
/Volumes/Seagate2T/BACKUPS/Fominha_de_Manga/models/
```

---

# 14. Estado da baseline de 25/09/2026

Na criação desta documentação:

- Cleaner V2 estava em Python 3.12.7;
- Gradiente Suave estava em Python 3.12.7;
- Level 3 Regional estava em Python 3.12.7;
- o snapshot lógico do Cleaner V2 havia sido comparado com a venv funcional;
- configuração `outlined-text` do Cleaner V2 havia sido preservada;
- os dois modelos do `pcleaner` haviam sido identificados por SHA-256;
- Gradiente Suave possuía snapshot de 2 pacotes;
- Level 3 Regional possuía snapshot de 62 pacotes;
- os manifests SHA das três baselines haviam sido validados;
- o backup físico das venvs havia passado na verificação de integridade;
- os quatro modelos do backup externo haviam sido validados por SHA-256.

Essa baseline deve ser considerada o **ponto de recuperação anterior à refatoração arquitetural**.

---

## Manutenção deste documento

Sempre que uma mudança aceita alterar de forma permanente:

- versão do Python;
- dependências;
- configuração operacional;
- modelo de IA;
- localização esperada de modelo;
- estratégia de recuperação;
- criação ou remoção de uma venv;

este documento e a baseline correspondente devem ser atualizados juntos.

Não sobrescrever uma baseline histórica.

Criar um novo diretório datado, por exemplo:

```text
docs/Refatoracao/environment_baseline/AAAA-MM-DD/
```

Assim o projeto mantém rastreabilidade sobre qual ambiente estava operacional em cada marco relevante.

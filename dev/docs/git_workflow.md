# Fluxo Git do Fominha de Manga

## Cola rápida

Quando alterar o `mangago_downloader`:

```bash
cd mangago_downloader

git status
git add ...
git commit -m "descrição da alteração"
git push

cd ..

git status
git add mangago_downloader
git commit -m "chore: update mangago_downloader submodule"
git push
```

O primeiro commit salva a alteração no repositório do downloader.

O segundo commit atualiza no `Fominha_de_Manga` qual versão do downloader deve ser utilizada. Esse commit não copia os arquivos internos do downloader; ele só move a referência do submodule para outro commit.

## Arquitetura

`Fominha_de_Manga` é o HUB principal.

`mangago_downloader` é um repositório Git independente conectado ao HUB como submodule.

```text
Fominha_de_Manga/
├── menu.py
├── docs/
├── tests/
└── mangago_downloader/   ← Git submodule
```

O HUB não armazena diretamente todos os arquivos do `mangago_downloader`. Ele guarda uma referência para um commit específico do repositório `mangago_downloader`.

Esse mesmo padrão pode ser usado no futuro para outros módulos independentes.

## Onde Fazer Cada Commit

### Alterações no downloader

Faça o commit dentro de `mangago_downloader/` quando alterar:

- Playwright;
- downloads;
- providers;
- Web;
- PDF;
- conversores;
- testes internos do downloader.

```bash
cd mangago_downloader
git status
git add ...
git commit -m "descrição da alteração"
git push
```

### Alterações no HUB

Faça o commit na raiz `Fominha_de_Manga/` quando alterar:

- `menu.py`;
- integração entre módulos;
- documentação geral do Fominha;
- testes do HUB;
- inclusão futura de novos módulos.

```bash
git status
git add ...
git commit -m "descrição da alteração"
git push
```

## Por Que Existem Dois Commits

Suponha que você altere o `mangago_downloader`.

Depois de fazer:

```bash
cd mangago_downloader
git commit -m "descrição da alteração"
git push
```

A nova versão já existe no repositório do downloader.

Mas o `Fominha_de_Manga` ainda pode estar apontando para o commit anterior desse submodule. Por isso, volte ao HUB e registre a nova referência:

```bash
cd ..
git status
git add mangago_downloader
git commit -m "chore: update mangago_downloader submodule"
git push
```

Esse segundo commit não copia novamente o downloader. Ele apenas diz: "o HUB agora usa esta versão do módulo".

## Como Verificar o Estado

No HUB:

```bash
git status
```

Mostra se `menu.py`, `docs/`, `tests/` ou a referência do submodule mudaram.

Para verificar o submodule:

```bash
git submodule status
```

Mostra o commit do `mangago_downloader` registrado pelo HUB.

Dentro do downloader:

```bash
cd mangago_downloader
git status
git log -1 --oneline
```

Mostra se o downloader tem alterações locais e qual é o último commit dele.

## Clonando o Projeto

Forma recomendada:

```bash
git clone --recurse-submodules https://github.com/angeline1986/Fominha_de_Manga.git
cd Fominha_de_Manga
```

A opção `--recurse-submodules` faz com que o `mangago_downloader` também seja inicializado na versão registrada pelo HUB.

## Se Clonar Sem Submodules

Se o repositório já foi clonado sem `--recurse-submodules`, rode:

```bash
git submodule update --init --recursive
```

Isso inicializa os submodules depois do clone.

## Depois de git pull

Quando atualizar o HUB:

```bash
git pull
```

Se houver mudança na referência de algum submodule, rode:

```bash
git submodule update --init --recursive
```

Isso coloca os módulos locais nas versões registradas pelo HUB.

## Atualizando um Submodule

Para atualizar o `mangago_downloader` para a versão mais recente do seu `origin/main`:

```bash
cd mangago_downloader
git pull origin main

cd ..
git status
```

Se o HUB mostrar `mangago_downloader` como modificado, registre a nova referência:

```bash
git add mangago_downloader
git commit -m "chore: update mangago_downloader submodule"
git push
```

Faça isso quando quiser que o HUB passe oficialmente a utilizar aquela versão do módulo.

## Cuidados Importantes

- Não apague manualmente a estrutura Git do submodule.
- Não copie os arquivos internos do downloader para o Git do HUB.
- Commits do downloader são feitos dentro de `mangago_downloader/`.
- Commits do HUB são feitos na raiz `Fominha_de_Manga/`.
- Antes de atualizar a referência do HUB, garanta que o commit do módulo já foi enviado ao remoto.
- Não use force push como parte do fluxo normal.



## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## 
Finalize o versionamento da alteração. Identifique primeiro a qual repositório cada arquivo pertence. Faça commit e push no repositório correspondente. Se houver novo commit em um submodule, depois atualize a referência desse submodule no Fominha_de_Manga e faça commit e push do hub. Não misture arquivos de repositórios diferentes no mesmo commit.

Antes dos commits, execute os testes aplicáveis, revise o git status e confirme que não há alterações inesperadas, arquivos locais ou artefatos que não devam ser versionados. Não use force push e não reescreva histórico.
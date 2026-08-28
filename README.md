# Fominha de Manga

Fominha de Manga é o hub principal para ferramentas de extração, organização e conversão de mangás.

O ponto de entrada atual é o menu de terminal:

```bash
cd Fominha_de_Manga
python3 menu.py
```

## Módulos

`mangago_downloader` é mantido como um projeto independente e referenciado por este hub como submodule Git. O hub registra uma versão específica desse módulo sem misturar seu histórico interno.

## Clone

Para clonar tudo de uma vez:

```bash
git clone --recurse-submodules https://github.com/angeline1986/Fominha_de_Manga.git
```

Se o repositório já foi clonado sem submodules:

```bash
git submodule update --init --recursive
```

## Atualizar o Submodule

```bash
cd mangago_downloader
git pull origin main
cd ..
git add mangago_downloader
git commit -m "chore: update mangago_downloader submodule"
```

## Desenvolvimento

O projeto utiliza Git submodules para manter seus módulos independentes. Para alterar módulos, atualizar suas referências ou consultar o fluxo de commits, veja [Fluxo Git e Submodules](docs/git_workflow.md).


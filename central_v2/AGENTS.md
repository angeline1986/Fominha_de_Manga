# Regras da Central V2

- Cada arquivo de código deve ter no máximo 200 linhas, incluindo comentários
  e linhas em branco. O limite é obrigatório, não apenas um gatilho de revisão.
- Cada arquivo deve ter uma responsabilidade coesa. Separar por feature ou
  componente; não reduzir linhas com compactação artificial.
- O shell compõe a interface. Features possuem módulos próprios e seus estilos.
- Chamadas HTTP do frontend ficam em `frontend/_app/api/`.
- Stores notificam alterações dos dados que possuem. Páginas observam o store
  dos dados apresentados; não dependem de notificações indiretas de outro store.
- `render(container)` pode retornar uma função de limpeza. O router deve
  executá-la ao sair da página; assinaturas não podem sobreviver à sua página.
- CSS deve preservar a apresentação validada e pertencer ao componente que
  estiliza. Evitar redefinições acumuladas e estilos inline.
- Valores visuais comuns vêm de `frontend/_shared/tokens.css`: fontes, cores,
  pesos e dimensões. Ícones vêm de `_shared/icons/icons.js`, em SVG; não usar
  caracteres de fonte como ícones. Componentes mantêm seu CSS próprio e
  consomem os tokens, sem recriar valores comuns por feature.
- Botões criados por JavaScript declaram uma classe visual: use `.btn` para
  ações comuns ou uma classe semântica do componente com regra CSS explícita.
  Não dependa do estilo padrão do navegador nem presuma que estilos do pai
  alcançarão um botão sem classe. O contrato é verificado em
  `button_contract.test.mjs`.
- Listagens paginadas usam `_shared/pagination/`: tamanho de página definido
  somente em `config.js`, estado em `model.js` e controles em `pagination.js`.
  Features não definem tamanhos locais; busca, filtros e troca de contexto
  devem retornar à primeira página.
- Popups de confirmação e mensagens usam `_shared/messages/messages.js`
  (`confirmMessage` / `showMessage`) e seu CSS compartilhado. Features definem
  somente conteúdo e ações; não usam alert/confirm nativos nem estilos locais
  para recriar o popup. A referência visual é o modal compacto da V1.
- `backend/server.py` cuida da inicialização; `http_handler.py` adapta HTTP;
  `routes/` contém contratos de endpoints; `state/` contém projeções.
- Fluxos funcionais seguem V2 → orquestração → domínio existente → artefatos.
  Não importar a interface legada nem copiar algoritmos ou regras de autoridade.
- A V1 permanece intacta: não alterar, extrair, mover ou copiar seu código para
  implementar a V2. Ela serve como referência de comportamento e de contratos.
- Implementar interface e orquestração V2 próprias, reutilizando os módulos de
  domínio existentes. Capacidades ausentes no domínio devem ser explicitadas;
  não duplicar algoritmos escondendo-os em routes, jobs ou orquestração.
- Não alterar algoritmos, thresholds, manifests, promoção ou runtimes como
  efeito colateral de ajustes na V2.
- Validar coesão em revisão: o teste de tamanho não prova responsabilidade única.

Verificações:

```sh
python3 -m unittest discover -s dev/tests -p 'test_central_v2_*.py'
node --experimental-vm-modules --test dev/tests/central_v2_frontend/*.test.mjs
```

Executar da raiz do projeto. Testes HTTP precisam abrir portas locais;
testes JavaScript usam Node com módulos VM e não exigem pacotes externos.

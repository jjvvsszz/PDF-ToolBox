# PDF Toolbox (branch `painel`) — instruções para o Claude

Ferramentas web para PDF (FastAPI + PyMuPDF), empacotadas para o **Pterodactyl**: imagem
Docker multi-arch com o app e o LibreOffice + egg. Visão geral, API e configuração:
[README.md](README.md); guia do painel: [pterodactyl/README.md](pterodactyl/README.md).
Responder e escrever em **português**.

## Branches

- **`master`**: versão para Windows Server (NSSM). Correções da aplicação entram **lá
  primeiro** e chegam aqui com `git merge master` (o `deploy.ps1`/`deploy.yml` foram removidos
  nesta branch: em conflito modify/delete, mantenha removidos).
- **`painel`** (esta): só o que é específico do container (`Dockerfile`, `pterodactyl/`,
  workflow da imagem, `UPLOADS_DIR`/`LOG_FILE`/`COMPRESS_MAX_WORKERS`/HTTPS). Nunca mesclar
  esta branch no `master`.

## Comandos

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q test_app.py      # o teste Office real é pulado sem LibreOffice
```

Não há Docker na máquina de desenvolvimento: a imagem só é construída e testada no CI
([painel-image.yml](.github/workflows/painel-image.yml)). Mudanças no `Dockerfile` ou no
`entrypoint.sh` devem ser validadas pelo resultado do workflow antes de qualquer deploy.

## Convenções

As mesmas do `master` (ver o `CLAUDE.md` de lá): `storage.save_upload()` para uploads,
rotas `def` com `run_job()`/`download()`, `UserError` para erros do usuário (mensagens do
backend sem acentos), `open_pdf()` para abrir PDFs, teste de regressão para cada bug,
Conventional Commits em português. Específico daqui:

- O egg ([pterodactyl/egg-pdf-toolbox.json](pterodactyl/egg-pdf-toolbox.json)) e o app precisam
  andar juntos: toda variável nova do egg tem que ser lida em `app/config.py` ou no
  `entrypoint.sh`, e o smoke test do workflow usa o `startup` do egg.
- `entrypoint.sh` e `Dockerfile` têm fim de linha LF (forçado no `.gitattributes`).
- O Wings roda o container com o UID do usuário `pterodactyl` do host, não como `container`:
  nada na imagem pode depender de escrever fora de `/home/container`.

## Deploy no painel

O painel é operado a partir de um repositório de operação **privado**, com o MCP
`pterodactyl`, as regras de operação, a cópia dos eggs e a lista de monitoramento.
**O deploy é feito numa sessão do Claude Code aberta nesse repositório**, não neste. Cole lá
o prompt abaixo.

Este repositório é **público**: endereço do painel, domínios, nomes de nodes, IPs e o nome do
repositório de operação nunca devem ser registrados aqui (nem em commits, issues ou logs).

> **Prompt de deploy (Pterodactyl):**
>
> Faça o deploy do PDF Toolbox (repositório `jjvvsszz/PDF-ToolBox`, branch `painel`) no
> painel, seguindo as regras do `CLAUDE.md` deste repositório de operação:
>
> 1. **Imagem**: com `gh run list -R jjvvsszz/PDF-ToolBox --branch painel --workflow
>    painel-image.yml --limit 1`, confirme que o último run passou e anote o commit
>    (a imagem é `ghcr.io/jjvvsszz/pdf-toolbox:painel`, com a tag fixa `painel-<7 primeiros
>    caracteres do commit>`). Se falhou ou está rodando, pare e relate.
> 2. **Egg**: baixe `pterodactyl/egg-pdf-toolbox.json` da branch `painel` e compare com
>    `eggs/pdf-toolbox.json` deste repositório.
>    - Se for novo ou diferente: grave em `eggs/pdf-toolbox.json` e faça commit aqui. A API não
>      importa eggs: peça para eu importar/atualizar em **Admin → Eggs** e espere a confirmação.
>    - Depois, localize o egg pelo MCP (eggs são só leitura) e anote o id.
> 3. **Servidor**: procure pelo MCP um servidor chamado "PDF Toolbox".
>    - **Já existe (atualização)**: confirme comigo e faça **restart** (o Wings baixa a imagem
>      nova ao iniciar). Se o egg mudou variáveis, confira se o servidor tem as novas com
>      valores sensatos.
>    - **Não existe (primeira instalação)**: proponha e só crie após minha confirmação:
>      node (a imagem é multi-arch; prefira o node ARM), uma **alocação já existente e livre**
>      (o firewall do node pode não liberar toda porta), memória ≥ 2048 MB, disco ≥ 3× o
>      `MAX_UPLOAD_SIZE_MB`, CPU conforme o node; variáveis: `HTTPS=1`, `WORKERS` e
>      `COMPRESS_MAX_WORKERS` ≤ vCPUs, demais no padrão do egg. Espere a instalação terminar e
>      inicie.
> 4. **Verificar** (uma chamada por vez, nada em paralelo):
>    - estado `running` e recursos pelo MCP;
>    - fim de `logs/app.log` (`get_recent_logs`, ~100 linhas): deve ter
>      `Application startup complete` e nenhum `[ERROR]`/`Traceback` do boot;
>    - `curl -k https://<ip-do-node>:<porta>/health` → `{"status":"ok"}`; se a porta não
>      responder, relate que provavelmente falta liberar a porta no firewall do node.
> 5. **Domínio** (primeira instalação ou se ainda não houver): pergunte o hostname e siga a
>    convenção deste repositório de operação para expor serviços web (o app serve HTTPS na
>    porta com certificado autoassinado, ou com `ssl/cert.pem` e `ssl/key.pem` fornecidos).
>    Passe-me a configuração de DNS/proxy para eu aplicar e, depois que eu confirmar, teste
>    `https://<hostname>/health`.
> 6. **Monitoramento**: adicione/atualize a entrada em `rotinas/servidores.yml` (formato em
>    `monitoramento.md`) e faça commit:
>
>    ```yaml
>      - id: <id curto>
>        nome: PDF Toolbox
>        node: <node>
>        deve_estar_online: true
>        reiniciar_se_cair: true
>        alertas:
>          disco: 80                 # uploads grandes enchem o disco rapido
>          memoria: 90
>        logs:
>          - caminho: logs/app.log
>            linhas: 300
>            procurar: ["[ERROR]", "[CRITICAL]", "Traceback"]
>        http: https://<hostname>/health
>        notas: >
>          PDF Toolbox (jjvvsszz/PDF-ToolBox, branch painel). App vem pronto na imagem
>          ghcr.io/jjvvsszz/pdf-toolbox:painel; restart baixa a versao mais recente.
>          Erros "nao e um PDF valido"/"protegido por senha" sao do usuario (400), nao
>          problema. uploads/ e tmp/ sao limpos automaticamente; disco alto e persistente
>          indica limpeza travada: relatar. Nunca apagar ssl/ (certificado da origem).
>    ```
> 7. **Relatório**: commit/tag da imagem implantada, id do servidor, node e porta, resultado
>    das verificações e o que ficou pendente comigo (egg, Cloudflare, firewall).
>
> **Rollback**: troque a imagem do servidor (*Startup → Docker Image*) para a tag
> `painel-<commit anterior>` (confirmar comigo) e reinicie.

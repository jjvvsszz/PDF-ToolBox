# PDF Toolbox — instruções para o Claude

Ferramentas web para PDF (FastAPI + PyMuPDF). Visão geral, API e configuração:
[README.md](README.md). Responder e escrever em **português**.

## Branches

- **`master`**: versão para **Windows Server** (serviço NSSM, [deploy.ps1](deploy.ps1)).
- **`painel`**: mesma aplicação empacotada para **Pterodactyl** (imagem Docker + egg).
  Tem o próprio `CLAUDE.md` com o prompt de deploy no painel.
- Correções da aplicação entram primeiro no `master` e depois são mescladas na `painel`
  (`git switch painel && git merge master`). Nunca mesclar `painel` no `master`: ela remove
  os arquivos de deploy do Windows.

## Comandos

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt   # dependências + pytest/httpx
.venv\Scripts\python -m pytest -q test_app.py                  # suíte completa (~5 s)
.venv\Scripts\python main.py                                   # servidor em :8000
```

## Convenções do código

- **Uploads**: sempre `storage.save_upload()`; nunca usar `UploadFile.filename` em caminho.
  IDs de sessão e nomes de miniatura vindos do cliente passam por
  `is_valid_session_id` / `is_valid_thumb_name`.
- **Rotas** são `def` (síncronas) e usam `routes/_common.py`: `run_job()` cria a pasta da
  sessão, marca `.busy` e converte erros; `download()` apaga a pasta após o envio.
- **Erros para o usuário**: levantar `UserError(mensagem, status)` nos serviços. Mensagens
  do backend em português **sem acentos** (padrão atual); o frontend tem acentos.
- **PDFs**: abrir com `pdf_utils.open_pdf()` (valida formato, senha e páginas). Não
  reintroduzir PyPDF2/pdf2image (dependiam de Poppler, ausente no servidor).
- Toda correção de bug ganha um teste de regressão em `test_app.py`.
- Commits em [Conventional Commits](https://www.conventionalcommits.org), em português:
  o semantic-release gera a versão a partir deles (`fix:` patch, `feat:` minor).

## Deploy no Windows

Executar o roteiro abaixo quando o usuário pedir "faça o deploy" nesta branch.

> **Prompt de deploy (Windows):**
>
> Faça o deploy do PDF Toolbox (branch `master`) no Windows Server seguindo o CLAUDE.md:
>
> 1. **Pré-checagem local**: `git status` limpo e branch `master` igual a `origin/master`
>    (se houver commits locais, perguntar se devem ir junto). Rodar
>    `python -m pytest -q test_app.py`; se falhar, parar e relatar.
> 2. **CI**: conferir com `gh run list --branch master --workflow release.yml --limit 1` que
>    o último *Test, Build and Release* do commit atual passou. Se não passou, parar e relatar.
> 3. **Destino**: perguntar (ou confirmar) host, usuário SSH, pasta do app no servidor
>    (padrão `C:\app\pdf-toolbox`), porta e workers, e se é a **primeira instalação**
>    (precisa de `-InstallDeps`, executado como Administrador).
> 4. **Escolher o método**:
>    - **GitHub Actions** (preferido): exige o secret `WINDOWS_SSH_KEY` no repositório
>      (`gh secret list`). Se não existir, explicar como criar (chave privada do usuário de
>      deploy, com a pública em `authorized_keys` do Windows) e não prosseguir por esse
>      método. Disparar só **depois de confirmar com o usuário**:
>      `gh workflow run deploy.yml -f windows_host=<host> -f windows_user=<usuario>
>      -f app_dir=<pasta> -f port=<porta> -f workers=<n> -f install_deps=<true|false>`
>      e acompanhar com `gh run watch`.
>    - **Manual** (sem SSH configurado): orientar o usuário a copiar o código para a pasta do
>      servidor e rodar, em PowerShell como Administrador, `.\deploy.ps1 -InstallService`
>      (primeira vez: `.\deploy.ps1 -InstallDeps -InstallService`).
> 5. **Verificar**: o `deploy.ps1` só termina com sucesso se `/health` responder. Conferir
>    também `http://<host>:<porta>/health` a partir daqui, se a rede permitir. Em caso de
>    falha, pedir/ler `logs\service.log` no servidor e relatar o trecho relevante.
> 6. **Relatar**: commit implantado, versão do `/health`, método usado e qualquer aviso.
>
> Regras: confirmar antes de qualquer ação no servidor ou no GitHub (disparar workflow,
> alterar secrets); nunca exibir chaves ou senhas; variáveis extras da aplicação ficam em
> `app.env` na pasta do servidor (modelo em `.env.example`), não no repositório.
> **Rollback**: fazer checkout do commit/tag anterior (`git tag --sort=-creatordate`) e
> repetir o deploy com ele.

# PDF Toolbox

Ferramentas web para PDF, em português, rodando no seu próprio servidor: os arquivos
são processados localmente e apagados logo após o download.

| Ferramenta | Página | O que faz |
|---|---|---|
| Mesclar | `/merge` | Junta vários PDFs na ordem escolhida |
| Mesclagem visual | `/detailed-merge` | Miniaturas de todas as páginas; reordenar, excluir e salvar |
| Dividir | `/split` | Um PDF por página (ZIP) |
| Extrair páginas | `/extract` | Intervalos como `1-3,5,8-`, com prévia |
| Comprimir | `/compress` | Leve (sem perda), Normal (recomprime imagens) ou Extremo (rasteriza) |
| Remover páginas em branco | `/remove-blanks` | Detecção por brilho/variação com sensibilidade ajustável e prévia |
| PDF → Imagens | `/pdf-to-images` | PNG ou JPG, 200 dpi |
| Imagens → PDF | `/images-to-pdf` | Respeita a rotação EXIF; transparência vira fundo branco |
| PDF → Word | `/pdf-to-office` | DOCX via `pdf2docx` |
| Office → PDF | `/office-to-pdf` | Word/Excel/PowerPoint/OpenDocument via LibreOffice |

> **Branches**: `master` é a versão para **Windows Server** (serviço via NSSM).
> A branch [`painel`](https://github.com/jjvvsszz/PDF-ToolBox/tree/painel) empacota a mesma
> aplicação em uma imagem Docker multi-arch para **Pterodactyl** (Wings em ARM64).

## Stack

- **Python 3.11+**, FastAPI + Uvicorn, Jinja2 (páginas) e JavaScript puro (sem build).
- **PyMuPDF** para ler, renderizar, mesclar e dividir PDFs; **pikepdf** e **img2pdf** na
  compressão; **Pillow** e **NumPy** para imagens; **pdf2docx** para PDF → Word.
- **LibreOffice** (opcional, externo) para Office → PDF. Sem ele, só essa ferramenta fica
  indisponível (a API responde 503).

Não depende de Poppler nem de outros binários além do LibreOffice.

## Rodando localmente

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python main.py
```

Acesse `http://localhost:8000`. O `main.py` lê `HOST`, `PORT`, `WORKERS` e `LOG_LEVEL` do
ambiente; para desenvolvimento use 1 worker (`set WORKERS=1`) ou rode
`python -m uvicorn app.main:app --reload`.

### Testes

```bash
.venv\Scripts\python -m pytest -q test_app.py
```

A suíte cobre todas as rotas e regressões de segurança (path traversal, CSRF, limite de
upload), concorrência da mesclagem visual, limpeza automática e tamanhos de página da
compressão. O teste de conversão Office real é pulado quando o LibreOffice não está
instalado. `python test_app.py` também funciona (sai com código 1 se algo falhar).

## Configuração

Tudo por variáveis de ambiente (a aplicação não carrega `.env` sozinha). No serviço Windows,
coloque as variáveis em `app.env` na pasta do app (modelo: [.env.example](.env.example));
o `deploy.ps1` as aplica a cada deploy.

| Variável | Padrão | Descrição |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Endereço e porta |
| `WORKERS` | `4` | Processos do Uvicorn |
| `LOG_LEVEL` | `info` | `critical`, `error`, `warning`, `info`, `debug` |
| `MAX_UPLOAD_SIZE_MB` | `500` | Limite por requisição (inclui uploads chunked) |
| `MAX_FILES` | `50` | Arquivos por envio |
| `OFFICE_TIMEOUT_SECONDS` | `180` | Tempo máximo de uma conversão do LibreOffice |
| `CLEANUP_DELAY_MINUTES` | `3` | Sobras de operações simples são apagadas após esse tempo |
| `CLEANUP_INTERVAL_SECONDS` | `60` | Frequência da limpeza |
| `SESSION_IDLE_MINUTES` | `30` | Expiração da mesclagem visual sem uso |
| `BUSY_TIMEOUT_MINUTES` | `60` | Tempo máximo que um processamento protege sua pasta |
| `CORS_ORIGINS` | vazio | Origens extras (separadas por vírgula) que podem chamar a API |

## Como funciona

```
app/
  main.py            # app FastAPI, middlewares, limpeza automática (lifespan)
  middleware.py      # limite de tamanho do corpo e proteção CSRF (ASGI puro)
  config.py          # variáveis de ambiente
  routes/            # uma rota por ferramenta; _common.py tem o ciclo de vida das sessões
  services/          # lógica de PDF (sem FastAPI), erros, armazenamento e limpeza
  static/, templates # frontend
```

- **Sessões em disco**: cada operação cria `uploads/<32 hex>/`. O upload vai para uma
  subpasta própria com nome sanitizado (`storage.save_upload`), então nomes iguais não
  colidem e `../` não escapa da pasta. Operações simples apagam a pasta assim que o download
  termina; previews e a mesclagem visual dependem da limpeza automática.
- **Limpeza** (`services/cleanup.py`): remove só pastas com nome de sessão e expiradas.
  Pastas com `.busy` (processamento em andamento) são preservadas; a mesclagem visual
  (`session.json`) usa `SESSION_IDLE_MINUTES`. É segura com vários workers.
- **Mesclagem visual**: estado em `session.json`, gravado de forma atômica e protegido por
  lock de arquivo, porque requisições da mesma sessão podem cair em workers diferentes.
- **Erros**: os serviços levantam `UserError` com mensagem para o usuário e status HTTP;
  qualquer outra exceção vira 500 genérico e é registrada no log.
- **Rotas síncronas** (`def`): o FastAPI as executa em threads, então uma compressão pesada
  não trava as outras requisições. A compressão extrema usa processos (`spawn`) a partir de
  8 páginas.
- **Segurança**: CSRF compara `Origin`/`Referer` com `Host` (ou `X-Forwarded-Host`); CORS
  desligado por padrão; nomes de arquivo escapados no frontend.

## API

Todas as rotas `POST` recebem `multipart/form-data`. Sucesso devolve o arquivo (PDF, ZIP,
imagem ou DOCX) com `Content-Disposition`; erro devolve `{"error": "mensagem"}`.

| Rota | Campos | Resposta |
|---|---|---|
| `POST /api/merge` | `files` (vários) | PDF |
| `POST /api/split` | `file` | ZIP (ou PDF se tiver 1 página) |
| `POST /api/compress` | `file`, `level` = `light`\|`normal`\|`extreme` | PDF |
| `POST /api/extract` | `file`, `pages` (ex.: `1-3,5,8-`) | PDF |
| `POST /api/extract/preview` | `file`, `pages` | JSON com miniaturas |
| `POST /api/pdf-to-images` | `file`, `format` = `png`\|`jpg` | imagem ou ZIP |
| `POST /api/images-to-pdf` | `files` (vários) | PDF |
| `POST /api/pdf-to-office` | `file` | DOCX |
| `POST /api/office-to-pdf` | `file` (`.doc[x]`, `.xls[x]`, `.ppt[x]`, `.od[tsp]`) | PDF |
| `POST /api/remove-blanks` | `file`, `threshold` (1–99, padrão 95) | PDF |
| `POST /api/remove-blanks/preview` | `file`, `threshold` | JSON com miniaturas |
| `POST /api/detailed-merge/create-session` | — | `{"session_id"}` |
| `POST /api/detailed-merge/add-pdf` | `session_id`, `files` | JSON com páginas e `errors` |
| `POST /api/detailed-merge/reorder` | `session_id`, `index`, `direction` = `up`\|`down` | JSON |
| `POST /api/detailed-merge/delete` | `session_id`, `index` | JSON |
| `POST /api/detailed-merge/clear` | `session_id` | JSON |
| `POST /api/detailed-merge/save` | `session_id` | PDF |
| `GET /api/{extract,remove-blanks,detailed-merge}/thumbnail/{sessao}/{arquivo}` | — | PNG |
| `GET /health` | — | `{"status": "ok", "version"}` |

Códigos de erro: `400` entrada inválida (PDF corrompido/protegido, intervalo, formato),
`403` origem recusada (CSRF), `404` sessão expirada (cabeçalho `X-Session-Expired: 1`) ou
miniatura inexistente, `413` arquivo grande demais, `422` LibreOffice não conseguiu converter,
`503` LibreOffice não instalado, `504` conversão excedeu o tempo, `500` erro interno.

## Deploy no Windows Server

O [`deploy.ps1`](deploy.ps1) prepara tudo e registra o serviço `PDFToolbox` com o
[NSSM](https://nssm.cc). Feito para Windows Server 2012 R2 em diante (PowerShell 5.1).

```powershell
# Primeira instalação (PowerShell como Administrador): Python 3.11, LibreOffice, NSSM + serviço
.\deploy.ps1 -InstallDeps -InstallService

# Atualizações: depois de copiar o código novo para a pasta
.\deploy.ps1 -InstallService

# Parâmetros opcionais (padrões: 0.0.0.0, 8000, 4)
.\deploy.ps1 -InstallService -BindHost 0.0.0.0 -Port 8000 -Workers 4
```

O script para o serviço antes de atualizar as dependências (DLLs carregadas travam o `pip`
no Windows), cria/atualiza o `venv`, reaplica a configuração do serviço (incluindo `app.env`),
grava logs com rotação em `logs\service.log` e termina com um health check em `/health`
(falha com código 1 se o serviço não responder).

### Deploy pelo GitHub Actions

O workflow [`deploy.yml`](.github/workflows/deploy.yml) (manual, *Run workflow*) copia o
repositório por SSH para o servidor e executa o `deploy.ps1 -InstallService`. Requer:

- OpenSSH Server ativo no Windows e o usuário com permissão de administrador;
- secret `WINDOWS_SSH_KEY` (chave privada) e, recomendado, a variável `WINDOWS_KNOWN_HOSTS`.

O prompt de deploy para o Claude Code está no [CLAUDE.md](CLAUDE.md).

## CI e releases

[`release.yml`](.github/workflows/release.yml): a cada push no `master` roda os testes e,
se passarem, o [semantic-release](https://semantic-release.gitbook.io) cria a release a
partir das mensagens de commit ([Conventional Commits](https://www.conventionalcommits.org):
`fix:` → patch, `feat:` → minor).

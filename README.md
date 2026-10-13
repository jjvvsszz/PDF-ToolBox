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

> **Esta é a branch `painel`**: a aplicação empacotada em uma imagem Docker multi-arch
> (`linux/arm64` + `linux/amd64`) para rodar como servidor no **Pterodactyl**, com o Wings em
> ARM64 (OCI Ampere). A versão para Windows Server fica na branch
> [`master`](https://github.com/jjvvsszz/PDF-ToolBox/tree/master).

## Stack

- **Python 3.11+**, FastAPI + Uvicorn, Jinja2 (páginas) e JavaScript puro (sem build).
- **PyMuPDF** para ler, renderizar, mesclar e dividir PDFs; **pikepdf** e **img2pdf** na
  compressão; **Pillow** e **NumPy** para imagens; **pdf2docx** para PDF → Word.
- **LibreOffice** para Office → PDF: incluso na imagem Docker (pacotes `-nogui` do Debian
  bookworm, com fontes compatíveis com Calibri/Cambria/Arial/Times). Fora da imagem é
  opcional; sem ele, só essa ferramenta fica indisponível (a API responde 503).

Não depende de Poppler nem de outros binários além do LibreOffice.

## Rodando localmente (desenvolvimento)

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

Tudo por variáveis de ambiente (a aplicação não carrega `.env` sozinha). No Pterodactyl, as
variáveis do egg aparecem na aba **Startup** do servidor; as marcadas como *imagem* abaixo já
vêm definidas na imagem Docker.

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
| `COMPRESS_MAX_WORKERS` | `4` (egg: `2`) | Processos da compressão extrema (no container o `cpu_count()` vê o host todo) |
| `HTTPS` | egg: `1` | `1` = HTTPS na porta com `ssl/cert.pem`/`ssl/key.pem` (gera autoassinado se faltar) |
| `UPLOADS_DIR` | `./uploads` (imagem: `/home/container/uploads`) | Pasta das sessões |
| `LOG_FILE` | vazio (imagem: `/home/container/logs/app.log`) | Também grava os logs (app + acessos) em arquivo |
| `TMPDIR` | imagem: `/home/container/tmp` | Temporários fora do `/tmp` (tmpfs pequeno do Wings) |

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

## Deploy no Pterodactyl

Resumo (passo a passo completo em [pterodactyl/README.md](pterodactyl/README.md); roteiro
para o Claude Code no [CLAUDE.md](CLAUDE.md)):

1. Push na branch `painel` → o workflow
   [`painel-image.yml`](.github/workflows/painel-image.yml) constrói a imagem em runners
   arm64 e amd64 nativos, roda a suíte **dentro da imagem** (com conversão Office real),
   sobe o container como o Wings faria (UID 988, `STARTUP` do egg, HTTPS) e publica
   `ghcr.io/jjvvsszz/pdf-toolbox:painel` (e `:painel-<commit>`). O pacote é público.
2. Importar/atualizar o egg [`pterodactyl/egg-pdf-toolbox.json`](pterodactyl/egg-pdf-toolbox.json)
   pela interface de admin do painel.
3. Criar o servidor com o egg e uma alocação de porta; para atualizar, basta reiniciar o
   servidor (o Wings baixa a imagem de novo ao iniciar).

Arquivos da imagem:

| Arquivo | Papel |
|---|---|
| [`Dockerfile`](Dockerfile) | Python 3.11 + LibreOffice + app em `/app`; usuário `container`, `tini` |
| [`pterodactyl/entrypoint.sh`](pterodactyl/entrypoint.sh) | Prepara pastas, rotaciona o log, gera o certificado, avalia o `STARTUP` do egg |
| [`pterodactyl/egg-pdf-toolbox.json`](pterodactyl/egg-pdf-toolbox.json) | Egg (PTDL_v2) com as variáveis |

No volume do servidor (`/home/container`) ficam só dados: `uploads/`, `tmp/`, `logs/app.log`
(+ `app.log.1`, rotacionado no boot acima de 10 MB) e `ssl/`.

## CI

- [`painel-image.yml`](.github/workflows/painel-image.yml): testes + imagem (push na `painel`;
  em pull requests só testa).
- O `release.yml` (semantic-release) roda apenas no `master`.

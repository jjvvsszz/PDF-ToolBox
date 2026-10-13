# PDF Toolbox no Pterodactyl

Guia de instalação da branch `painel` em um painel Pterodactyl com o Wings em ARM64
(OCI Ampere A1). Escrito para o painel **2.0** (eggs em *Admin → Eggs*, sem nests); no 1.x o
caminho é *Admin → Nests → Import Egg*.

## Como funciona

- A aplicação, o Python 3.11 e o **LibreOffice** vêm prontos na imagem multi-arch
  `ghcr.io/jjvvsszz/pdf-toolbox:painel` (`linux/arm64` e `linux/amd64`). O pacote é público:
  o Wings baixa sem credenciais.
- A imagem é publicada pelo workflow [`painel-image.yml`](../.github/workflows/painel-image.yml)
  a cada push na `painel`, só depois de passar nos testes dentro da própria imagem e em um
  boot simulado do Wings (UID 988, `STARTUP` do egg, HTTPS, conversão Office → PDF real).
- Não há `git clone` nem `pip install` no servidor. Atualizar = publicar imagem nova e
  **reiniciar** o servidor (o Wings baixa a imagem de novo ao iniciar).
- O volume do servidor (`/home/container`) guarda só dados:

  | Caminho | Conteúdo |
  |---|---|
  | `uploads/` | Arquivos em processamento (apagados após o download / pela limpeza automática) |
  | `tmp/` | Temporários (o `/tmp` do Wings é um tmpfs de ~100 MB); limpo a cada boot |
  | `logs/app.log` | Logs da aplicação e de acesso; vira `app.log.1` no boot quando passa de 10 MB |
  | `ssl/cert.pem`, `ssl/key.pem` | Certificado HTTPS (autoassinado gerado no 1º boot, ou o seu) |

## Instalação

1. **Imagem**: confirme que o último run do workflow *Painel - Imagem Docker (Pterodactyl)*
   na branch `painel` passou.
2. **Egg**: *Admin → Eggs* → importar [`egg-pdf-toolbox.json`](egg-pdf-toolbox.json)
   (para atualizar um egg existente, use a opção de atualizar/importar por cima dele).
3. **Servidor** com esse egg:
   - **Allocation**: porta onde a ferramenta vai responder. A porta precisa estar liberada
     no firewall do node/provedor (na OCI, na Security List da VCN); teste depois.
   - **Memória**: LibreOffice e compressão extrema são os maiores consumidores; comece com
     pelo menos 2 GB e ajuste pelo uso real.
   - **Disco**: alguns uploads simultâneos + arquivos gerados; use no mínimo 3× o
     *Tamanho máximo de upload*. A imagem Docker não conta no disco do servidor.
   - **Variáveis**: `Workers` e `Processos da compressão extrema` ≤ vCPUs do servidor.
4. Inicie. Quando o console mostrar `Application startup complete`:
   `curl -k https://IP-DO-NODE:PORTA/health` → `{"status":"ok",...}`.

### Variáveis do egg

| Variável | Padrão | Descrição |
|---|---|---|
| `HTTPS` | `1` | `1` = HTTPS (certificado de `ssl/`, autoassinado se faltar); `0` = HTTP puro |
| `WORKERS` | `2` | Processos do servidor web (1 por vCPU) |
| `MAX_UPLOAD_SIZE_MB` | `200` | Limite por requisição |
| `MAX_FILES` | `50` | Arquivos por envio |
| `COMPRESS_MAX_WORKERS` | `2` | Processos da compressão extrema |
| `OFFICE_TIMEOUT_SECONDS` | `180` | Tempo máximo de uma conversão Office → PDF |
| `CLEANUP_DELAY_MINUTES` | `3` | Sobras de operações simples são apagadas após esse tempo |
| `SESSION_IDLE_MINUTES` | `30` | Expiração da mesclagem visual sem uso |
| `CORS_ORIGINS` | vazio | Outros sites autorizados a chamar a API |
| `LOG_LEVEL` | `info` | Nível de log |

## Domínio com HTTPS (Cloudflare)

O padrão é Cloudflare com SSL **Full** e o serviço servindo HTTPS na origem (o certificado
autoassinado basta; não use SSL *Flexible*):

1. Registro **A proxied** (`pdf.exemplo.com`) apontando para o IP do node.
2. **Origin Rule** para esse hostname reescrevendo a porta de destino para a porta da alocação.
3. Pronto: `https://pdf.exemplo.com/health`. A proteção CSRF compara a origem do navegador
   com o `Host`, que o Cloudflare repassa sem alterar.

Para usar um certificado próprio (ex.: Cloudflare Origin CA), grave `ssl/cert.pem` e
`ssl/key.pem` pelo gerenciador de arquivos e reinicie.

## Atualizar

Push na `painel` → esperar o workflow → reiniciar o servidor. Cada imagem também recebe a
tag imutável `painel-<commit>`; para fixar uma versão, troque a imagem do servidor em
*Startup → Docker Image*.

## Testar a imagem fora do painel

```bash
docker run --rm -p 8080:8080 -e SERVER_PORT=8080 -e WORKERS=2 -e LOG_LEVEL=info \
  -e STARTUP="python -m uvicorn app.main:app --app-dir /app --host 0.0.0.0 --port {{SERVER_PORT}} --workers {{WORKERS}} --log-level {{LOG_LEVEL}}" \
  ghcr.io/jjvvsszz/pdf-toolbox:painel
# https://localhost:8080 (certificado autoassinado)
```

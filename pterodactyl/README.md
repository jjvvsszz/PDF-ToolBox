# PDF Toolbox no Pterodactyl

Esta branch (`painel`) empacota o PDF Toolbox para rodar como servidor no Pterodactyl,
com o Wings em uma VM ARM (OCI Ampere A1, free tier).

## Como funciona

- A aplicação, o Python 3.11 e o **LibreOffice** vêm prontos em uma imagem Docker
  multi-arch (`linux/arm64` e `linux/amd64`): `ghcr.io/jjvvsszz/pdf-toolbox:painel`.
- A imagem é construída pelo workflow [`painel-image.yml`](../.github/workflows/painel-image.yml)
  a cada push na branch `painel`, em runners nativos (arm64 e amd64). Antes de publicar, o
  workflow roda a suíte de testes **dentro da imagem** (incluindo uma conversão Office → PDF
  real) e sobe o container como o Wings faz, com o comando do egg.
- O volume do servidor (`/home/container`) guarda só dados: `uploads/` (arquivos em
  processamento, limpos automaticamente) e `tmp/` (temporários; o `/tmp` do Wings é um tmpfs
  pequeno e não comportaria uploads grandes).
- Não há `git clone` nem `pip install` no servidor: atualizar = publicar uma imagem nova e
  reiniciar o servidor no painel (o Wings baixa a imagem de novo ao iniciar).

## Instalação

1. **Publicar a imagem**: faça push da branch `painel` e espere o workflow
   *Painel - Imagem Docker (Pterodactyl)* terminar.
2. **Tornar o pacote público** (uma vez): GitHub → seu perfil → *Packages* → `pdf-toolbox` →
   *Package settings* → *Change visibility* → **Public**. Sem isso o Wings não consegue baixar a
   imagem, a menos que você configure credenciais do `ghcr.io` em `docker.registries` no
   `config.yml` do Wings.
3. **Importar o egg**: no painel, *Admin* → *Nests* → escolha (ou crie) um nest →
   *Import Egg* → envie [`egg-pdf-toolbox.json`](egg-pdf-toolbox.json).
4. **Criar o servidor** com esse egg:
   - **Allocation**: a porta onde a ferramenta vai responder (ex.: `8080`).
   - **Memória**: o LibreOffice e a compressão extrema são os maiores consumidores; comece com
     pelo menos 2 GB e ajuste pelo uso real.
   - **Disco**: precisa comportar alguns uploads simultâneos mais os arquivos gerados — use no
     mínimo 3× o *Tamanho máximo de upload*. A imagem Docker não conta no disco do servidor.
   - **Variáveis**: `Workers` e `Processos da compressão extrema` não devem passar das vCPUs
     alocadas ao servidor.
5. **Liberar a porta na OCI**: adicione uma regra de entrada TCP para a porta na *Security List*
   (ou NSG) da VCN da instância. Se o firewall do sistema da VM também bloquear, libere lá.
6. Inicie o servidor. Quando o console mostrar `Application startup complete`, acesse
   `http://IP-DO-NODE:PORTA`.

## Atualizar

Faça push na branch `painel` → espere o workflow → reinicie o servidor no painel.

Cada imagem também recebe uma tag imutável `painel-<commit>`. Para fixar uma versão, troque a
imagem do servidor em *Startup* → *Docker Image* (o egg aceita imagem customizada).

## HTTPS / domínio

O Pterodactyl só expõe a porta. Para usar domínio com HTTPS, coloque um proxy reverso
(nginx, Caddy, Cloudflare Tunnel) na frente. Configure o proxy para repassar o cabeçalho
`Host` original (ou `X-Forwarded-Host`); a proteção CSRF compara a origem do navegador com ele.

## Rodar a imagem fora do painel (teste)

```bash
docker run --rm -p 8080:8080 -e SERVER_PORT=8080 -e WORKERS=2 -e LOG_LEVEL=info \
  -e STARTUP="python -m uvicorn app.main:app --app-dir /app --host 0.0.0.0 --port {{SERVER_PORT}} --workers {{WORKERS}} --log-level {{LOG_LEVEL}}" \
  ghcr.io/jjvvsszz/pdf-toolbox:painel
```

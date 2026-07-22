# Gestão de Arranjo

Aplicativo para o coordenador de discursos públicos organizar o arranjo de
oradores entre congregações do circuito: programação mensal, designações,
presidentes da reunião de fim de semana e geração dos materiais para envio e
impressão.

Feito em Python com [Flet](https://flet.dev), banco SQLite local e exportações
em PNG (WhatsApp) e PDF (impressão). Disponível para Windows, Linux e Android.

## Downloads

Baixe a versão mais recente na página de
**[Releases](../../releases/latest)**:

| Sistema | Arquivo | Como usar |
| --- | --- | --- |
| Windows | `GestaoArranjo-*-windows.zip` | Descompacte e execute `GestaoArranjo.exe` |
| Linux | `GestaoArranjo-*-linux.tar.gz` | Descompacte e execute `GestaoArranjo` |
| Android | `GestaoArranjo-*-android.apk` | Instale o APK (permita apps de fontes desconhecidas) |

O app começa vazio: preencha **Ajustes → Minha congregação** com os dados da
sua congregação e cadastre congregações, oradores e temas — ou importe tudo de
uma planilha (veja abaixo).

> **Observação sobre o Android**: a geração do PDF de envio depende de
> Excel/LibreOffice e está disponível apenas nas versões de computador. As
> demais exportações (PNGs e PDFs internos) funcionam em todas as plataformas.

## Funcionalidades

- **Dashboard** — visão geral: totais de oradores, temas, congregações e
  designações do mês.
- **Oradores** — cadastro dos oradores (nome, telefone, privilégio, temas que
  pode fazer), separados entre "Minha congregação" e "Outras congregações"
  (agrupados por congregação). Gera o PDF da lista de oradores para envio ao
  superintendente de circuito.
- **Temas** — os discursos públicos numerados, com controle de uso por ano e
  observações. Importa os títulos dos formulários oficiais S-99/S-99a em PDF.
- **Congregações** — cadastro das congregações do circuito (responsável,
  telefone, endereço, dia e horário da reunião).
- **Arranjos** — a programação mensal: oradores recebidos e designações
  enviadas de cada mês, com sugestão automática de datas conforme o dia de
  reunião da congregação e exportação de listas em PNG.
- **Designações** — as designações enviadas organizadas por mês/ano, com
  geração de imagem individual da designação (modelo pronto para enviar ao
  orador pelo WhatsApp).
- **Presidentes** — cadastro de quem pode presidir (nome + privilégio) e
  atribuição semana a semana, por ano e mês.
- **Quadro de Anúncios** — prévia fiel e exportação em PDF do quadro de
  conferência pública, publicado de 2 em 2 meses, no layout oficial usado no
  quadro de anúncios da congregação.
- **Minha Congregação** — dados da sua congregação (usados nos cabeçalhos dos
  PDFs), backup e restauração.
- **Importação por planilha** — modelo de planilha para preencher congregações,
  oradores e programação de uma vez e importar tudo de volta.

## Executar a partir do código

Requisitos: Python 3.11 ou mais novo e as dependências de
[requirements.txt](requirements.txt). Para a geração do PDF de envio:
Microsoft Excel (Windows, opcional) ou LibreOffice (Linux/macOS).

### Windows

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
run.bat
```

### Linux / macOS

```bash
python3 -m venv venv-linux
venv-linux/bin/pip install -r requirements.txt
./run.sh
```

No primeiro uso, o banco de dados é criado em `data/` e os temas são
importados de `data/Temas.xlsx`.

### Testar o layout de celular no computador

Para ver a interface **de celular** rodando no PC (sem gerar o APK), dê dois
cliques em [`preview-mobile.bat`](preview-mobile.bat) — ele prepara o ambiente
na primeira vez e abre o app já no layout mobile (basta estreitar a janela). O
mesmo efeito pode ser obtido definindo `GA_FORCAR_MOBILE=1` antes de executar.

## Publicar uma nova versão (gerar os instaladores)

Os instaladores das Releases são gerados automaticamente pelo GitHub Actions
([.github/workflows/release.yml](.github/workflows/release.yml)). **O gatilho é
a publicação de uma tag `vX.Y.Z`** — um `git push` de commits para o `main`,
sozinho, **não** gera instaladores. A versão dos arquivos vem do nome da tag
(`v1.0.7` → `1.0.7`).

Fluxo recomendado, com o script [`release.sh`](release.sh) (rode no Git Bash):

```bash
# 1) Commite normalmente as suas alterações e faça o push do main.
# 2) Publique a versão (cria e envia a tag que dispara a compilação):
./release.sh 1.0.8     # grava a versão no pyproject, commita e envia a tag
# ou, se a versão em mobile/pyproject.toml já for a desejada:
./release.sh           # usa a versão atual do pyproject e só cria/envia a tag
```

O script recusa versões repetidas (tag já existente) e exige a árvore limpa
antes de publicar. Depois é só acompanhar em **Actions → Gerar instaladores**;
ao terminar, os arquivos aparecem na **Release** correspondente:

| Sistema | Arquivo |
| --- | --- |
| Windows | `GestaoArranjo-<versão>-windows.zip` |
| Linux | `GestaoArranjo-<versão>-linux.tar.gz` |
| Android | `GestaoArranjo-<versão>-android.apk` |

Para publicar sem o script, faça o mesmo à mão:

```bash
git tag -a v1.0.8 -m "v1.0.8"
git push origin v1.0.8
```

Para compilar localmente (sem publicar), use o
[`flet build`](https://flet.dev/docs/publish/):

```bash
pip install "flet[all]"
flet build windows   # ou: flet build linux / flet build apk
```

## Backup e restauração

Na aba **Minha Congregação**:

- **Exportar backup** gera um arquivo JSON versionado em `backups/` com todos
  os dados (congregações, oradores, temas, arranjos, designações, presidentes
  e configurações).
- **Restaurar backup** importa um desses arquivos, salvando antes uma cópia de
  segurança do banco atual.

O formato JSON é autodescritivo e independente de plataforma — use-o para
migrar os dados entre computadores.

## Estrutura do projeto

| Arquivo | Papel |
| --- | --- |
| `main.py` | Interface (Flet): telas, dialogs e navegação |
| `database.py` | Esquema SQLite, migrações, consultas e backup |
| `pdf_quadro.py` | PDF do Quadro de Anúncios (ReportLab, layout do modelo oficial) |
| `pdf_envio.py` | PDF da lista de oradores (Excel no Windows, LibreOffice nos demais) |
| `pdf_temas.py` | Leitura dos formulários oficiais de temas (S-99/S-99a) |
| `png_oradores.py` | Imagens PNG: listas mensais, designação individual e prévia do quadro |
| `planilha_dados.py` | Exportação/importação dos dados em planilha Excel |
| `models/` | Templates Excel dos documentos |
| `assets/` | Ícones do aplicativo |

## Privacidade

Este repositório não contém dados de pessoas: o app é distribuído vazio. O
banco de dados (`data/gestao_arranjo.db`), as exportações (`exports/`) e os
backups (`backups/`) são criados localmente em cada instalação e nunca são
enviados a lugar nenhum.

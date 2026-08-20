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
| Windows | `GestaoArranjo-*-windows-instalador.exe` | Execute e siga o instalador (não pede administrador) |
| Linux | `GestaoArranjo-*-linux.tar.gz` | Descompacte e execute `GestaoArranjo` |
| Android | `GestaoArranjo-*-android.apk` | Instale (celulares atuais). Aparelho antigo de 32 bits? Use `GestaoArranjo-*-android-32bits.apk` |

O app começa vazio: preencha **Minha congregação** com os dados da
sua congregação e cadastre congregações, oradores e temas — ou importe tudo de
uma planilha (veja abaixo).

> **Observação sobre o Android**: a geração do PDF de envio depende de
> Excel/LibreOffice e está disponível apenas nas versões de computador. As
> demais exportações (PNGs e PDFs internos) funcionam em todas as plataformas.

## Funcionalidades

- **Início** — a próxima reunião, as semanas seguintes e as pendências dos
  **próximos 3 meses** (o arranjo se monta com pouca antecedência; cobrar o ano
  inteiro só enche a lista de meses que ainda nem começaram).
- **Oradores** — cadastro dos oradores (nome, telefone, privilégio, temas que
  pode fazer), separados entre "Minha congregação" e "Outras congregações"
  (agrupados por congregação). Cada orador com telefone tem o botão de
  **WhatsApp** na lista, para falar com ele na hora. Gera o PDF da lista de
  oradores para envio ao superintendente de circuito.
- **Temas** — os discursos públicos numerados, com controle de uso por ano e
  observações. Importa os títulos dos formulários oficiais S-99/S-99a em PDF.
  Ao adicionar um orador recebido, a **escolha assistida** sugere pares
  orador+tema pelos prioritários (★) e pelos há mais tempo sem fazer —
  escolhendo um orador, ela lista **todos** os temas dele nessa ordem, com a
  observação do tema (⚠ uso restrito, limite de data) e sem repetir quem já
  está naquele mês.
  Ocultar a coluna de um ano esconde só a **coluna**: o histórico de uso
  continua contando na ordenação.
- **Congregações** — cadastro das congregações do circuito (responsável,
  telefone, endereço, dia e horário da reunião). Cada uma com telefone tem
  o botão de **WhatsApp** ao lado do responsável, para falar com ele sem
  abrir o cadastro. A busca também procura pelo **nome do orador**: digitar
  o nome dele traz a congregação de onde ele vem, com o cartão já aberto
  naquela pessoa.
- **Contatos do celular** — no cadastro de oradores e de presidentes, o botão
  **Buscar nos contatos** preenche o telefone a partir da agenda do aparelho.
  No **Android** abre o seletor do próprio sistema; no **computador**, e se o
  seletor não estiver disponível, o app lê o arquivo que o celular exporta
  (Contatos → Configurações → **Exportar**, formato `.vcf`).
  Ao escolher, a pessoa fica **vinculada** àquele contato: o app guarda a
  chave dele e, a cada abertura, relê a agenda — trocou de número no celular,
  o número muda aqui sozinho. A **foto do contato** vira o avatar na lista (é
  a mesma imagem que o WhatsApp costuma sincronizar nos contatos; o WhatsApp
  em si não expõe fotos de perfil para outros aplicativos).
  Nenhuma agenda é gravada: ficam salvos só o número e a chave do contato — e
  esses vão no backup. As fotos ficam em cache fora do backup e voltam
  sozinhas do aparelho.
- **Telefones** — todos os campos se formatam enquanto você digita
  (`(11) 90000-0000`), em celular e fixo. O `+55` que vem dos contatos é
  descartado: o link do WhatsApp recoloca o país sozinho.
- **Arranjos** — a programação mensal: oradores recebidos e designações
  enviadas de cada mês, com sugestão automática de datas conforme o dia de
  reunião da congregação e exportação de listas em PNG. Cada **orador
  recebido** tem também o botão de WhatsApp, que gera a **designação avulsa**
  dele (data, tema, sua congregação, reunião, endereço e contato) — é o que
  usar quando o arranjo foi combinado direto com o orador, e não pela
  congregação anfitriã do mês.
- **Designações** — as designações enviadas organizadas por mês/ano, com
  geração de imagem individual da designação (modelo pronto para enviar ao
  orador pelo WhatsApp). No rodapé do mês, **Falar com o responsável** abre o
  WhatsApp do irmão responsável pela congregação anfitriã daquele mês, com uma
  mensagem já começada (o telefone vem do cadastro em Congregações).
- **Minha congregação** — tela com o que é seu: os **dados** da congregação
  (usados nos cabeçalhos dos PDFs) e os **presidentes**, com o cadastro de
  quem pode presidir e a ordem do rodízio. A atribuição semana a semana
  continua na Programação, por ano e mês. Semanas tomadas por
  uma **data especial** (assembleia, congresso, visita) não pedem presidente:
  a linha mostra o evento no lugar do seletor, e o rodízio automático já as
  pula. Quando a data especial **tem** presidente (discurso especial, por
  exemplo), isso conta no rodízio — inclusive para as semanas **antes** dela.
  O rodízio também evita dois anciãos ou dois servos ministeriais seguidos,
  cedendo quando ninguém do outro privilégio está de folga.
- **Rodízio das datas especiais** — na aba **Especiais**, o botão *Preencher
  em rodízio* escolhe quem preside o discurso especial, a visita do
  superintendente e afins. É uma fila à parte da semanal e **só entre
  anciãos**: a vez anda pelas datas especiais, então quem presidiu sábado
  passado continua na frente se nunca fez uma. Cada tipo de evento tem uma
  marca **Presidente** (na engrenagem ao lado do campo Tipo) dizendo se ali há
  reunião no salão — assembleia e congresso vêm desmarcados, e o rodízio não
  gasta a vez de ninguém com eles.
- **Mensagem da presidência** — na **tela inicial**, tanto no card da próxima
  reunião quanto nas semanas seguintes, o botão de WhatsApp monta a mensagem
  para o presidente daquele dia: você digita só o número do cântico e o app
  completa com o título e o texto bíblico (catálogo do *Cante de Coração para
  Jeová*, em [`src/canticos.py`](src/canticos.py)), mais o orador, a
  congregação dele e o tema já programados.
- **Quadro de Anúncios** — prévia fiel e exportação em PDF do quadro de
  conferência pública, publicado de 2 em 2 meses, no layout oficial usado no
  quadro de anúncios da congregação. O arquivo já sai nomeado como
  `DISCURSOS PÚBLICOS - SETEMBRO-OUTUBRO.pdf`, pronto para ir para a pasta do
  ano sem renomear (o ano fica no título do documento).
- **Relatórios** — tela com o retrato do arranjo, o que só aparece somando o
  ano inteiro: números do ano (semanas com e sem orador, com presidente,
  recebidos, enviados, aguardando confirmação), o **mês a mês** da cobertura
  (onde estão os buracos), a frequência dos oradores da sua congregação e
  **quantas vezes cada um presidiu**. Dá para trocar o ano e exportar em PDF.
- **Ajustes** — só manutenção: backup local e na nuvem, carga inicial por
  planilha e tamanho do texto.
- **Importação por planilha** — modelo de planilha para preencher congregações,
  oradores e programação de uma vez e importar tudo de volta.

## Executar a partir do código

Requisitos: Python 3.11 ou mais novo e as dependências de
[requirements.txt](requirements.txt). Para a geração do PDF de envio:
Microsoft Excel (Windows, opcional) ou LibreOffice (Linux/macOS).

O código do app é único e fica em [`src/`](src/) — os builds de Windows, Linux e
Android compilam todos dessa mesma pasta.

### Windows

```bat
python -m venv venv
venv\Scripts\pip install -r src\requirements.txt
run.bat
```

### Linux / macOS

```bash
python3 -m venv venv-linux
venv-linux/bin/pip install -r src/requirements.txt
./run.sh
```

No primeiro uso, o banco de dados é criado em `data/` e os temas são
importados de `data/Temas.xlsx`.

### Testes e lint

A lógica pura (datas, rodízio de presidentes, backup) tem testes em
[`tests/`](tests/). Rodam sem Flet — bastam `pytest` e `ruff`:

```bash
pip install pytest ruff
ruff check src tests
pytest -q
```

O GitHub Actions roda lint + testes em cada push/PR
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

### Testar o layout de celular no computador

Para ver a interface **de celular** rodando no PC (sem gerar o APK), dê dois
cliques em [`preview-mobile.bat`](preview-mobile.bat) — ele prepara o ambiente
na primeira vez e abre o app já no layout mobile (basta estreitar a janela). O
mesmo efeito pode ser obtido definindo `GA_FORCAR_MOBILE=1` antes de executar.

### Compilar o APK na sua máquina (opcional)

O APK das Releases sai do GitHub Actions, mas dá para compilar localmente para
testar antes. No **Windows** o build só passa com três condições:

1. **Modo de desenvolvedor ligado** (`start ms-settings:developers`) — o
   Flutter precisa de symlinks para montar os plugins.
2. **Caminho sem acento** — o Gradle recusa `Gestão de Arranjo`. Copie o
   projeto para algo como `C:\Users\voce\gab`. (No CI isso não aparece porque o
   GitHub troca o `ã` por hífen no checkout.)
3. **Caminho curto** — os arquivos intermediários estouram o limite de caminho
   do Windows se a pasta estiver funda demais.

Antes de compilar, tire as dependências que só existem no desktop (o job do
Android faz o mesmo):

```bash
sed -i '/python-calamine ; /d;/pywin32>=306 ; /d' pyproject.toml
flet build apk --yes --arch arm64-v8a
```

> O APK gerado assim é assinado com a **sua** chave de depuração, diferente da
> que o CI usa — ele não instala por cima do app vindo da Release. Serve para
> testar num aparelho limpo, não para substituir a instalação do dia a dia.

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
# ou, se a versão em pyproject.toml já for a desejada:
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

### Backup na nuvem (Google Drive)

O app pode enviar o backup automático para a sua conta do Google e restaurá-lo
em outro aparelho (PC ou celular) — assim os dados acompanham você.

**Privacidade:** o app usa o escopo `drive.appdata`, ou seja, enxerga apenas a
**pasta oculta dele mesmo** no seu Drive; nunca os seus outros arquivos. O
login é feito na página oficial do Google — o app não vê a sua senha, só
recebe um token guardado na área privada do próprio aplicativo (o arquivo
`nuvem_google.json`, que nunca vai para o repositório).

**Para quem usa o app:** vá em **Ajustes → Backup na nuvem → Entrar com o
Google**. O navegador abre, você escolhe a sua conta e o app conecta sozinho —
o mesmo fluxo no computador e no celular. Cada pessoa entra na **própria**
conta: os backups de uma nunca aparecem para a outra.

Feito isso, o backup diário passa a subir sozinho. Em outro aparelho, entre com
a mesma conta e use **Restaurar da nuvem** para trazer o backup mais recente.

> **No celular apareceu "não é possível acessar esse site" (127.0.0.1)?**
> É o Android congelando o aplicativo enquanto o navegador está na frente: o
> endereço que devolve o código deixa de responder. **O login não se perdeu** —
> o código continua no endereço. Toque na barra de endereço do navegador, copie
> o endereço inteiro, volte ao aplicativo e cole em **Concluir colando o
> endereço** (aparece no diálogo do login e também em Ajustes → Backup na
> nuvem, por até 30 minutos).

<details>
<summary><b>Para quem publica o app</b> (criar as credenciais do Google, uma vez)</summary>

Os instaladores das Releases levam as credenciais embutidas, injetadas pelo
GitHub Actions a partir dos *secrets* — elas não ficam no código publicado.
Para gerar as suas:

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um
   projeto (ex.: "Gestão de Arranjo").
2. Em **APIs e serviços → Biblioteca**, ative a **Google Drive API**.
3. Em **APIs e serviços → Tela de permissão OAuth**, configure: tipo
   **Externo**, nome e e-mail de contato. Depois **publique** a tela (botão
   *Publicar aplicativo*). Como o escopo usado (`drive.appdata`) é
   **não sensível**, não é preciso passar pela verificação do Google — e,
   publicada, a conexão não expira a cada 7 dias (limite do modo "Teste").
4. Em **Credenciais → Criar credenciais → ID do cliente OAuth**, crie **uma**
   do tipo **App para computador**. Ela serve para o PC e para o Android: nos
   dois o login abre o navegador e volta sozinho para o app (`127.0.0.1`).
5. Em **Settings → Secrets and variables → Actions** do repositório no GitHub,
   cadastre os dois valores: `GOOGLE_CLIENT_ID_DESKTOP` e
   `GOOGLE_CLIENT_SECRET_DESKTOP`.

A próxima Release já sai com o login pronto. Sem os secrets, nada quebra: o app
apenas pede as credenciais em **Usar minhas credenciais (avançado)** — que é
também o caminho de quem compila do código-fonte.

</details>

> **Como funciona no dia a dia:** trata-se de backup e restauração, não de
> sincronização em tempo real. Use um aparelho por vez como o "principal": ao
> trocar de aparelho, restaure antes de continuar o trabalho. Restaurar sempre
> pede confirmação e salva uma cópia de segurança dos dados atuais antes.

## Estrutura do projeto

Todo o código do app vive em [`src/`](src/) — **fonte única** para os três
sistemas. A única parte fora dali é
[`extensoes/flet_contatos`](extensoes/flet_contatos/), a extensão do seletor
nativo de contatos: ela carrega código Flutter, só existe para Android e é
removida do `pyproject.toml` nos builds de Windows e Linux (ver
[`.github/scripts/sem_extensao_contatos.py`](.github/scripts/sem_extensao_contatos.py)).
As diferenças de plataforma são resolvidas em tempo de execução por
`src/armazenamento.py` (`eh_mobile()`), sem cópias paralelas.

| Arquivo | Papel |
| --- | --- |
| `src/main.py` | Interface (Flet): telas, dialogs e navegação; layout responsivo (PC/celular) |
| `src/database.py` | Esquema SQLite, migrações, consultas e backup |
| `src/armazenamento.py` | Resolução de caminhos de dados (desktop vs. área privada do celular) |
| `src/nuvem_drive.py` | Backup na nuvem: OAuth (loopback + PKCE) e arquivos na pasta do app no Drive |
| `src/pdf_quadro.py` | PDF do Quadro de Anúncios (ReportLab, layout do modelo oficial) |
| `src/pdf_envio.py` | PDF da lista de oradores (Excel no Windows, LibreOffice nos demais) |
| `src/pdf_temas.py` | Leitura dos formulários oficiais de temas (S-99/S-99a) |
| `src/pdf_relatorios.py` | Exportação em PDF da tela de Relatórios |
| `src/contatos.py` | Leitura da agenda do celular exportada em vCard (.vcf) |
| `extensoes/flet_contatos/` | Extensão Flet (Python + Flutter) com o seletor nativo de contatos do Android |
| `src/canticos.py` | Catálogo dos 163 cânticos (número, título e texto bíblico) |
| `src/png_oradores.py` | Imagens PNG: listas mensais, designação individual e prévia do quadro |
| `src/planilha_dados.py` | Exportação/importação dos dados em planilha Excel |
| `src/assets/` | Ícones, fontes e a carga inicial de temas (`temas_seed.json`) |
| `pyproject.toml` | Configuração do `flet build` (Windows, Linux e Android) |
| `assets/` | Ícone do instalador Windows (`icon_windows.ico`) |

## Privacidade

Este repositório não contém dados de pessoas: o app é distribuído vazio. O
banco de dados (`data/gestao_arranjo.db`), as exportações (`exports/`) e os
backups (`backups/`) são criados localmente em cada instalação e nunca são
enviados a lugar nenhum — **exceto** se você ativar o backup na nuvem, que
envia os backups para a **sua própria** conta do Google, sob seu controle.
As credenciais e tokens dessa conexão ficam apenas no seu aparelho
(`nuvem_google.json`, fora do repositório).

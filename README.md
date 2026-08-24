# Gestão de Arranjo

Aplicativo para o coordenador de discursos públicos organizar o arranjo de
oradores entre congregações do circuito: programação mensal, designações,
presidentes da reunião de fim de semana e geração dos materiais para envio e
impressão.

Feito em Python com [Flet](https://flet.dev), banco SQLite local e exportações
em PNG (WhatsApp) e PDF (impressão). Funciona em Windows, Linux e Android.

## Downloads

Baixe a versão mais recente na página de
**[Releases](../../releases/latest)**:

| Sistema | Arquivo | Como usar |
| --- | --- | --- |
| Windows | `GestaoArranjo-*-windows-instalador.exe` | Execute e siga o instalador (não pede administrador) |
| Linux | `GestaoArranjo-*-linux.tar.gz` | Descompacte e execute `GestaoArranjo` |
| Android | `GestaoArranjo-*-android.apk` | Instale (celulares atuais). Aparelho antigo de 32 bits? Use `GestaoArranjo-*-android-32bits.apk` |

O app começa **vazio**. Preencha *Minha congregação* com os seus dados e
cadastre congregações, oradores e temas — ou importe tudo de uma planilha, em
*Ajustes → Importar planilha*. Os títulos dos discursos vêm dos formulários
oficiais S-99/S-99a, em *Temas → Importar*.

> No Android, o PDF da lista de envio depende de Excel/LibreOffice e sai
> apenas nas versões de computador. As demais exportações funcionam em todas
> as plataformas.

## O que ele faz

- **Início** — a próxima reunião, as semanas seguintes e as pendências dos
  próximos três meses.
- **Programação** — o mês a mês do arranjo: oradores recebidos, designações
  enviadas, presidentes e datas especiais, com sugestão de datas conforme o
  dia de reunião e exportação das listas em PNG para o WhatsApp.
- **Congregações** — as congregações do circuito e os oradores de cada uma,
  com botão de WhatsApp para falar com o responsável. A busca acha também pelo
  nome do orador.
- **Minha congregação** — os seus dados, os seus oradores e o cadastro de
  presidentes, com a ordem do rodízio.
- **Temas** — os discursos numerados, com o controle de quem fez o quê e
  quando. Ao escolher um orador recebido, o app sugere pares orador+tema pelos
  que estão há mais tempo sem fazer.
- **Quadro de Anúncios** — prévia e PDF do quadro da conferência pública, no
  layout oficial, publicado de dois em dois meses.
- **Calendário e Relatórios** — a visão do ano e o retrato do arranjo: onde
  faltam oradores, quem está discursando e presidindo de menos.
- **Backup** — arquivo local ou, se você quiser, na sua própria conta do
  Google Drive, para levar os dados de um aparelho para outro.

## Rodízios

O app monta as escalas sozinho, e a ideia é sempre a mesma: **vai quem está há
mais tempo sem fazer**.

- **Presidentes da semana** — rodízio pela ordem do cadastro, evitando dois
  anciãos ou dois servos ministeriais seguidos.
- **Datas especiais** — uma fila **por tipo de evento** (Celebração, visita do
  superintendente, discurso especial), entre quem você marcar como presidente
  de datas especiais. Presidir uma não faz ninguém perder a vez na outra.
- **Oradores para enviar** — a lista já vem na ordem de quem está há mais
  tempo sem discursar fora.

## Privacidade

Este repositório não contém dados de pessoas nem de congregações. O banco, as
exportações e os backups são criados na sua instalação e não saem dela —
exceto se você ativar o backup na nuvem, que envia para a **sua própria** conta
do Google, com o escopo `drive.appdata`: o app enxerga somente a pasta oculta
dele mesmo no seu Drive, nunca os seus outros arquivos. O token fica no seu
aparelho.

## Backup na nuvem: credenciais do Google

O backup na nuvem usa a **sua própria** conta do Google. Para o app falar com
o Drive, ele precisa de um par *Client ID* + *Client Secret* — que sai de um
projeto gratuito no Google Cloud, criado uma vez só.

Se o app avisar **"Faltam as credenciais"**, é porque a versão instalada foi
compilada sem elas. O backup em arquivo local continua funcionando normalmente.

### 1. Criar as credenciais no Google

1. Abra o [Google Cloud Console](https://console.cloud.google.com) e crie um
   projeto (qualquer nome).
2. Em **APIs e serviços → Biblioteca**, procure *Google Drive API* e clique em
   **Ativar**.
3. Em **Tela de permissão OAuth**, escolha o tipo **Externo**, preencha o nome
   do app e o e-mail de contato, e adicione o escopo
   `https://www.googleapis.com/auth/drive.appdata` — só esse.
4. Ainda ali, adicione a sua conta do Google em **Usuários de teste**.
5. Em **Credenciais → Criar credenciais → ID do cliente OAuth**, escolha o tipo
   **App para computador**. Serve para PC e celular: os dois fazem o mesmo
   fluxo (navegador e retorno em `127.0.0.1`).
6. Copie o **Client ID** e o **Client Secret**.

> Enquanto a tela de permissão ficar em modo *Teste*, o Google expira a
> autorização a cada 7 dias e o app pede para conectar de novo. Publicar o app
> na mesma tela (botão **Publicar**) resolve; como o escopo `drive.appdata` é
> restrito ao próprio app, não é preciso passar por verificação para uso
> pessoal.

### 2. Usar as credenciais

**No app instalado** — em *Ajustes → Backup na nuvem → Usar minhas credenciais
(avançado)*, cole o Client ID e o Client Secret e toque em **Salvar
credenciais**. Depois é só conectar.

**Nas versões geradas pelo GitHub Actions** — cadastre os dois valores como
*secrets* do repositório; a compilação os embute nos instaladores, e quem
instala não precisa criar nada:

```bash
gh secret set GOOGLE_CLIENT_ID_DESKTOP
gh secret set GOOGLE_CLIENT_SECRET_DESKTOP
```

Valem para a próxima *release* (`git tag v… && git push --tags`). As
credenciais nunca entram no código publicado: `src/credenciais_app.py` fica
vazio no repositório e só é preenchido durante a compilação.

## Rodar a partir do código

Precisa de Python 3.12 ou 3.13.

```bash
python -m venv venv
venv/Scripts/pip install -r src/requirements.txt
run.bat
```

No Linux e no macOS, troque `venv/Scripts` por `venv/bin` e use `./run.sh`.

Para os testes e o lint:

```bash
pip install pytest ruff
ruff check src tests
pytest -q
```

## Licença

Uso livre pelas congregações. O aplicativo não é publicação oficial e não
substitui as instruções que vêm da organização.

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
| Android | `GestaoArranjo-*-android.apk` | Instale no aparelho. Os antigos, de 32 bits, usam `GestaoArranjo-*-android-32bits.apk` |

Comece preenchendo *Minha congregação* com os seus dados e cadastre
congregações, oradores e temas. Também dá para importar tudo de uma planilha,
em *Ajustes → Importar planilha*. Os títulos dos discursos vêm dos formulários
oficiais S-99/S-99a, em *Temas → Importar*.

Em *Ajustes → Atualizações* o aplicativo procura a versão publicada mais
recente e baixa o arquivo certo para o aparelho.

> No Android, o PDF da lista de envio depende de Excel/LibreOffice e sai
> apenas nas versões de computador. As demais exportações funcionam em todas
> as plataformas.

## O que ele faz

- **Início.** A próxima reunião, as semanas seguintes e as pendências dos
  próximos três meses.
- **Programação.** O mês a mês do arranjo: oradores recebidos, designações
  enviadas, presidentes e datas especiais, com sugestão de datas conforme o
  dia de reunião e exportação das listas em PNG para o WhatsApp.
- **Congregações.** As congregações do circuito e os oradores de cada uma, com
  botão de WhatsApp para falar com o responsável. A busca acha também pelo
  nome do orador.
- **Minha congregação.** Os seus dados, os seus oradores e o cadastro de
  presidentes, com a ordem do rodízio.
- **Temas.** Os discursos numerados, com o controle de quem fez o quê e
  quando. Ao escolher um orador recebido, o aplicativo sugere pares de orador
  e tema pelos que estão há mais tempo sem fazer.
- **Quadro de Anúncios.** Prévia e PDF do quadro da conferência pública, no
  layout oficial, publicado de dois em dois meses.
- **Calendário e Relatórios.** A visão do ano e o retrato do arranjo: onde
  faltam oradores, quem está discursando e presidindo de menos.
- **Backup.** Arquivo local ou, se você preferir, na sua própria conta do
  Google Drive, para levar os dados de um aparelho para outro.

## Rodízios

As escalas seguem sempre o mesmo critério: vai quem está há mais tempo sem
fazer.

- **Presidentes da semana.** Rodízio pela ordem do cadastro, evitando dois
  anciãos ou dois servos ministeriais seguidos.
- **Datas especiais.** Uma fila por tipo de evento (Celebração, visita do
  superintendente, discurso especial), entre quem você marcar como presidente
  de datas especiais. Presidir uma não faz ninguém perder a vez na outra.
- **Oradores para enviar.** A lista já vem na ordem de quem está há mais tempo
  sem discursar fora.

## Privacidade

Este repositório não contém dados de pessoas nem de congregações. O banco, as
exportações e os backups são criados na sua instalação e não saem dela. A
exceção é o backup na nuvem, que você ativa se quiser: ele envia para a sua
própria conta do Google, com o escopo `drive.appdata`. Nesse escopo o
aplicativo enxerga somente a pasta oculta dele mesmo no seu Drive, nunca os
seus outros arquivos. O token fica no seu aparelho.

## Backup na nuvem: credenciais do Google

O backup na nuvem usa a sua própria conta do Google. Para o aplicativo falar
com o Drive, ele precisa de um par *Client ID* e *Client Secret*, que sai de um
projeto gratuito no Google Cloud, criado uma vez só.

O aviso **"Faltam as credenciais"** significa que a versão instalada foi
compilada sem elas. O backup em arquivo local continua funcionando.

### 1. Criar as credenciais no Google

1. Abra o [Google Cloud Console](https://console.cloud.google.com) e crie um
   projeto (qualquer nome).
2. Em **APIs e serviços → Biblioteca**, procure *Google Drive API* e clique em
   **Ativar**.
3. Em **Tela de permissão OAuth**, escolha o tipo **Externo**, preencha o nome
   do aplicativo e o e-mail de contato, e adicione somente o escopo
   `https://www.googleapis.com/auth/drive.appdata`.
4. Ainda ali, adicione a sua conta do Google em **Usuários de teste**.
5. Em **Credenciais → Criar credenciais → ID do cliente OAuth**, escolha o tipo
   **App para computador**. Ele serve para os dois lados: computador e celular
   fazem o mesmo fluxo, com navegador e retorno em `127.0.0.1`.
6. Copie o **Client ID** e o **Client Secret**.

> Enquanto a tela de permissão ficar em modo *Teste*, o Google expira a
> autorização a cada 7 dias e o aplicativo pede para conectar de novo. Publicar
> a tela (botão **Publicar**) resolve. Como o escopo `drive.appdata` fica
> restrito à pasta do próprio aplicativo, o uso pessoal não passa por
> verificação.

### 2. Usar as credenciais

**No aplicativo instalado.** Em *Ajustes → Backup na nuvem → Usar minhas
credenciais (avançado)*, cole o Client ID e o Client Secret e toque em **Salvar
credenciais**. Depois é só conectar.

**Nas versões geradas pelo GitHub Actions.** Cadastre os dois valores como
*secrets* do repositório. A compilação os embute nos instaladores, e quem
instala não precisa criar nada:

```bash
gh secret set GOOGLE_CLIENT_ID_DESKTOP
gh secret set GOOGLE_CLIENT_SECRET_DESKTOP
```

Valem a partir da próxima *release* (`git tag v… && git push --tags`). As
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

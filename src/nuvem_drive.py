"""Backup na nuvem via Google Drive (pasta privada do aplicativo).

Usa o fluxo **loopback + PKCE** do OAuth 2.0, igual no PC e no celular: o app
sobe um servidor em ``127.0.0.1``, abre a página oficial do Google no navegador
do aparelho e recebe o código de volta ali mesmo. O app nunca vê a senha —
recebe apenas os tokens, guardados na área privada do próprio app.

O fluxo de dispositivo (código digitado numa TV) foi abandonado: o Google
recusa o escopo ``drive.appdata`` nele ("Invalid device flow scope"), e sem
esse escopo o celular não enxergaria os backups enviados pelo PC.

Escopo: ``drive.appdata`` — o app só enxerga a **pasta oculta dele mesmo**
(appDataFolder), nunca o resto do Drive do usuário. Como as duas plataformas
usam a mesma credencial e o mesmo escopo, elas compartilham os backups.

O transporte HTTP é injetável (``http=``) para permitir testar todo o
protocolo sem rede nem credenciais (ver ``tests/test_nuvem_drive.py``).
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

import credenciais_app
from armazenamento import BASE_DIR

URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
URL_ARQUIVOS = "https://www.googleapis.com/drive/v3/files"

# Só a pasta privada do app — não dá acesso a nenhum outro arquivo do Drive.
ESCOPO = "https://www.googleapis.com/auth/drive.appdata"

ARQUIVO_CREDENCIAIS = BASE_DIR / "nuvem_google.json"

# Resposta HTTP: (status, corpo em bytes)
Resposta = tuple[int, bytes]
Http = Callable[..., Resposta]


class ErroNuvem(Exception):
    """Falha ao falar com o Google Drive (mensagem já pronta para o usuário)."""


# ---------------------------------------------------------------------------
# Transporte
# ---------------------------------------------------------------------------


def _http_padrao(
    metodo: str,
    url: str,
    corpo: bytes | None = None,
    cabecalhos: dict[str, str] | None = None,
    timeout: int = 30,
) -> Resposta:
    requisicao = urllib.request.Request(
        url, data=corpo, headers=cabecalhos or {}, method=metodo
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:  # noqa: S310
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:  # respostas 4xx/5xx trazem detalhes úteis
        return erro.code, erro.read()


def _json_ou_erro(resposta: Resposta, contexto: str) -> dict:
    status, corpo = resposta
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        dados = {}
    if status >= 400:
        detalhe = (
            dados.get("error_description")
            or (dados.get("error") if isinstance(dados.get("error"), str) else None)
            or (dados.get("error") or {}).get("message")
            or f"HTTP {status}"
        )
        raise ErroNuvem(f"{contexto}: {detalhe}")
    return dados


# ---------------------------------------------------------------------------
# Quais credenciais usar
# ---------------------------------------------------------------------------


def credenciais_do_app(mobile: bool) -> tuple[str, str]:
    """Client ID/Secret embutidos (vazios se a compilação não os tiver).

    Todas as plataformas usam o cliente "App para computador": o celular faz o
    mesmo fluxo do PC (navegador + retorno em 127.0.0.1). O fluxo de dispositivo
    (código na TV) foi abandonado porque o Google recusa o escopo
    ``drive.appdata`` nele — e sem esse escopo o celular não enxergaria os
    backups enviados pelo PC.
    """
    _ = mobile  # mesma credencial nas duas plataformas
    return credenciais_app.CLIENT_ID_DESKTOP, credenciais_app.CLIENT_SECRET_DESKTOP


def credenciais_efetivas(mobile: bool, salvas: dict | None = None) -> tuple[str, str]:
    """As credenciais que devem ser usadas agora.

    As do usuário (informadas em Ajustes) têm prioridade; senão, as embutidas
    na compilação. Assim o app funciona "de fábrica", mas quem compila do
    código-fonte pode usar as suas.
    """
    salvas = carregar_credenciais() if salvas is None else salvas
    if salvas.get("client_id") and salvas.get("client_secret"):
        return salvas["client_id"], salvas["client_secret"]
    return credenciais_do_app(mobile)


def ha_credenciais(mobile: bool, salvas: dict | None = None) -> bool:
    client_id, client_secret = credenciais_efetivas(mobile, salvas)
    return bool(client_id and client_secret)


# ---------------------------------------------------------------------------
# Autorização no PC: o navegador volta sozinho para o app (loopback + PKCE)
# ---------------------------------------------------------------------------


def _gerar_pkce() -> tuple[str, str]:
    """Par (verificador, desafio) do PKCE, que protege a troca do código."""
    verificador = secrets.token_urlsafe(64)[:128]
    resumo = hashlib.sha256(verificador.encode("ascii")).digest()
    desafio = base64.urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")
    return verificador, desafio


def montar_url_autorizacao(
    client_id: str, redirect_uri: str, desafio: str, escopo: str = ESCOPO
) -> str:
    """Endereço da tela de login/consentimento do Google."""
    parametros = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": escopo,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        # offline + consent garantem o refresh_token (conexão duradoura).
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{URL_AUTORIZACAO}?{urllib.parse.urlencode(parametros)}"


_PAGINA_OK = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Gestão de Arranjo</title>
<body style="font-family:system-ui;background:#0E1524;color:#E7ECF5;
text-align:center;padding-top:80px">
<h2 style="color:#2DD4BF">Tudo certo!</h2>
<p>O Gestão de Arranjo está conectado ao seu Google Drive.</p>
<p style="color:#7C89A6">Você já pode fechar esta aba e voltar ao aplicativo.</p>
</body></html>"""

_PAGINA_ERRO = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Gestão de Arranjo</title>
<body style="font-family:system-ui;background:#0E1524;color:#E7ECF5;
text-align:center;padding-top:80px">
<h2 style="color:#F87171">Não foi possível conectar</h2>
<p style="color:#7C89A6">Volte ao aplicativo e tente novamente.</p>
</body></html>"""


def extrair_codigo(texto: str) -> str:
    """Extrai o código de autorização de uma URL de retorno colada pelo usuário.

    Aceita a URL inteira (``http://127.0.0.1:1234/?code=ABC&scope=...``) ou só
    o código. Usado no celular, onde o Android pode encerrar o aplicativo
    enquanto o navegador está aberto — aí o retorno automático não acontece e o
    usuário conclui o login colando o endereço da barra.
    """
    texto = (texto or "").strip()
    if not texto:
        raise ErroNuvem("Cole o endereço que apareceu no navegador.")
    if "code=" in texto:
        consulta = urllib.parse.urlparse(texto).query or texto.split("?", 1)[-1]
        campos = urllib.parse.parse_qs(consulta)
        if campos.get("error"):
            raise ErroNuvem(f"Autorização não concluída ({campos['error'][0]}).")
        codigo = (campos.get("code") or [""])[0]
        if not codigo:
            raise ErroNuvem("Não encontrei o código nesse endereço.")
        return codigo
    # Um código do Google costuma ter barra ("4/0AbC..."), então barra sozinha
    # não desqualifica: só recusamos o que é claramente um endereço sem code.
    if texto.lower().startswith("http") or "?" in texto:
        raise ErroNuvem("Não encontrei o código nesse endereço.")
    return texto


def salvar_login_pendente(dados: dict) -> None:
    """Guarda o PKCE e a credencial do login em andamento.

    No celular o app pode ser encerrado enquanto o navegador está aberto; sem
    isso, ao voltar não haveria como concluir a troca do código por tokens.
    """
    atual = carregar_credenciais()
    atual["login_pendente"] = dados
    salvar_credenciais(atual)


def carregar_login_pendente() -> dict:
    return carregar_credenciais().get("login_pendente") or {}


def limpar_login_pendente() -> None:
    atual = carregar_credenciais()
    atual.pop("login_pendente", None)
    salvar_credenciais(atual)


class ServidorRetorno:
    """Servidor local que recebe o retorno do Google após o login.

    Sobe em 127.0.0.1 numa porta livre; o Google redireciona o navegador para
    cá com o código de autorização. Use como gerenciador de contexto.
    """

    def __init__(self) -> None:
        self._resultado: dict[str, str] = {}
        pronto = threading.Event()
        resultado = self._resultado

        class Manipulador(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 — nome exigido pelo BaseHTTPRequestHandler
                consulta = urllib.parse.urlparse(self.path).query
                campos = urllib.parse.parse_qs(consulta)
                if "code" in campos:
                    resultado["code"] = campos["code"][0]
                    corpo = _PAGINA_OK
                else:
                    resultado["erro"] = (campos.get("error") or ["desconhecido"])[0]
                    corpo = _PAGINA_ERRO
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(corpo.encode("utf-8"))
                pronto.set()

            def log_message(self, *_):  # silencia o log no console
                return

        self._pronto = pronto
        self._servidor = HTTPServer(("127.0.0.1", 0), Manipulador)
        self._thread = threading.Thread(target=self._servidor.serve_forever, daemon=True)

    @property
    def url_redirecionamento(self) -> str:
        return f"http://127.0.0.1:{self._servidor.server_address[1]}"

    def __enter__(self) -> ServidorRetorno:
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self.encerrar()

    def aguardar_codigo(self, timeout: float = 300) -> str:
        """Espera o retorno do navegador e devolve o código de autorização."""
        if not self._pronto.wait(timeout):
            raise ErroNuvem("Tempo esgotado esperando a autorização no navegador.")
        if "erro" in self._resultado:
            raise ErroNuvem(f"Autorização não concluída ({self._resultado['erro']}).")
        return self._resultado["code"]

    def encerrar(self) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()


def trocar_codigo_por_tokens(
    client_id: str,
    client_secret: str,
    codigo: str,
    redirect_uri: str,
    verificador: str,
    http: Http = _http_padrao,
) -> dict:
    """Troca o código do navegador pelos tokens de acesso."""
    corpo = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": codigo,
            "code_verifier": verificador,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    dados = _json_ou_erro(
        http("POST", URL_TOKEN, corpo,
             {"Content-Type": "application/x-www-form-urlencoded"}),
        "Não foi possível concluir o login",
    )
    return _credenciais_de_resposta(dados)


def _credenciais_de_resposta(dados: dict, agora: float | None = None) -> dict:
    agora = time.time() if agora is None else agora
    return {
        "access_token": dados.get("access_token", ""),
        "refresh_token": dados.get("refresh_token", ""),
        # Renova um pouco antes de expirar, para não usar um token no limite.
        "expira_em": agora + float(dados.get("expires_in", 3600)) - 60,
    }


def renovar_token(
    client_id: str, client_secret: str, refresh_token: str, http: Http = _http_padrao
) -> dict:
    """Troca o refresh_token por um access_token novo."""
    corpo = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    dados = _json_ou_erro(
        http("POST", URL_TOKEN, corpo,
             {"Content-Type": "application/x-www-form-urlencoded"}),
        "Não foi possível renovar o acesso ao Google Drive",
    )
    novas = _credenciais_de_resposta(dados)
    # O Google não reenvia o refresh_token na renovação: preservamos o atual.
    novas["refresh_token"] = dados.get("refresh_token") or refresh_token
    return novas


def precisa_renovar(credenciais: dict, agora: float | None = None) -> bool:
    """True se o access_token está ausente ou vencido."""
    agora = time.time() if agora is None else agora
    if not credenciais.get("access_token"):
        return True
    return agora >= float(credenciais.get("expira_em") or 0)


# ---------------------------------------------------------------------------
# Credenciais no disco (área privada do app)
# ---------------------------------------------------------------------------


def carregar_credenciais(caminho: Path | None = None) -> dict:
    """Lê as credenciais salvas. Nunca levanta: sem arquivo devolve {}."""
    caminho = caminho or ARQUIVO_CREDENCIAIS
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — arquivo ausente/corrompido: começa do zero
        return {}


def salvar_credenciais(dados: dict, caminho: Path | None = None) -> None:
    caminho = caminho or ARQUIVO_CREDENCIAIS
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2), encoding="utf-8")


def esquecer_credenciais(caminho: Path | None = None) -> None:
    """Desconecta: apaga os tokens locais (não mexe no que está na nuvem)."""
    caminho = caminho or ARQUIVO_CREDENCIAIS
    dados = carregar_credenciais(caminho)
    for chave in ("access_token", "refresh_token", "expira_em"):
        dados.pop(chave, None)
    salvar_credenciais(dados, caminho)


def esta_conectado(credenciais: dict | None = None) -> bool:
    credenciais = carregar_credenciais() if credenciais is None else credenciais
    return bool(credenciais.get("refresh_token"))


def obter_access_token(
    credenciais: dict, http: Http = _http_padrao, caminho: Path | None = None
) -> str:
    """Devolve um access_token válido, renovando e salvando se preciso."""
    if not credenciais.get("refresh_token"):
        raise ErroNuvem("Conecte-se ao Google Drive em Ajustes → Backup na nuvem.")
    if precisa_renovar(credenciais):
        novas = renovar_token(
            credenciais.get("client_id", ""),
            credenciais.get("client_secret", ""),
            credenciais["refresh_token"],
            http=http,
        )
        credenciais.update(novas)
        salvar_credenciais(credenciais, caminho)
    return credenciais["access_token"]


# ---------------------------------------------------------------------------
# Arquivos na pasta privada do app
# ---------------------------------------------------------------------------


def _corpo_multipart(nome: str, conteudo: bytes) -> tuple[bytes, str]:
    """Monta o corpo multipart/related (metadados + arquivo) do Drive v3."""
    limite = f"gestao-arranjo-{secrets.token_hex(8)}"
    tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
    metadados = json.dumps({"name": nome, "parents": ["appDataFolder"]})
    corpo = b"".join(
        [
            f"--{limite}\r\n".encode(),
            b"Content-Type: application/json; charset=UTF-8\r\n\r\n",
            metadados.encode("utf-8"),
            f"\r\n--{limite}\r\n".encode(),
            f"Content-Type: {tipo}\r\n\r\n".encode(),
            conteudo,
            f"\r\n--{limite}--".encode(),
        ]
    )
    return corpo, f"multipart/related; boundary={limite}"


def enviar_backup(access_token: str, caminho: Path | str, http: Http = _http_padrao) -> dict:
    """Sobe um arquivo de backup para a pasta privada do app no Drive."""
    caminho = Path(caminho)
    corpo, tipo_conteudo = _corpo_multipart(caminho.name, caminho.read_bytes())
    return _json_ou_erro(
        http(
            "POST",
            URL_UPLOAD,
            corpo,
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": tipo_conteudo,
            },
        ),
        "Não foi possível enviar o backup",
    )


def listar_backups(access_token: str, http: Http = _http_padrao) -> list[dict]:
    """Lista os backups na pasta do app, do mais novo para o mais antigo."""
    consulta = urllib.parse.urlencode(
        {
            "spaces": "appDataFolder",
            "orderBy": "modifiedTime desc",
            "pageSize": "50",
            "fields": "files(id,name,modifiedTime,size)",
        }
    )
    dados = _json_ou_erro(
        http("GET", f"{URL_ARQUIVOS}?{consulta}", None,
             {"Authorization": f"Bearer {access_token}"}),
        "Não foi possível listar os backups da nuvem",
    )
    return dados.get("files", [])


def escolher_mais_novo(arquivos: list[dict]) -> dict | None:
    """O backup mais recente da lista (não confia na ordem vinda da API)."""
    validos = [a for a in arquivos if a.get("modifiedTime")]
    if not validos:
        return None
    return max(validos, key=lambda a: a["modifiedTime"])


def baixar_backup(access_token: str, file_id: str, http: Http = _http_padrao) -> bytes:
    """Baixa o conteúdo de um backup da nuvem."""
    status, corpo = http(
        "GET",
        f"{URL_ARQUIVOS}/{file_id}?alt=media",
        None,
        {"Authorization": f"Bearer {access_token}"},
    )
    if status >= 400:
        _json_ou_erro((status, corpo), "Não foi possível baixar o backup")
    return corpo

"""Backup na nuvem via Google Drive (pasta privada do aplicativo).

Usa o **fluxo de dispositivo** do OAuth 2.0: o app mostra um código e um link;
o usuário autoriza no navegador (em qualquer aparelho), na página oficial do
Google. O app nunca vê a senha — recebe apenas os tokens, guardados na área
privada do próprio app.

Escopo: ``drive.appdata`` — o app só enxerga a **pasta oculta dele mesmo**
(appDataFolder), nunca o resto do Drive do usuário. É um dos poucos escopos
que o fluxo de dispositivo aceita, o que também o torna viável no Android.

O transporte HTTP é injetável (``http=``) para permitir testar todo o
protocolo sem rede nem credenciais (ver ``tests/test_nuvem_drive.py``).
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from armazenamento import BASE_DIR

URL_DEVICE_CODE = "https://oauth2.googleapis.com/device/code"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
URL_ARQUIVOS = "https://www.googleapis.com/drive/v3/files"

# Só a pasta privada do app — não dá acesso a nenhum outro arquivo do Drive.
ESCOPO = "https://www.googleapis.com/auth/drive.appdata"
GRANT_DEVICE = "urn:ietf:params:oauth:grant-type:device_code"

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
# Autorização (fluxo de dispositivo)
# ---------------------------------------------------------------------------


def iniciar_autorizacao(client_id: str, http: Http = _http_padrao) -> dict:
    """Pede o código de dispositivo. Retorna o que o usuário precisa ver.

    Chaves úteis: ``user_code`` (código a digitar), ``verification_url`` (link),
    ``device_code`` e ``interval`` (usados internamente no aguardo).
    """
    corpo = urllib.parse.urlencode({"client_id": client_id, "scope": ESCOPO}).encode()
    dados = _json_ou_erro(
        http("POST", URL_DEVICE_CODE, corpo,
             {"Content-Type": "application/x-www-form-urlencoded"}),
        "Não foi possível iniciar a conexão com o Google",
    )
    # A API usa verification_url; alguns retornos trazem verification_uri.
    dados.setdefault("verification_url", dados.get("verification_uri", ""))
    return dados


def consultar_autorizacao(
    client_id: str, client_secret: str, device_code: str, http: Http = _http_padrao
) -> dict | None:
    """Uma tentativa de resgatar os tokens.

    Retorna as credenciais quando o usuário já autorizou, ``None`` enquanto
    ainda está pendente, e levanta ``ErroNuvem`` se foi negado/expirou.
    """
    corpo = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "device_code": device_code,
            "grant_type": GRANT_DEVICE,
        }
    ).encode()
    status, bruto = http(
        "POST", URL_TOKEN, corpo, {"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        dados = json.loads(bruto or b"{}")
    except ValueError:
        dados = {}

    if status < 400:
        return _credenciais_de_resposta(dados)

    erro = dados.get("error", "")
    if erro in ("authorization_pending", "slow_down"):
        return None
    if erro == "access_denied":
        raise ErroNuvem("Autorização negada na tela do Google.")
    if erro == "expired_token":
        raise ErroNuvem("O código expirou. Gere um novo e tente de novo.")
    raise ErroNuvem(dados.get("error_description") or f"Falha ao autorizar ({erro or status}).")


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

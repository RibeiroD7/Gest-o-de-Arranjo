"""Testes do backup na nuvem (Google Drive) com transporte HTTP falso.

Cobrem o protocolo inteiro sem rede e sem credenciais: fluxo de dispositivo,
renovação de token, montagem do upload multipart, listagem e download.
"""

import json

import pytest

import nuvem_drive as nd


class HttpFalso:
    """Transporte de mentira: devolve respostas na ordem e grava as chamadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, metodo, url, corpo=None, cabecalhos=None, timeout=30):
        self.chamadas.append(
            {"metodo": metodo, "url": url, "corpo": corpo, "cabecalhos": cabecalhos or {}}
        )
        return self.respostas.pop(0)


def _json(status, dados):
    return (status, json.dumps(dados).encode())


def _campos(corpo: bytes) -> dict:
    from urllib.parse import parse_qs

    return {k: v[0] for k, v in parse_qs(corpo.decode()).items()}


class TestRenovacao:
    def test_preserva_refresh_token_quando_nao_reenviado(self):
        # O Google não reenvia o refresh_token ao renovar.
        http = HttpFalso([_json(200, {"access_token": "NOVO", "expires_in": 3600})])
        cred = nd.renovar_token("id", "seg", "RT-ORIGINAL", http=http)
        assert cred["access_token"] == "NOVO"
        assert cred["refresh_token"] == "RT-ORIGINAL"

    def test_precisa_renovar(self):
        assert nd.precisa_renovar({}) is True
        assert nd.precisa_renovar({"access_token": "AT", "expira_em": 0}) is True
        assert nd.precisa_renovar(
            {"access_token": "AT", "expira_em": 10_000}, agora=1
        ) is False

    def test_obter_access_token_renova_e_salva(self, tmp_path):
        destino = tmp_path / "cred.json"
        cred = {"client_id": "id", "client_secret": "s", "refresh_token": "RT",
                "access_token": "VELHO", "expira_em": 0}
        http = HttpFalso([_json(200, {"access_token": "FRESCO", "expires_in": 3600})])
        assert nd.obter_access_token(cred, http=http, caminho=destino) == "FRESCO"
        # Persistiu para a próxima abertura do app.
        assert nd.carregar_credenciais(destino)["access_token"] == "FRESCO"

    def test_obter_access_token_sem_conexao_orienta(self):
        with pytest.raises(nd.ErroNuvem, match="Ajustes"):
            nd.obter_access_token({})


class TestUpload:
    def test_multipart_tem_metadados_e_pasta_do_app(self, tmp_path):
        arquivo = tmp_path / "backup_teste.json"
        arquivo.write_text('{"a": 1}', encoding="utf-8")
        http = HttpFalso([_json(200, {"id": "FILE1", "name": "backup_teste.json"})])

        assert nd.enviar_backup("AT", arquivo, http=http)["id"] == "FILE1"

        chamada = http.chamadas[0]
        assert chamada["cabecalhos"]["Authorization"] == "Bearer AT"
        assert chamada["cabecalhos"]["Content-Type"].startswith("multipart/related; boundary=")

        corpo = chamada["corpo"].decode()
        assert '"parents": ["appDataFolder"]' in corpo
        assert '"name": "backup_teste.json"' in corpo
        assert '{"a": 1}' in corpo
        # Fecha com os dois hífens exigidos pelo formato.
        limite = chamada["cabecalhos"]["Content-Type"].split("boundary=")[1]
        assert corpo.endswith(f"--{limite}--")

    def test_erro_de_upload_vira_mensagem(self, tmp_path):
        arquivo = tmp_path / "b.json"
        arquivo.write_text("{}", encoding="utf-8")
        http = HttpFalso([_json(403, {"error": {"message": "Cota excedida"}})])
        with pytest.raises(nd.ErroNuvem, match="Cota excedida"):
            nd.enviar_backup("AT", arquivo, http=http)


class TestListarEBaixar:
    def test_listagem_pede_so_a_pasta_do_app(self):
        http = HttpFalso([_json(200, {"files": [{"id": "1", "name": "b.json",
                                                 "modifiedTime": "2026-01-01T00:00:00Z"}]})])
        assert len(nd.listar_backups("AT", http=http)) == 1
        assert "spaces=appDataFolder" in http.chamadas[0]["url"]

    def test_escolher_mais_novo(self):
        arquivos = [
            {"id": "a", "modifiedTime": "2026-01-01T10:00:00Z"},
            {"id": "c", "modifiedTime": "2026-03-15T08:00:00Z"},
            {"id": "b", "modifiedTime": "2026-02-01T23:00:00Z"},
        ]
        assert nd.escolher_mais_novo(arquivos)["id"] == "c"
        assert nd.escolher_mais_novo([]) is None
        assert nd.escolher_mais_novo([{"id": "x"}]) is None

    def test_baixar_devolve_bytes(self):
        http = HttpFalso([(200, b'{"tabelas": {}}')])
        assert nd.baixar_backup("AT", "FILE1", http=http) == b'{"tabelas": {}}'
        assert "alt=media" in http.chamadas[0]["url"]


class TestLoginNoPc:
    """Fluxo de loopback: o navegador volta sozinho para o app."""

    def test_pkce_gera_desafio_valido(self):
        import base64
        import hashlib

        verificador, desafio = nd._gerar_pkce()
        assert 43 <= len(verificador) <= 128
        esperado = base64.urlsafe_b64encode(
            hashlib.sha256(verificador.encode()).digest()
        ).rstrip(b"=").decode()
        assert desafio == esperado
        assert "=" not in desafio  # base64url sem padding, como o Google exige

    def test_url_de_autorizacao(self):
        from urllib.parse import parse_qs, urlparse

        url = nd.montar_url_autorizacao("meu-id", "http://127.0.0.1:9999", "DESAFIO")
        partes = urlparse(url)
        campos = {k: v[0] for k, v in parse_qs(partes.query).items()}
        assert partes.netloc == "accounts.google.com"
        assert campos["client_id"] == "meu-id"
        assert campos["redirect_uri"] == "http://127.0.0.1:9999"
        assert campos["code_challenge_method"] == "S256"
        # offline + consent são o que garantem o refresh_token.
        assert campos["access_type"] == "offline"
        assert campos["prompt"] == "consent"
        assert campos["scope"] == nd.ESCOPO

    def test_servidor_captura_o_codigo(self):
        """Sobe o servidor de verdade e simula o retorno do navegador."""
        import urllib.request

        with nd.ServidorRetorno() as servidor:
            url = servidor.url_redirecionamento
            assert url.startswith("http://127.0.0.1:")

            with urllib.request.urlopen(f"{url}/?code=CODIGO-123&scope=x") as resposta:
                pagina = resposta.read().decode("utf-8")
            assert "Tudo certo" in pagina  # o usuário vê uma página amigável
            assert servidor.aguardar_codigo(timeout=5) == "CODIGO-123"

    def test_servidor_reporta_recusa(self):
        import urllib.request

        with nd.ServidorRetorno() as servidor:
            with urllib.request.urlopen(
                f"{servidor.url_redirecionamento}/?error=access_denied"
            ) as resposta:
                assert "Não foi possível" in resposta.read().decode("utf-8")
            with pytest.raises(nd.ErroNuvem, match="access_denied"):
                servidor.aguardar_codigo(timeout=5)

    def test_troca_do_codigo_envia_pkce(self):
        http = HttpFalso([_json(200, {"access_token": "AT", "refresh_token": "RT",
                                      "expires_in": 3600})])
        cred = nd.trocar_codigo_por_tokens(
            "id", "seg", "CODIGO", "http://127.0.0.1:1234", "VERIF", http=http
        )
        assert cred["refresh_token"] == "RT"
        enviado = _campos(http.chamadas[0]["corpo"])
        assert enviado["grant_type"] == "authorization_code"
        assert enviado["code_verifier"] == "VERIF"
        assert enviado["redirect_uri"] == "http://127.0.0.1:1234"


class TestEscolhaDeCredenciais:
    def test_usuario_tem_prioridade_sobre_embutidas(self, monkeypatch):
        monkeypatch.setattr(nd.credenciais_app, "CLIENT_ID_DESKTOP", "EMBUTIDO")
        monkeypatch.setattr(nd.credenciais_app, "CLIENT_SECRET_DESKTOP", "S-EMB")
        salvas = {"client_id": "MEU", "client_secret": "S-MEU"}
        assert nd.credenciais_efetivas(False, salvas) == ("MEU", "S-MEU")

    def test_mesma_credencial_nas_duas_plataformas(self, monkeypatch):
        """PC e celular usam o mesmo cliente (fluxo loopback nos dois).

        É isso que faz os dois enxergarem os mesmos backups: mesma credencial,
        mesmo escopo, mesma appDataFolder.
        """
        monkeypatch.setattr(nd.credenciais_app, "CLIENT_ID_DESKTOP", "PC")
        monkeypatch.setattr(nd.credenciais_app, "CLIENT_SECRET_DESKTOP", "S-PC")
        assert nd.credenciais_efetivas(False, {}) == ("PC", "S-PC")
        assert nd.credenciais_efetivas(True, {}) == ("PC", "S-PC")
        assert nd.ha_credenciais(True, {}) is True

    def test_sem_credenciais(self, monkeypatch):
        for nome in ("CLIENT_ID_DESKTOP", "CLIENT_SECRET_DESKTOP"):
            monkeypatch.setattr(nd.credenciais_app, nome, "")
        assert nd.ha_credenciais(False, {}) is False
        assert nd.ha_credenciais(True, {}) is False


class TestCredenciaisLocais:
    def test_ida_e_volta_e_desconectar(self, tmp_path):
        destino = tmp_path / "cred.json"
        assert nd.carregar_credenciais(destino) == {}

        nd.salvar_credenciais(
            {"client_id": "id", "client_secret": "s", "refresh_token": "RT",
             "access_token": "AT", "expira_em": 123},
            destino,
        )
        assert nd.esta_conectado(nd.carregar_credenciais(destino)) is True

        nd.esquecer_credenciais(destino)
        restante = nd.carregar_credenciais(destino)
        assert nd.esta_conectado(restante) is False
        # Desconectar não apaga as credenciais do app (só os tokens).
        assert restante["client_id"] == "id"

    def test_arquivo_corrompido_nao_quebra(self, tmp_path):
        destino = tmp_path / "cred.json"
        destino.write_text("não é json", encoding="utf-8")
        assert nd.carregar_credenciais(destino) == {}

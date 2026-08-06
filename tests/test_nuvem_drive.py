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


class TestIniciarAutorizacao:
    def test_pede_codigo_com_escopo_da_pasta_do_app(self):
        http = HttpFalso([
            _json(200, {"device_code": "DC", "user_code": "ABC-DEF",
                        "verification_url": "https://google.com/device", "interval": 5})
        ])
        dados = nd.iniciar_autorizacao("meu-id", http=http)
        assert dados["user_code"] == "ABC-DEF"
        assert dados["verification_url"] == "https://google.com/device"

        enviado = _campos(http.chamadas[0]["corpo"])
        assert enviado["client_id"] == "meu-id"
        # Escopo mínimo: só a pasta privada do app, nunca o Drive inteiro.
        assert enviado["scope"] == "https://www.googleapis.com/auth/drive.appdata"
        assert "drive.file" not in enviado["scope"]

    def test_aceita_verification_uri(self):
        http = HttpFalso([_json(200, {"device_code": "DC", "user_code": "X",
                                      "verification_uri": "https://g.co/dev"})])
        assert nd.iniciar_autorizacao("id", http=http)["verification_url"] == "https://g.co/dev"

    def test_erro_vira_mensagem_legivel(self):
        http = HttpFalso([_json(400, {"error": "invalid_client",
                                      "error_description": "Cliente inválido"})])
        with pytest.raises(nd.ErroNuvem, match="Cliente inválido"):
            nd.iniciar_autorizacao("errado", http=http)


class TestConsultarAutorizacao:
    def test_pendente_retorna_none(self):
        http = HttpFalso([_json(428, {"error": "authorization_pending"})])
        assert nd.consultar_autorizacao("id", "seg", "DC", http=http) is None

    def test_slow_down_tambem_e_pendente(self):
        http = HttpFalso([_json(403, {"error": "slow_down"})])
        assert nd.consultar_autorizacao("id", "seg", "DC", http=http) is None

    def test_sucesso_devolve_credenciais(self):
        http = HttpFalso([_json(200, {"access_token": "AT", "refresh_token": "RT",
                                      "expires_in": 3600})])
        cred = nd.consultar_autorizacao("id", "seg", "DC", http=http)
        assert cred["access_token"] == "AT"
        assert cred["refresh_token"] == "RT"
        assert cred["expira_em"] > 0

    def test_negado_e_expirado_avisam_o_usuario(self):
        with pytest.raises(nd.ErroNuvem, match="negada"):
            nd.consultar_autorizacao("id", "s", "DC",
                                     http=HttpFalso([_json(403, {"error": "access_denied"})]))
        with pytest.raises(nd.ErroNuvem, match="expirou"):
            nd.consultar_autorizacao("id", "s", "DC",
                                     http=HttpFalso([_json(400, {"error": "expired_token"})]))


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

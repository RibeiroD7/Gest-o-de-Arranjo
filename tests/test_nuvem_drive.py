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


class TestExtrairCodigo:
    """Conclusão manual do login (celular): o usuário cola o endereço."""

    def test_url_completa(self):
        url = "http://127.0.0.1:33123/?code=4/0AbC-xyz&scope=drive.appdata"
        assert nd.extrair_codigo(url) == "4/0AbC-xyz"

    def test_so_o_codigo(self):
        assert nd.extrair_codigo("4/0AbC-xyz") == "4/0AbC-xyz"

    def test_espacos_ao_redor(self):
        assert nd.extrair_codigo("  4/0AbC  ") == "4/0AbC"

    def test_erro_do_google_vira_mensagem(self):
        with pytest.raises(nd.ErroNuvem, match="access_denied"):
            nd.extrair_codigo("http://127.0.0.1:1/?error=access_denied&code=")

    def test_vazio_e_endereco_sem_codigo(self):
        with pytest.raises(nd.ErroNuvem, match="Cole o endereço"):
            nd.extrair_codigo("   ")
        with pytest.raises(nd.ErroNuvem, match="Não encontrei o código"):
            nd.extrair_codigo("http://127.0.0.1:33123/")


class TestLoginPendente:
    """O PKCE precisa sobreviver ao app ser encerrado pelo Android."""

    def test_salva_e_recupera(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nd, "ARQUIVO_CREDENCIAIS", tmp_path / "n.json")
        nd.salvar_login_pendente({"verificador": "V", "redirect_uri": "http://x"})
        assert nd.carregar_login_pendente()["verificador"] == "V"
        nd.limpar_login_pendente()
        assert nd.carregar_login_pendente() == {}

    def test_nao_apaga_as_credenciais(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nd, "ARQUIVO_CREDENCIAIS", tmp_path / "n.json")
        nd.salvar_credenciais({"client_id": "ID", "refresh_token": "RT"})
        nd.salvar_login_pendente({"verificador": "V"})
        nd.limpar_login_pendente()
        assert nd.carregar_credenciais()["client_id"] == "ID"
        assert nd.carregar_credenciais()["refresh_token"] == "RT"

    def test_guarda_o_momento_do_inicio(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nd, "ARQUIVO_CREDENCIAIS", tmp_path / "n.json")
        nd.salvar_login_pendente({"verificador": "V"}, agora=1000.0)
        assert nd.carregar_login_pendente()["criado_em"] == 1000.0


class TestLoginPendenteValido:
    """Decide se o app oferece 'concluir colando o endereço'.

    Cenário real: o Android congela o app em segundo plano, o servidor de
    retorno em 127.0.0.1 morre e o navegador para em ERR_CONNECTION_REFUSED —
    mas o código continua na barra de endereço, então o login ainda dá para
    ser concluído.
    """

    def _pendente(self, **extra):
        return {"verificador": "V", "redirect_uri": "http://127.0.0.1:1", **extra}

    def test_recente_pode_ser_concluido(self):
        pendente = self._pendente(criado_em=1000.0)
        assert nd.login_pendente_valido(pendente, agora=1000.0 + 60)

    def test_antigo_nao_e_mais_oferecido(self):
        pendente = self._pendente(criado_em=1000.0)
        assert not nd.login_pendente_valido(pendente, agora=1000.0 + 3600)

    def test_sem_pkce_nao_serve(self):
        assert not nd.login_pendente_valido({"criado_em": 1000.0}, agora=1000.0)

    def test_vazio(self):
        assert not nd.login_pendente_valido({}, agora=1000.0)

    def test_pendente_antigo_sem_carimbo_e_descartado(self):
        """Registro gravado por uma versão anterior (sem criado_em)."""
        assert not nd.login_pendente_valido(self._pendente(), agora=1000.0)


class TestTrocaComRetentativa:
    """No Android o app fica sem DNS em segundo plano; a troca precisa insistir."""

    def test_insiste_ate_a_rede_voltar(self):
        chamadas = {"n": 0}

        def http(metodo, url, corpo=None, cabecalhos=None, timeout=30):
            chamadas["n"] += 1
            if chamadas["n"] < 3:  # duas falhas de DNS, como no Android
                raise OSError("[Errno 7] No address associated with hostname")
            return _json(200, {"access_token": "AT", "refresh_token": "RT",
                               "expires_in": 3600})

        esperas = []
        cred = nd.trocar_codigo_com_retentativa(
            "id", "seg", "COD", "http://127.0.0.1:1", "V",
            http=http, espera=0.01, dormir=esperas.append,
        )
        assert cred["access_token"] == "AT"
        assert chamadas["n"] == 3
        assert len(esperas) == 2  # esperou entre as tentativas

    def test_codigo_recusado_nao_repete(self):
        """Se o Google recusou, insistir não muda nada — falha na hora."""
        chamadas = {"n": 0}

        def http(metodo, url, corpo=None, cabecalhos=None, timeout=30):
            chamadas["n"] += 1
            return _json(400, {"error": "invalid_grant",
                               "error_description": "Código expirado"})

        with pytest.raises(nd.ErroNuvem, match="Código expirado"):
            nd.trocar_codigo_com_retentativa(
                "id", "seg", "COD", "http://x", "V", http=http, dormir=lambda _: None
            )
        assert chamadas["n"] == 1

    def test_desiste_com_mensagem_amigavel(self):
        def http(*a, **k):
            raise OSError("[Errno 7] No address associated with hostname")

        with pytest.raises(nd.ErroNuvem, match="Sem conexão para concluir"):
            nd.trocar_codigo_com_retentativa(
                "id", "seg", "COD", "http://x", "V",
                http=http, tentativas=3, dormir=lambda _: None,
            )

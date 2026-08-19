"""Simpósio: um discurso dividido entre dois oradores da congregação.

Antes virava DUAS linhas no mês, com data e tema repetidos — na tela, no PNG
do quadro e no relatório. Agora é uma linha só, com os dois nomes juntos: é um
compromisso só (uma data, um tema, uma confirmação).
"""

import pytest

import database
from database import create_tables, get_connection
from util import nome_oradores

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # `main` chama ft.run() ao ser importado


def _preparar():
    conn = get_connection()
    try:
        create_tables(conn)
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM arranjos")
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Minha')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('Eduardo Nunes', 'Ancião', ?), ('Danilo Reis', 'Ancião', ?)",
            (cong, cong),
        )
        conn.execute("INSERT OR REPLACE INTO temas (nr, titulo) VALUES (176, 'Paz e segurança')")
        conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 5, 5)")
        conn.commit()
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        ids = {
            nome: oid
            for oid, nome in conn.execute("SELECT id, nome FROM oradores")
        }
    finally:
        conn.close()
    return arranjo, ids, cong


class TestGravacao:
    def test_grava_os_dois_oradores_numa_linha_so(self):
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        registros = database.carregar_oradores_arranjo(arranjo)
        assert len(registros) == 1, "simpósio não pode virar duas linhas"
        (registro,) = registros
        assert registro["orador_nome"] == "Eduardo Nunes"
        assert registro["orador_2_nome"] == "Danilo Reis"
        assert registro["orador_2_id"] == ids["Danilo Reis"]

    def test_discurso_comum_continua_sem_segundo_orador(self):
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026"
        )

        (registro,) = database.carregar_oradores_arranjo(arranjo)
        assert registro["orador_2_id"] is None
        assert registro["orador_2_nome"] == ""

    def test_editar_transforma_em_simposio_e_de_volta(self):
        arranjo, ids, cong = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026"
        )
        (registro,) = database.carregar_oradores_arranjo(arranjo)

        database.atualizar_orador_arranjo(
            registro["id"], 176, cong, "03/05/2026", ids["Danilo Reis"]
        )
        (virou,) = database.carregar_oradores_arranjo(arranjo)
        assert virou["orador_2_nome"] == "Danilo Reis"

        database.atualizar_orador_arranjo(registro["id"], 176, cong, "03/05/2026", None)
        (voltou,) = database.carregar_oradores_arranjo(arranjo)
        assert voltou["orador_2_id"] is None

    def test_o_tema_conta_uma_vez_so_no_catalogo(self):
        """Dois oradores, um discurso: o tema não pode contar em dobro."""
        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        conn = get_connection()
        try:
            usos = conn.execute(
                "SELECT data_uso FROM tema_uso_por_ano WHERE tema_nr = 176"
            ).fetchall()
        finally:
            conn.close()
        assert usos == [("05/2026",)]


class TestExibicao:
    @pytest.mark.parametrize(
        "registro, esperado",
        [
            ({"orador_nome": "Eduardo", "orador_2_nome": "Danilo"}, "Eduardo/Danilo"),
            ({"orador_nome": "Eduardo", "orador_2_nome": ""}, "Eduardo"),
            ({"orador_nome": "Eduardo"}, "Eduardo"),
            ({"orador_nome": "", "orador_2_nome": "Danilo"}, "Danilo"),
            ({}, ""),
            ({"orador_nome": "  Eduardo  ", "orador_2_nome": " Danilo "}, "Eduardo/Danilo"),
        ],
    )
    def test_nome_junta_os_dois(self, registro, esperado):
        assert nome_oradores(registro) == esperado


class TestRelatorio:
    def test_sai_numa_linha_com_os_dois_nomes(self):
        import relatorios

        arranjo, ids, _ = _preparar()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="03/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )

        secoes = relatorios.secoes_programacao(2026)
        linhas = [li for s in secoes for li in s["linhas"] if li and li[0] == "03/05"]
        assert len(linhas) == 1, "o relatório não pode repetir a data"
        assert linhas[0][1] == "Eduardo Nunes/Danilo Reis"


class TestQuadroDeAnuncios:
    """O quadro é o que vai para a parede: o simpósio precisa sair inteiro."""

    def _com_simposio(self):
        arranjo, ids, _ = _preparar()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE configuracoes SET dia_reuniao = 'Sábado', nome_congregacao = 'Minha' "
                "WHERE id = 1"
            )
            conn.commit()
        finally:
            conn.close()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", ids["Eduardo Nunes"], 176, data="02/05/2026",
            orador_2_id=ids["Danilo Reis"],
        )
        return ids

    def test_os_dois_nomes_saem_separados_por_barra(self):
        import pdf_quadro

        self._com_simposio()
        linhas = pdf_quadro.carregar_dados_mes(2026, 5)
        do_dia = [li for li in linhas if li["data"].strftime("%d/%m/%Y") == "02/05/2026"]
        assert do_dia, "a data do simpósio não apareceu no quadro"
        assert do_dia[0]["orador"] == "Eduardo Nunes/Danilo Reis"

    def test_formato_antigo_com_duas_linhas_ainda_junta(self):
        """Arranjos cadastrados antes do campo continuam com dois registros."""
        import pdf_quadro

        arranjo, ids, _ = _preparar()
        conn = get_connection()
        try:
            conn.execute("UPDATE configuracoes SET dia_reuniao = 'Sábado' WHERE id = 1")
            conn.commit()
        finally:
            conn.close()
        for nome in ("Eduardo Nunes", "Danilo Reis"):
            database.adicionar_orador_arranjo(
                arranjo, "recebido", ids[nome], 176, data="02/05/2026"
            )

        linhas = pdf_quadro.carregar_dados_mes(2026, 5)
        do_dia = [li for li in linhas if li["data"].strftime("%d/%m/%Y") == "02/05/2026"]
        assert "/" in do_dia[0]["orador"]
        assert set(do_dia[0]["orador"].split("/")) == {"Eduardo Nunes", "Danilo Reis"}


class TestAprovacaoParaDiscursoFora:
    """Quem faz só o discurso local não pode ser oferecido num envio."""

    def _cadastrar(self, aprovado_fora):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        finally:
            conn.close()
        return database.salvar_orador(
            "Só Local", "", "Ancião", cong, "", set(), aprovado_fora=aprovado_fora
        ), cong

    def test_padrao_e_aprovado(self):
        _preparar()
        conn = get_connection()
        try:
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            oid = conn.execute("SELECT id FROM oradores LIMIT 1").fetchone()[0]
            aprovado = conn.execute(
                "SELECT COALESCE(aprovado_fora, 1) FROM oradores WHERE id = ?", (oid,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert aprovado == 1, "quem já existia continua podendo ser enviado"
        assert cong

    def test_salvar_e_reler_a_marcacao(self):
        import main

        oid, _ = self._cadastrar(False)
        assert main.carregar_orador(oid)["aprovado_fora"] is False

    def test_nao_aparece_no_seletor_de_envio(self):
        """É o efeito prático: ao designar um envio ele some da lista."""
        import main

        oid, cong = self._cadastrar(False)
        database.salvar_orador("Vai Fora", "", "Ancião", cong, "", set())

        def nomes(**kwargs):
            return [
                (o.text or "").split(" — ")[0]
                for o in main.carregar_oradores_com_congregacao_opcoes(cong, **kwargs)
            ]

        assert "Só Local" in nomes()
        assert "Só Local" not in nomes(apenas_aprovados_fora=True)
        assert "Vai Fora" in nomes(apenas_aprovados_fora=True)
        assert oid

    def test_editar_volta_a_aprovar(self):
        oid, cong = self._cadastrar(False)
        database.salvar_orador(
            "Só Local", "", "Ancião", cong, "", set(), orador_id=oid, aprovado_fora=True
        )
        conn = get_connection()
        try:
            valor = conn.execute(
                "SELECT aprovado_fora FROM oradores WHERE id = ?", (oid,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert valor == 1

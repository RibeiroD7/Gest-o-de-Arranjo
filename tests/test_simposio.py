"""Simpósio: um discurso dividido entre dois oradores da congregação.

Antes virava DUAS linhas no mês, com data e tema repetidos — na tela, no PNG
do quadro e no relatório. Agora é uma linha só, com os dois nomes juntos: é um
compromisso só (uma data, um tema, uma confirmação).
"""

import pytest

import database
from database import create_tables, get_connection
from util import nome_oradores


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
            ({"orador_nome": "Eduardo", "orador_2_nome": "Danilo"}, "Eduardo e Danilo"),
            ({"orador_nome": "Eduardo", "orador_2_nome": ""}, "Eduardo"),
            ({"orador_nome": "Eduardo"}, "Eduardo"),
            ({"orador_nome": "", "orador_2_nome": "Danilo"}, "Danilo"),
            ({}, ""),
            ({"orador_nome": "  Eduardo  ", "orador_2_nome": " Danilo "}, "Eduardo e Danilo"),
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
        assert linhas[0][1] == "Eduardo Nunes e Danilo Reis"

"""O que conta como discurso feito por um orador da congregação.

A fila ("há mais tempo sem discursar") e o relatório de frequência contavam
só o que foi ENVIADO a outra congregação. O discurso que o irmão daqui faz
aqui mesmo — o arranjo local, que entra na lista de recebidos — não contava,
e nem a segunda metade de um simpósio.
"""

import pytest

import database
import main

flet = pytest.importorskip("flet")

CONFIG_BASE = {
    "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
    "coordenador_discursos": "", "telefone_coordenador": "",
    "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
}


@pytest.fixture
def cenario():
    """Dois oradores da casa, um visitante e um arranjo do mês."""
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("arranjo_oradores", "arranjos", "orador_temas", "oradores",
                       "congregacoes"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Minha'), ('Vizinha')")
        congs = {nome: cid for cid, nome in conn.execute("SELECT id, nome FROM congregacoes")}
        for nome, cong in (
            ("Daqui Um", "Minha"), ("Daqui Dois", "Minha"), ("Visitante", "Vizinha")
        ):
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) "
                "VALUES (?, 'Ancião', ?)",
                (nome, congs[cong]),
            )
        conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 5, 5)")
        conn.commit()
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        ids = {nome: oid for oid, nome in conn.execute("SELECT id, nome FROM oradores")}
    finally:
        conn.close()
    main.salvar_configuracao(dict(CONFIG_BASE))
    return {"arranjo": arranjo, "ids": ids, "congs": congs}


def _ultima(cenario, nome: str) -> str:
    return database.ultima_data_discurso_por_orador().get(cenario["ids"][nome], "")


def _frequencia(cenario, nome: str) -> dict:
    minha = cenario["congs"]["Minha"]
    return next(
        item for item in database.relatorio_frequencia_oradores(minha)
        if item["nome"] == nome
    )


class TestOQueConta:
    def test_o_enviado_conta(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "enviado", cenario["ids"]["Daqui Um"], None,
            data="02/05/2026",
        )
        assert _ultima(cenario, "Daqui Um") == "02/05/2026"

    def test_o_orador_da_casa_discursando_aqui_conta(self, cenario):
        """É o arranjo local: entra como recebido, com o orador daqui."""
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Daqui Um"], None,
            data="09/05/2026",
        )
        assert _ultima(cenario, "Daqui Um") == "09/05/2026"

    def test_o_visitante_nao_conta_como_discurso_nosso(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Visitante"], None,
            data="09/05/2026",
        )
        assert _ultima(cenario, "Visitante") == ""

    def test_a_segunda_metade_do_simposio_conta(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Daqui Um"], None,
            data="16/05/2026", orador_2_id=cenario["ids"]["Daqui Dois"],
        )
        assert _ultima(cenario, "Daqui Um") == "16/05/2026"
        assert _ultima(cenario, "Daqui Dois") == "16/05/2026"

    def test_a_segunda_metade_conta_tambem_no_envio(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "enviado", cenario["ids"]["Daqui Um"], None,
            data="23/05/2026", orador_2_id=cenario["ids"]["Daqui Dois"],
        )
        assert _ultima(cenario, "Daqui Dois") == "23/05/2026"

    def test_fica_com_a_data_mais_recente(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "enviado", cenario["ids"]["Daqui Um"], None,
            data="02/05/2026",
        )
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Daqui Um"], None,
            data="30/05/2026",
        )
        assert _ultima(cenario, "Daqui Um") == "30/05/2026"

    def test_sem_congregacao_definida_o_recebido_nao_conta(self, cenario):
        """Sem saber qual é a minha, não dá para dizer que o discurso é nosso."""
        main.salvar_configuracao({**CONFIG_BASE, "nome_congregacao": ""})
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Daqui Um"], None,
            data="09/05/2026",
        )
        assert _ultima(cenario, "Daqui Um") == ""


class TestNoRelatorio:
    def test_conta_o_discurso_feito_aqui(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Daqui Um"], None,
            data="09/05/2026",
        )
        linha = _frequencia(cenario, "Daqui Um")
        assert linha["quantidade"] == 1
        assert linha["ultima_data"] == "09/05/2026"

    def test_conta_os_dois_do_simposio(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "enviado", cenario["ids"]["Daqui Um"], None,
            data="16/05/2026", orador_2_id=cenario["ids"]["Daqui Dois"],
        )
        assert _frequencia(cenario, "Daqui Um")["quantidade"] == 1
        assert _frequencia(cenario, "Daqui Dois")["quantidade"] == 1

    def test_quem_nunca_discursou_continua_zerado(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "enviado", cenario["ids"]["Daqui Um"], None,
            data="16/05/2026",
        )
        linha = _frequencia(cenario, "Daqui Dois")
        assert linha["quantidade"] == 0
        assert linha["ultima_data"] == ""

    def test_o_visitante_nao_entra_na_conta_da_minha_congregacao(self, cenario):
        database.adicionar_orador_arranjo(
            cenario["arranjo"], "recebido", cenario["ids"]["Visitante"], None,
            data="09/05/2026",
        )
        nomes = [
            item["nome"] for item in database.relatorio_frequencia_oradores(
                cenario["congs"]["Minha"]
            )
        ]
        assert "Visitante" not in nomes

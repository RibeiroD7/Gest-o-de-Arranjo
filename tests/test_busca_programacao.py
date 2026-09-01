"""Busca da tela de Programação: achar quem discursou sem abrir mês por mês.

O que está marcado no ano vive em quatro lugares (orador recebido, designação
enviada, presidente da semana e data especial). A busca junta os quatro numa
lista só e procura por nome, tema, congregação ou tipo do evento.
"""

import types

import pytest

flet = pytest.importorskip("flet")

import database  # noqa: E402
import main  # noqa: E402


def _page():
    return types.SimpleNamespace(
        update=lambda *a, **k: None, width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None, title="",
    )


def _controles(raiz):
    achados = [raiz]
    for atributo in ("content", "controls", "actions"):
        valor = getattr(raiz, atributo, None)
        if isinstance(valor, list):
            for filho in valor:
                achados += _controles(filho)
        elif valor is not None and not isinstance(valor, str):
            achados += _controles(valor)
    return achados


@pytest.fixture(autouse=True)
def programacao_de_teste():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("arranjo_oradores", "arranjos", "datas_especiais", "orador_temas",
                       "oradores", "congregacoes", "presidentes", "presidentes_cadastro",
                       "temas"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Vila Sônia')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute("INSERT INTO temas (nr, titulo) VALUES (46, 'Fortaleça sua confiança')")
        for nome in ("Carlos Soares", "Marcio Rocha"):
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES (?, 'Ancião', ?)",
                (nome, cong),
            )
        ids = {nome: oid for oid, nome in conn.execute("SELECT id, nome FROM oradores")}
        conn.execute(
            "INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 11, 11)"
        )
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        conn.execute(
            "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, tema_nr, "
            "congregacao_id, data) VALUES (?, 'recebido', ?, 46, ?, '07/11/2026')",
            (arranjo, ids["Carlos Soares"], cong),
        )
        conn.execute(
            "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, orador_2_id, "
            "data) VALUES (?, 'enviado', ?, ?, '14/11/2026')",
            (arranjo, ids["Marcio Rocha"], ids["Carlos Soares"]),
        )
        conn.commit()
    finally:
        conn.close()
    presidente = database.salvar_presidente_cadastro("David Ribeiro", "Ancião")
    database.salvar_presidente("07/11/2026", presidente)
    database.salvar_presidente("05/07/2025", presidente)
    database.salvar_data_especial(
        "21/11/2026", "Visita do Superintendente", "Wagner Mendes", "Tema da visita", None
    )


class TestOQueEntraNaLista:
    def test_junta_os_quatro_lugares(self):
        categorias = {i["categoria"] for i in database.listar_itens_programacao()}
        assert categorias == {
            "Orador recebido", "Designação enviada", "Presidente",
            "Visita do Superintendente",
        }

    def test_o_ano_filtra(self):
        do_ano = database.listar_itens_programacao(2026)
        assert all(i["data"].endswith("2026") for i in do_ano)
        assert any(i["data"].endswith("2025") for i in database.listar_itens_programacao())

    def test_vem_em_ordem_de_calendario(self):
        datas = [i["data"] for i in database.listar_itens_programacao()]
        assert datas == sorted(datas, key=lambda d: (d[6:10], d[3:5], d[0:2]))
        assert datas[0] == "05/07/2025"

    def test_o_simposio_traz_os_dois_nomes(self):
        enviada = next(
            i for i in database.listar_itens_programacao()
            if i["categoria"] == "Designação enviada"
        )
        assert "Marcio Rocha" in enviada["pessoa"]
        assert "Carlos Soares" in enviada["pessoa"]

    def test_a_data_especial_traz_orador_e_tema(self):
        visita = next(
            i for i in database.listar_itens_programacao()
            if i["categoria"] == "Visita do Superintendente"
        )
        assert "Wagner Mendes" in visita["pessoa"]
        assert "Tema da visita" in visita["tema_titulo"]


class TestOQueABuscaAcha:
    def _buscar(self, termo: str, ano: int | None = None) -> list[dict]:
        return main.filtrar_itens_programacao(
            database.listar_itens_programacao(ano), termo
        )

    def test_pelo_nome_do_orador(self):
        achados = self._buscar("carlos")
        assert {i["categoria"] for i in achados} == {"Orador recebido", "Designação enviada"}

    def test_pelo_tema(self):
        achados = self._buscar("fortaleça")
        assert [i["data"] for i in achados] == ["07/11/2026"]

    def test_sem_acento_acha_com_acento(self):
        assert self._buscar("fortaleca")
        assert self._buscar("VILA SONIA")

    def test_pela_congregacao(self):
        assert [i["data"] for i in self._buscar("vila sônia")] == ["07/11/2026"]

    def test_pelo_tipo_do_evento(self):
        assert [i["data"] for i in self._buscar("superintendente")] == ["21/11/2026"]

    def test_pelo_presidente(self):
        datas = [i["data"] for i in self._buscar("david")]
        assert datas == ["05/07/2025", "07/11/2026"]

    def test_duas_palavras_precisam_casar_as_duas(self):
        assert self._buscar("carlos fortaleça")
        assert not self._buscar("carlos superintendente")

    def test_termo_vazio_nao_traz_nada(self):
        """A tela mostra a grade de meses quando não há busca."""
        assert self._buscar("") == []
        assert self._buscar("   ") == []

    def test_pela_data(self):
        assert [i["categoria"] for i in self._buscar("21/11")] == [
            "Visita do Superintendente"
        ]


class TestNaTela:
    def test_a_tela_tem_o_campo_de_busca(self):
        campos = [
            c.hint_text for c in _controles(
                main.tela_programacao(_page(), lambda: None, None)
            )
            if isinstance(c, flet.TextField)
        ]
        assert any("Buscar orador" in (t or "") for t in campos)

    def test_a_linha_do_resultado_mostra_data_pessoa_e_tema(self):
        item = database.listar_itens_programacao(2026)[0]
        textos = [
            c.value for c in _controles(main._linha_resultado_busca(item))
            if isinstance(c, flet.Text) and c.value
        ]
        assert item["data"] in textos
        assert item["pessoa"] in textos

    def test_o_resultado_abre_o_mes_quando_ha_um(self):
        item = database.listar_itens_programacao(2026)[0]
        abertos = []
        linha = main._linha_resultado_busca(item, lambda i: abertos.append(i))
        linha.on_click(None)
        assert abertos and abertos[0]["data"] == item["data"]

    def test_sem_mes_cadastrado_a_linha_nao_clica(self):
        item = database.listar_itens_programacao(2026)[0]
        assert main._linha_resultado_busca(item).on_click is None

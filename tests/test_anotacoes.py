"""Anotações do calendário: o que lembrar de fazer num dia.

"Ligar para o Fulano", "confirmar o orador" — coisas que não são orador nem
presidente, e que precisam aparecer no Início quando a data chega.
"""

import types

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import database  # noqa: E402
import main  # noqa: E402
from telas.calendario import tela_calendario  # noqa: E402


@pytest.fixture(autouse=True)
def _sem_anotacoes():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        conn.execute("DELETE FROM anotacoes")
        conn.commit()
    finally:
        conn.close()


class TestGuardarAnotacoes:
    def test_criar_listar_e_apagar(self):
        anotacao = database.salvar_anotacao("29/08/2026", "Ligar para o Fulano")
        assert [a["texto"] for a in database.listar_anotacoes("29/08/2026")] == [
            "Ligar para o Fulano"
        ]
        database.excluir_anotacao(anotacao)
        assert database.listar_anotacoes("29/08/2026") == []

    def test_marcar_como_feita_e_desmarcar(self):
        anotacao = database.salvar_anotacao("29/08/2026", "Confirmar o orador")
        database.marcar_anotacao(anotacao)
        assert database.listar_anotacoes("29/08/2026")[0]["feita"] is True
        database.marcar_anotacao(anotacao, feita=False)
        assert database.listar_anotacoes("29/08/2026")[0]["feita"] is False

    def test_cada_dia_tem_as_suas(self):
        database.salvar_anotacao("29/08/2026", "Do sábado")
        database.salvar_anotacao("05/09/2026", "Do outro sábado")
        assert len(database.listar_anotacoes("29/08/2026")) == 1
        assert len(database.listar_anotacoes()) == 2

    def test_a_lista_vem_em_ordem_de_calendario(self):
        """Como texto, 05/09 viria antes de 29/08."""
        database.salvar_anotacao("29/08/2026", "Primeira")
        database.salvar_anotacao("05/09/2026", "Segunda")
        assert [a["texto"] for a in database.listar_anotacoes()] == ["Primeira", "Segunda"]


class TestOQueOInicioCobra:
    def test_a_data_que_chegou_entra(self):
        database.salvar_anotacao("29/08/2026", "Ligar para o Fulano")
        assert [a["texto"] for a in database.anotacoes_ate("29/08/2026")] == [
            "Ligar para o Fulano"
        ]

    def test_a_data_que_ainda_nao_chegou_fica_de_fora(self):
        database.salvar_anotacao("05/09/2026", "Só semana que vem")
        assert database.anotacoes_ate("29/08/2026") == []

    def test_a_atrasada_continua_cobrando(self):
        database.salvar_anotacao("20/08/2026", "Era para ontem")
        assert len(database.anotacoes_ate("29/08/2026")) == 1

    def test_a_feita_para_de_cobrar(self):
        anotacao = database.salvar_anotacao("20/08/2026", "Já resolvido")
        database.marcar_anotacao(anotacao)
        assert database.anotacoes_ate("29/08/2026") == []

    def test_virada_de_ano_na_comparacao(self):
        """A chave de ordenação precisa ser AAAAMMDD, não o texto da data."""
        database.salvar_anotacao("28/12/2025", "Do ano passado")
        assert len(database.anotacoes_ate("02/01/2026")) == 1


class TestNoCalendario:
    def test_a_tela_monta_com_anotacoes(self):
        database.salvar_anotacao("29/08/2026", "Ligar para o Fulano")
        page = types.SimpleNamespace(
            update=lambda *a, **k: None, width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
            on_keyboard_event=None, title="",
        )
        assert tela_calendario(page, lambda: None) is not None

    def test_a_anotacao_viaja_no_backup(self):
        """Anotação perdida numa troca de aparelho é anotação inútil."""
        assert "anotacoes" in database.TABELAS_BACKUP

    def test_o_inicio_cobra_a_anotacao_vencida(self):
        import re

        database.salvar_anotacao("01/01/2020", "Coisa antiga a fazer")
        page = types.SimpleNamespace(
            update=lambda *a, **k: None, width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
            on_keyboard_event=None, title="",
        )
        tela = main.tela_inicio(page, lambda: None, lambda i: None)
        textos = []

        def varrer(no):
            if isinstance(no, flet.Text) and no.value:
                textos.append(no.value)
            for atributo in ("content", "controls"):
                valor = getattr(no, atributo, None)
                if isinstance(valor, list):
                    for filho in valor:
                        varrer(filho)
                elif valor is not None and not isinstance(valor, str):
                    varrer(valor)

        varrer(tela)
        assert any(re.search(r"Anota[çc][ãa]o: Coisa antiga", t) for t in textos)

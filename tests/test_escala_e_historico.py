"""Escala dos presidentes e o histórico por trás dos números.

Cobre três coisas que andam juntas: tirar alguém da escala sem apagar o que
ele fez, separar os tipos de evento que têm fila própria dos que não têm, e
o detalhe que abre ao clicar numa pessoa no relatório.
"""

from datetime import date

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture(autouse=True)
def _banco_limpo():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("arranjo_oradores", "arranjos", "datas_especiais", "orador_temas",
                       "oradores", "congregacoes", "presidentes", "presidentes_cadastro"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.commit()
    finally:
        conn.close()


class TestTirarDaEscala:
    """Quem muda de congregação sai do rodízio; o que presidiu continua lá."""

    def test_arquivado_some_das_listas_e_dos_rodizios(self):
        ficou = database.salvar_presidente_cadastro("Quem Fica", "Ancião", preside_especiais=True)
        saiu = database.salvar_presidente_cadastro("Quem Sai", "Ancião", preside_especiais=True)

        database.arquivar_presidente_cadastro(saiu)

        ids = [p["id"] for p in database.listar_presidentes_cadastro()]
        assert ids == [ficou]
        assert saiu not in [p["id"] for p in database.listar_presidentes_cadastro(escala="especiais")]
        assert saiu in [
            p["id"] for p in database.listar_presidentes_cadastro(incluir_arquivados=True)
        ]

    def test_o_historico_do_arquivado_continua_no_lugar(self):
        saiu = database.salvar_presidente_cadastro("Quem Sai", "Ancião", preside_especiais=True)
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", saiu)
        database.salvar_presidente("07/03/2026", saiu)

        database.arquivar_presidente_cadastro(saiu)

        especiais = database.listar_datas_especiais_por_ano(2026)
        assert especiais["11/04/2026"]["presidente_nome"] == "Quem Sai"
        assert database.historico_presidencias_da_pessoa(saiu), "as datas continuam ligadas a ele"

    def test_volta_para_a_escala(self):
        pid = database.salvar_presidente_cadastro("Voltou", "Ancião")
        database.arquivar_presidente_cadastro(pid)
        database.arquivar_presidente_cadastro(pid, arquivar=False)
        assert [p["id"] for p in database.listar_presidentes_cadastro()] == [pid]

    def test_quem_tem_historico_e_quem_nao_tem(self):
        com = database.salvar_presidente_cadastro("Com História", "Ancião")
        sem = database.salvar_presidente_cadastro("Sem História", "Ancião")
        database.salvar_presidente("07/03/2026", com)

        assert database.presidente_tem_historico(com) is True
        assert database.presidente_tem_historico(sem) is False

    def test_historico_conta_tambem_a_data_especial(self):
        pid = database.salvar_presidente_cadastro("Só Especial", "Ancião", preside_especiais=True)
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", pid)
        assert database.presidente_tem_historico(pid) is True


class TestTipoForaDoRodizio:
    """Ter presidente e ter fila própria são coisas diferentes."""

    def test_arranjo_local_nasce_fora_do_rodizio(self):
        assert "Arranjo Local" in database.tipos_fora_do_rodizio_especiais()

    def test_o_rodizio_nao_preenche_um_tipo_de_fora(self):
        database.salvar_presidente_cadastro("Ancião A", "Ancião", preside_especiais=True)
        database.salvar_data_especial("13/06/2099", "Arranjo Local", "", "", None)

        preenchidas = main.preencher_presidentes_especiais_rodizio(
            2099, a_partir_de=date(2026, 1, 1)
        )

        assert preenchidas == 0
        especiais = database.listar_datas_especiais_por_ano(2099)
        assert not especiais["13/06/2099"]["presidente_nome"]

    def test_a_marcacao_pode_ser_ligada_e_desligada(self):
        tipos = {t["nome"]: t for t in database.listar_tipos_evento()}
        alvo = tipos["Arranjo Local"]
        assert alvo["entra_rodizio"] is False

        database.definir_tipo_evento_entra_rodizio(alvo["id"], True)
        assert "Arranjo Local" not in database.tipos_fora_do_rodizio_especiais()

        database.definir_tipo_evento_entra_rodizio(alvo["id"], False)
        assert "Arranjo Local" in database.tipos_fora_do_rodizio_especiais()

    def test_a_aba_nao_mostra_fila_de_quem_esta_fora(self):
        import types

        database.salvar_presidente_cadastro("Ancião A", "Ancião", preside_especiais=True)
        database.salvar_data_especial("13/06/2099", "Arranjo Local", "", "", None)
        page = types.SimpleNamespace(
            update=lambda *a, **k: None, width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
            on_keyboard_event=None, title="",
        )
        secao = main._secao_presidentes_especiais(page, lambda: None)
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

        varrer(secao)
        # A data aparece na lista, mas sem card de fila e sem ser cobrada.
        assert "Celebração" in textos
        assert textos.count("Arranjo Local") <= 1
        assert "não pede presidente" in textos


class TestHistoricoDaPessoa:
    def _orador(self, nome: str, congregacao: str) -> int:
        conn = database.get_connection()
        try:
            conn.execute("INSERT OR IGNORE INTO congregacoes (nome) VALUES (?)", (congregacao,))
            cong = conn.execute(
                "SELECT id FROM congregacoes WHERE nome = ?", (congregacao,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES (?, 'Ancião', ?)",
                (nome, cong),
            )
            conn.execute("INSERT INTO arranjos (ano, mes_inicio) VALUES (2026, 3)")
            # O tema é chave estrangeira: sem ele o vínculo não entra.
            conn.execute(
                "INSERT OR IGNORE INTO temas (nr, titulo) VALUES (12, 'Tema de teste')"
            )
            conn.commit()
            return conn.execute("SELECT id FROM oradores WHERE nome = ?", (nome,)).fetchone()[0]
        finally:
            conn.close()

    def test_lista_os_discursos_do_mais_recente_para_tras(self):
        orador = self._orador("Orador Um", "Vizinha")
        conn = database.get_connection()
        try:
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            for data in ("07/03/2026", "05/12/2026", "11/04/2026"):
                conn.execute(
                    "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, "
                    "congregacao_id, data, tema_nr) VALUES (?, 'enviado', ?, ?, ?, 12)",
                    (arranjo, orador, cong, data),
                )
            conn.commit()
        finally:
            conn.close()

        historico = database.historico_discursos_do_orador(orador)
        assert [h["data"] for h in historico] == ["05/12/2026", "11/04/2026", "07/03/2026"]
        assert historico[0]["congregacao"] == "Vizinha"

    def test_simposio_conta_para_os_dois_oradores(self):
        primeiro = self._orador("Orador Um", "Vizinha")
        segundo = self._orador("Orador Dois", "Vizinha")
        conn = database.get_connection()
        try:
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            conn.execute(
                "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, orador_2_id, "
                "data, tema_nr) VALUES (?, 'enviado', ?, ?, '11/04/2026', 12)",
                (arranjo, primeiro, segundo),
            )
            conn.commit()
        finally:
            conn.close()

        assert len(database.historico_discursos_do_orador(primeiro)) == 1
        assert len(database.historico_discursos_do_orador(segundo)) == 1

    def test_presidencias_juntam_semanas_e_datas_especiais(self):
        pid = database.salvar_presidente_cadastro("Presidente", "Ancião", preside_especiais=True)
        database.salvar_presidente("07/03/2026", pid)
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", pid)

        historico = database.historico_presidencias_da_pessoa(pid)
        assert [h["data"] for h in historico] == ["11/04/2026", "07/03/2026"]
        assert historico[0]["tipo"] == "Celebração"
        assert historico[1]["tipo"] == "Reunião de fim de semana"

    def test_o_ranking_do_relatorio_traz_o_id_para_abrir_o_detalhe(self):
        pid = database.salvar_presidente_cadastro("Presidente", "Ancião")
        database.salvar_presidente("07/03/2026", pid)
        assert all("id" in linha for linha in database.relatorio_presidencias())
        assert all("id" in linha for linha in database.relatorio_frequencia_oradores())

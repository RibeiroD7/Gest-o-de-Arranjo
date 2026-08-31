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


def _page():
    import types

    return types.SimpleNamespace(
        update=lambda *a, **k: None, width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda *a, **k: None, pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None, platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None, title="",
    )


def _textos(controle):
    achados = []

    def varrer(no):
        if isinstance(no, flet.Text) and no.value:
            achados.append(no.value)
        for atributo in ("content", "controls"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, list):
                for filho in valor:
                    varrer(filho)
            elif valor is not None and not isinstance(valor, str):
                varrer(valor)

    varrer(controle)
    return achados


class TestExcluirDeVez:
    """Excluir tira do cadastro; o que a pessoa fez continua registrado."""

    def test_a_semana_presidida_fica_com_o_nome(self):
        pid = database.salvar_presidente_cadastro("Quem Saiu", "Ancião")
        database.salvar_presidente("07/03/2026", pid)

        database.excluir_presidente_cadastro(pid)

        semana = database.carregar_presidentes_por_ano(2026)["07/03/2026"]
        assert semana["nome"] == "Quem Saiu"
        assert semana["presidente_id"] is None, "vira avulso, fora dos rodízios"

    def test_a_data_especial_presidida_fica_com_o_nome(self):
        pid = database.salvar_presidente_cadastro("Quem Saiu", "Ancião", preside_especiais=True)
        database.salvar_data_especial("11/04/2026", "Celebração", "", "", pid)

        database.excluir_presidente_cadastro(pid)

        registro = database.listar_datas_especiais_por_ano(2026)["11/04/2026"]
        assert registro["presidente_nome"] == "Quem Saiu"
        assert registro["presidente_id"] is None

    def test_some_do_cadastro_e_dos_rodizios(self):
        pid = database.salvar_presidente_cadastro("Quem Saiu", "Ancião")
        database.salvar_presidente("07/03/2026", pid)

        database.excluir_presidente_cadastro(pid)

        cadastrados = database.listar_presidentes_cadastro(incluir_arquivados=True)
        assert all(item["id"] != pid for item in cadastrados)

    def test_quem_nunca_presidiu_sai_sem_deixar_rastro(self):
        pid = database.salvar_presidente_cadastro("Digitado Errado", "Ancião")
        database.excluir_presidente_cadastro(pid)
        assert database.listar_presidentes_cadastro(incluir_arquivados=True) == []

    def test_orador_da_segunda_metade_do_simposio_nao_e_apagado(self):
        """Ele só aparece em `orador_2_id`; apagar deixaria a designação sem nome."""
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Alfa')")
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            for nome in ("Primeira Parte", "Segunda Parte"):
                conn.execute(
                    "INSERT INTO oradores (nome, categoria, congregacao_id) "
                    "VALUES (?, 'Ancião', ?)",
                    (nome, cong),
                )
            conn.execute("INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 5, 5)")
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            ids = {nome: oid for oid, nome in conn.execute("SELECT id, nome FROM oradores")}
            conn.execute(
                "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, orador_2_id, data) "
                "VALUES (?, 'enviado', ?, ?, '09/05/2026')",
                (arranjo, ids["Primeira Parte"], ids["Segunda Parte"]),
            )
            conn.commit()
        finally:
            conn.close()

        database.excluir_orador(ids["Segunda Parte"])

        conn = database.get_connection()
        try:
            nome = conn.execute(
                "SELECT nome FROM oradores WHERE id = ?", (ids["Segunda Parte"],)
            ).fetchone()
            designacao = conn.execute(
                "SELECT orador_2_id FROM arranjo_oradores"
            ).fetchone()
        finally:
            conn.close()
        assert nome and nome[0] == "Segunda Parte", "arquivado, não apagado"
        assert designacao[0] == ids["Segunda Parte"], "a designação continua inteira"


class TestTipoForaDoRodizio:
    """Ter presidente e ter fila própria são coisas diferentes."""

    def _tipo_de_fora(self, nome: str = "Reunião do Corpo") -> dict:
        """Um tipo com reunião no salão, mas sem fila própria de anciãos."""
        database.adicionar_tipo_evento(nome)
        tipo = {t["nome"]: t for t in database.listar_tipos_evento()}[nome]
        database.definir_tipo_evento_entra_rodizio(tipo["id"], False)
        return tipo

    def test_o_rodizio_nao_preenche_um_tipo_de_fora(self):
        self._tipo_de_fora()
        database.salvar_presidente_cadastro("Ancião A", "Ancião", preside_especiais=True)
        database.salvar_data_especial("13/06/2099", "Reunião do Corpo", "", "", None)

        preenchidas = main.preencher_presidentes_especiais_rodizio(
            2099, a_partir_de=date(2026, 1, 1)
        )

        assert preenchidas == 0
        especiais = database.listar_datas_especiais_por_ano(2099)
        assert not especiais["13/06/2099"]["presidente_nome"]

    def test_a_marcacao_pode_ser_ligada_e_desligada(self):
        alvo = self._tipo_de_fora()
        assert "Reunião do Corpo" in database.tipos_fora_do_rodizio_especiais()

        database.definir_tipo_evento_entra_rodizio(alvo["id"], True)
        assert "Reunião do Corpo" not in database.tipos_fora_do_rodizio_especiais()

        database.definir_tipo_evento_entra_rodizio(alvo["id"], False)
        assert "Reunião do Corpo" in database.tipos_fora_do_rodizio_especiais()

    def test_a_aba_nao_mostra_fila_de_quem_esta_fora(self):
        self._tipo_de_fora()
        database.salvar_presidente_cadastro("Ancião A", "Ancião", preside_especiais=True)
        database.salvar_data_especial("13/06/2099", "Reunião do Corpo", "", "", None)

        textos = _textos(main._secao_presidentes_especiais(_page(), lambda: None))

        # A data aparece na lista, mas sem card de fila e sem ser cobrada.
        assert "Celebração" in textos
        assert textos.count("Reunião do Corpo") <= 1
        assert "não pede presidente" in textos


class TestArranjoLocalSaiuDoApp:
    """Não é um evento à parte: é a reunião normal, com o presidente da semana."""

    def test_nao_e_mais_um_tipo_padrao(self):
        assert "Arranjo Local" not in database.TIPOS_EVENTO_PADRAO
        assert "Arranjo Local" not in [t["nome"] for t in database.listar_tipos_evento()]

    def test_uma_data_antiga_nao_o_traz_de_volta(self):
        """A semeadura recria os tipos usados nas datas — menos os removidos."""
        database.salvar_data_especial("13/06/2020", "Arranjo Local", "", "", None)
        conn = database.get_connection()
        try:
            database._semear_tipos_evento(conn)
        finally:
            conn.close()
        assert "Arranjo Local" not in [t["nome"] for t in database.listar_tipos_evento()]

    def test_a_data_antiga_continua_no_registro(self):
        database.salvar_data_especial("13/06/2020", "Arranjo Local", "", "", None)
        registro = database.listar_datas_especiais_por_ano(2020)["13/06/2020"]
        assert registro["tipo"] == "Arranjo Local"

    def test_sem_fila_e_sem_cobranca_na_aba(self):
        database.salvar_presidente_cadastro("Ancião A", "Ancião", preside_especiais=True)
        database.salvar_data_especial("13/06/2099", "Arranjo Local", "", "", None)

        textos = _textos(main._secao_presidentes_especiais(_page(), lambda: None))

        assert textos.count("Arranjo Local") <= 1, "sem card de fila"
        assert "não pede presidente" in textos

    def test_cadastrar_de_novo_desfaz_a_remocao(self):
        """Quem quiser o tipo de volta é só criar; a remoção não é definitiva."""
        database.adicionar_tipo_evento("Arranjo Local")
        try:
            assert "Arranjo Local" in [t["nome"] for t in database.listar_tipos_evento()]
        finally:
            tipo = {t["nome"]: t for t in database.listar_tipos_evento()}["Arranjo Local"]
            database.excluir_tipo_evento(tipo["id"])

    def test_remover_um_tipo_o_deixa_removido(self):
        database.adicionar_tipo_evento("Tipo Passageiro")
        tipo = {t["nome"]: t for t in database.listar_tipos_evento()}["Tipo Passageiro"]
        database.excluir_tipo_evento(tipo["id"])
        assert "Tipo Passageiro" in database.tipos_evento_removidos()
        conn = database.get_connection()
        try:
            database._semear_tipos_evento(conn)
        finally:
            conn.close()
        assert "Tipo Passageiro" not in [t["nome"] for t in database.listar_tipos_evento()]


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

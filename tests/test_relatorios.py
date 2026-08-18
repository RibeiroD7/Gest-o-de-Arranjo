"""Conteúdo dos relatórios de cada tela (src/relatorios.py).

Cada tela exporta em PDF o que ela mostra. Aqui o que se testa é o CONTEÚDO
(as seções), não o desenho: com dados conhecidos no banco, as linhas certas
precisam aparecer — inclusive o presidente avulso, que existe só na
programação e não no cadastro.
"""

import pytest

import database
import relatorios
from database import create_tables, get_connection


def _limpar():
    conn = get_connection()
    try:
        create_tables(conn)
        for tabela in (
            "arranjo_oradores", "arranjos", "datas_especiais", "presidentes",
            "presidentes_cadastro", "orador_temas", "oradores", "congregacoes",
        ):
            conn.execute(f"DELETE FROM {tabela}")  # noqa: S608 — nomes fixos
        conn.commit()
    finally:
        conn.close()


def _linhas(secoes):
    """Todas as linhas de todas as seções, achatadas."""
    return [linha for secao in secoes for linha in secao["linhas"]]


def _tabelas(secoes):
    """Só as seções que têm tabela (pula as tarjas de bloco)."""
    return [s for s in secoes if s["linhas"] or s["cabecalhos"]]


def _faixas(secoes):
    return [s["titulo"] for s in secoes if s.get("faixa")]


class TestProgramacao:
    def _montar_mes(self):
        _limpar()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO congregacoes (nome) VALUES ('Central')")
            cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
            conn.execute(
                "INSERT INTO oradores (nome, categoria, congregacao_id) "
                "VALUES ('Zé da Silva', 'Ancião', ?)",
                (cong,),
            )
            orador = conn.execute("SELECT id FROM oradores").fetchone()[0]
            conn.execute(
                "INSERT OR REPLACE INTO temas (nr, titulo) VALUES (74, 'Tema Setenta')"
            )
            conn.execute(
                "INSERT INTO arranjos (ano, mes_inicio, mes_fim, congregacao_host_id) "
                "VALUES (2026, 1, 1, ?)",
                (cong,),
            )
            arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        database.adicionar_orador_arranjo(
            arranjo, "recebido", orador, 74, congregacao_id=cong, data="03/01/2026"
        )
        return cong

    def test_traz_o_orador_recebido_do_mes(self):
        self._montar_mes()
        linhas = _linhas(relatorios.secoes_programacao(2026))
        assert any("Zé da Silva" in linha for linha in linhas)
        assert any("74 — Tema Setenta" in linha for linha in linhas)

    def test_ano_sem_arranjo_nao_quebra(self):
        _limpar()
        secoes = relatorios.secoes_programacao(2031)
        assert secoes and secoes[0]["linhas"] == []
        assert "Nenhum arranjo" in secoes[0]["vazio"]

    def test_presidente_avulso_aparece_marcado_fora_do_rodizio(self):
        """O nome digitado à mão precisa sair no relatório, identificado."""
        self._montar_mes()
        database.salvar_presidente_avulso("10/01/2026", "José Que Saiu")

        linhas = _linhas(relatorios.secoes_programacao(2026))
        linha = next(li for li in linhas if "José Que Saiu" in li)
        assert "fora do rodízio" in linha

    def test_presidente_do_cadastro_aparece_como_no_rodizio(self):
        self._montar_mes()
        pid = database.salvar_presidente_cadastro("Lucas", "Ancião")
        database.salvar_presidente("17/01/2026", pid)

        linhas = _linhas(relatorios.secoes_programacao(2026))
        linha = next(li for li in linhas if "Lucas" in li)
        assert linha[2] == "", "quem está no cadastro não recebe observação"

    def test_so_entram_as_datas_daquele_mes(self):
        self._montar_mes()
        pid = database.salvar_presidente_cadastro("Lucas", "Ancião")
        database.salvar_presidente("07/03/2026", pid)  # março, sem arranjo

        linhas = _linhas(relatorios.secoes_programacao(2026))
        assert not any("07/03" in li for li in linhas)


class TestOradores:
    def test_agrupa_por_congregacao(self):
        secoes = relatorios.secoes_oradores(
            [
                {"nome": "Ana", "categoria": "Ancião", "congregacao": "Central",
                 "telefone": "1", "temas": "1, 2"},
                {"nome": "Bruno", "categoria": "Servo Ministerial",
                 "congregacao": "Vila", "telefone": "", "temas": ""},
            ]
        )
        assert _faixas(secoes) == ["Central", "Vila"]
        assert _tabelas(secoes)[1]["linhas"][0][2] == "—", "sem telefone vira travessão"

    def test_lista_vazia_nao_quebra(self):
        secoes = relatorios.secoes_oradores([])
        assert _linhas(secoes) == []
        assert any("Nenhum orador" in s["vazio"] for s in secoes)


class TestCongregacoes:
    def test_junta_dia_e_horario(self):
        secoes = relatorios.secoes_congregacoes(
            [{"nome": "Central", "responsavel": "João", "telefone": "9",
              "dia_semana": "Domingo", "horario": "09:00", "endereco": "Rua A"}]
        )
        assert _tabelas(secoes)[0]["linhas"][0][3] == "Domingo 09:00"

    def test_sem_congregacao_nao_quebra(self):
        assert _linhas(relatorios.secoes_congregacoes([])) == []


class TestTemasEPresidentes:
    def test_temas_contam_os_nunca_feitos(self):
        _limpar()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM temas")
            conn.execute("INSERT INTO temas (nr, titulo) VALUES (1, 'Um'), (2, 'Dois')")
            conn.commit()
        finally:
            conn.close()
        secoes = relatorios.secoes_temas()
        assert len(_linhas(secoes)) == 2
        assert any("2 ainda não apresentado" in s["descricao"] for s in secoes)

    def test_presidentes_saem_na_ordem_do_rodizio(self):
        _limpar()
        database.salvar_presidente_cadastro("Primeiro", "Ancião")
        database.salvar_presidente_cadastro("Segundo", "Servo Ministerial")

        linhas = _linhas(relatorios.secoes_presidentes())
        assert [li[0] for li in linhas] == ["1", "2"]
        assert [li[1] for li in linhas] == ["Primeiro", "Segundo"]


class TestPdfDeVerdade:
    """O PDF precisa sair de fato — erro de largura de coluna só aparece aqui."""

    @pytest.mark.parametrize(
        "montar",
        [
            lambda: relatorios.secoes_programacao(2026),
            lambda: relatorios.secoes_temas(),
            lambda: relatorios.secoes_presidentes(),
            lambda: relatorios.secoes_congregacoes(
                [{"nome": "C", "responsavel": "R", "telefone": "9",
                  "dia_semana": "Domingo", "horario": "09:00", "endereco": "Rua A"}]
            ),
            lambda: relatorios.secoes_oradores(
                [{"nome": "Ana", "categoria": "Ancião", "congregacao": "Central",
                  "telefone": "1", "temas": "1"}]
            ),
        ],
    )
    def test_gera_arquivo(self, montar):
        from pathlib import Path

        from pdf_relatorios import gerar_pdf_secoes

        _limpar()
        caminho, erro = gerar_pdf_secoes(montar(), "Teste", "sub", "Teste")
        assert erro is None, erro
        assert Path(caminho).stat().st_size > 500, "PDF saiu vazio"

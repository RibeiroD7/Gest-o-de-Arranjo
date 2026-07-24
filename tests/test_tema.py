"""Testes da escala de fonte (acessibilidade) e da sua persistência."""

import database
import tema


class TestEscalaFonte:
    def teardown_method(self):
        tema.definir_escala(1.0)

    def test_padrao_nao_altera_tamanhos(self):
        tema.definir_escala(1.0)
        assert tema.fonte(13) == 13
        assert tema.LARGURA_COL_DATA_MES == 76
        assert tema.LARGURA_BARRA_LATERAL == 192

    def test_escala_maior_aumenta_fonte_e_larguras(self):
        tema.definir_escala(1.5)
        assert tema.fonte(10) == 15
        assert tema.LARGURA_COL_DATA_MES == 114  # 76 * 1.5
        assert tema.LARGURA_BARRA_LATERAL == 288  # 192 * 1.5

    def test_tamanho_minimo_legivel(self):
        tema.definir_escala(0.9)
        assert tema.fonte(8) >= 8

    def test_limites(self):
        tema.definir_escala(99)
        assert tema.escala_atual() == tema.ESCALA_MAX
        tema.definir_escala(0.01)
        assert tema.escala_atual() == tema.ESCALA_MIN


class TestPersistenciaEscala:
    def teardown_method(self):
        database.salvar_escala_fonte(1.0)
        tema.definir_escala(1.0)

    def test_ida_e_volta(self):
        conn = database.get_connection()
        try:
            database.create_tables(conn)
        finally:
            conn.close()
        database.salvar_escala_fonte(1.3)
        assert database.carregar_escala_fonte() == 1.3

    def test_upsert_sem_linha_de_configuracao(self):
        """Instalação nova: a linha id=1 pode não existir ainda."""
        conn = database.get_connection()
        try:
            database.create_tables(conn)
            conn.execute("DELETE FROM configuracoes")
            conn.commit()
        finally:
            conn.close()
        database.salvar_escala_fonte(1.15)
        assert database.carregar_escala_fonte() == 1.15

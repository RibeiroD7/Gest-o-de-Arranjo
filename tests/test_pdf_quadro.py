"""Nome do PDF do Quadro de Anúncios.

O arquivo é enviado para a pasta da congregação como sai do app, então o nome
é contrato: mudar aqui obriga alguém a renomear na mão a cada dois meses.
"""

from pdf_quadro import PARES_MESES, _nome_arquivo, par_meses_do_mes


class TestNomeDoArquivo:
    def test_formato_usado_na_pasta_da_congregacao(self):
        assert _nome_arquivo(9) == "DISCURSOS PÚBLICOS - SETEMBRO-OUTUBRO.pdf"

    def test_mes_com_cedilha_sobe_para_maiuscula_certa(self):
        # "Março".upper() é MARÇO, não MARCO nem MARÇO sem cedilha.
        assert _nome_arquivo(3) == "DISCURSOS PÚBLICOS - MARÇO-ABRIL.pdf"

    def test_os_seis_pares_do_ano_saem_nomeados(self):
        nomes = [_nome_arquivo(inicio) for inicio, _ in PARES_MESES]
        assert nomes == [
            "DISCURSOS PÚBLICOS - JANEIRO-FEVEREIRO.pdf",
            "DISCURSOS PÚBLICOS - MARÇO-ABRIL.pdf",
            "DISCURSOS PÚBLICOS - MAIO-JUNHO.pdf",
            "DISCURSOS PÚBLICOS - JULHO-AGOSTO.pdf",
            "DISCURSOS PÚBLICOS - SETEMBRO-OUTUBRO.pdf",
            "DISCURSOS PÚBLICOS - NOVEMBRO-DEZEMBRO.pdf",
        ]

    def test_outubro_cai_no_mesmo_arquivo_que_setembro(self):
        """gerar_quadro_anuncios normaliza o mês escolhido para o par dele."""
        setembro = _nome_arquivo(par_meses_do_mes(9)[0])
        outubro = _nome_arquivo(par_meses_do_mes(10)[0])
        assert setembro == outubro == "DISCURSOS PÚBLICOS - SETEMBRO-OUTUBRO.pdf"


class TestDiaDaSemanaNoQuadro:
    """O cabeçalho de cada data sai da própria data, não de um dia fixo."""

    def test_nome_do_dia_vem_da_data(self):
        from datetime import date

        from pdf_quadro import NOMES_DIA_SEMANA

        assert NOMES_DIA_SEMANA[date(2021, 6, 6).weekday()] == "DOMINGO"
        assert NOMES_DIA_SEMANA[date(2026, 7, 4).weekday()] == "SÁBADO"
        # A Celebração cai em qualquer dia; o rótulo acompanha.
        assert NOMES_DIA_SEMANA[date(2026, 4, 2).weekday()] == "QUINTA-FEIRA"

    def test_a_lista_cobre_a_semana_toda(self):
        from pdf_quadro import NOMES_DIA_SEMANA

        assert len(NOMES_DIA_SEMANA) == 7


class TestQuadroSegueALinhaDoTempo:
    """Um quadro de época de domingo não pode ser montado com o sábado de hoje."""

    def test_datas_do_mes_seguem_o_periodo(self):
        import database
        from pdf_quadro import carregar_dados_mes

        conn = database.get_connection()
        try:
            database.create_tables(conn)
            conn.execute("DELETE FROM reuniao_historico")
            conn.commit()
        finally:
            conn.close()
        import main

        main.salvar_configuracao({
            "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
            "coordenador_discursos": "", "telefone_coordenador": "",
            "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
        })
        database.salvar_reuniao_historico("2020-05", "Domingo")
        database.salvar_reuniao_historico("2024-01", "Sábado")

        assert all(li["data"].weekday() == 6 for li in carregar_dados_mes(2021, 6))
        assert all(li["data"].weekday() == 5 for li in carregar_dados_mes(2024, 1))
        # Antes do primeiro período, vale a configuração.
        assert all(li["data"].weekday() == 5 for li in carregar_dados_mes(2019, 6))


class TestTracoQuandoNaoHaPresidente:
    """Campo vazio no quadro impresso parece esquecimento, não "a definir"."""

    def _linhas(self):
        import database
        import main

        conn = database.get_connection()
        try:
            database.create_tables(conn)
            for tabela in ("presidentes", "datas_especiais", "reuniao_historico"):
                conn.execute(f"DELETE FROM {tabela}")
            conn.commit()
        finally:
            conn.close()
        main.salvar_configuracao({
            "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
            "coordenador_discursos": "", "telefone_coordenador": "",
            "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
        })
        from pdf_quadro import carregar_dados_mes

        return carregar_dados_mes(2026, 9)

    def test_a_semana_sem_presidente_vem_com_traco(self):
        assert all(linha["presidente"] == "—" for linha in self._linhas())

    def test_a_previa_do_celular_mostra_o_traco(self):
        import flet

        import main

        dados = self._linhas()
        controle = main._preview_quadro_mobile(2026, 9, dados, "Minha")
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

        varrer(controle)
        assert any(t.startswith("PRESIDENTE:") and "—" in t for t in textos)
        assert not any(t.strip() == "PRESIDENTE:" for t in textos)

    def test_o_pdf_sai_com_o_traco(self):
        import pytest

        pypdf = pytest.importorskip("pypdf")
        self._linhas()
        from pdf_quadro import gerar_quadro_anuncios

        caminho, erro = gerar_quadro_anuncios(2026, 9)
        assert erro is None
        texto = pypdf.PdfReader(caminho).pages[0].extract_text()
        assert "PRESIDENTE:" in texto
        assert "PRESIDENTE: —" in " ".join(texto.split())

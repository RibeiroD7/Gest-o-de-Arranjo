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

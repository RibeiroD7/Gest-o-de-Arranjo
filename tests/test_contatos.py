"""Leitura da agenda exportada do celular (src/contatos.py).

O Flet não abre os contatos do aparelho, então a associação passa pelo .vcf
que o próprio celular exporta. Cada aparelho exporta num dialeto um pouco
diferente — estes testes travam os que aparecem na prática.
"""

import pytest

from contatos import Contato, filtrar_contatos, formatar_telefone, ler_vcard

VCARD_ANDROID = """BEGIN:VCARD
VERSION:3.0
N:Barbosa;Danilo;;;
FN:Danilo Reis
TEL;TYPE=CELL:(11) 95555-4444
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Fábio Moreira
TEL;TYPE=CELL:+55 11 94444-3333
TEL;TYPE=HOME:1133334444
END:VCARD
"""


class TestLerVcard:
    def test_le_nome_e_telefone(self):
        contatos = ler_vcard(VCARD_ANDROID)
        assert contatos == [
            Contato("Danilo Reis", ["11955554444"]),
            Contato("Fábio Moreira", ["+5511944443333", "1133334444"]),
        ]

    def test_ordena_por_nome_ignorando_acento(self):
        vcf = "".join(
            f"BEGIN:VCARD\nFN:{nome}\nTEL:11999999999\nEND:VCARD\n"
            for nome in ("Ítalo", "Ana", "Zeca", "Ângela")
        )
        assert [c.nome for c in ler_vcard(vcf)] == ["Ana", "Ângela", "Ítalo", "Zeca"]

    def test_descarta_contato_sem_telefone(self):
        vcf = "BEGIN:VCARD\nFN:Sem Numero\nEMAIL:x@y.z\nEND:VCARD\n"
        assert ler_vcard(vcf) == []

    def test_monta_o_nome_pelo_campo_n_quando_nao_ha_fn(self):
        vcf = "BEGIN:VCARD\nN:Rodrigues;Isaias;Santos;;\nTEL:11999999999\nEND:VCARD\n"
        assert ler_vcard(vcf)[0].nome == "Isaias Santos Rodrigues"

    def test_vcard_21_com_quoted_printable(self):
        """Agendas antigas mandam o nome codificado; sem decodificar vira lixo."""
        vcf = (
            "BEGIN:VCARD\r\n"
            "VERSION:2.1\r\n"
            "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Jo=C3=A3o Ruas\r\n"
            "TEL;CELL:11988887777\r\n"
            "END:VCARD\r\n"
        )
        assert ler_vcard(vcf)[0].nome == "Marcelo Bastos"

    def test_vcard_40_com_prefixo_tel(self):
        vcf = "BEGIN:VCARD\nVERSION:4.0\nFN:Rafael Pires\nTEL;VALUE=uri:tel:+5511988887777\nEND:VCARD\n"
        assert ler_vcard(vcf)[0].telefone == "+5511988887777"

    def test_linha_dobrada_e_remontada(self):
        """O vCard quebra linhas longas e marca a continuação com um espaço."""
        vcf = "BEGIN:VCARD\nFN:Adriano Prado\n  Medeiros\nTEL:11999999999\nEND:VCARD\n"
        assert ler_vcard(vcf)[0].nome == "Adriano Prado"

    def test_grupo_antes_da_propriedade(self):
        """O iPhone exporta com grupos: `item1.TEL:...`."""
        vcf = "BEGIN:VCARD\nFN:Ivan Barros\nitem1.TEL:11977776666\nEND:VCARD\n"
        assert ler_vcard(vcf)[0].telefone == "11977776666"

    def test_arquivo_truncado_aproveita_o_ultimo(self):
        vcf = "BEGIN:VCARD\nFN:Danilo\nTEL:11966665555\n"
        assert ler_vcard(vcf)[0].nome == "Danilo"

    def test_repetidos_entram_uma_vez_so(self):
        assert len(ler_vcard(VCARD_ANDROID + VCARD_ANDROID)) == 2

    @pytest.mark.parametrize("texto", ["", "lixo qualquer", "BEGIN:VCARD\nEND:VCARD\n"])
    def test_entrada_invalida_nao_quebra(self, texto):
        assert ler_vcard(texto) == []


class TestFormatarTelefone:
    def test_tira_a_formatacao(self):
        assert formatar_telefone("(11) 95555-4444") == "11955554444"

    def test_preserva_o_codigo_do_pais(self):
        assert formatar_telefone("+55 (11) 95555-4444") == "+5511955554444"

    def test_vazio(self):
        assert formatar_telefone("") == ""
        assert formatar_telefone(None) == ""


class TestFiltrarContatos:
    def _contatos(self):
        return [
            Contato("Danilo Reis", ["11955554444"]),
            Contato("Fábio Moreira", ["11944443333"]),
            Contato("Ângela Souza", ["11933332222"]),
        ]

    def test_por_nome_ignorando_acento_e_caixa(self):
        assert [c.nome for c in filtrar_contatos(self._contatos(), "angela")] == [
            "Ângela Souza"
        ]

    def test_por_pedaco_do_numero(self):
        assert [c.nome for c in filtrar_contatos(self._contatos(), "9444")] == [
            "Fábio Moreira"
        ]

    def test_numero_digitado_com_formatacao(self):
        assert [c.nome for c in filtrar_contatos(self._contatos(), "(11) 9555")] == [
            "Danilo Reis"
        ]

    def test_termo_vazio_devolve_tudo(self):
        assert len(filtrar_contatos(self._contatos(), "  ")) == 3

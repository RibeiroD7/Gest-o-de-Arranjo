"""Leitura da agenda exportada do celular (src/contatos.py).

O Flet não abre os contatos do aparelho, então a associação passa pelo .vcf
que o próprio celular exporta. Cada aparelho exporta num dialeto um pouco
diferente — estes testes travam os que aparecem na prática.
"""

import base64

import pytest

from contatos import (
    Contato,
    caminho_foto_contato,
    filtrar_contatos,
    formatar_telefone,
    iniciais_do_nome,
    ler_vcard,
    mascara_telefone,
    mudancas_de_contato,
    salvar_foto_contato,
)

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


class TestMascaraTelefone:
    """Formata enquanto se digita, sem o traço pular de posição a cada tecla."""

    def test_celular_completo(self):
        assert mascara_telefone("11900000000") == "(11) 90000-0000"

    def test_fixo_completo(self):
        assert mascara_telefone("1130000000") == "(11) 3000-0000"

    def test_traco_fica_parado_ao_digitar_celular(self):
        """O 9 do celular já define o corte: o traço nasce no lugar certo."""
        parciais = []
        digitado = ""
        for tecla in "11900000000":
            digitado += tecla
            parciais.append(mascara_telefone(digitado))
        assert parciais == [
            "1",
            "(11)",
            "(11) 9",
            "(11) 95",
            "(11) 952",
            "(11) 9000",
            "(11) 90000",
            "(11) 90000-0",
            "(11) 90000-00",
            "(11) 90000-000",
            "(11) 90000-0000",
        ]

    def test_apagar_no_meio_recalcula(self):
        """O que vale são os dígitos: apagar não deixa separador solto."""
        assert mascara_telefone("(11) 90000-000") == "(11) 90000-000"
        assert mascara_telefone("(11) 9000") == "(11) 9000"

    def test_reaplicar_nao_muda(self):
        uma = mascara_telefone("11900000000")
        assert mascara_telefone(uma) == uma

    def test_codigo_do_pais(self):
        assert mascara_telefone("+5511900000000") == "+55 (11) 90000-0000"
        assert mascara_telefone("5511900000000") == "+55 (11) 90000-0000"

    def test_numero_grande_demais_fica_sem_mascara(self):
        """Não inventa separador onde não se sabe o formato."""
        assert mascara_telefone("551190000000012") == "+55 1190000000012"

    @pytest.mark.parametrize("entrada", ["", "   ", "abc", None])
    def test_entrada_sem_digito(self, entrada):
        assert mascara_telefone(entrada) == ""


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


class TestVinculoComAgenda:
    """O telefone salvo acompanha o que muda nos contatos do celular."""

    def _vinculos(self):
        return [
            {
                "tabela": "presidentes_cadastro",
                "id": 1,
                "contato_id": "chave-lucas",
                "nome": "Fábio Moreira",
                "telefone": "(11) 94444-3333",
            }
        ]

    def test_numero_novo_na_agenda_vira_mudanca(self):
        lidos = [{"id": "chave-lucas", "nome": "Lucas M.", "telefones": ["11955554444"]}]
        (mudanca,) = mudancas_de_contato(self._vinculos(), lidos)
        assert mudanca["telefone"] == "(11) 95555-4444"
        assert mudanca["telefone_antigo"] == "(11) 94444-3333"
        assert mudanca["tabela"] == "presidentes_cadastro"

    def test_numero_igual_nao_gera_escrita(self):
        """Sem isso o app marcaria o banco como alterado a cada abertura."""
        lidos = [{"id": "chave-lucas", "nome": "Lucas", "telefones": ["11944443333"]}]
        assert mudancas_de_contato(self._vinculos(), lidos) == []

    def test_contato_apagado_no_celular_preserva_o_numero(self):
        """Some da agenda mas continua no app: perder o telefone seria pior."""
        assert mudancas_de_contato(self._vinculos(), []) == []

    def test_contato_sem_telefone_e_ignorado(self):
        lidos = [{"id": "chave-lucas", "nome": "Lucas", "telefones": []}]
        assert mudancas_de_contato(self._vinculos(), lidos) == []


class TestFotoDoContato:
    def test_grava_e_encontra(self, tmp_path):
        dados = base64.b64encode(b"conteudo-da-foto").decode()
        caminho = salvar_foto_contato("chave-x", dados, tmp_path)
        assert caminho is not None and caminho.read_bytes() == b"conteudo-da-foto"
        assert caminho_foto_contato("chave-x", tmp_path) == caminho

    def test_sem_foto_apaga_a_anterior(self, tmp_path):
        """Tirar a imagem no celular também tem que sumir do app."""
        salvar_foto_contato("chave-x", base64.b64encode(b"foto").decode(), tmp_path)
        assert salvar_foto_contato("chave-x", None, tmp_path) is None
        assert caminho_foto_contato("chave-x", tmp_path) is None

    def test_contato_sem_foto_nao_tem_caminho(self, tmp_path):
        assert caminho_foto_contato("nunca-salvo", tmp_path) is None
        assert caminho_foto_contato("", tmp_path) is None

    def test_foto_corrompida_nao_quebra(self, tmp_path):
        assert salvar_foto_contato("chave-x", "isso não é base64!!", tmp_path) is None

    def test_chave_com_barra_vira_nome_de_arquivo_valido(self, tmp_path):
        """A chave do Android tem barras, que não valem em nome de arquivo."""
        chave = "0r1-2A3B4C/estranho:demais"
        caminho = salvar_foto_contato(chave, base64.b64encode(b"x").decode(), tmp_path)
        assert caminho is not None and caminho.parent == tmp_path


class TestIniciaisDoNome:
    def test_nome_composto(self):
        assert iniciais_do_nome("Fábio Moreira Pereira") == "LP"

    def test_nome_simples(self):
        assert iniciais_do_nome("Danilo") == "GI"

    def test_vazio(self):
        assert iniciais_do_nome("") == "?"
        assert iniciais_do_nome("   ") == "?"

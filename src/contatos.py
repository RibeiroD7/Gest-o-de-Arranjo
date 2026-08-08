"""Leitura da agenda do celular exportada em vCard (.vcf).

O Flet não expõe os contatos do aparelho — não há como abrir o seletor de
contatos do Android sem um plugin nativo. O caminho que funciona só com o que
o app já tem é o arquivo que o próprio celular exporta: em Contatos →
Configurações → Exportar, o Android grava um ``.vcf`` com nomes e telefones.
O app lê esse arquivo e deixa o coordenador escolher o contato, em vez de
digitar o número.

Só nome e telefone são aproveitados, e nada da agenda é gravado: o que fica
salvo (e vai para o backup) é apenas o número do orador ou presidente
escolhido.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["Contato", "ler_vcard", "filtrar_contatos", "formatar_telefone"]


class Contato:
    """Um contato lido do arquivo: nome e os telefones encontrados."""

    __slots__ = ("nome", "telefones")

    def __init__(self, nome: str, telefones: list[str]) -> None:
        self.nome = nome
        self.telefones = telefones

    @property
    def telefone(self) -> str:
        """O primeiro telefone — o que preenche o campo ao escolher."""
        return self.telefones[0] if self.telefones else ""

    def __repr__(self) -> str:  # pragma: no cover — só para depuração
        return f"Contato({self.nome!r}, {self.telefones!r})"

    def __eq__(self, outro) -> bool:
        return (
            isinstance(outro, Contato)
            and (self.nome, self.telefones) == (outro.nome, outro.telefones)
        )


def _desdobrar_linhas(texto: str) -> list[str]:
    """Junta as continuações do vCard (linha seguinte começando com espaço).

    O formato quebra linhas longas e marca a continuação com um espaço ou tab
    no início — sem desdobrar, um nome comprido chegaria partido ao meio.
    """
    linhas: list[str] = []
    for bruta in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if bruta[:1] in (" ", "\t") and linhas:
            linhas[-1] += bruta[1:]
        else:
            linhas.append(bruta)
    return linhas


def _decodificar_valor(propriedade: str, valor: str) -> str:
    """Resolve o quoted-printable que aparece em agendas antigas."""
    if "quoted-printable" not in propriedade.lower():
        return valor
    try:
        import quopri

        return quopri.decodestring(valor.encode("utf-8")).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — valor estranho: devolve como veio
        return valor


def _nome_de_n(valor: str) -> str:
    """Monta o nome a partir do campo ``N`` (sobrenome;nome;meio;...)."""
    partes = [p.strip() for p in valor.split(";")]
    sobrenome = partes[0] if partes else ""
    proprio = partes[1] if len(partes) > 1 else ""
    meio = partes[2] if len(partes) > 2 else ""
    return " ".join(p for p in (proprio, meio, sobrenome) if p).strip()


def formatar_telefone(numero: str) -> str:
    """Limpa o número mantendo só dígitos e um ``+`` inicial, se houver."""
    numero = (numero or "").strip()
    mais = numero.startswith("+")
    digitos = re.sub(r"\D", "", numero)
    return ("+" if mais else "") + digitos


def ler_vcard(texto: str) -> list[Contato]:
    """Lê um arquivo .vcf e devolve os contatos que têm telefone.

    Aceita vCard 2.1, 3.0 e 4.0 — o que muda entre eles (parâmetros na
    propriedade, ``TEL;TYPE=CELL`` vs ``TEL;CELL``, ``tel:`` na frente do
    número) é tratado aqui. Contatos sem telefone são descartados: não servem
    para o que o app faz com eles.

    Returns:
        Contatos em ordem alfabética, sem repetir nome+telefone.
    """
    contatos: list[Contato] = []
    nome_fn = ""
    nome_n = ""
    telefones: list[str] = []
    dentro = False

    def fechar():
        nome = nome_fn or nome_n
        if dentro and nome and telefones:
            contatos.append(Contato(nome, list(dict.fromkeys(telefones))))

    for linha in _desdobrar_linhas(texto):
        limpa = linha.strip()
        if not limpa:
            continue
        acima = limpa.upper()
        if acima.startswith("BEGIN:VCARD"):
            # BEGIN sem END antes (arquivo malformado): começa o cartão do zero.
            dentro, nome_fn, nome_n, telefones = True, "", "", []
            continue
        if acima.startswith("END:VCARD"):
            fechar()
            dentro, nome_fn, nome_n, telefones = False, "", "", []
            continue
        if not dentro or ":" not in limpa:
            continue

        propriedade, _, valor = limpa.partition(":")
        # Alguns arquivos usam grupos ("item1.TEL:..."); o nome vem depois do ponto.
        nome_prop = propriedade.split(";")[0].split(".")[-1].upper()
        valor = _decodificar_valor(propriedade, valor).strip()
        if nome_prop == "FN":
            nome_fn = valor
        elif nome_prop == "N":
            nome_n = _nome_de_n(valor)
        elif nome_prop == "TEL":
            numero = formatar_telefone(valor.removeprefix("tel:"))
            if numero:
                telefones.append(numero)

    fechar()  # arquivo truncado, sem o END final

    vistos: set[tuple[str, str]] = set()
    unicos: list[Contato] = []
    for contato in contatos:
        chave = (contato.nome.casefold(), contato.telefone)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(contato)
    unicos.sort(key=lambda c: _chave_ordenacao(c.nome))
    return unicos


def _chave_ordenacao(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def filtrar_contatos(contatos: list[Contato], termo: str) -> list[Contato]:
    """Filtra por nome ou telefone, ignorando acentos e maiúsculas."""
    termo = (termo or "").strip()
    if not termo:
        return contatos
    alvo = _chave_ordenacao(termo)
    digitos = re.sub(r"\D", "", termo)
    return [
        c
        for c in contatos
        if alvo in _chave_ordenacao(c.nome)
        or (digitos and any(digitos in t for t in c.telefones))
    ]

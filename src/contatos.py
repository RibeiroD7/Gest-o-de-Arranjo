"""Apoio para telefones e para os contatos vinculados à agenda do celular.

Três coisas moram aqui, todas sem depender do Flet (por isso são testáveis):

- **Máscara de telefone** (``mascara_telefone``), aplicada enquanto se digita.
- **Leitura de vCard** (``ler_vcard``), o caminho do computador e a reserva do
  celular: o aparelho exporta a agenda em ``.vcf`` (Contatos → Configurações →
  Exportar) e o app lê dali. No Android o normal é o seletor nativo, na
  extensão ``extensoes/flet_contatos``.
- **Vínculo com o contato** (``mudancas_de_contato``, foto em cache), que faz o
  telefone salvo acompanhar sozinho o que mudar na agenda.

Nenhuma agenda é gravada: do contato escolhido ficam só o número, a chave dele
(para reler depois) e a foto em cache — e a foto fica fora do backup.
"""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from pathlib import Path

__all__ = [
    "Contato",
    "ler_vcard",
    "filtrar_contatos",
    "formatar_telefone",
    "mascara_telefone",
    "iniciais_do_nome",
    "caminho_foto_contato",
    "salvar_foto_contato",
    "mudancas_de_contato",
]


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


def mascara_telefone(texto: str, digitando: bool = True) -> str:
    """Formata um telefone brasileiro.

    Vai montando a máscara conforme os dígitos chegam — ``11900000000`` vira
    ``(11) 90000-0000`` — sem atrapalhar quem apaga no meio: o que vale são os
    dígitos, os separadores são recalculados a cada tecla.

    ``digitando=True`` (o padrão, dos campos do formulário) assume que os dois
    primeiros dígitos são o DDD desde o começo, para o parêntese não pular de
    lugar. Já um número que chega PRONTO — da agenda do celular — pode não ter
    DDD nenhum, e aí ``digitando=False`` evita o erro de transformar os dois
    primeiros dígitos de ``988887777`` num DDD "98" que não existe.

    O ``+55`` é descartado (todo mundo aqui é do Brasil e o link do
    WhatsApp recoloca o país). O que não couber em formato brasileiro conhecido
    é devolvido só com os dígitos, sem separador inventado.
    """
    texto = (texto or "").strip()
    if not texto:
        return ""

    pais = ""
    digitos = re.sub(r"\D", "", texto)
    # O 55 do Brasil é ruído aqui: todo mundo é daqui, e o link do
    # WhatsApp recoloca o país sozinho. Some com ele e mostra só (11) 9…
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    elif texto.startswith("+"):
        # Número estrangeiro de verdade: preserva como veio, sem máscara do BR.
        return "+" + digitos

    if len(digitos) > 11:
        # Fora dos formatos do Brasil: não force máscara no lugar errado.
        return (pais + digitos).strip()

    def _com_traco(numero: str) -> str:
        """Separa o assinante: celular corta depois de 5; fixo, depois de 4."""
        corte = 5 if numero.startswith("9") else 4
        if len(numero) <= corte:
            return numero
        return f"{numero[:corte]}-{numero[corte:]}"

    # Número pronto e curto demais para ter DDD (8 ou 9 dígitos): formata só o
    # assinante. Fingir um DDD aqui é o que fazia 988887777 virar (98) 8887-777.
    if not digitando and len(digitos) < 10:
        return pais + _com_traco(digitos)

    if len(digitos) < 2:
        return pais + digitos
    if len(digitos) == 2:
        return f"{pais}({digitos})"
    return f"{pais}({digitos[:2]}) {_com_traco(digitos[2:])}"


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


# ---------------------------------------------------------------------------
# Vínculo com um contato da agenda: foto e sincronização
# ---------------------------------------------------------------------------


def iniciais_do_nome(nome: str) -> str:
    """Até duas iniciais para o avatar de quem não tem foto."""
    partes = [p for p in re.split(r"\s+", (nome or "").strip()) if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _nome_arquivo_foto(contato_id: str) -> str:
    """Nome de arquivo seguro e estável para a chave do contato.

    A chave do Android tem barras e outros caracteres que não valem em nome de
    arquivo, então o que vai para o disco é um resumo dela.
    """
    return hashlib.sha1((contato_id or "").encode("utf-8")).hexdigest() + ".jpg"


def caminho_foto_contato(contato_id: str, pasta: Path) -> Path | None:
    """Caminho da foto guardada desse contato, ou None se não houver."""
    if not contato_id:
        return None
    caminho = pasta / _nome_arquivo_foto(contato_id)
    return caminho if caminho.exists() else None


def salvar_foto_contato(contato_id: str, foto_base64: str | None, pasta: Path) -> Path | None:
    """Grava (ou apaga) a foto do contato na pasta de fotos.

    Recebe o que a agenda devolveu em base64. Sem foto, remove a que existia —
    assim tirar a imagem no celular também some do app.
    """
    if not contato_id:
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / _nome_arquivo_foto(contato_id)
    if not foto_base64:
        caminho.unlink(missing_ok=True)
        return None
    try:
        caminho.write_bytes(base64.b64decode(foto_base64))
    except (ValueError, OSError):
        # Foto corrompida não pode impedir a sincronização do telefone.
        return None
    return caminho


def _so_digitos(texto: str) -> str:
    """Só os dígitos — o que de fato identifica um telefone."""
    return re.sub(r"\D", "", texto or "")


def mudancas_de_contato(
    vinculos: list[dict], contatos: list[dict]
) -> list[dict]:
    """Compara o que está salvo com o que a agenda devolveu.

    Args:
        vinculos: ``[{tabela, id, contato_id, nome, telefone}]`` do banco.
        contatos: ``[{id, nome, telefones, foto}]`` lidos do aparelho.

    A comparação é feita pelos **dígitos**, não pelo texto formatado: assim uma
    mudança de máscara entre versões do app não faz o telefone de todo mundo
    "mudar" na abertura seguinte.

    Returns:
        Uma entrada por pessoa cujo telefone mudou, no formato
        ``{tabela, id, contato_id, nome, telefone, telefone_antigo, foto}``.
        Contatos que a agenda não devolveu (apagados, ou de outro aparelho) não
        entram: manter o número antigo é melhor do que apagá-lo.
    """
    por_id = {c.get("id"): c for c in contatos if c.get("id")}
    mudancas = []
    for vinculo in vinculos:
        contato = por_id.get(vinculo.get("contato_id"))
        if not contato:
            continue
        telefones = [
            numero
            for numero in (formatar_telefone(t) for t in contato.get("telefones") or [])
            if numero
        ]
        if not telefones:
            continue
        # O número vem PRONTO da agenda: não inventar DDD se ele não tiver.
        novo = mascara_telefone(telefones[0], digitando=False)
        salvo = vinculo.get("telefone", "")
        # Os dois lados passam pela MESMA normalização antes de comparar: um
        # número salvo como "+55 (11) 9…" por uma versão antiga tem 13 dígitos
        # e o novo tem 11 — sem isso eles diferiam para sempre, e o app dizia
        # "telefone atualizado" a cada abertura.
        if _so_digitos(novo) == _so_digitos(
            mascara_telefone(salvo, digitando=False)
        ):
            continue
        mudancas.append(
            {
                **vinculo,
                "telefone": novo,
                "telefone_antigo": vinculo.get("telefone", ""),
                "nome_contato": contato.get("nome", ""),
                "foto": contato.get("foto"),
            }
        )
    return mudancas

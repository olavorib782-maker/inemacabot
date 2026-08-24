from __future__ import annotations

import pytest

from leadsheet_builder import LeadsheetBuilder, LeadsheetValidationError


EXPECTED_FOUR_BARS = """(title Guide Tones)
(composer InemacaBot)
(meter 4 4)
(key 0)
(tempo 120)

(part
    (type chords)
)

Dm7 | G7 | Cmaj7 | Cmaj7 |

(part
    (type melody)
    (stave treble)
)

r1+1+1+1
"""


def test_quatro_acordes_geram_quatro_compassos_e_placeholder() -> None:
    rendered = LeadsheetBuilder().render_guidetones(
        ["Dm7", "G7", "Cmaj7", "Cmaj7"]
    )

    assert rendered == EXPECTED_FOUR_BARS
    assert "Dm7 | G7 | Cmaj7 | Cmaj7 |" in rendered
    assert rendered.endswith("r1+1+1+1\n")


@pytest.mark.parametrize(
    ("chords", "placeholder"),
    [(["Cmaj7"], "r1"), (["Dm7", "G7"], "r1+1")],
)
def test_placeholder_corresponde_ao_numero_de_compassos(
    chords: list[str], placeholder: str
) -> None:
    assert LeadsheetBuilder().render_guidetones(chords).endswith(
        f"{placeholder}\n"
    )


@pytest.mark.parametrize("slash_chord", ["D/F#", "G7/B"])
def test_preserva_slash_chords(slash_chord: str) -> None:
    rendered = LeadsheetBuilder().render_guidetones([slash_chord])

    assert f"{slash_chord} |" in rendered


def test_progressao_termina_com_barra() -> None:
    rendered = LeadsheetBuilder().render_guidetones(["Cmaj7", "Fmaj7"])

    assert "Cmaj7 | Fmaj7 |\n" in rendered


def test_lista_vazia_e_rejeitada() -> None:
    with pytest.raises(LeadsheetValidationError, match="ao menos um"):
        LeadsheetBuilder().render_guidetones([])


def test_mais_de_64_compassos_e_rejeitado() -> None:
    with pytest.raises(LeadsheetValidationError, match="no máximo 64"):
        LeadsheetBuilder().render_guidetones(["Cmaj7"] * 65)


@pytest.mark.parametrize("empty_chord", ["", "   "])
def test_simbolo_vazio_e_rejeitado(empty_chord: str) -> None:
    with pytest.raises(LeadsheetValidationError, match="não pode ser vazio"):
        LeadsheetBuilder().render_guidetones([empty_chord])


def test_simbolo_maior_que_32_caracteres_e_rejeitado() -> None:
    with pytest.raises(LeadsheetValidationError, match="no máximo 32"):
        LeadsheetBuilder().render_guidetones(["C" * 33])


def test_barra_isolada_e_rejeitada() -> None:
    with pytest.raises(LeadsheetValidationError, match="repetição"):
        LeadsheetBuilder().render_guidetones(["/"])


@pytest.mark.parametrize("character", ["\n", "\r", "\t", "\x00", "\x1f", "\x7f"])
def test_controles_e_whitespace_sao_rejeitados(character: str) -> None:
    with pytest.raises(LeadsheetValidationError):
        LeadsheetBuilder().render_guidetones([f"C{character}maj7"])


@pytest.mark.parametrize("character", ["\n", "\r", "\t"])
def test_controles_nas_extremidades_nao_sao_removidos_pelo_strip(
    character: str,
) -> None:
    with pytest.raises(LeadsheetValidationError, match="caractere de controle"):
        LeadsheetBuilder().render_guidetones([f"{character}Cmaj7"])


@pytest.mark.parametrize("character", ["(", ")", '"', "'", ";", "|"])
def test_caracteres_de_injecao_sao_rejeitados(character: str) -> None:
    with pytest.raises(LeadsheetValidationError, match="caractere proibido"):
        LeadsheetBuilder().render_guidetones([f"C{character}maj7"])


@pytest.mark.parametrize("whitespace", [" ", "\u00a0"])
def test_whitespace_interno_e_rejeitado(whitespace: str) -> None:
    with pytest.raises(LeadsheetValidationError, match="whitespace interno"):
        LeadsheetBuilder().render_guidetones([f"C{whitespace}maj7"])


def test_strip_ocorre_somente_nas_extremidades() -> None:
    rendered = LeadsheetBuilder().render_guidetones(["  G7alt  ", " Db7#11 "])

    assert "G7alt | Db7#11 |" in rendered


def test_metadados_sao_fixos() -> None:
    rendered = LeadsheetBuilder().render_guidetones(["D/F#"])

    assert rendered.startswith(
        "(title Guide Tones)\n"
        "(composer InemacaBot)\n"
        "(meter 4 4)\n"
        "(key 0)\n"
        "(tempo 120)\n"
    )


def test_saida_e_deterministica() -> None:
    builder = LeadsheetBuilder()
    chords = ["Dm7", "G7", "Cmaj7", "Cmaj7"]

    assert builder.render_guidetones(chords) == builder.render_guidetones(chords)


def test_texto_unico_nao_e_aceito_como_sequencia_de_acordes() -> None:
    with pytest.raises(LeadsheetValidationError, match="sequência"):
        LeadsheetBuilder().render_guidetones("Cmaj7")


def test_item_nao_textual_e_rejeitado() -> None:
    with pytest.raises(LeadsheetValidationError, match="deve ser um texto"):
        LeadsheetBuilder().render_guidetones(["Cmaj7", 7])  # type: ignore[list-item]

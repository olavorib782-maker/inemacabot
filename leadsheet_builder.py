"""Serialização determinística de entradas mínimas do Impro-Visor."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence


class LeadsheetValidationError(ValueError):
    """Indica que uma progressão não pode ser serializada com segurança."""


class LeadsheetBuilder:
    """Cria leadsheets mínimos sem interpretar semanticamente os acordes."""

    MAX_BARS = 64
    MAX_CHORD_LENGTH = 32

    _FORBIDDEN_CHARACTERS = frozenset("()\"';|")

    def render_guidetones(self, chords: Sequence[str]) -> str:
        """Retorna um leadsheet 4/4 com um acorde em cada compasso."""
        if isinstance(chords, (str, bytes)):
            raise LeadsheetValidationError("A progressão deve ser uma sequência de acordes.")

        normalized_chords = tuple(self._normalize_chord(chord) for chord in chords)
        if not normalized_chords:
            raise LeadsheetValidationError("A progressão deve ter ao menos um compasso.")
        if len(normalized_chords) > self.MAX_BARS:
            raise LeadsheetValidationError(
                f"A progressão deve ter no máximo {self.MAX_BARS} compassos."
            )

        progression = " | ".join(normalized_chords) + " |"
        melody_placeholder = "r1" + "+1" * (len(normalized_chords) - 1)
        return (
            "(title Guide Tones)\n"
            "(composer InemacaBot)\n"
            "(meter 4 4)\n"
            "(key 0)\n"
            "(tempo 120)\n"
            "\n"
            "(part\n"
            "    (type chords)\n"
            ")\n"
            "\n"
            f"{progression}\n"
            "\n"
            "(part\n"
            "    (type melody)\n"
            "    (stave treble)\n"
            ")\n"
            "\n"
            f"{melody_placeholder}\n"
        )

    def _normalize_chord(self, chord: str) -> str:
        if not isinstance(chord, str):
            raise LeadsheetValidationError("Cada acorde deve ser um texto.")
        if any(unicodedata.category(character) == "Cc" for character in chord):
            raise LeadsheetValidationError("O símbolo do acorde contém caractere de controle.")

        normalized = chord.strip()
        if not normalized:
            raise LeadsheetValidationError("O símbolo do acorde não pode ser vazio.")
        if len(normalized) > self.MAX_CHORD_LENGTH:
            raise LeadsheetValidationError(
                f"O símbolo do acorde deve ter no máximo {self.MAX_CHORD_LENGTH} caracteres."
            )
        if normalized == "/":
            raise LeadsheetValidationError("A repetição de acorde não é aceita.")
        if any(character.isspace() for character in normalized):
            raise LeadsheetValidationError("O símbolo do acorde não pode conter whitespace interno.")
        if any(character in self._FORBIDDEN_CHARACTERS for character in normalized):
            raise LeadsheetValidationError("O símbolo do acorde contém caractere proibido.")

        return normalized

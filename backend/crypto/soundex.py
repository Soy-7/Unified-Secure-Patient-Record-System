"""
crypto/soundex.py — Classic Soundex phonetic algorithm.

Purpose: Allow fuzzy patient name search by phonetic similarity.
A search for "Sharma" will also match "Sharmaa" or "Sharme" because
they all encode to the same Soundex code.

The code is pre-computed at patient creation and stored in the
`soundexCode` field (indexed in MongoDB).  Searches compare the
Soundex of the search query against the index — no full-text scan.

Algorithm (American Soundex):
  1. Keep the first letter (uppercase).
  2. Map remaining letters to digits:
       B, F, P, V         → 1
       C, G, J, K, Q, S, X, Z → 2
       D, T               → 3
       L                  → 4
       M, N               → 5
       R                  → 6
       A, E, I, O, U, H, W, Y → 0 (removed)
  3. Remove consecutive duplicate digits.
  4. Remove all 0s.
  5. Pad with trailing zeros or truncate to exactly 4 characters.

Examples:
  soundex("Smith")   → "S530"
  soundex("Smyth")   → "S530"  (same! so "Smith" search finds "Smyth")
  soundex("Srihari") → "S600"
  soundex("Sharma")  → "S650"
"""

# Soundex digit table — only consonants get a digit
_SOUNDEX_TABLE: dict[str, str] = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2",
    "Q": "2", "S": "2", "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
    # A, E, I, O, U, H, W, Y → not in table (treated as "0" / ignored)
}


def soundex(name: str) -> str:
    """
    Compute the 4-character Soundex code for a name.

    Args:
        name: A person's name (any case, may include spaces — only
              the first word is used).

    Returns:
        A 4-character string: one uppercase letter + three digits.
        Returns "0000" for empty input.

    Examples:
        soundex("Smith")   → "S530"
        soundex("Srihari") → "S600"
        soundex("Sharma")  → "S650"
    """
    if not name:
        return "0000"

    # Use only the first word (ignore middle/last names for the code)
    name = name.strip().split()[0].upper()

    # Remove non-alphabetic characters
    name = "".join(ch for ch in name if ch.isalpha())
    if not name:
        return "0000"

    first_letter = name[0]
    rest         = name[1:]

    # Map each remaining character to its digit (0 = ignored vowel)
    coded = [_SOUNDEX_TABLE.get(ch, "0") for ch in rest]

    # Remove consecutive duplicate digits
    deduped: list[str] = []
    prev = _SOUNDEX_TABLE.get(first_letter, "0")  # skip if first letter == its own code
    for digit in coded:
        if digit != "0" and digit != prev:
            deduped.append(digit)
        prev = digit

    # Build result: first letter + up to 3 digits, padded with zeros
    code = first_letter + "".join(deduped)
    code = (code + "000")[:4]

    return code


def soundex_search(query: str) -> str:
    """
    Convenience wrapper that cleans and Soundex-encodes a search query.

    Args:
        query: Raw search input from the user.

    Returns:
        4-character Soundex code to query the `soundexCode` index.
    """
    return soundex(query.strip())

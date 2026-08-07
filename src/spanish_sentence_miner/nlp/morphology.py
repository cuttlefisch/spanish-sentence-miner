"""Deterministic grammar analysis of a cloze target from spaCy morphology.

The morphological *facts* (tense, mood, person, number, gender) come straight from
spaCy's ``token.morph``; this module normalizes them into a human label and detects
short deterministic *cue phrases* (subjunctive triggers, preterite/imperfect aspect,
ser/estar). Claude Code later turns those cues into a natural-language "why". No LLM
here — pure lookup + regex.
"""

from __future__ import annotations

import re
import unicodedata

from spanish_sentence_miner.enrich.schema import GrammarInfo
from spanish_sentence_miner.nlp.pipeline import Sentence, Token, norm_lemma

_MOOD = {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative", "Cnd": "conditional"}
# NB: spaCy uses Tense=Imp for the *imperfect*; Mood=Imp is the imperative. Always read
# Mood before Tense so the two never collide.
_TENSE = {"Pres": "present", "Past": "preterite", "Imp": "imperfect", "Fut": "future",
          "Pqp": "pluperfect"}
_PERSON = {"1": "1st person", "2": "2nd person", "3": "3rd person"}
_NUMBER = {"Sing": "singular", "Plur": "plural"}
_GENDER = {"Masc": "masculine", "Fem": "feminine"}
_VERBFORM = {"Fin": "finite", "Inf": "infinitive", "Ger": "gerund", "Part": "participle"}

# Subjunctive-triggering cues (subordinators, volition/emotion/doubt matrices, impersonals).
_SUBJUNCTIVE_CUES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bantes de que\b"), "subordinator 'antes de que' (always + subjunctive)"),
    (re.compile(r"\bpara que\b"), "purpose 'para que' (+ subjunctive)"),
    (re.compile(r"\bsin que\b"), "'sin que' (+ subjunctive)"),
    (re.compile(r"\ba menos que\b"), "'a menos que' (+ subjunctive)"),
    (re.compile(r"\ba fin de que\b"), "'a fin de que' (+ subjunctive)"),
    (re.compile(r"\bcon tal de que\b"), "'con tal (de) que' (+ subjunctive)"),
    (re.compile(r"\ben caso de que\b"), "'en caso de que' (+ subjunctive)"),
    (re.compile(r"\bcuando\b"), "'cuando' + future/hypothetical reference (+ subjunctive)"),
    (re.compile(r"\baunque\b"), "concessive 'aunque' (subjunctive when hypothetical)"),
    (re.compile(r"\boj[aá]l[aá]\b"), "'ojalá' (wish, + subjunctive)"),
    (re.compile(r"\bquiz[aá]s?\b"), "'quizá(s)' (doubt, + subjunctive)"),
    (re.compile(r"\btal vez\b"), "'tal vez' (doubt, + subjunctive)"),
    (re.compile(r"\besper\w* que\b"), "verb of hope 'esperar que' (+ subjunctive)"),
    (re.compile(r"\bquier\w* que\b"), "volition 'querer que' (+ subjunctive)"),
    (re.compile(r"\bdud\w* que\b"), "doubt 'dudar que' (+ subjunctive)"),
    (re.compile(r"\bno cre\w* que\b"), "negated belief (+ subjunctive)"),
    (re.compile(r"\b(es|sea|era) (necesario|important\w+|posible|mejor|preciso|raro) que\b"),
     "impersonal expression + que (+ subjunctive)"),
    (re.compile(r"\bpara\b"), "purpose 'para' (+ infinitive/subjunctive)"),
]

# Adverbial reinforcement for the preterite/imperfect aspect contrast.
_PRETERITE_ADV = re.compile(r"\b(de repente|de pronto|de golpe|ayer|anoche|entonces|una vez)\b")
_IMPERFECT_ADV = re.compile(r"\b(siempre|mientras|cada|a menudo|de ni\wo|todos los d\was|"
                            r"generalmente|a veces)\b")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def analyze_grammar(sentence: Sentence, target: Token) -> GrammarInfo:
    """Return deterministic grammar for a cloze target (verb-rich, noun/adj light)."""
    pos = target.pos
    if pos in ("VERB", "AUX"):
        return _verb(sentence, target)
    if pos == "NOUN":
        return _nominal(target, kind="noun")
    if pos == "ADJ":
        return _nominal(target, kind="adjective")
    return GrammarInfo(kind="other")


def _verb(sentence: Sentence, target: Token) -> GrammarInfo:
    m = target.morph_dict
    mood = _MOOD.get(m.get("Mood", ""))
    verbform = _VERBFORM.get(m.get("VerbForm", ""))
    reflexive = m.get("Reflex") == "Yes"
    infinitive = norm_lemma(target.lemma)

    # Tense/aspect only make sense for finite forms. Non-finite (infinitive/gerund/
    # participle) carry Tense=Past etc. in spaCy but that's not a preterite — suppress it.
    # Conditional is a mood in spaCy (Mood=Cnd) with no separate tense.
    if verbform in ("infinitive", "gerund", "participle") or mood == "conditional":
        tense = None
    else:
        tense = _TENSE.get(m.get("Tense", ""))
    person = _PERSON.get(m.get("Person", ""))
    number = _NUMBER.get(m.get("Number", ""))

    label = _verb_label(tense, mood, person, number, verbform, reflexive)
    triggers = _verb_triggers(sentence, target, tense, mood, infinitive)
    return GrammarInfo(
        kind="verb", infinitive=infinitive, tense=tense, mood=mood, person=person,
        number=number, verbform=verbform, reflexive=reflexive, label=label, triggers=triggers,
    )


def _verb_label(
    tense: str | None, mood: str | None, person: str | None,
    number: str | None, verbform: str | None, reflexive: bool,
) -> str:
    # Non-finite forms have no person/tense to show.
    if verbform in ("infinitive", "gerund", "participle"):
        return f"{verbform} (reflexive)" if reflexive else (verbform or "")
    tm = " ".join(p for p in (tense, mood) if p)  # 'present subjunctive' / 'imperative'
    pn = " ".join(p for p in (person, number) if p)  # '3rd person singular'
    return ", ".join(p for p in (tm, pn) if p)


def _verb_triggers(
    sentence: Sentence, target: Token, tense: str | None, mood: str | None, infinitive: str,
) -> list[str]:
    prefix = _normalize(sentence.text[: target.char_start])
    full = _normalize(sentence.text)
    out: list[str] = []

    for rx, label in _SUBJUNCTIVE_CUES:
        if rx.search(prefix):
            # only surface subjunctive-specific cues when the verb really is subjunctive
            if mood == "subjunctive" or "infinitive" in label:
                out.append(label)

    if tense == "preterite":
        out.append("preterite: completed/bounded past action")
        if _PRETERITE_ADV.search(full):
            out.append("reinforced by a punctual adverbial (e.g. 'de repente', 'ayer')")
    elif tense == "imperfect":
        out.append("imperfect: ongoing/habitual/background past")
        if _IMPERFECT_ADV.search(full):
            out.append("reinforced by a habitual adverbial (e.g. 'siempre', 'mientras')")

    if infinitive == "ser":
        out.append("ser: identity/inherent trait/origin")
    elif infinitive == "estar":
        out.append("estar: state/location/result")

    # de-dupe while preserving order
    seen: set[str] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


def _nominal(target: Token, *, kind: str) -> GrammarInfo:
    m = target.morph_dict
    gender = _GENDER.get(m.get("Gender", ""))
    number = _NUMBER.get(m.get("Number", ""))
    label = " ".join(p for p in (gender, number) if p)
    return GrammarInfo(kind=kind, gender=gender, number=number, label=label)

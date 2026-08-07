"""Tests for the portable textbook schema (units / grammar notes / exercises / items)."""

from __future__ import annotations

from pathlib import Path

from spanish_sentence_miner import (
    Exercise,
    ExerciseItem,
    GrammarNote,
    Unit,
    exercise_id,
    item_id,
    load_exercises,
    load_grammar_notes,
    load_items,
    load_units,
    write_jsonl,
)


def test_ids_are_zero_padded_and_stable() -> None:
    assert exercise_id(512, 2, 3) == "512:02:03"
    assert item_id(512, 2, 3, 1) == "512:02:03:001"
    # item id extends its exercise id
    assert item_id(512, 2, 3, 1).startswith(exercise_id(512, 2, 3) + ":")


def test_units_and_notes_roundtrip(tmp_path: Path) -> None:
    upath = tmp_path / "units.jsonl"
    write_jsonl(upath, [Unit(id=2, book_id=512, title="Subject pronouns", source="ch2.xhtml")])
    units, bad = load_units(upath)
    assert bad == 0 and units[2].title == "Subject pronouns"

    gpath = tmp_path / "grammar_notes.jsonl"
    note = GrammarNote(
        id="512:02:g000",
        book_id=512,
        unit=2,
        heading_path=["The present tense"],
        level=3,
        text="Regular -ar verbs…",
    )
    write_jsonl(gpath, [note])
    notes, bad = load_grammar_notes(gpath)
    assert bad == 0 and notes["512:02:g000"].heading_path == ["The present tense"]


def test_exercises_and_items_join(tmp_path: Path) -> None:
    eid = exercise_id(512, 2, 3)
    ex = Exercise(
        id=eid,
        book_id=512,
        unit=2,
        number=3,
        label="2·3",
        title="Traducción",
        instruction="Translate the sentences into Spanish.",
        kind="translation",
        gradable=True,
        prompt_lang="en",
        answer_lang="es",
    )
    items = [
        ExerciseItem(
            id=item_id(512, 2, 3, 1),
            exercise_id=eid,
            book_id=512,
            unit=2,
            number=1,
            prompt="You (sing., fam.) need to rest.",
            answer="Necesitas descansar.",
        ),
        ExerciseItem(
            id=item_id(512, 2, 3, 2),
            exercise_id=eid,
            book_id=512,
            unit=2,
            number=2,
            prompt="He talks, I listen.",
            answer="Él habla, yo escucho.",
        ),
    ]
    epath, ipath = tmp_path / "exercises.jsonl", tmp_path / "items.jsonl"
    write_jsonl(epath, [ex])
    write_jsonl(ipath, items)

    exercises, ebad = load_exercises(epath)
    loaded_items, ibad = load_items(ipath)
    assert ebad == 0 and ibad == 0
    assert exercises[eid].kind == "translation"
    mine = [i for i in loaded_items.values() if i.exercise_id == eid]
    assert len(mine) == 2
    assert loaded_items[item_id(512, 2, 3, 1)].answer == "Necesitas descansar."


def test_open_item_is_non_gradable(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    write_jsonl(
        path,
        [
            ExerciseItem(
                id=item_id(512, 2, 6, 1),
                exercise_id=exercise_id(512, 2, 6),
                book_id=512,
                unit=2,
                number=1,
                prompt="Y en tu caso…",
                answer="",
                answer_note="Answers will vary.",
                gradable=False,
            )
        ],
    )
    items, bad = load_items(path)
    assert bad == 0
    only = next(iter(items.values()))
    assert only.gradable is False and only.answer_note == "Answers will vary."


def test_bad_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "exercises.jsonl"
    write_jsonl(path, [Exercise(id=exercise_id(1, 1, 1), book_id=1, unit=1, number=1, label="1·1")])
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ not json\n")
    exercises, bad = load_exercises(path)
    assert bad == 1 and len(exercises) == 1

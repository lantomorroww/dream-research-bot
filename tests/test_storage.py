"""Юнит-тесты чистых функций CSV-хранилища (без Telegram-API)."""
import csv
import os
from datetime import date

import pytest

import main


@pytest.fixture
def patched_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ANSWERS_CSV", str(tmp_path / "answers.csv"))
    monkeypatch.setattr(main, "DESCRIPTIONS_CSV", str(tmp_path / "descriptions.csv"))
    monkeypatch.setattr(main, "VOICE_NOTES_DIR", str(tmp_path / "voice"))
    os.makedirs(str(tmp_path / "voice"), exist_ok=True)


def test_save_answers_creates_file_with_header(patched_paths):
    main.save_answers("resp-1", 1, [5, 4, 3, 2, 1, 5, 4, 3])
    with open(main.ANSWERS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    row = rows[0]
    assert row["respondent_id"] == "resp-1"
    assert row["day"] == "1"
    assert row["q1"] == "5"
    assert row["q8"] == "3"
    assert row["date"] == date.today().isoformat()


def test_save_answers_appends_rows(patched_paths):
    main.save_answers("resp-1", 1, [1] * 8)
    main.save_answers("resp-1", 2, [2] * 8)
    with open(main.ANSWERS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[1]["day"] == "2"


def test_save_dream_description_no_dream(patched_paths):
    main.save_dream_description("resp-1", 1, "no_dream", "", "")
    with open(main.DESCRIPTIONS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["dream_type"] == "no_dream"
    assert rows[0]["dream_content"] == ""


def test_delete_day_records_removes_only_target(patched_paths):
    main.save_answers("resp-1", 1, [1] * 8)
    main.save_answers("resp-1", 2, [2] * 8)
    main.save_dream_description("resp-1", 1, "text", "dream 1", "")
    main.save_dream_description("resp-1", 2, "text", "dream 2", "")

    main.delete_day_records("resp-1", 1)

    with open(main.ANSWERS_CSV, encoding="utf-8") as f:
        answers = list(csv.DictReader(f))
    assert [r["day"] for r in answers] == ["2"]

    with open(main.DESCRIPTIONS_CSV, encoding="utf-8") as f:
        descs = list(csv.DictReader(f))
    assert [r["day"] for r in descs] == ["2"]

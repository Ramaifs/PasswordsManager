from copy import deepcopy

from password_manager import model


def test_space_review_and_repair_respect_record_exception_and_keep_prose():
    doc = model.new_document()
    changed = model.save_entry(doc, {"title": "Read me", "email": "x @example.invalid ",
                                    "note": "keep these spaces", "additional_fields": {"password": ["second secret"]}})
    exempt = model.save_entry(doc, {"title": "Exempt", "password": "intentional space", "allow_spaces": True})
    assert model.space_problems(doc) == [(changed, "Read me", ["email", "password"])]
    original = deepcopy(doc)
    model.repair_spaces(doc)
    assert doc["entries"][changed]["email"] == "x@example.invalid"
    assert doc["entries"][changed]["additional_fields"]["password"] == ["secondsecret"]
    assert doc["entries"][changed]["note"] == "keep these spaces"
    assert doc["entries"][exempt] == original["entries"][exempt]
    assert not model.space_problems(model.validate(doc))


def test_hide_suggestion_leaves_sources_and_ignores_trailing_whitespace():
    doc = model.new_document()
    first = model.save_entry(doc, {"title": "First", "username": "Example"})
    model.save_entry(doc, {"title": "Duplicate", "username": "example"})
    model.save_entry(doc, {"title": "Trailing", "username": "other "})
    assert model.suggestion_sources(doc, "username")["Example"]["id"] == first
    model.hide_suggestion(doc, "username", "Example")
    assert not model.suggestions(model.validate(doc), "username")
    assert doc["entries"][first]["username"] == "Example"

"""Test predicate building for note and account filters"""

import AppKit
import pytest

from macnotesapp.notesapp import filter_accounts, notes_predicate

NOTES = AppKit.NSArray.arrayWithArray_(
    [
        {
            "name": "Food Log",
            "plaintext": "eggs",
            "passwordProtected": False,
            "id": "p1",
        },
        {
            "name": "log",
            "plaintext": "daily log",
            "passwordProtected": False,
            "id": "p2",
        },
        {
            "name": "Changelog",
            "plaintext": "v1 eggs",
            "passwordProtected": True,
            "id": "p3",
        },
        {
            "name": "Recipes",
            "plaintext": "cake",
            "passwordProtected": False,
            "id": "p4",
        },
    ]
)

ACCOUNTS = AppKit.NSArray.arrayWithArray_(
    [{"name": "iCloud"}, {"name": "On My Mac"}, {"name": "Gmail"}]
)


def ids(predicate):
    return [n["id"] for n in NOTES.filteredArrayUsingPredicate_(predicate)]


def test_no_filters_returns_none():
    assert notes_predicate() is None


def test_name_contains():
    assert ids(notes_predicate(name=["log"])) == ["p1", "p2", "p3"]


def test_name_exact_is_case_insensitive():
    assert ids(notes_predicate(name=["LOG"], exact_name=True)) == ["p2"]
    assert ids(notes_predicate(name=["food log"], exact_name=True)) == ["p1"]


def test_multiple_values_are_ored():
    assert ids(notes_predicate(name=["food", "recipes"])) == ["p1", "p4"]


def test_properties_are_anded():
    assert ids(notes_predicate(name=["log"], body=["eggs"])) == ["p1", "p3"]
    assert ids(
        notes_predicate(name=["log"], body=["eggs"], password_protected=False)
    ) == ["p1"]


def test_text_matches_name_or_body():
    assert ids(notes_predicate(text=["cake"])) == ["p4"]
    assert ids(notes_predicate(text=["daily"])) == ["p2"]


def test_id():
    assert ids(notes_predicate(id=["p2", "p4"])) == ["p2", "p4"]


def test_arguments_not_mutated():
    """Regression test for #72: building the predicate must not modify the caller's lists"""
    name, body, text = ["log"], ["eggs"], ["v1"]
    notes_predicate(name=name, body=body, text=text, id=["p3"])
    notes_predicate(name=name, body=body, text=text, id=["p3"])
    assert (name, body, text) == (["log"], ["eggs"], ["v1"])


@pytest.mark.parametrize(
    "accounts,expected",
    [
        (None, ["iCloud", "On My Mac", "Gmail"]),
        ([], ["iCloud", "On My Mac", "Gmail"]),
        (["iCloud"], ["iCloud"]),
        (["iCloud", "Gmail"], ["iCloud", "Gmail"]),
        (("On My Mac",), ["On My Mac"]),
        (["Nope"], []),
    ],
)
def test_filter_accounts(accounts, expected):
    """Regression test for #72: filtering by one or more accounts"""
    assert [a["name"] for a in filter_accounts(ACCOUNTS, accounts)] == expected

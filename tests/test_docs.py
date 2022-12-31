"""Test macnotesapp docs"""


import pathlib
import pytest

from mktestdocs import check_md_file


def test_readme():
    check_md_file(fpath=pathlib.Path(__file__).parent.parent / "README.md")

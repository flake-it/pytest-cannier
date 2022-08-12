import os
import pytest
import sqlite3
import subprocess as sp

from pytest_cannier.churn import get_churn, save_churn


@pytest.fixture
def repo_dir(tmpdir):
    cwd = os.getcwd()
    os.chdir(tmpdir.strpath)
    sp.run(["git", "init"], check=True, stdout=sp.DEVNULL)

    yield
    os.chdir(cwd)


def git_repo_commit():
    sp.run(["git", "add", "-A"], check=True, stdout=sp.DEVNULL)
    sp.run(["git", "commit", "-m", "message"], check=True, stdout=sp.DEVNULL)


def test_get_churn(repo_dir):
    with open("foo.py", "w") as fd_foo, \
         open("bar.py", "w") as fd_bar, \
         open("baz.py", "w") as fd_baz, \
         open("qux.js", "w") as fd_qux:
        fd_foo.write("foo\nbar\nbaz\n")
        fd_bar.write("foo\nbar\nbaz\n")
        fd_baz.write("foo\nbar\nbaz\n")
        fd_qux.write("foo\nbar\nbaz\n")

    git_repo_commit()

    with open("foo.py", "w") as fd:
        fd.write("foo\nbarr\nbaz\n")

    git_repo_commit()

    with open("bar.py", "w") as fd:
        fd.write("fooo\nbar\nbazz\n")

    git_repo_commit()

    with open("foo.py", "w") as fd:
        fd.write("foo\nbarrr\nbaz\n")

    with open("qux.js", "w") as fd:
        fd.write("foo\nbarrr\nbaz\n")

    git_repo_commit()

    assert get_churn(3) == {
        "foo.py": {2: 2}, 
        "bar.py": {1: 1, 3: 1}
    }

    assert get_churn(2) == {
        "foo.py": {2: 1}, 
        "bar.py": {1: 1, 3: 1}
    }

    assert get_churn(1) == {
        "foo.py": {2: 1}
    }


def test_save_churn(db_file):
    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_churn "
            "from counters"
        )

        assert cur.fetchone()[0] == 0

    churn = {
        "foo.py": {2: 2}, 
        "bar.py": {1: 1, 3: 1}
    }

    save_churn(db_file, churn)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_churn "
            "from counters"
        )

        assert cur.fetchone()[0] == 1

        cur.execute(
            "select id, file_name "
            "from file"
        )

        file_name_to_id = {
            file_name: file_id for file_id, file_name in cur.fetchall()
        }

        cur.execute(
            "select file_id, l_no, churn_l_no "
            "from line"
        )

        assert set(cur.fetchall()) == {
            (file_name_to_id["foo.py"], 2, 2),
            (file_name_to_id["bar.py"], 1, 1),
            (file_name_to_id["bar.py"], 3, 1),
        }
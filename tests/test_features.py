import ast
import sys
import radon
import pytest
import sqlite3

from pytest_cannier.features import (
    get_coverage_feats, get_tree_depth, get_external_modules, 
    get_unindented_source, FeaturesPlugin
)


class MockCoverageData:
    def __init__(self, data):
        self.data = data

    def measured_files(self):
        return self.data.keys()

    def lines(self, file_name):
        return self.data.get(file_name, [])


class MockCoverage:
    def __init__(self, data):
        self.data = MockCoverageData(data)

    def get_data(self):
        return self.data


def test_get_coverage_feats():
    coverage = MockCoverage({
        "foo.py": [1, 2, 3, 4],
        "bar.py": [1, 2, 3, 4],
        "baz.py": [1, 2, 3, 4],
        "bar.js": [1, 2, 3, 4]
    })

    test_files = {"foo.py", "bar.py"}

    churn = {
        "foo.py": {1: 1, 2: 1, 3: 1},
        "bar.py": {2: 2, 4: 2, 6: 2},
        "baz.py": {3: 3, 6: 3, 9: 3},
        "bar.js": {4: 4, 8: 4, 12: 4}
    }

    assert get_coverage_feats(coverage, test_files, churn) == (16, 8, 7)


@pytest.mark.parametrize(
    "source,expected", 
    [
        (
            "a = foo()\n",
            1
        ),
        (
            "if bar():\n"
            "    a = foo()\n",
            2
        ),
        (
            "for x in bar():\n"
            "    if bar():\n"
            "        a = foo()\n",
            3
        ),
        (
            "for x in bar():\n"
            "    if bar():\n"
            "        a = foo()\n"
            "if bar():\n"
            "    a = foo()\n",
            3
        ),        
        (
            "while baz():\n"
            "    for x in bar():\n"
            "        if bar():\n"
            "            a = foo()\n"
            "if bar():\n"
            "    a = foo()\n",
            4
        )
    ]
)
def test_get_tree_depth(source, expected):
    assert get_tree_depth(ast.parse(source)) == expected


@pytest.mark.parametrize(
    "varnames,source,expected", 
    [
        (
            [],
            "import numpy\n"
            "import pytest\n",
            {"numpy"}
        ),
        (
            [],
            "from coverage import Coverage\n"
            "import pytest_cannier\n",
            {"coverage"}
        ),
        (
            [],
            "foo = radon.metrics.mi_parameters(foo)\n"
            "bar = ast.parse(bar)\n",
            {"radon"}
        ),
        (
            ["radon"],
            "foo = radon.metrics.mi_parameters(foo)\n"
            "bar = ast.parse(bar)\n"
            "baz = pytest_cannier.churn.ChurnPlugin(baz)\n",
            set()
        )
    ]
)
def test_get_external_modules(varnames, source, expected):
    module = sys.modules[__name__]
    output = set(get_external_modules(module, varnames, ast.parse(source)))
    assert output == expected


def test_load_from_db(db_file):
    plugin = FeaturesPlugin(db_file, None)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.executemany(
            "insert into file "
            "values (?, ?)", 
            [(1, "foo.py"), (2, "bar.py")]
        )

        cur.executemany(
            "insert into line "
            "values (?, ?, ?)", 
            [(1, 1, 1), (1, 2, 2), (1, 3, 3), (2, 4, 1), (2, 5, 2), (2, 6, 3)]
        )

    with sqlite3.connect(db_file) as con:
        plugin.load_from_db(con.cursor())

    assert plugin.churn == {
        "foo.py": {1: 1, 2: 2, 3: 3},
        "bar.py": {4: 1, 5: 2, 6: 3}
    }


def test_save_to_db(db_file):
    plugin = FeaturesPlugin(db_file, None)

    plugin.features = {
        "test_foo": [0] * 18,
        "test_bar": [1] * 18,
    }

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_features "
            "from counters"
        )

        assert cur.fetchone()[0] == 0

        plugin.save_to_db(cur)

    plugin.features = {
        "test_bar": [2] * 18
    }

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_features "
            "from counters"
        )

        assert cur.fetchone()[0] == 1

        plugin.save_to_db(cur)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_features "
            "from counters"
        )

        assert cur.fetchone()[0] == 2

        cur.execute(
            "select nodeid, n_runs_features "
            "from item"
        )

        assert set(cur.fetchall()) == {
            ("test_foo", 1),
            ("test_bar", 2)
        }

        cur.execute(
            "select id, nodeid "
            "from item"
        )

        nodeid_to_id = {
            nodeid: item_id for item_id, nodeid in cur.fetchall()
        }

        cur.execute(
            "select * "
            "from features"
        )

        assert set(cur.fetchall()) == {
            (nodeid_to_id["test_foo"], *[0] * 18),
            (nodeid_to_id["test_bar"], *[1] * 18),
            (nodeid_to_id["test_bar"], *[2] * 18)
        }


def test_get_unindented_source():
    lines1 = [
        "    foo\n", 
        "        bar\n", 
        "    baz\n", 
        "    qux\n"
    ]

    lines2 = [
        "    foo\n", 
        "        bar\n", 
        "baz\n", 
        "    qux\n"
    ]

    assert get_unindented_source(lines1) == get_unindented_source(lines2) == (
        "foo\n"
        "    bar\n"
        "baz\n"
        "qux\n"
    )
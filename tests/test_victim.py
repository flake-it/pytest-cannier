import sqlite3

from pytest_cannier.victim import VictimPlugin


def test_load_from_db(db_file):
    plugin = VictimPlugin(db_file, None)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "update counters "
            "set count_features = 10, count_baseline = 10, count_shuffle = 10 "
            "where id = 1"
        )

        cur.executemany(
            "insert into item "
            "values (null, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("test_foo", 10, 10, 0, 10, 0, 0),
                ("test_bar", 9, 10, 0, 10, 0, 0),
                ("test_baz", 10, 9, 0, 10, 0, 0),
                ("test_qux", 10, 10, 0, 9, 0, 0),
            ]
        )

    with sqlite3.connect(db_file) as con:
        plugin.load_from_db(con.cursor())

    assert plugin.candidate_polluters == {"test_foo"}


def test_save_to_db(db_file):
    plugin = VictimPlugin(db_file, "test_foo")

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.executemany(
            "insert into item "
            "values (null, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("test_foo", 10, 10, 0, 10, 0, 0),
                ("test_bar", 10, 10, 0, 10, 0, 0),
                ("test_baz", 10, 10, 0, 10, 0, 0),
                ("test_qux", 10, 10, 0, 10, 0, 0),
            ]
        )

    plugin.polluters = {"test_bar", "test_baz", "test_qux"}

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select id, nodeid "
            "from item"
        )

        nodeid_to_id = {
            nodeid: item_id for item_id, nodeid in cur.fetchall()
        }

        plugin.save_to_db(cur)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select nodeid, n_runs_victim "
            "from item"
        )

        assert set(cur.fetchall()) == {
            ("test_foo", 1),
            ("test_bar", 0),
            ("test_baz", 0),
            ("test_qux", 0),
        }

        cur.execute(
            "select victim_id, polluter_id "
            "from dependency"
        )

        assert set(cur.fetchall()) == {
            (nodeid_to_id["test_foo"], nodeid_to_id["test_bar"]),
            (nodeid_to_id["test_foo"], nodeid_to_id["test_baz"]),
            (nodeid_to_id["test_foo"], nodeid_to_id["test_qux"]),
        }
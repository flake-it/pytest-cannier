import sqlite3

from pytest_cannier.rerun import RerunPlugin


def test_save_to_db(db_file):
    plugin = RerunPlugin(db_file, "baseline")
    plugin.executed = {"test_foo", "test_bar"}
    plugin.failed = {"test_foo"}

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_baseline, count_shuffle "
            "from counters"
        )

        assert cur.fetchone() == (0, 0)

        plugin.save_to_db(cur)

    plugin.mode = "shuffle"
    plugin.executed.add("test_baz")
    plugin.failed = {"test_bar"}

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_baseline, count_shuffle "
            "from counters"
        )

        assert cur.fetchone() == (1, 0)

        plugin.save_to_db(cur)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()

        cur.execute(
            "select count_baseline, count_shuffle "
            "from counters"
        )

        assert cur.fetchone() == (1, 1)

        cur.execute(
            "select nodeid, n_runs_baseline, n_fail_baseline, n_runs_shuffle, "
            "n_fail_shuffle "
            "from item"
        )

        assert set(cur.fetchall()) == {
            ("test_foo", 1, 1, 1, 0),
            ("test_bar", 1, 0, 1, 1),
            ("test_baz", 0, 0, 1, 0),
        }
import os
import pytest
import random
import sqlite3

from pytest_cannier.base import BasePlugin


PASSED, FAILED, SKIPPED = 0, 1, 2


class RerunPlugin(BasePlugin):
    def __init__(self, db_file, mode):
        super().__init__(db_file)
        self.executed = set()
        self.failed = set()
        self.mode = mode

    def load_from_db(self, cur):
        pass

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        if self.mode == "shuffle":
            random.shuffle(items)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        self.outcome = PASSED
        yield

        if self.outcome != SKIPPED:
            self.executed.add(item.nodeid)
        
        if self.outcome == FAILED:
            self.failed.add(item.nodeid)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        result = yield
        report = result.get_result()

        if report.skipped:
            self.outcome = SKIPPED
        elif report.failed:
            self.outcome = FAILED

    def save_to_db(self, cur):
        cur.execute(
            "update counters "
            f"set count_{self.mode} = count_{self.mode} + 1 "
            "where id = 1"
        )

        executed = [(nodeid,) for nodeid in self.executed]

        cur.executemany(
            "insert or ignore into item "
            "values (null, ?, 0, 0, 0, 0, 0, 0)", 
            executed
        )

        cur.executemany(
            "update item "
            f"set n_runs_{self.mode} = n_runs_{self.mode} + 1 "
            "where nodeid = ?", 
            executed
        )

        failed = [(nodeid,) for nodeid in self.failed]
        
        cur.executemany(
            "update item "
            f"set n_fail_{self.mode} = n_fail_{self.mode} + 1 "
            "where nodeid = ?", 
            failed
        )
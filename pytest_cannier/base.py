import pytest
import sqlite3


class BasePlugin:
    def __init__(self, db_file):
        self.db_file = db_file

    def load_from_db(self, cur):
        raise NotImplementedError

    def pytest_sessionstart(self, session):
        with sqlite3.connect(self.db_file) as con:
            self.load_from_db(con.cursor())

    def save_to_db(self, cur):
        raise NotImplementedError

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if exitstatus in {
            pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED
        }:
            session.exitstatus = pytest.ExitCode.OK

            with sqlite3.connect(self.db_file) as con:
                self.save_to_db(con.cursor())
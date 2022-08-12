import gc
import os
import pytest
import random
import sqlite3

from psutil import Process
from multiprocessing import Pipe

from pytest_cannier.base import BasePlugin


PASSED, FAILED, SKIPPED = 0, 1, 2


class VictimPlugin(BasePlugin):
    def __init__(self, db_file, victim_nodeid):
        super().__init__(db_file)
        self.polluters = set()
        self.victim_nodeid = victim_nodeid

    def load_from_db(self, cur):
        cur.execute(
            "select count_features, count_baseline, count_shuffle "
            "from counters "
            "where id = 1"
        )

        cur.execute(
            "select nodeid "
            "from item "
            "where n_runs_features = ? and "
            "n_runs_baseline = ? and "
            "n_runs_shuffle = ?",
            cur.fetchone()
        )

        self.candidate_polluters = set(nodeid for nodeid, in cur.fetchall())

    def get_victim(self, items):
        for it in items:
            if it.nodeid == self.victim_nodeid:
                return it

        pytest.exit(
            "pytest-cannier: could not find victim test case.", 
            pytest.ExitCode.INTERNAL_ERROR
        )

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        victim = self.get_victim(items)
        pipe_parent, self.pipe_child = Pipe()
        gc.disable()
        pid = os.fork()

        if pid == 0:
            items[:] = [victim]
            return

        if Process(pid).wait():
            pytest.exit(
                "pytest-cannier: child process error.", 
                pytest.ExitCode.INTERNAL_ERROR
            )

        expected_outcome = pipe_parent.recv()

        for polluter in items:
            if polluter.nodeid not in self.candidate_polluters:
                continue

            pid = os.fork()

            if pid == 0:
                items[:] = [polluter, victim]
                return

            if Process(pid).wait():
                pytest.exit(
                    "pytest-cannier: child process error.", 
                    pytest.ExitCode.INTERNAL_ERROR
                )

            outcome = pipe_parent.recv()
            
            if expected_outcome != outcome:
                self.polluters.add(polluter.nodeid)

        pytest.exit("pytest-cannier: finished.", pytest.ExitCode.OK)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        if item.nodeid != self.victim_nodeid:
            yield
            return

        self.outcome = PASSED
        yield

        self.pipe_child.send(self.outcome)
        os._exit(0)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        if item.nodeid != self.victim_nodeid:
            yield
            return

        result = yield
        report = result.get_result()

        if report.skipped:
            self.outcome = SKIPPED
        elif report.failed:
            self.outcome = FAILED

    def save_to_db(self, cur):
        cur.execute(
            "select id, nodeid "
            "from item"
        )

        nodeid_to_id = {
            nodeid: item_id for item_id, nodeid in cur.fetchall()
        }

        victim_id = nodeid_to_id[self.victim_nodeid]

        cur.execute(
            "update item "
            "set n_runs_victim = n_runs_victim + 1 "
            "where id = ?", 
            (victim_id,)
        )

        cur.executemany(
            "insert or ignore into dependency "
            "values (?, ?)", 
            [
                (victim_id, nodeid_to_id[polluter_nodeid]) 
                for polluter_nodeid in self.polluters
            ]
        )
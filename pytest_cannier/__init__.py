import os
import pytest

from pytest_cannier.rerun import RerunPlugin
from pytest_cannier.victim import VictimPlugin
from pytest_cannier.features import FeaturesPlugin
from pytest_cannier.churn import get_churn, save_churn


def pytest_addoption(parser):
    group = parser.getgroup("pytest-cannier")

    group.addoption(
        "--mode", action="store", dest="mode", type=str
    )

    group.addoption(
        "--db-file", action="store", dest="db-file", type=str
    )

    group.addoption(
        "--victim-nodeid", action="store", dest="victim-nodeid", type=str
    )

    group.addoption(
        "--commit-window", action="store", default=75, dest="commit-window", 
        type=int
    )

    group.addoption(
        "--poll-rate", action="store", default=0.025, dest="poll-rate", 
        type=float
    )

    group.addoption(
        "--mock-flaky", action="store_true", dest="mock-flaky",
    )


def pytest_configure(config):
    mode = config.getoption("mode")

    if not mode:
        return

    db_file = config.getoption("db-file")

    if not db_file:
        pytest.exit(
            "pytest-cannier: no database file specified.", 
            pytest.ExitCode.USAGE_ERROR
        )

    if mode == "churn":
        save_churn(db_file, get_churn(config.getoption("commit-window")))
        pytest.exit("pytest-cannier: finished", pytest.ExitCode.OK)

    if mode == "features":
        plugin = FeaturesPlugin(db_file, config.getoption("poll-rate"))
    elif mode in {"baseline", "shuffle"}:
        plugin = RerunPlugin(db_file, mode)
    elif mode == "victim":
        victim_nodeid = config.getoption("victim-nodeid")

        if not victim_nodeid:
            pytest.exit(
                "pytest-cannier: no victim nodeid specified.", 
                pytest.ExitCode.USAGE_ERROR
            )

        plugin = VictimPlugin(db_file, victim_nodeid)
    else:
        pytest.exit(
            f"pytest-cannier: {mode} is not a valid mode.", 
            pytest.ExitCode.USAGE_ERROR
        )

    if config.getoption("mock-flaky"):
        config.addinivalue_line("markers", "flaky: mock flaky plugin")

    config.pluginmanager.register(plugin)

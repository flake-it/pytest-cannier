import os
import pytest
import sqlite3


def pytest_addoption(parser):
    parser.addoption(
        "--schema-file", action="store", dest="schema-file", type=str
    )


@pytest.fixture
def db_file(request, tmpdir):
    schema_file = request.config.getoption("schema-file")

    with open(schema_file, "r") as f:
        schema = f.read()

    db_file = os.path.join(tmpdir.strpath, "db.sqlite3")
    
    with sqlite3.connect(db_file) as con:
        con.executescript(schema)

    yield db_file
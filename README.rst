==============
pytest-CANNIER
==============

pytest-CANNIER is plugin for `pytest <https://docs.pytest.org/en/7.1.x/>`_ that provides the instrumentation required by `CANNIER-Framework <https://github.com/flake-it/cannier-framework>`_. We designed pytest-CANNIER to be used automatically by CANNIER-Framework, though manual use is possible. 

Prerequisites
=============

The dependencies of pytest-CANNIER can be found in ``requirements.txt``. We have only tested pytest-CANNIER on Ubuntu 20.04 and Python 3.8. We cannot guarantee correct results with other environments.

Installation
============

You can install pytest-CANNIER with ``pip install PATH`` where ``PATH`` is the directory containing ``setup.py``. This will also install the dependencies.

Usage
=====

You can use pytest-CANNIER by executing a project's test suite with pytest (typically using ``python -m pytest`` or simply ``pytest``) along with the following command line options:

- ``--mode={MODE}`` Specify the mode of pytest-CANNIER. ``MODE`` can be one of:

    - ``churn`` Measure code churn.
    - ``features`` Perform a test suite run and measure 18 test case features.
    - ``baseline`` Perform a test suite run and record test case outcomes.
    - ``shuffle`` Same as ``baseline`` but shuffle the test run order.
    - ``victim`` Find polluters of a single victim test case.
- ``--db-file={DB_FILE}`` Specify the database file to store the results in.
- ``--victim-nodeid={NODEID}`` Specify the name of the victim test case when ``MODE`` is ``victim``.
- ``--commit-window={COMMIT_WINDOW}`` Specify the commit window when ``MODE`` is ``churn`` (default 75).
- ``--poll-rate={POLL_RATE}`` Specify the poll rate in seconds when ``MODE`` is ``features`` (default 0.025).
- ``--mock-flaky`` Register a marker named "flaky" for test suites that expect the `flaky <https://github.com/box/flaky>`_ plugin.

If you do not specify ``MODE`` or ``DB_FILE``, the plugin will be disabled and pytest will run as normal.

Output
======

pytest-CANNIER stores the results in an `SQLite <https://www.sqlite.org/index.html>`_ database specified by ``DB_FILE``. The schema for this database can be found in the `CANNIER-Experiment <https://github.com/flake-it/cannier-expierment>`_ repository. CANNIER-Framework will automatically create a blank database for pytest-CANNIER when it is used on a project for the first time.

Testing
=======

pytest-CANNIER has its own pytest test suite. To execute it, you must pass the ``--schema-file={SCHEMA_FILE}`` where ``SCHEMA_FILE`` is the path to the schema file for the database. This can be found in the CANNIER-Experiment repository.
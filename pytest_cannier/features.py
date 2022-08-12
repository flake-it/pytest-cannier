import gc
import os
import re
import ast
import time
import pytest
import inspect
import sqlite3

from radon import metrics
from importlib import util
from coverage import Coverage
from distutils import sysconfig
from multiprocessing import Event, Pipe
from psutil import AccessDenied, Process

from pytest_cannier.base import BasePlugin


WHITESPACE_RE = re.compile("(^[ \t]*)(?:[^ \t\n])")
PYTHON_LIB = sysconfig.get_python_lib(standard_lib=False)


def get_cumulative_feats(proc):
    io = proc.io_counters()
    read_count = io.read_count
    write_count = io.write_count
    time_exec = time.perf_counter()
    time_iowait = proc.cpu_times().iowait
    n_switches = proc.num_ctx_switches().voluntary
    return read_count, write_count, time_exec, time_iowait, n_switches


def get_coverage_feats(coverage, test_files, churn):
    data = coverage.get_data()
    n_lines = n_lines_source = n_changes = 0

    for file_name in data.measured_files():
        lines = data.lines(file_name)

        if not lines:
            continue

        n_lines += len(lines)
        file_name_rel = os.path.relpath(file_name)

        if file_name_rel in test_files:
            continue

        n_lines_source += len(lines)
        churn_file = churn.get(file_name_rel, {})
        n_changes += sum(churn_file.get(l_no, 0) for l_no in lines)

    return n_lines, n_lines_source, n_changes


def get_noncumulative_feats(proc):
    n_threads = proc.num_threads()
    n_children = len(proc.children())
    n_bytes = proc.memory_full_info().uss
    return n_threads, n_children, n_bytes


def get_node_depth(node):
    if isinstance(node, ast.stmt):
        node_iter = ast.iter_child_nodes(node)
        return 1 + max((get_node_depth(n) for n in node_iter), default=0)
    else:
        return 0


def get_tree_depth(tree):
    return max((get_node_depth(node) for node in tree.body), default=0)


def is_external_module(module_name):
    try:
        spec = util.find_spec(module_name)
    except (ValueError, ModuleNotFoundError):
        return False

    if spec is None:
        return False

    origin = spec.origin or ""
    return origin.startswith(PYTHON_LIB)


def iter_module_names_import(node):
    for n in node.names:
        module_name = n.name.split(".")[0]

        if is_external_module(module_name):
            yield module_name


def iter_module_names_import_from(node):
    if node.module is None:
        return

    module_name = node.module.split(".")[0]

    if is_external_module(module_name):
        yield module_name


def iter_module_names_name(module, varnames, node):
    if node.id in varnames:
        return

    obj = getattr(module, node.id, None)

    if inspect.ismodule(obj):
        module_obj = obj
    else:
        module_obj = inspect.getmodule(obj)

    if module_obj is None:
        return

    module_name = getattr(module_obj, "__name__", None)

    if module_name is None:
        return

    if is_external_module(module_name):
        yield module_name


def get_external_modules(module, varnames, tree):
    module_names = set()

    class Visitor(ast.NodeVisitor):
        def visit_Import(self, node):
            module_names.update(iter_module_names_import(node))

        def visit_ImportFrom(self, node):
            module_names.update(iter_module_names_import_from(node))

        def visit_Name(self, node):
            module_names.update(iter_module_names_name(module, varnames, node))

        def visit_Attribute(self, node):
            outer = node

            while isinstance(outer, ast.Attribute):
                outer = outer.value

            self.visit(outer)

    Visitor().visit(tree)        
    return [name for name in module_names if "pytest" not in name]


def get_unindented_source(lines):
    source = "".join(lines)
    indent = WHITESPACE_RE.findall(lines[0])
    return re.sub(r"(?m)^" + indent[0], "", source) if indent else source


def get_static_feats(module, varnames, lines, tree):
    tree_depth = get_tree_depth(tree)
    n_ext_mods = len(get_external_modules(module, varnames, tree))
    n_assert = sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
    source_body = get_unindented_source(lines[tree.body[0].lineno - 1:])
    hal_vol, cyc_cmp, lloc, per_com = metrics.mi_parameters(source_body)
    mnt_idx = metrics.mi_compute(hal_vol, cyc_cmp, lloc, per_com)
    return tree_depth, n_ext_mods, n_assert, hal_vol, cyc_cmp, lloc, mnt_idx


class FeaturesPlugin(BasePlugin):
    def __init__(self, db_file, poll_rate):
        super().__init__(db_file)
        self.features = {}
        self.poll_rate = poll_rate

    def load_from_db(self, cur):
        cur.execute(
            "select id, file_name "
            "from file"
        )

        id_to_file_name = {
            file_id: file_name for file_id, file_name in cur.fetchall()
        }

        cur.execute(
            "select file_id, l_no, churn_l_no "
            "from line"
        )

        self.churn = {}

        for file_id, l_no, churn_l_no in cur.fetchall():
            file_name = id_to_file_name[file_id]
            churn_file = self.churn.setdefault(file_name, {})
            churn_file[l_no] = churn_l_no

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        self.test_files = set()
        self.static = {}
        self.items = {}
        items_new = []

        for it in items:
            self.test_files.add(it.location[0])
            obj = getattr(it, "obj", None)

            if obj is None:
                continue

            if id(obj) in self.static:
                self.items[it.nodeid] = id(obj)
                items_new.append(it)
                continue

            module = inspect.getmodule(obj)
            code = getattr(obj, "__code__", None)

            if module is None or code is None:
                continue

            try:
                lines, _ = inspect.getsourcelines(obj)
            except (TypeError, OSError):
                continue

            source = get_unindented_source(lines)

            try:
                tree = ast.parse(source).body[0]
            except SyntaxError:
                continue

            if not isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            self.static[id(obj)] = module, set(code.co_varnames), lines, tree
            self.items[it.nodeid] = id(obj)
            items_new.append(it)

        items[:] = items_new

    def pytest_runtestloop(self, session):
        noncumul_start, noncumul_stop = Event(), Event()
        pipe_parent, pipe_child = Pipe()
        gc.disable()

        for it in session.items:
            pid = os.fork()

            if pid == 0:
                proc = Process()

                coverage = Coverage(
                    data_file=None, cover_pylib=False, source=[os.getcwd()]
                )

                coverage.start()
                cumul_feats = get_cumulative_feats(proc)
                noncumul_start.set()

                try:
                    it.ihook.pytest_runtest_protocol(item=it, nextitem=None)
                finally:
                    noncumul_stop.set()

                    cumul_feats = [
                        x - y for x, y in zip(
                            get_cumulative_feats(proc), cumul_feats
                        )
                    ]

                    cov_feats = get_coverage_feats(
                        coverage, self.test_files, self.churn
                    )

                    pipe_child.send((cumul_feats, cov_feats))
                    os._exit(0)

            proc = Process(pid)
            noncumul_start.wait()
            noncumul_feats = get_noncumulative_feats(proc)

            while not noncumul_stop.wait(self.poll_rate):
                noncumul_feats = [
                    max(x, y) for x, y in zip(
                        get_noncumulative_feats(proc), noncumul_feats
                    )
                ]

            if proc.wait():
                pytest.exit(
                    "pytest-cannier: child process error.", 
                    pytest.ExitCode.INTERNAL_ERROR
                )

            cumul_feats, cov_feats = pipe_parent.recv()
            static_data = self.static[self.items[it.nodeid]]
            static_feats = get_static_feats(*static_data)
            
            self.features[it.nodeid] = [
                *cumul_feats, *cov_feats, *noncumul_feats, *static_feats
            ]
            
            noncumul_start.clear()
            noncumul_stop.clear()

        return True

    def save_to_db(self, cur):
        cur.execute(
            "update counters "
            "set count_features = count_features + 1 "
            "where id = 1"
        )

        cur.executemany(
            "insert or ignore into item "
            "values (null, ?, 0, 0, 0, 0, 0, 0)", 
            [(nodeid,) for nodeid in self.features]
        )

        cur.execute(
            "select id, nodeid "
            "from item"
        )

        nodeid_to_id = {
            nodeid: item_id for item_id, nodeid in cur.fetchall()
        }

        cur.executemany(
            "update item "
            "set n_runs_features = n_runs_features + 1 "
            "where id = ?", 
            [(nodeid_to_id[nodeid],) for nodeid in self.features]
        )

        cur.executemany(
            "insert into features "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
            [
                (nodeid_to_id[nodeid], *features_nodeid) 
                for nodeid, features_nodeid in self.features.items()
            ]
        )
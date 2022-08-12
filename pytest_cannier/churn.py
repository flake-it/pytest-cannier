import os
import pytest
import sqlite3
import subprocess as sp


def get_churn_file(commit_window, file_name):
    l_no = 1
    churn_file = {}

    while True:
        proc = sp.run(
            [
                "git", "--no-pager", "log", "-L", 
                f"{l_no},{l_no}:{file_name}", "--no-patch", 
                f"HEAD~{commit_window}..HEAD"
            ],
            encoding="UTF-8", stdout=sp.PIPE, stderr=sp.PIPE
        )

        if proc.returncode:
            if proc.stderr == (
                f"fatal: file {file_name} has only {l_no - 1} lines\n"
            ):
                break

            proc.check_returncode()

        lines = proc.stdout.splitlines()
        churn_l_no = sum(l.startswith("commit") for l in lines)

        if churn_l_no:
            churn_file[l_no] = churn_l_no
            
        l_no += 1

    return churn_file


def get_churn(commit_window):
    churn = {}

    stdout = sp.check_output(
        [
            "git", "--no-pager", "diff", "--name-only",
            f"HEAD~{commit_window}..HEAD"
        ],
        encoding="UTF-8"
    )

    for file_name in stdout.splitlines():
        if os.path.exists(file_name) and file_name.endswith(".py"):
            churn_file = get_churn_file(commit_window, file_name)

            if churn_file:
                churn[file_name] = churn_file

    return churn


def save_churn(db_file, churn):
    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        
        cur.execute(
            "update counters "
            "set count_churn = count_churn + 1 "
            "where id = 1"
        )

        cur.executemany(
            "insert or ignore into file "
            "values (null, ?)", 
            [(file_name,) for file_name in churn]
        )

        cur.execute(
            "select id, file_name "
            "from file"
        )

        file_name_to_id = {
            file_name: file_id for file_id, file_name in cur.fetchall()
        }

        params = []

        for file_name, churn_file in churn.items():
            file_id = file_name_to_id[file_name]

            for l_no, churn_l_no in churn_file.items():
                params.append((file_id, l_no, churn_l_no))

        cur.executemany(
            "insert or ignore into line "
            "values (?, ?, ?)", 
            params
        )
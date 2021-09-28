#!/usr/bin/env python3

import sys
import psycopg2
import psycopg2.extras
import json
import time
import pytz
import itertools
import argparse
from datetime import datetime
from matplotlib import pyplot as plt

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--dbaddr", help="Хост базы данных, по-умолчанию localhost", default="localhost")
parser.add_argument("--dbname", help="Название базы данных, по-умолчанию v2021_om", default="v2021_om")
parser.add_argument("--dbuser", help="Пользователь базы данных, по-умолчанию postgres", default="postgres")
parser.add_argument("--dbpass", help="Пароль базы данных, по-умолчанию mypsqlpassword", default="mypsqlpassword")
args = parser.parse_args()

# Connect to database
conn = psycopg2.connect(
    host=args.dbaddr,
    user=args.dbuser,
    password=args.dbpass,
    database=args.dbname)

cur = conn.cursor(cursor_factory = psycopg2.extras.DictCursor)

# Cache all issued ballots in set
cur.execute("select payload -> 'voter_id' from transactions where method_id=4")
voter_ids_with_ballots = set([r[0] for r in cur.fetchall()])

# Perform database searches for all registrations
cur.execute("select payload from transactions where method_id=1")
total_blocks = cur.rowcount
binned_results = [0] * total_blocks
for i,row in enumerate(cur):
    voters = row[0]["voters"]
    for v in voters:
        if v in voter_ids_with_ballots:
            binned_results[i] += 1

# Build pretty plot
plt.plot(binned_results)
plt.grid()
plt.legend(["Процент проголосовавших в блоке"])
plt.xlabel("Последовательный номер блока (транзакции) регистрации избирателя")
    
# Show window with plot    
plt.show()

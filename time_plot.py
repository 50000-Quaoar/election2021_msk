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
parser.add_argument("-l", action="store", help="Номер округа для которого необходимо вывести ID кандидатов вместо построениея графика, 0 - все округа, по-умолчанию не выводить", default=-1)
parser.add_argument("-c", action="store", help="Путь до JSON файла с параметрами графика для построения", default="plot_config.json")
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
cur2 = conn.cursor(cursor_factory = psycopg2.extras.DictCursor)

# Load vote config from "create vote" transaction
cur.execute("select payload from transactions where method_id=0")
ballots_config = cur.fetchone()[0]["ballots_config"]
vote_options = {}
for d in ballots_config:
    vote_options.update(d["options"])
    
# If list command was issued - process it and exit
list_arg = int(args.l)
if list_arg >= 0:
    for d in ballots_config:
        if (list_arg == 0) or (d["district_id"] == list_arg):
            for o in d["options"]:
                print(o, ":", d["options"][o])
    sys.exit(0)

# Load plot configuration from JSON   
plot_config = json.load(open(args.c))

# Some helper constants, all times are in seconds
def TimeToSecs(t):
    return int(time.mktime(t.timetuple()))
MSK_TZ              = pytz.timezone("Europe/Moscow")
MSK_START_TIME      = datetime(2021, 9, 17, 8, 0, 0)
UNIXTIME_MSK_START  = TimeToSecs(datetime(2021, 9, 17, 8, 0, 0, tzinfo=MSK_TZ))
UNIXTIME_MSK_END    = TimeToSecs(datetime(2021, 9, 19, 21, 0, 0, tzinfo=MSK_TZ))
BIN_TIME            = plot_config["minutes_in_bin"] * 60 
RESULT_BINS         = (UNIXTIME_MSK_END-UNIXTIME_MSK_START) // BIN_TIME
GRAPH_TICK_TIME     = plot_config["minutes_per_axis_tick"] * 60

# Some helper functions
def TimeToSecondsFromStart(t):
    unixtime_msk = TimeToSecs(t)
    return unixtime_msk - UNIXTIME_MSK_START

def TimeToBin(t):
    mt = t.astimezone(MSK_TZ)   # to correct if DB has non MSK time
    return TimeToSecondsFromStart(mt) // BIN_TIME

def BinToTime(b):
    return datetime.fromtimestamp(b + UNIXTIME_MSK_START)

def GenerateTicks():
    x = range(0, RESULT_BINS, GRAPH_TICK_TIME // BIN_TIME)
    labels = []
    for i in x:
        labels.append(BinToTime(i * BIN_TIME).strftime('%d.%m %H:%M'))
    return [x,labels]

# Prepare data structures for plot
candidate_list = plot_config["candidates_to_plot"]
binned_results = [[0 for i in range(RESULT_BINS)] for j in range(len(candidate_list))]
legend_names = []

# Perform database searches for all candidates
for i,candidate in enumerate(candidate_list):
    candidate_name = vote_options[str(candidate)]
    print(i, ": обрабатываем голоса за кандидата", candidate_name)
    legend_names.append(candidate_name)
    
    cur.execute("select store_tx_hash from decrypted_ballots where decrypted_choice[1]='" + str(candidate) + "'")
    for row in cur:
        hash = row[0]
        cur2.execute("select datetime from transactions where hash=\'"+str(hash)+"\' limit 1")
        vote_time=cur2.fetchone()[0]
        bin_num = TimeToBin(vote_time)
        binned_results[i][bin_num] += 1

# Integrate if required
if plot_config["integrate"]:
    for b in range(1, RESULT_BINS):
        for i in range(len(candidate_list)):
            binned_results[i][b] += binned_results[i][b-1]

# Calculate percentage if required
if plot_config["percentage"]:
    for b in range(RESULT_BINS):
        total_votes_in_bin = 0
        for i in range(len(candidate_list)):
            total_votes_in_bin += binned_results[i][b]
        if (total_votes_in_bin != 0):
            for i in range(len(candidate_list)):
                binned_results[i][b] /= (total_votes_in_bin / 100)

# Build pretty plot
markers = itertools.cycle(['o', 's', 'v', '^', 'p', '*'])
for res in binned_results:
    plt.plot(res, marker=next(markers))
ticks = GenerateTicks()
plt.xticks(ticks[0], ticks[1], rotation=90)
plt.grid()
plt.legend(legend_names)
    
# Show window with plot    
plt.show()

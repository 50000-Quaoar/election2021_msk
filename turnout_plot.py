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

# Some helper constants, all times are in seconds
def TimeToSecs(t):
    return int(time.mktime(t.timetuple()))
MSK_TZ              = pytz.timezone("Europe/Moscow")
MSK_START_TIME      = datetime(2021, 9, 17, 8, 0, 0)
UNIXTIME_MSK_START  = TimeToSecs(datetime(2021, 9, 17, 8, 0, 0, tzinfo=MSK_TZ))
UNIXTIME_MSK_END    = TimeToSecs(datetime(2021, 9, 19, 21, 0, 0, tzinfo=MSK_TZ))
BIN_TIME            = 30*60 
RESULT_BINS         = (UNIXTIME_MSK_END-UNIXTIME_MSK_START) // BIN_TIME
GRAPH_TICK_TIME     = 3600 * 2
PREREVOTE_TIME      = datetime(2021, 9, 17, 9, 0, 0, tzinfo=MSK_TZ)
LOW_TURNOUT_VAL     = 90
HIGH_TURNOUT_VAL    = 99

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

# Cache all issued ballots in set
prerevote_issued = 0
prerevote_voted = 0
cur.execute("select payload->'voter_id' from transactions where method_id=4")
voter_ids_with_ballots = [r[0] for r in cur.fetchall()]
cur.execute("select datetime from transactions where method_id=4")
ballot_times_list = [r['datetime'] for r in cur.fetchall()]
for t in ballot_times_list:
    if t < PREREVOTE_TIME:
        prerevote_issued += 1
ballots_times = dict(zip(voter_ids_with_ballots, ballot_times_list))
voter_ids_with_ballots_set = set(voter_ids_with_ballots)

# Perform database searches for all registrations
cur.execute("select payload from transactions where method_id=1")

total_blocks = cur.rowcount
turnout = [0] * total_blocks
forplot_x = []
forplot_y = []
low_turnout_bins = [0] * RESULT_BINS
high_turnout_bins = [0] * RESULT_BINS
norm_turnout_bins = [0] * RESULT_BINS
votes_time = [0] * RESULT_BINS

for i,row in enumerate(cur):
    voters = row[0]["voters"]
    voters_voted = []
    for v in voters:
        if v in voter_ids_with_ballots_set:
            voters_voted.append(v)
            turnout[i] += 1
            forplot_x.append(i)
            forplot_y.append(ballots_times[v])
    for v in voters_voted:
        if turnout[i] < LOW_TURNOUT_VAL:
            low_turnout_bins[TimeToBin(ballots_times[v])] += 1
        elif (turnout[i] >HIGH_TURNOUT_VAL):
            high_turnout_bins[TimeToBin(ballots_times[v])] += 1
        else:
            norm_turnout_bins[TimeToBin(ballots_times[v])] += 1

# Perform database searches for all votes
cur.execute("select datetime from transactions where method_id=6")
for i,row in enumerate(cur):
    votes_time[TimeToBin(row[0])] += 1
    if row[0] < PREREVOTE_TIME:
        prerevote_voted += 1

print("Время до возможности переголосования:", PREREVOTE_TIME.strftime('%d.%m %H:%M'), "Выдано бюллетеней:", prerevote_issued, "Голосов:", prerevote_voted)    

# Normalize
low_sum = sum(low_turnout_bins)
high_sum = sum(high_turnout_bins)
norm_sum = sum(norm_turnout_bins)
vote_sum = sum(votes_time)
for i in range(RESULT_BINS):
    low_turnout_bins[i] *=  100 / low_sum
    high_turnout_bins[i] *= 100 / high_sum
    norm_turnout_bins[i] *= 100 / norm_sum
    votes_time[i] *= 100 / vote_sum

# Build several plots
axs = [plt.subplot2grid((2, 2), (1, 0), colspan=2),plt.subplot2grid((2, 2),(0, 0)), plt.subplot2grid((2, 2),(0, 1))]

# Create issue ballots & vote times plot
markers = itertools.cycle(['o', 's', 'v', '^', 'p', '*'])
axs[0].plot(low_turnout_bins, marker=next(markers))
axs[0].plot(high_turnout_bins, marker=next(markers))
axs[0].plot(norm_turnout_bins, marker=next(markers))
axs[0].plot(votes_time, marker=next(markers))
ticks = GenerateTicks()
axs[0].set_xticks(ticks[0])
axs[0].set_xticklabels(ticks[1], rotation=90)
axs[0].grid()
axs[0].legend(["Динамика выдачи бюллетеней избирателям из блоков с явкой < "+str(LOW_TURNOUT_VAL)+"% (в % от полного числа таковых)", \
    "Динамика выдачи бюллетеней избирателям из блоков с явкой > "+str(HIGH_TURNOUT_VAL)+"% (в % от полного числа таковых)", \
    "Динамика выдачи бюллетеней избирателям из блоков с явкой "+str(LOW_TURNOUT_VAL)+"-"+str(HIGH_TURNOUT_VAL)+"% (в % от полного числа таковых)", \
    "Динамика голосования  (в % от полного числа голосов)"])

# Create 
axs[1].plot(turnout)
axs[1].grid()
axs[1].legend(["Процент проголосовавших в блоке"])
axs[1].set_xlabel("Последовательный номер блока (транзакции) регистрации избирателя")

# Create issue ballot time scatter plot
axs[2].scatter(forplot_x, forplot_y, 0.005)
axs[2].set_xlabel("Последовательный номер блока (транзакции) регистрации избирателя")
axs[2].set_ylabel("Время выдачи бюллетеня")

    
# Show window with plot    
plt.show()

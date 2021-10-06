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
cur2 = conn.cursor(cursor_factory = psycopg2.extras.DictCursor)

# Some helper constants, all times are in seconds
def TimeToSecs(t):
    return int(time.mktime(t.timetuple()))
def TimeToMSecs(t):
    return TimeToSecs(t)*1000 + t.microsecond//1000
def MskT(d, h, m = 0, s = 0):
    return datetime(2021, 9, d, h, m, s, tzinfo=MSK_TZ)
    
MSK_TZ              = pytz.timezone("Europe/Moscow")
MSK_START_TIME      = datetime(2021, 9, 17, 8, 0, 0)
UNIXTIME_MSK_START  = TimeToSecs(datetime(2021, 9, 17, 8, 0, 0, tzinfo=MSK_TZ))
UNIXTIME_MSK_END    = TimeToSecs(datetime(2021, 9, 19, 21, 0, 0, tzinfo=MSK_TZ))
BIN_TIME            = 60*60 
RESULT_BINS         = (UNIXTIME_MSK_END-UNIXTIME_MSK_START) // BIN_TIME
GRAPH_TICK_TIME     = 3600 * 1

MSECS_IN_BIN        = 20
MSEC_BINS           = 5000 // MSECS_IN_BIN

# Some helper functions
def TimeDiffMs(t0, t1):
    return (TimeToMSecs(t0) - TimeToMSecs(t1))
    
def DiffToBin(t0, t1):
    diff_msec = TimeDiffMs(t0, t1) // MSECS_IN_BIN
    if diff_msec < 0:
        diff_msec = 0
    elif diff_msec >= MSEC_BINS:
        diff_msec = MSEC_BINS-1
    return diff_msec 

# Cache all voted keys in dict
cur.execute("select author,datetime,hash from transactions where method_id=6")
tmp_list = cur.fetchall()
voter_keys_voted = [r[0] for r in tmp_list]
vote_times_list = [r[1] for r in tmp_list]
hash_list = [int(r[2], base=16) for r in tmp_list]
vote_times = dict(zip(voter_keys_voted, tuple(zip(hash_list, vote_times_list))))
assert(len(voter_keys_voted) == len(vote_times))

# Cache all decrypted choices in dict
cur.execute("select store_tx_hash,decrypted_choice[1] from decrypted_ballots")
tmp_list = cur.fetchall()
decrypted_choice_list = [int(r[1]) for r in tmp_list]
hash_list = [int(r[0], base=16) for r in tmp_list]
decrypted_choices = dict(zip(hash_list, decrypted_choice_list))

# Some structs & consts (dirty)
to_plot_bins = [0] * MSEC_BINS
er_bins = [0] * MSEC_BINS
kprf_bins = [0] * MSEC_BINS
nl_bins = [0] * MSEC_BINS
ldpr_bins = [0] * MSEC_BINS
sr_bins = [0] * MSEC_BINS
other_bins = [0] * MSEC_BINS
total_bins = [0] * MSEC_BINS
invalid_votes = 0

sobyanin_list=[111906259, 182884641, 216438542, 162832179, 191070849, 142334949, 113246509, 178404279, 115873463, 182247230, 172154321, 217404809, 193509934, 111366669, 149646701]
ug_list=[174344765, 153770437, 136749451, 147971856, 181315508, 191715167, 153469885, 173789580, 191550503, 191309977, 143715510, 213415260, 153878280, 164133981, 193846930]

ER = 151256486
KPRF = 113055488
NL = 143916521
ZEL = 122866705
LDPR = 131810669
SR = 167917702

# Perform database searches for all access checks
cur.execute("select payload->'voter_key',datetime from transactions where method_id=5")

for i,row in enumerate(cur):
    voter_key = row[0]
    try:
        vote_time = vote_times[voter_key][1]
    except:
        invalid_votes += 1
        continue
    
    # Filter by time if desired
    # ~ if not (((vote_time > MskT(19,2)) and (vote_time < MskT(19,12))) or \
        # ~ ((vote_time > MskT(19,13)) and (vote_time < MskT(19,16)))):
        # ~ continue
    
    timediff = TimeDiffMs(vote_time, row[1])
    timediff_bin = DiffToBin(vote_time, row[1])
    to_plot_bins[timediff_bin] += 1
    
    total_bins[timediff_bin]+=1
    chash = vote_times[voter_key][0]
    cand = decrypted_choices[chash]
    
    if cand == ER:
        er_bins[timediff_bin]+=1
    elif cand == KPRF:
        kprf_bins[timediff_bin]+=1
    elif cand == NL:
        nl_bins[timediff_bin]+=1
    elif cand == LDPR:
        ldpr_bins[timediff_bin]+=1
    elif cand == SR:
        sr_bins[timediff_bin]+=1
    else:
        other_bins[timediff_bin]+=1

# Normalize
for i in range(1,MSEC_BINS):
    if (total_bins[i] >= 100):
        er_bins[i] /= total_bins[i] * 0.01
        kprf_bins[i] /= total_bins[i] * 0.01
        nl_bins[i] /= total_bins[i] * 0.01
        ldpr_bins[i] /= total_bins[i] * 0.01
        sr_bins[i] /= total_bins[i] * 0.01
        other_bins[i] /= total_bins[i] * 0.01
    else:
        er_bins[i] = er_bins[i-1]
        kprf_bins[i] = kprf_bins[i-1]
        nl_bins[i] = nl_bins[i-1]
        ldpr_bins[i] = ldpr_bins[i-1]
        sr_bins[i] = sr_bins[i-1]
        other_bins[i] = other_bins[i-1]

# Plotting
fig,axs = plt.subplots(2)
axs[0].plot(to_plot_bins)
axs[0].grid()
axs[1].plot(er_bins)
axs[1].plot(kprf_bins)
axs[1].plot(nl_bins)
axs[1].plot(ldpr_bins)
axs[1].plot(sr_bins)
axs[1].plot(other_bins)
axs[1].grid()
axs[1].legend(["ЕР, %", "КПРФ, %", "Новые Люди, %", "ЛДПР, %", "СР, %", "Остальные, %"])

ticks = range(0, MSEC_BINS, MSECS_IN_BIN)
axs[0].set_xticks(ticks)
axs[0].set_xticklabels([r*MSECS_IN_BIN for r in ticks])
axs[1].set_xticks(ticks)
axs[1].set_xticklabels([r*MSECS_IN_BIN for r in ticks])
axs[1].set_xlabel("Время между транзакцией проверки ключа избирателя и транзакцией голосования в миллисекундах")

# Show window with plot    
plt.show()

#!/usr/bin/env python3
# Based on https://gist.github.com/SaveTheRbtz/246eab8557b0217ab3945e15cef6ffe8

import psycopg2
import psycopg2.extras
import json
import sys
import argparse
import nacl.utils
from nacl.public import PrivateKey, PublicKey, Box
from choices_pb2 import Choices

# Decode command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--dbaddr", help="Хост базы данных, по-умолчанию localhost", default="localhost")
parser.add_argument("--dbname", help="Название базы данных, по-умолчанию v2021_om", default="v2021_om")
parser.add_argument("--dbuser", help="Пользователь базы данных, по-умолчанию postgres", default="postgres")
parser.add_argument("--dbpass", help="Пароль базы данных, по-умолчанию mypsqlpassword", default="mypsqlpassword")
args = parser.parse_args()

# Helper functions
def ErrorExit(e):
    print("Во время расшифровки произошла ошибка, возможно БД повреждена:", e)
    sys.exit(1)

def GetDecryptedBallotsNumber(conn):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM decrypted_ballots")
    decrypted_ballots = int(cur.fetchone()[0])
    return decrypted_ballots

def GetVotedBallotsNumber(conn):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM transactions WHERE method_id = 6;")
    voted_ballots = int(cur.fetchone()[0])
    return voted_ballots

# Connect to database
conn = psycopg2.connect(
    host=args.dbaddr,
    user=args.dbuser,
    password=args.dbpass,
    database=args.dbname)

# Fetch decryption key
cur_tmp = conn.cursor(cursor_factory = psycopg2.extras.DictCursor)  
cur_tmp.execute("select payload from transactions where method_id=8")
hex_privatekey = cur_tmp.fetchone()[0]['private_key']
skey = PrivateKey(bytes.fromhex(hex_privatekey))

# Check ballots number
voted_ballots=GetVotedBallotsNumber(conn)
inititally_decrypted_ballots=GetDecryptedBallotsNumber(conn)
if voted_ballots == inititally_decrypted_ballots:
    print("База полностью расшифрована, работа не требуется")
    sys.exit(0)
    
# Perform decode
print("Приватный ключ голосования:", hex_privatekey)
print("Расшифрование бюллетеней, это может занять продолжительное время...")
cur = conn.cursor(name="cursor_name", withhold=True, cursor_factory = psycopg2.extras.DictCursor)
cur.execute("select * from transactions where method_id=6")
for i, row in enumerate(cur):
    try:
        if (i%20000) == 0:
            decrypted_ballots=GetDecryptedBallotsNumber(conn)
            print("Процент расшифрованных бюллетеней в БД: {:.2f}%".format(decrypted_ballots*100/(voted_ballots)))
        cur2 = conn.cursor()
        cur2.execute(f"select * from decrypted_ballots where store_tx_hash='{row['hash']}'")
        if cur2.rowcount == 0:
            enc = row['payload']['encrypted_choice']
            pkey = PublicKey(bytes.fromhex(enc['public_key']))
            box = Box(skey, pkey)
            pb = box.decrypt(bytes.fromhex(enc['encrypted_message']), bytes.fromhex(enc['nonce']))
            offset = int.from_bytes(pb[:2], 'big')+2
            choices = Choices().FromString(pb[offset:])
            sql = f"""INSERT INTO decrypted_ballots(store_tx_hash,decrypted_choice,status)
                 VALUES('{row['hash']}',array[{choices.data[0]}]::bigint[],'"Manual"');"""
            cur2.execute(sql)
            conn.commit()
    except Exception as e:
        try:
            decrypted_ballots=GetDecryptedBallotsNumber(conn)
            if decrypted_ballots == voted_ballots:
                print("Все доступные в БД бюллетени расшифрованы, полное число бюллетеней:", decrypted_ballots)
                sys.exit(0)
            else:
                ErrorExit(e)
        except Exception as e:
            ErrorExit(e)

decrypted_ballots=GetDecryptedBallotsNumber(conn)
if decrypted_ballots == voted_ballots:
    print("Все доступные в БД бюллетени расшифрованы, полное число бюллетеней:", decrypted_ballots)            
    

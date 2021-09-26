#!/usr/bin/env bash

set -e

if [ "$#" != 2 ]; then
	echo "Usage: $0 <gzipped-sql-dump-file-path> <db-name>"
	exit 1
fi

echo "Создание базы данных $2 и её импорт из дампа $1. Процесс может занять продолжительное время..."

echo "CREATE DATABASE $2" | sudo -u postgres -i psql
zcat $1 | sudo -u postgres -i psql $2
	

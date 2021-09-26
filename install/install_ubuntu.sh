#!/bin/sh

# Installs all required packages for vote DB & plot builder
sudo apt update
sudo apt install -y postgresql python3-psycopg2 python3-googleapi python3-nacl python3-matplotlib python3-pip
pip install --upgrade --user protobuf

# Reset PosgreSQL password
echo "ALTER USER postgres WITH PASSWORD 'mypsqlpassword';" | sudo -u postgres psql -w

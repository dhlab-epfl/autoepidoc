# AutoEpiDoc – Automated Generation of EpiDoc XML Files from CSV Data
This project provides a two-step Python pipeline to convert tabular CSV data of Armenian epigraphic inscriptions into EpiDoc-compliant TEI XML files.
It was developed as part of the ArmEpiC initiative hosted by the EPFL Digital Humanities Laboratory (DHLab).
## Project Overview
The workflow consists of two main scripts:
1. `csv_to_mysql.py` imports and normalizes all CSV files into a MySQL database.
2. `mysql_to_epidoc.py` queries the MySQL database and exports one EpiDoc XML file per inscription record.
## Requirements 
Make sure you have [Python 3.9+](https://www.python.org/downloads). 

You also need to setup a MySQL Server by downloading the [installer](https://dev.mysql.com/downloads/mysql) and configurating the server by following the instructions during the installation wizard. Make sure you write down the host ip, port, username and password to access the server

If you have issues you can follow this [official tutorial](https://dev.mysql.com/doc/mysql-getting-started/en). 

Then install the necessary Python libraries :
```
pip install -r requirements.txt
```
## Step 1: Import CSVs into MySQL
The first script reads all .csv files from a directory and uploads them as tables into a MySQL database. If the database doesn't already exists the script will create it.
You can do so by putting all your input data into a directory and call the script with the right arguments. Here is an example usage :
```bash
python csvs_to_mysql.py \
  --csv_dir ./path_to_directory \
  --mysql_user server_username \
  --mysql_pass server_password \
  --mysql_host server_host (most likely 127.0.0.1) \
  --mysql_port server_port  \
  --mysql_db database_name
```

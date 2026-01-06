# AutoEpiDoc – Automated Generation of EpiDoc XML Files from CSV Data
This project provides a two-step Python pipeline to convert tabular CSV data of Armenian epigraphic inscriptions into EpiDoc-compliant TEI XML files.
It was developed as part of the ArmEpiC initiative hosted by the EPFL Digital Humanities Laboratory (DHLab).
## Project Overview
The workflow consists of two main scripts:
1. `csv_to_mysql.py` imports and normalizes all CSV files into a MySQL database.
2. `mysql_to_epidoc.py` queries the MySQL database and exports one EpiDoc XML file per inscription record.
3. `mysql_to_authority_list.py` queries the MySQL database and exports XML authority lists.
## Requirements 
Make sure you have [Python 3.9+](https://www.python.org/downloads). 

You also need to setup a MySQL Server by downloading the [installer](https://dev.mysql.com/downloads/mysql) and configurating the server by following the instructions during the installation wizard. Make sure you write down the host ip, port, username and password to access the server.

If you have issues you can follow this [official tutorial](https://dev.mysql.com/doc/mysql-getting-started/en). 

Your data must follow the format presented in the `dummy_data` folder.

Then clone the repository and navigate to it via the terminal. Install the necessary Python libraries :
```
pip install -r requirements.txt
```
## Step 1: Import CSVs into MySQL
First you need to prepare your data as csv files. If you have it as spreadsheets you can simply do `File -> Export -> CSV`. Make sure the data doesn't contain commas or replaces them with other characters such as `;`.

The first script reads all .csv files from a directory and uploads them as tables into a MySQL database.
You can do so by putting all your input data into a directory and call the script in the terminal with the right arguments. Here is an example usage :
```bash
python csvs_to_mysql.py \
  --csv_dir ./path_to_directory \
  --mysql_user server_username \
  --mysql_pass server_password \
  --mysql_db database_name
```
#### Explanation of the parameters :
- `csv_dir` is the path to the directory containing your csv epigraphic data.
- `mysql_user`, `mysql_pass` are respectively the username and password you use to connect to your MySQL server.
- `mysql_db` is the name of the database you want to use. If the database doesn't already exist, the script will create it.
- Optional : `mysql_host` and `mysql_port` are the host address and port you use to connect to your MySQL server. Their default values are `127.0.0.1` and `3306`.

## Step 2: Convert your data into EpiDoc format
Now that your data is transfered in the database, you can use the second script to convert it to EpiDoc XML files. The script will create one XML file for each line in the `epigraphysamples` table.
Once again you can call the script following this example :
```bash
python mysql_to_epidoc.py \
--user databaseuser \
--password userpassword \
--db databasename \
--out ./output_folder
```
#### Explanation of the parameters :
- Once again, `user` and `password` are the identifiers to connect to your server.
- `db` is the name of the database containing your data. Make sure it is the same as the one in the previous script.
- `out` is the name of the folder where you want the xml files to be put
- Optional : As previously, `host` and `port` can be specified and have default values `127.0.0.1` and `3306`. `limit` specifies the maximum number of epigraphic samples you want to process, default value is `10`. `authority` is the name of your project/organisation and has default value `ArmEpic - digital collection of armenian epigraphic inscriptions`.

With proper execution, you should have the XML files ready in the specified folder. If you have issues with sql queries, make sure the collumn names follow the required format or modify the code if need be.

## Step 3: Convert your data to authority lists
The last step is to use the third script to produce authority lists. This script will produce 9 authority lists, one for each of the following : biblography, inscription types, materials, monuments, object types, places, preservation states, scripts and techniques. Note that the provided folder can either be blank or already have authority lists of the correct format. If the list is missing the script creates it, otherwise the existing one is updated with new entries from your database.
```
 python mysql_to_authority_list.py \
        --host 127.0.0.1 \
        --user databaseuser \
        --password userpassword \
        --db databasename \
        --out ./output_folder
```
## Final Notice

This codebase is provided as a flexible and extensible framework.
Although it has been developed for a specific research context, its structure and logic are intentionally modular and can be adapted to other datasets, schemas, or workflows.

Users are encouraged to modify, extend, or repurpose the code to fit their own use cases, including but not limited to:

Different database structures

Alternative authority lists or controlled vocabularies

Other TEI / EpiDoc–based projects or XML standards

No part of the code is considered fixed or prescriptive. Adjustments may be required depending on local requirements, data models, or institutional practices.

# Overview
A python program that grabs select data from TFRRS.com (online track & field database) and stores in a PostgresSQL database. A database.ini file is used to read in credentials. Collects the top 100 marks for each event for a given range of indoor/outdoor seasons (startyear-endyear). Ranges from 2012 to current marks. Formats and stores rows in a very functional format. BeauitfulSoup and PostgreSQL used. Loading animation and progress bar shown below. Also has several mechanisms for preventing invalid rows (runs queries to remove errors and skips over bad data).


![running](https://github.com/jacknormand/TFRRS-TopQualifer/assets/21299000/c6669730-820b-4fa6-a97e-84a5be6e6790)



# Usage
'python3 scrape.py 2012 2024' <br>
Supports scraping just one year also, just make startyear = endyear <br>
**ONLY WORKS FROM 2012-ON**<br>




# Disclaimer
This project is for educational purposes only. Please do not use irresponsibly.

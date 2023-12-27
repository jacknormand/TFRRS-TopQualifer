import bs4
import psycopg2
import requests
import time
import sys
from configparser import ConfigParser
from datetime import datetime

# gets performances from a results links for given year/season
# store in postgre
# returns true if success, false otherwise
def scrapePerformances(resultsLink):
    r = requests.get(resultsLink)
    soup = bs4.BeautifulSoup(r.content, "html5lib")
    outer_div = soup.find('div', class_= 'panel-body frame-loading-hide')

    if outer_div:
        rowList = outer_div.find_all('tr', class_='allRows')
        return rowList

    return None

# gets the link to the page containing all the top marks for each season
# year is just the year, seasonStr is either indoor or outdoor
# CURRENTLY ONLY: results for NCAA d1 qualifiers
# TODO: D2, D3, juco, christian, naia
def getResultsLink(year,seasonStr):

    #Depending on older results might add gender spec 
    url = "https://tf.tfrrs.org/college_archives_tab.html?"+seasonStr+"=1&year="+year
    r = requests.get(url)
    soup = bs4.BeautifulSoup(r.content, 'html5lib')
    
    # just gets first div in row, first list in div, and link from first a tag
    # should be the same for every year, returns link when found
    row_div = soup.find('div', class_= 'row')
    if row_div:
        first_div_inside_row = row_div.find('div')
        if first_div_inside_row:
            ul_inside_first_div = first_div_inside_row.find('ul')
            if ul_inside_first_div:
                first_li_inside_ul = ul_inside_first_div.find('li')
                a_tag = first_li_inside_ul.find('a')
                if a_tag:
                    return a_tag.get('href')
    return None

# config parse function
# gets data from database.ini file
def config(filename='database.ini', section='postgresql'):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))
    return db

# progress!
def progressbar(current_value,total_value):
    if total_value == 0:
        total_value = 1
    progress = (current_value/total_value) * 10
    boxes = ("■" * int(abs(progress)))
    spaces = " " * (10-len(boxes))
    loadbar = f" Scraping Progress:[{boxes+spaces}]{int(abs(progress)*10)}%"
    print(loadbar, end ='\r')

# convert
def convertTime(time_str):
    try:
        if ':' in time_str:
            # If the time format includes minutes and seconds (e.g., 10:56.66)
            time_format = "%M:%S.%f"
        else:
            # If the time format is in seconds only (e.g., 6.94)
            time_format = "%S.%f"

        # Parse the time string to a timedelta object
        time_delta = datetime.strptime(time_str, time_format) - datetime(1900, 1, 1)

        # Convert the timedelta to seconds with 2 decimal places
        seconds = time_delta.total_seconds()

        # Round to 2 decimal places
        seconds = round(seconds, 2)

        return seconds
    except ValueError:
        print("Invalid time format. Please use either seconds (e.g., 6.94) or minutes:seconds.milliseconds (e.g., 10:56.66).")
        return None
    
# remove m at the end, or just keep the same
def convertMark(mark):
    # if a meter distance
    if mark[-1] == 'm':
        return mark[:-1]
    return mark

# connects to db, scrapes all, stores them in postgreSQL
def scrapeAllYears():
    if not sys.argv[1] or not sys.argv[2]:
        print("Please provide a valid start and stop year")
        print("Example usage: Python3 scrape.py 2023 2024")
    # connect
    conn = None
    try:
        params = config()
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)
        cur = conn.cursor()

        # temp year and season vars
        # begin operations
        cur.execute("""DROP TABLE IF EXISTS TopPerformances""")
        cur.execute("""CREATE TABLE IF NOT EXISTS TopPerformances (
            entryid SERIAL PRIMARY KEY,
            event varchar(255),
            rank int NOT NULL,
            athlete varchar(255),
            team varchar(255),
            time float,
            mark float,
            score int,
            meet varchar(255),
            season varchar(255),
            meetdate date)
            """)

        # loop through seasons and scrape!!!!
        # starts at 2010
        # ends at latest year (2024)
        #START
        # startYear 
        startYear = 2013
        endYear = 0
        year = datetime.today().year
        # if user inputs range
        if sys.argv[1]:
            startYear = int(sys.argv[1])

        if sys.argv[2]:
            endYear = int(sys.argv[2])
        # variables
        linkYear = startYear
        linkSeason = "indoor"
        curLink = getResultsLink(str(linkYear), linkSeason)
        # END YEAR
        
        # event hashing, so we can check how to store event marks in DB
        timeEvents = { '400Hurdles', '110Hurdles', '100Hurdles', '10000Meters', '1500Meters',  '100Meters', '60Meters', '200Meters', 
                      '400Meters', '800Meters', '4x400Relay', '4x100Relay', '3000Steeplechase', 'Mile', '3000Meters', '5000Meters',
                      '60Hurdles', '4x400Relay', 'DistanceMedleyRelay'}
        meterEvents = {'Javelin', 'Hammer', 'HighJump', 'PoleVault', 'LongJump', 'TripleJump', 'ShotPut', 'Discus', 'WeightThrow'}
        multiEvents = ('Decathlon', 'Pentathlon', 'Heptathlon')
        
        print(f"Beginning scrape from {startYear} to {endYear}")
        
        # loop through the years/seasons
        while curLink and linkYear <= endYear:
            progressbar(linkYear-startYear, year-endYear)
            #scrape indoor
            # print(f"{linkYear}, {linkSeason}, {curLink}")
            # gets rows
            rows = scrapePerformances(curLink)
            
            # loop through the rows in each season
            for row in rows:
                try:
                    data = row.find_all('a')
                    rank = data[0].text
                    meetdate = row.find('td', class_='tablesaw-priority-2').text
                    meetdate = datetime.strptime(meetdate, '%b %d, %Y').strftime('%Y-%m-%d')
                    # this div doesnt exist in relays, so i use it to check
                    checkRelay = row.find('td', class_='tablesaw-priority-1')
                    # gather data depending on relay or nah
                    # IF A RELAY!
                    # fix high jump 
                    if not checkRelay:
                        team = data[1].text
                        result = data[2].text
                        # MULTIPLE athletes are stored as one for the time being, dont need to make another table
                        athlete = f"{data[3].text}, {data[4].text}, {data[5].text}, {data[6].text}"
                        meet = data[7].text
                        event = data[2].get("href").split("/")[-1].replace("-","")
                        # if rank == "1":
                        #     print(f"rank:{rank} team:{team} time: {time}athletes:{athlete} meet:{meet} date:{meetdate}")
                    else:
                        athlete = data[1].text
                        team = data[2].text
                        result = data[3].text
                        meet = data[4].text
                        event = data[3].get("href").split("/")[-1].replace("-","")
                        # if rank == "1":
                            # print(f"rank:{rank} athlete:{athlete} team:{team} time:{time} meet:{meet} date:{meetdate} ")

                    #RESULT INSERT depending on a field event, multi, or run
                    # convert to seconds
                    if event in timeEvents:
                        time = convertTime(result)
                        cur.execute("""INSERT INTO TopPerformances (event, rank, athlete, team, time, meet, season, meetdate)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                                (event, int(rank), athlete, team, time, meet, linkSeason, meetdate))
                    elif event in meterEvents:
                        mark = convertMark(result)
                        meet = data[5].text
                        cur.execute("""INSERT INTO TopPerformances (event, rank, athlete, team, mark, meet, season, meetdate)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                                (event, int(rank), athlete, team, mark, meet, linkSeason, meetdate))
                    elif event in multiEvents:
                        score = convertMark(result)
                        cur.execute("""INSERT INTO TopPerformances (event, rank, athlete, team, score, meet, season, meetdate)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                                (event, int(rank), athlete, team, score, meet, linkSeason, meetdate))
                    else:
                        print("ERROR: BAD EVENT DETECTED")
                        return
                except:
                    continue
            # set for next one
            if linkSeason == "indoor":
                linkSeason = "outdoor"
            else:
                linkYear+=1
                linkSeason = "indoor"
            # get link for outdoor
            curLink = getResultsLink(str(linkYear), linkSeason)
        progressbar(1, 1)

        print("\nSuccessfully completed scrape")

        cur.close()
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print('\n')
        print(athlete)
        print(event)
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')

if __name__ == "__main__":
    #currently works 2012-current
    #doesnt work earlier (yet) because:
    #in the lists before 2012 there is weird imgs and stuff
    #that screws up the indexing of the scraper
    #can be fixed and might eventually get fixed
    #link scraper (getResultsLink) doesnt get links for
    #before 2010 though. havent even looked into it

    #happy scraping :)
    scrapeAllYears()

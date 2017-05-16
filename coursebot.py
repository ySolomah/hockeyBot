#!/usr/bin/env python
import praw
import pyrebase
import re
import requests
from bs4 import BeautifulSoup
from config import firebase, reddit
from time import sleep
import json


# Subreddits to monitor, separated by '+'
SUBREDDITS = 'testingground4bots'
courseBotName = reddit["username"]
dbIncrement = "6"
NewTestDb = "itemIdDb" + dbIncrement
CourseDb = "courseDb" + dbIncrement

# Regex constants
COURSE_NAME_REGEX = re.compile(r'(?i)[Gg][Aa][Mm][Ee][ ][Tt][Hh][Rr][Ee][Aa][Dd]')
GDT_REGEX = re.compile(r'((?i)[Gg][Dd][Tt])')
COURSE_INFO_REGEX = re.compile(r'[a-zA-Z]{3}[0-9]{3}[h|H|y|Y]{1}[1]{1}')

# Firebase initialization

fb = pyrebase.initialize_app(firebase)
db = fb.database()

# Reddit bot login, returns reddit object used to reply with this account
def login():
    r = praw.Reddit(username = reddit["username"],
                password = reddit["password"],
                client_id = reddit["client_id"],
                client_secret = reddit["client_secret"],
                user_agent = 'BetterCourseBot')
    print("Logged in");
    return r

# Update firebase 'serviced' with <item_id> to avoid multiple comments by bot
def updateServiced(item_id):
    print("Updating service");
    payload = {item_id: True}
    db.child(NewTestDb).update(payload)

#def setFalse(item_id):
#    payload = { item_id: False }
#    db.child(NewTestDb).update(payload);

# Check if <item_id> has already been replied to by bot
def isServiced(item_id):
    request = db.child(NewTestDb).child(item_id).get().val()
    if request:
        print("Already serviced: " + item_id)
        return True
    print("Not serviced yet: " + item_id)
    return False

def parseForTeam(title):
        url = "http://stats.tsn.ca/GET/urn:tsn:nhl:injuries?type=json"
        injuriesHeader = { 'Referer': 'http://www.tsn.ca/nhl/injuries'}
        r = requests.get(url, headers=injuriesHeader);
        #print(r.text);
        data = json.loads(r.text)
        returnString = "Source: www.tsn.ca/nhl/injuries" + "\n\n\n\n";
        injuryReports = data["InjuryReports"]
        print("Data length: " + str(len(data)));
        print("Injury reports length: " + str(len(injuryReports)));
        matched = False;
        for i in range (0, len(injuryReports)):
            teamObj = injuryReports[i];
            print("\n\nTeam: " + teamObj["Team"]["Name"])
            if(teamObj["Team"]["Name"].lower() in title):
                matched = True;
                returnString = returnString + teamObj["Team"]["Name"] + "|\n\n";
                totalAddString = '';
                for j in range (0, len(teamObj["Injuries"])):
                    injuryItem = teamObj["Injuries"][j];
                    print("Player: " + injuryItem["Player"]["FirstName"] + " " + injuryItem["Player"]["LastName"]);
                    print("Injury: " + injuryItem["InjuryDetail"]["Description"]);
                    print("Date: " + injuryItem["ReportedDate"]);
                    totalAddString = totalAddString + injuryItem["Player"]["FirstName"] + " " + injuryItem["Player"]["LastName"] + "\n" + "Injury: " + injuryItem["InjuryDetail"]["Description"] + "\n" + "Date: " + injuryItem["ReportedDate"] + " |" + "\n\n"
                totalAddString = totalAddString + "\n\n" + "Total: " + str(len(teamObj["Injuries"]));
                returnString = returnString + totalAddString + "\n\n\n\n";
        if(not matched):
            returnString = "";
        return(returnString);

def espnParse(title):
    url = "http://www.espn.com/nhl/injuries";
    r = requests.get(url);
    doc = BeautifulSoup(r.text, "html.parser")
    returnString = "\n\nSource: www.espn.com/nhl/injuries" + "\n\n";
    table = doc.body;
    tableMain = doc.findAll("table", recursive=True);
    print("Body length: " + str(len(doc.findAll(True))));
    print("Length of elements: " + str(len(table)));
    print("Length of tbody elements: " + str(len(tableMain)));
    first = True;
    addTeam = False;
    matched = False;
    TotalCount = 0;
    previousTeamUsed = False;
    if("table" in r.text):
        print("table is in!!!");
    if(tableMain and len(tableMain) >= 1):
        for item in tableMain[0].findAll(True, recursive=False):
            #print("Text: "  + item.text + "\n");

            if("stathead" in item['class']):
                print("\n\n\nTeam: " + item.td.text + "\n\n");
                if(previousTeamUsed):
                    previousTeamUsed = False;
                    if(matched):
                        returnString += "\n\n" + "Total: " + str(TotalCount) + "\n\n\n\n";
                        TotalCount = 0;
                if(item.td.text.lower() in title):
                    matched = True;
                    previousTeamUsed = True;
                    print("Team: " + item.td.text + " is in the title");
                    addTeam = True;
                    returnString = returnString + "\n\n\nTeam: " + item.td.text + "\n\n";
                else:
                    addTeam = False;
            if("oddrow" in item['class'] or "evenrow" in item['class']):
                if(first):
                    print("Player: " + item.td.a.text)
                    print("Status: " + item.findAll("td")[1].text);
                    print("Date: " + item.findAll("td")[2].text);
                    first = False;
                    if(addTeam):
                        returnString += ("Player: " + item.td.a.text + "\n\n")
                        returnString += ("Status: " + item.findAll("td")[1].text + "\n\n");
                        returnString += ("Date: " + item.findAll("td")[2].text + "\n\n");
                else:
                    print(item.td.text + "\n")
                    first = True;
                    if(addTeam):
                        returnString += item.td.text + "\n\n\n\n"
                    if(previousTeamUsed):
                        TotalCount += 1;

    print("Final string: " + returnString);
    if(not matched):
        returnString = "";
    return(returnString);

        #injuryTable = table[0];
        #for item in injuryTable.findAll(True):
        #    print("Tag Name: " + item.name);
        #    print("Tag Text: " + item.text);

# Check submissions and comments for course names and reply accordingly
def checkItem(item):
    gameThread = re.findall(COURSE_NAME_REGEX, item.title)
    gdtThread = re.findall(GDT_REGEX, item.title)
    lower_title = item.title.lower()
    #print("My title is: " + lower_title + " and my author: " + item.author.name);
    if (len(gameThread) >= 1 or len(gdtThread) >= 1) and not isServiced(item.id):


        print(item.title);



        reply = parseForTeam(lower_title);

        if reply:
            reply = reply + "\n\n";
            secondReply = espnParse(lower_title);
            if(secondReply):
                reply += secondReply;
        else:
            reply = espnParse(lower_title);

        if(reply):
            reply = reply + "\n" + "&nbsp;" + "\n" + "test";


        print("\n\n\nEXPECTED REPLY\n\n\n");
        if(reply):
            print(reply);
        else:
            print("No teams found");

        #course_name = course_mentioned[0]
        #if(len(course_name) > 6):
        #    courseInner = re.findall(re.compile(r'[a-zA-Z]{3}[0-9]{3}'), course_mentioned[0])
        #    if(len(courseInner) > 0):
        #        course_name = courseInner[0];
        #reply = getCourseInfo(course_name.lower())
        #print("courseNameMatched: " + course_name)
        #reply = "hello world"
        #reply = getCourseInfo(course_name)
        #IncrementCourse(course_name, item.id)
        #reply = getOverallCourseHits(course_name);
        #replyCourseDescription = getCourseInfo(course_name)
        if reply:
            #reply = reply + '\n\n'
            #pre = '###' + course_name.upper() + ':\n\n'
            #if(replyCourseDescription == ''):
            #    reply = pre + reply
            #else:
            #    reply = pre + "\n" + replyCourseDescription + "\n" + reply
            try:
                item.reply(reply)
                updateServiced(item.id)
            except:
                sleep(5)
                return
            print(reply)

        #if reply and skip:
        #    reply = reply + '\n\n'
        #    pre = '###' + course_name.upper() + ':\n\n'
        #    if(replyCourseDescription == ''):
        #        reply = pre + reply
        #    else:
        #        reply = pre + "\n" + replyCourseDescription + "\n" + reply
        #    try:
        #        item.add_comment(reply)
        #    except:
        #        sleep(5)
        #        return
        #    print(reply)

        return

# Start scanning subreddits and comments for matches and act accordingly
def run(r):
    subreddits = r.subreddit(SUBREDDITS)
    subreddit_comments = subreddits.comments()
    subreddit_submissions = subreddits.hot(limit=100    )
    #for comment in subreddit_comments:
        #print("Comment Author: " + comment.author.name)
        #print("Comment Body: " + comment.body)
    #    checkItem(comment)
    for submission in subreddit_submissions:
        checkItem(submission)

# Log in once
r = login()

# Every 5 minutes, scan subreddits and comments for matches and act accordingly
while True:
    run(r)
    sleep(300)


from gluon import *
from gluon import current
import urllib2

global g_myScore, g_otScore, g_playState
g_Score_1 = 0
g_Score_2 = 0
g_playState = "init"

def getBaseballinfo():
    global g_myScore, g_otScore, g_playState
    baseballinfo = ["Baseball","Information"]
    
    try:
        page = urllib2.urlopen("http://sports.news.naver.com/schedule/index.nhn?category=kbo")
        text = page.read()
    except httplib.IncompleteRead, e:
        baseballinfo[0] = "Sorry,"
        baseballinfo[1] = "Now Loading..."
        return baseballinfo
    
    if '<ul class="sch_vs" id="todaySchedule">' not in text:
        baseballinfo[0] = "Sorry,"
        baseballinfo[1] = "Not Season."
        return baseballinfo
    
    cut_1 = text.split('<ul class="sch_vs" id="todaySchedule">')[1].split('<form name="monthlyScheduleForm"')[0]
    cut_2 = cut_1.split('<div class="vs_cnt ">')
    
    myTeamInfo = " "
    for i in cut_2:
        if teamName(getMyTeamfromDB(),0) in i:
            myTeamInfo = i
            if '<div class="cancel">' in myTeamInfo:
                baseballinfo[0] = "Sorry,"
                baseballinfo[1] = "Game Cancel."
                return baseballinfo
    
    play_state = myTeamInfo.split('<em class="state">')[1].split('</em>')[0].strip()
    if g_playState == "init":
        g_playState = play_state
    if g_playState in ['18:30']:
        if play_state not in ['18:30','종료']:
            th = threading.Thread(target=printAlarm_game_start_end, args=())
            th.start()
            g_playState = play_state
    if g_playState not in ['18:30','종료']:
        if play_state in ['종료']:
            th = threading.Thread(target=printAlarm_game_start_end, args=())
            th.start()
            g_playState = 'init'
    
    if play_state in ['18:30']:
        baseballinfo[0] = "Sorry,"
        baseballinfo[1] = "Not Game Time."
        return baseballinfo
    
    team_1=["name1","score1"]
    team_2=["name2","score2"]
    team_1[0] = myTeamInfo.split('alt="')[1].split('" title=')[0]
    team_2[0] = myTeamInfo.split('alt="')[2].split('" title=')[0]
    team_1[1] = myTeamInfo.split('<strong class="vs_num">')[1].split('<')[0]
    team_2[1] = myTeamInfo.split('<strong class="vs_num">')[2].split('<')[0]
    
    if (g_Score_1 != int(team_1[1])) or (g_Score_2 != int(team_2[1])):
        th = threading.Thread(target=printAlarm_game_score, args=())
        th.start()
        g_Score_1 = int(team_1[1])
        g_Score_2 = int(team_2[1])
    
    baseballinfo[0] = teamName(team_1[0],1) + " vs " + teamName(team_2[0],1)
    baseballinfo[1] = team_1[1] + " : " + team_2[1] + " " +  convertState(play_state)
    
    return baseballinfo

#def getMyTeamfromDB():
#    db = current.db
#    if db(db.tablebar_baseball.team_name).isempty():
#        return "삼성"
#    else:
#        return db(db.tablebar_baseball.id>0).select().first().team_name

def teamName(teamcode, code):    #code - 0:searching , 1:printing
    if teamcode == "삼성":
        return "SS"
    elif teamcode == "NC":
        return "NC"
    elif teamcode == "두산":
        if code == 0:
            return "OB"
        elif code == 1:
            return "DB"
    elif teamcode == "넥센":
        if code == 0:
            return "WO"
        elif code == 1:
            return "NX"
    elif teamcode == "한화":
        return "HH"
    elif teamcode == "SK":
        return "SK"
    elif teamcode == "KIA":
        if code == 0:
            return "HT"
        elif code == 1:
            return "KIA"
    elif teamcode == "롯데":
        return "LT"
    elif teamcode == "LG":
        return "LG"
    elif teamcode == "KT":
        return "KT"
    else:
        return "default"

def convertState(state):
    if state in ['종료']:
        return 'end'
    else:
        if '초' in state:
            return '%sTOP'%state[:state.find('회초')]
        else:
            return '%sBOT'%state[:state.find('회말')]

def printAlarm_game_start_end():
    for i in range(0,10):
        redLCDon()
        time.sleep(0.2)
        whiteLCDon()
        time.sleep(0.2)

def printAlarm_game_score():
    for i in range(0,3):
        redLCDon()
        time.sleep(0.2)
        yellowLCDon()
        time.sleep(0.2)
        pinkLCDon()
        time.sleep(0.2)
        whiteLCDon()
        time.sleep(0.2)

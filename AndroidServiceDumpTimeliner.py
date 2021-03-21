import subprocess as sub
import re
import dateutil.parser
from datetime import datetime as dt
from datetime import timedelta as td

def getBoundedBy(body, string_start, string_end):
    start = out.find(string_start)
    end = out.find(string_end, start + len(string_start) + 1)
    return(body[start:end])

def fixAssumedYearFlip(inputlist):
    outputlist = []
    datediff = max([x[0] for x in inputlist]) - min([x[0] for x in inputlist])
    if datediff.days > 30:
        thisyear = dt.now().year
        for j in inputlist:
            if j[0].month > 6:
                outputlist.append([j[0].replace(year = thisyear -1)] + j[1:])
            else:
                outputlist.append(j)
    return(outputlist)

def guessDate(monthday):
    month = int(monthday[:2])
    day = int(monthday[3:])
    year = dt.now().year
    if month > dt.now().month:
        year -= 1
    elif day > dt.now().day and month == dt.now().month:
        year -= 1    
    return([year, month, day])

def shortLogDate(inp):
    tempdate = guessDate(str(inp[:5],'latin-1'))
    temptime = re.findall(b'(\d\d)\:(\d\d)\:(\d\d)',inp)[0]
    datetime = dt(tempdate[0], tempdate[1], tempdate[2], int(temptime[0]), int(temptime[1]), int(temptime[2]))
    return(datetime)

def relativeTimeParse(basedate, timestring, retro):
    summed = basedate
    d = re.search(b'(\d+)d', timestring)
    if d != None:
        summed += td(days=int(d.groups()[0])) * (-1 if retro else 1)
    h = re.search(b'(\d+)h', timestring)
    if h != None:
        summed += td(hours=int(h.groups()[0])) * (-1 if retro else 1)
    m = re.search(b'(\d+)m[^s]', timestring)
    if m != None:
        summed += td(minutes=int(m.groups()[0])) * (-1 if retro else 1)
    s = re.search(b'(\d+)s', timestring)
    if s != None:
        summed += td(seconds=int(s.groups()[0])) * (-1 if retro else 1)

    return(summed)

def parseBatterystatsRow(string, basestamp):
    trunc = string.lstrip(b' ')
    timestring = trunc[:trunc.find(b' ')].lstrip(b'+')
    timestamp = relativeTimeParse(basestamp, timestring, False)
    founds = re.findall(b'(?:\S+\s){3}(.*)[\r\n]',trunc)
    if len(founds) < 1:
        return(None)
    else:
        return([timestamp, founds[0]]) 

adb_list_abridged = ["activity recents", "audio", "batterystats", "deviceidle", "media.camera", "media.extractor", "media.metrics", "notification",
                     "package", "powercontrol", "sensorservice", "telecom", "telephony.registry", "usagestats", "vibrator", "wifi"]

# TODO: add "display" for brightness changes - see if by user



destination = input("Please enter a filepath for data to be saved at:\n")


pu = sub.Popen(["cmd", "/c", "adb shell uptime -s"], stdout=sub.PIPE, stderr=sub.PIPE, shell=True)
outu, erru = pu.communicate()
phone_up_datetime = dt.strptime(str(outu, encoding='latin-1').rstrip(),'%Y-%m-%d %H:%M:%S')

interactions = []
for i in adb_list_abridged:
    print("Running dumpsys of {0}".format(i))
    p = sub.Popen(["cmd", "/c", "adb shell dumpsys", i], stdout=sub.PIPE, stderr=sub.PIPE, shell=True)
    out, err = p.communicate()
        
    if i == "activity recents":
        [stack_real, stack_visible]= re.findall(b'ecent tasks(.+?)(?:(?:\r\n\r)|(?:\r\n$))',out, re.DOTALL)
        
        items_real = re.findall(b'Recent #.*?#([^-]\d+).+?mActivityComponent=(\S+).*?lastActiveTime=(\d*)', stack_real, re.DOTALL) #ignore -1 (is home screen)
        visibles = re.findall(b'id=(\d+).*?lastActiveTime=(\S+).*?cmp=(\S*)', stack_visible, re.DOTALL)

        visible_arr = []
        for j in visibles:
            visible_arr.append(str(j[0],'latin-1'))
            interactions.append([phone_up_datetime+td(milliseconds=int(str(j[1],'latin-1'))), str(j[2],'latin-1'),"Recent Stack - Last time visible (shown in stack)", i])
        for j in items_real:
            stackid = str(j[0],'latin-1')
            if stackid not in [x for x  in visible_arr]:
                interactions.append([phone_up_datetime+td(milliseconds=int(str(j[2],'latin-1'))), str(j[1],'latin-1'),"Recent Stack - Last time visible (not shown in stack)", i])
        
    elif i == "audio":
        eventlog = re.findall(b'Audio event log: playback(.*?)[\r\n]{3}',out, re.DOTALL)
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')
            for j in [x for x in eventlog[1:] if b'state:' in x]:
                datetime = shortLogDate(j)
                reason = "Audio play event " + ("started" if b'started' in j else "ended")
                interactions.append([datetime, "android", reason, i])

        eventlog = re.findall(b'Audio event log: recording(.*?)[\r\n]{3}',out, re.DOTALL)
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')
            for j in [x for x in eventlog[1:] if b'rec' in x]:
                datetime = shortLogDate(j)
                reason = "Audio recording event {}".format("started" if b'start' in j else "stopped")
                sourcepackage = str(j[j.find(b'pack:')+5:].rstrip(),'latin-1')
                interactions.append([datetime, sourcepackage, reason, i])

        eventlog = re.findall(b'Audio event log: phone state(.*?)[\r\n]{3}',out, re.DOTALL)
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')
            for j in [x for x in eventlog[1:] if b'setMode' in x]:
                datetime = shortLogDate(j)
                reason = "Audio mode changed to {}".format(str(re.findall(b'mode=(.+?)\s', j)[0].rstrip(),'latin-1'))
                sourcepackage = str(re.findall(b'package=(.+?)\s', j)[0].rstrip(),'latin-1')
                interactions.append([datetime, sourcepackage, reason, i])

        eventlog = re.findall(b'Audio event log: wired(.*?)[\r\n]{3}',out, re.DOTALL) # 30 entries max?
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')
            for j in [x for x in eventlog[1:] if b'handleBluetooth' in x]:
                datetime = shortLogDate(j)
                if b'state=2' in j:
                    [addr, vol] = re.findall(b'addr=(.*?)\s.+?vol=(.+?)[\s\n\r]', j)[0]
                    reason = "Connected to Bluetooth audio device with MAC {} at volume {}".format(str(addr,'latin-1'), str(vol,'latin-1'))
                else:
                    reason = "Bluetooth audio disconnected"
                interactions.append([datetime, "android", reason, i])

        eventlog = re.findall(b'Audio event log: volume(.*)',out, re.DOTALL|re.MULTILINE) # 40 entries max?
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')
            for j in [x for x in eventlog[1:] if b'ADJUST_' in x]:
                datetime = shortLogDate(j)
                interactions.append([datetime, "android", "Volume adjusted {}".format("up" if b'ADJUST_RAISE' in j else "down"), i])
    
    elif i == "deviceidle":
        #have to get time here to be most accurate - log is relative to now
        pd = sub.Popen(["cmd", "/c", r"adb shell date +%Y-%m-%d-%H-%M-%S"], stdout=sub.PIPE, stderr=sub.PIPE, shell=True)
        outd, errd = pd.communicate()
        nowtime = dt.strptime(str(outd,encoding='latin-1').rstrip(),"%Y-%m-%d-%H-%M-%S")

        timings_dict = dict(re.findall(b'([\S_]*)=(.*)[\r$]',out, re.MULTILINE))
        if b'light_idle_to' in timings_dict:
            time_to_idle = str(timings_dict[b'light_idle_to'], 'latin-1')
        if b'inactive_to' in timings_dict:
            time_to_inactive = str(timings_dict[b'inactive_to'], 'latin-1') ## time to "deep doze"

        parts = re.findall(b'(\S*?)\:\s+\-(.*?)[\s](\(\S+)?.*$',out, re.MULTILINE)
        for j in parts:
            datetime = relativeTimeParse(nowtime, j[1], True)
            reason = "Entered '{}' state  frome idle".format(str(j[0],'latin-1'))
            if len(j[2]) > 0:
                reason += ", reason: {}".format(str(j[2][1:-1],'latin-1')) # remove brackets
            sourcepackage = "android"
            interactions.append([datetime, sourcepackage, reason, i])

    elif i == "media.camera":
        #get friendly name for id
        names = dict([(str(x,'latin-1'),str(y,'latin-1')) for (x,y) in re.findall(b'Camera HAL.+?legacy/(.+?)\s.+?Facing\:\s(.+?)[\n\r]',out, re.DOTALL)])

        #get logs
        eventlog = re.findall(b'service events(.+?)[\r\n]{3}',out, re.DOTALL)
        if len(eventlog) > 0:
            eventlog = eventlog[0].split(b'\n')[1:]
            ignores = [b'PID -1', b'ADD', b'USER_SWITCH']
            for j in [x for x in eventlog if not any([(y in x) for y in ignores])]:
                datetime = shortLogDate(j[:j.find(b' : ')].strip())
                if b'Torch' in j: # torch only - camera flash not logged
                    reason = j[j.find(b' : ')+3:].strip()
                    reason = reason[:reason.find(b'for clie')]
                    sourcepackage = "android"
                else:
                    data = re.findall(b'\:\s(.+?)\sclient', j)[0].strip()
                    reason = str(data,'latin-1') + " ({})".format(names[chr(data[-1])]) # chr because single from b'' is byte/int
                    sourcepackage = str(re.findall(b'package\s(.+?)\s', j)[0],'latin-1')
                interactions.append([datetime, sourcepackage, reason, i])

    elif i == "media.extractor":
        parts = re.findall(b'(\d\d\-\d\d \d\d:\d\d:\d\d):.*?fd\((.*?)\).*?,.*?,\s(\d*).*?dura.*?\)\s(\d*).*?[\r\n]{1,2}',out, re.DOTALL)
        for j in parts:
            datetime = shortLogDate(j[0])
            originating_file = str(j[1],'latin-1')
            file_size = float(str(j[2],'latin-1'))/1024 # kB  
            file_seconds = float(str(j[3],'latin-1'))/1000000
            sourcepackage = "Android - media decoder"
            reason  = "System extracted media file from {} (file duration: {:0.2f}s, file size: {:0.0f} kB)".format(originating_file, file_seconds, file_size)
            interactions.append([datetime, sourcepackage, reason, i]) 


    elif i == "media.metrics":
        parts = re.findall(b'\[(?:.+?\:){4}(.*?)\:(?:.+?\:){3}(.*?)\:.+?\:(.+?)\]', out)
        for j in range(len(parts)):
            sourcepackage = str(parts[j][0],encoding='latin-1')
            datetime = dt.fromtimestamp(int(str(parts[j][1],encoding='latin-1')[:10]))
            event = None
            data = parts[j][2]
            if b'mode=video' in data:
                event = "Video playing or streaming"
            elif b'AUDIO_STREAM' in data:
                event = "Audio is streaming"
            elif b'mode=audio' in data:
                event = "Audio playing"

            if sourcepackage == "audioserver":
                #sourcepackage = "android"
                if b'OFFLOAD' in data:      
                    event = "Audio streaming to external device"
                elif b'MIXER' in data:
                    event = "Audio mixer event - media may be playing"

            packet = [datetime, sourcepackage, event if event != None else "Media codec used", i]
            if j == 0:
                interactions.append(packet) 
            elif packet != interactions[-1] and (sourcepackage != "media" and event != None):
                interactions.append(packet)

    elif i == "notification":
        parts = re.findall(b'NotificationRecord.*?pkg=(.*?)\s.*?mCreationTimeMs=(.*?)[\r|\n].*?mName=(.*?),.*?mAdj', out, re.MULTILINE|re.DOTALL)
        for j in parts:
            datetime = dt.fromtimestamp(float(str(j[1],encoding='latin-1')[:10]))
            if datetime.year > 2000 and datetime.year < 2050:
                sourcepackage = str(j[0],encoding='latin-1').strip()
                event = str(j[2],encoding='latin-1').strip()
                interactions.append([datetime, sourcepackage, event, i])

    elif i == "batterystats":
        tags = [b'-top', b'+top', b'device_idle', b'+screen',
        b'-screen',b'+audio',b'-audio', b'ble_scan',
        b'active=1000', b'phone_in_call', b'wifi_scan',
        b'screenwake=1000', b'pkginst', b'plugged'] #b'wifi_radio'
        recent = out[:out.find(b'Per PID')]
        split = recent.split(b'\n')
        starttime = re.findall(b': (\d.*)[\r\n]', split[1])[0]
        stamp = dt.strptime(str(starttime,'latin-1'), '%Y-%m-%d-%H-%M-%S')
        for n in range(len(split)):
            if any([(x in split[n])for x in tags]):

                [datetime, bytedata] = parseBatterystatsRow(split[n], stamp)

                reason = None

                if b'top' in bytedata:
                    reason = "Application " + ("now on top: " if b'+top' in bytedata else "no longer visible: ")+ str(re.findall(b'\d:"(.*)"', bytedata)[0], encoding='latin-1')
                #if b'brightness=' in bytedata:
                #    reason = "Screen backlight now " + str(re.findall(b'brightness=(.*?)\W', bytedata)[0], encoding='latin-1')
                if b'screen' in bytedata:
                    reason = "Screen turned " + ("on" if b'+screen' in bytedata else "off")
                if b'mPowerKeyWakeLock' in bytedata:
                    reason = "Power button pressed"
                if b'ble_scan' in bytedata:
                    reason = "System " + ("started" if b'+ble_scan' in bytedata else "ended") + " Bluetooth scan"
                if b'wifi_scan' in bytedata:
                    reason = "System " + ("started" if b'+wifi_scan' in bytedata else "ended") + " WiFi scan"
                if b'active=1000:"unlocked"' in bytedata:
                    reason = "Device unlocked"
                if b'phone_in_call' in bytedata:
                    reason = "Phonecall " + ("started" if b'+phone_in_call' in bytedata else "ended")
                if b'plugged' in bytedata:
                    reason = "USB " + ("plugged in" if b'+plugged' in bytedata else "unplugged")
                if b'pkginst' in bytedata:
                    reason = "App installed or updated: " + str(re.findall(b'pkginst.*?"(.*)"', bytedata)[0], encoding='latin-1')    
                if b'audio' in bytedata:
                    if b'+audio' in bytedata and not audio_on:
                        audio_on = True
                        interactions.append([datetime, "android", "Start of audio use", i])
                    if b'-audio' in bytedata:
                        [nextstamp, nextdata] = parseBatterystatsRow(split[n+1], stamp)
                        if b'+audio' not in nextdata or nextstamp > timestring + td(seconds=1): ## need to check if time is <1 +
                            audio_on = False
                            interactions.append([datetime, "android", "End of audio use", i])
                    
                if reason != None:
                    interactions.append([datetime, "android", reason, i])
    
    elif i == "package":
        start = out.find(b'Package warning messages')
        end = out.find(b'Active install sessions')
        section = out[start:end]
        parts = re.findall(b'(\d\d.{7,15})\s.*?(Up.{4}ing from .*?)[\r\n]', section)
        for j in [x for x in parts if b'/69' not in x[0] and b'/70' not in x[0]]:
            datetime = dt.strptime(str(j[0],encoding='latin-1').rstrip(':'),"%d/%m/%Y %H:%M")
            sourcepackage = "android"
            event = str(j[1],encoding='latin-1').strip()
            interactions.append([datetime, sourcepackage, event, i])

        section = out[re.search(b'^Packages:',out,re.MULTILINE).start():]
        parts = re.findall(b'Package \[(.*?)\].*?codePath=(.*?)[\r\n].*?firstInstallTime=(.*?)[\r\n].*?lastUpdateTime=(.*?)[\r\n]', section, re.DOTALL)
        parts = [x for x in parts if x[1][:4] != b'/sys'] # no system apps, but still vendor apps like SNotes, etc.
        for j in parts:
            install = dateutil.parser.parse(str(j[2],encoding='latin-1'))
            update = dateutil.parser.parse(str(j[3],encoding='latin-1'))
            sourcepackage = str(j[0],encoding='latin-1')
            interactions.append([install, "android", "Application first installed: " + sourcepackage, i])
            interactions.append([update, "android", "Application last updated: " + sourcepackage, i])

    elif i == "powercontrol":
        start = out.find(b'IDLE RECORD')
        end = out.find(b'User DEEP SLEEP')
        section = out[start:end]
        parts = re.findall(b'start=(.*?), end=(.*?),', section)
        for j in parts:
            datetimestart = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            interactions.append([datetimestart, "android", "Enter idle/sleep", i])
            datetimeend = dateutil.parser.parse(str(j[1],encoding='latin-1'))
            interactions.append([datetimeend, "android", "Exit idle/sleep (Wake)", i])

    elif i == "sensorservice":
        service_lookup = dict(re.findall(b'(0x.+?)\)\s(.+?)\s+\|', out))

        sensor_data_block_headers = re.findall(b'^(.+?last (\d+?) event)', out, re.MULTILINE) #get header and number of data lines
        for k in sensor_data_block_headers:
            sensordata = re.findall(k[0] + b'.*?[\n\r](((.+?)[\r\n]){'+ k[1] + b'})', out)[0][0]
            for line in [x for x in sensordata.split(b'\r') if len(x) > 0]:
                [secs, sensor_outputs] = re.findall(b'ts=(\d*).*?\)\s(.*)[\s\r\n]', line)[0]
                datetime = phone_up_datetime + td(seconds=int(str(secs, encoding='latin-1')))

                interactions.append([datetime, "Sensor: " + str(k[0][:k[0].find(b':')], encoding='latin-1'), "Data registered: " + str(sensor_outputs.rstrip(b','), encoding='latin-1'), i])

    elif i == "telecom":
        start = out.find(b'Historical Events')
        section = out[start:]
        parts = re.findall(b'(Call.*?Timings)', section, re.MULTILINE|re.DOTALL)
        for j in parts:
            header = re.findall(b'Call.{3,9}\[(.*?)\]\(.{5}(.*?)\)', j, re.MULTILINE|re.DOTALL)
            datetimestart = dateutil.parser.parse(str(header[0][0],encoding='latin-1'))
            disconnect = re.findall(b'([\d\:]{6,10}).{10,60}DisconnectCause.*?Code.*?\((.*?)\)', j, re.MULTILINE|re.DOTALL)
            datetimeend = dt.combine(datetimestart.date(), dateutil.parser.parse(str(disconnect[0][0],encoding='latin-1')).time())
            interactions.append([datetimestart, "android", "Call started: " + str(header[0][1],encoding='latin-1'), i])
            interactions.append([datetimeend, "android", "Call ended. Reason: " + str(disconnect[0][1],encoding='latin-1'), i])

    elif i == "telephony.registry":
        end = out.find(b'listen logs')
        section = out[:end]
        parts = re.findall(b'^\s{0,8}(\d\S{16,24})\s.*?mCi=(.*?) mPci=(.{3}) mTac=(.*?)\s', section, re.MULTILINE)
        persit_tower = None
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            mci = str(j[1],encoding='latin-1').strip()
            mpci = str(j[2],encoding='latin-1').strip()
            mtac = str(j[3],encoding='latin-1').strip()

            if mci != persit_tower:
                interactions.append([datetime, "android", ("Cell Tower Connection - Tower CI " if persit_tower == None else "Cell Tower Changed from CI {0} to CI ".format(persit_tower)) + mci, i])
                
            persit_tower = mci

    elif i == "usagestats":
        # Notes: KEYGUARD_SHOWN means lock screen became visible (e.g. by waking up when power pressed)
        parts = re.findall(b'time="(.*?)"\s.*?type=(.*?)\spackage=(.*?)\s(?:.*?class=(.*?)\s)?', out)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            sourcepackage = str(j[2],encoding='latin-1').strip() + (("/" + str(j[3],encoding='latin-1').strip()) if len(j)>3 and len(j[3])>0 else "")
            event = str(j[1],encoding='latin-1').strip()
            if event not in ["STANDBY_BUCKET_CHANGED","SCREEN_NON_INTERACTIVE"] and "SERVICE" not in event:
                interactions.append([datetime, sourcepackage, event, i])
        if b'In-memory yearly stats' in out:
            section = out[out.find(b'In-memory yearly stats'):]
            section = section[:section.find(b'Chooser')]
            parts = re.findall(b'package=(.*?)\s.*lastTimeUsed="(.*?)"', section)
            for j in parts:
                if b'1970' not in j[1]:
                    datetime = dateutil.parser.parse(str(j[1],encoding='latin-1'))
                    sourcepackage = str(j[0],encoding='latin-1').strip()
                    event = "Last Time Used"
                    interactions.append([datetime, sourcepackage, event, i])

    elif i == "vibrator":
        parts = re.findall(b'startTime\:\s(.*?),\seffect.*opPkg\:\s(.*?),.*on\:\s(.*)', out)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            sourcepackage = str(j[1],encoding='latin-1').strip()
            reason = str(j[2],encoding='latin-1').strip()
            interactions.append([datetime, sourcepackage, reason, i])
          
    elif i == "wifi":
        end = out.find(b'curState')
        section = out[:end]
        parts = re.findall(b'time=(.*)\sproc.*?dest=(.*?)\s', section)
        templist = []
        for j in parts:
            if b'null' not in j[1]: # I think null is not user-initiated
                datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
                event = str(j[1],encoding='latin-1')
                templist.append([datetime, "android", "Wi-Fi " + ("enabled" if 'Enable' in event else "disabled"), "wifi (controller"])
        interactions.extend(fixAssumedYearFlip(templist))

        section = getBoundedBy(out, b'Dump of WifiConnectivityManager', b'Log End')
        parts = re.findall(b'^(\d\d.*?) - (Set WiFi .{2,3}abled)', section, re.MULTILINE)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            event = str(j[1],encoding='latin-1')
            interactions.append([datetime, "android", event, "wifi (connectivity)"])     
        parts = re.findall(b'^(\d\d.{18,24}) \- connectToNetwork\W+(.*?)\r', section, re.MULTILINE)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            event = str(j[1],encoding='latin-1')
            interactions.append([datetime, "android", event, "wifi (connectivity)"])
        
        parts = re.findall(b'^(\d\d.{18,24}) \- SavedNetworkEvaluator selects\W+(.*?)\r', section, re.MULTILINE)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            event = "Wi-Fi: autoconnect to {0}".format(str(j[1],encoding='latin-1'))
            interactions.append([datetime, "android", event, "wifi (connectivity)"])

        section = getBoundedBy(out, b'WifiLastResortWatchdog - Log Begin', b'Log End')
        parts = re.findall(b'^(\d\d.{18,24}) \- connectedStateTransition: isEntering = (.*?)\r', section, re.MULTILINE)
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            interactions.append([datetime, "android", "{0} Wi-Fi Network (name not saved)".format("Disconnected from" if j[1]==b'false' else "Connected to"), "wifi (watchdog)"])
            
        section = getBoundedBy(out, b'mConnectionEvents:', b'mWifiLogProto.')
        parts = re.findall(b'startTime=(\d\d.{10,24}),.*?SSID=(.*?, BSSID=.*?),', section)
        templist = []
        for j in parts:
            datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
            templist.append([datetime, "android", "Wi-Fi: Connected to {0}".format(str(j[1],encoding='latin-1')), "wifi (metrics)"])
        interactions.extend(fixAssumedYearFlip(templist))

        desired_events = [b'WIFI_DISABLED', b'WIFI_ENABLED', b'CMD_START_CONNECT', b'NETWORK_DISCONNECTION_EVENT', b'CMD_IP_REACHABILITY_LOST']
        for ev in desired_events:
            section = getBoundedBy(out, b'StaEventList:', b'mWifiLogProto.')
            parts = re.findall(b'^(\d\d.{10,24}) ('+ev+b')', section, re.MULTILINE)
            templist = []
            for j in parts:
                datetime = dateutil.parser.parse(str(j[0],encoding='latin-1'))
                templist.append([datetime, "android", str(j[1],encoding='latin-1'), "wifi (StaEvent)"])
            interactions.extend(fixAssumedYearFlip(templist))

    print("Output of 'dumpsys {0}' processed.".format(i))

print("Sorting in chronological order.")
interactions.sort(key=lambda x: x[0])        
print("Writing data to file.")
with open(destination,'w') as f:
    for i in interactions:
        f.write(str(i) + "\n")
print("Done.")

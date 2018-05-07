
__author__ = "James G. Watson"
__copyright__ = "Copyright 2018, James G. Watson"
__version__ = "1.0"
__license__ = "MIT License"

appName = "WhatsApp"

def textTimeFormat(timeText):
    if "m" in timeText: ## am/pm
        temp = timeText[:5].rstrip()
        if "p" in timeText and temp[0:1] != "12":
            output = str(int(temp[0])+12)+temp[temp.find(":"):]
        else:
            output = temp
    else:
        output = timeText[:5]
    return(output)

## main program
directory=input("Exported text files directory: ")

if not os.path.isdir(directory):
    print("This is not a valid directory .")
    exit

for i in os.walk(directory):
    for j in i[2]:
        print("Processing: " + j)
        chatArrays = []
        exportArray=[]

        with codecs.open(os.sep.join([directory,j]), encoding="utf-8") as chat:
            chatBody = chat.read()

        for k in range(0,len(chatBody)):
            if chatBody[k] == chr(10): ## EOL
                item = chatBody[sum([len(x) for x in chatArrays]):k+1]
                chatArrays.append(item)
        ## EOF - don't want to miss the last line
        item = chatBody[sum([len(x) for x in chatArrays]):k]
        chatArrays.append(item)

        print(str(len(chatArrays)) + " lines.")

        for k in chatArrays:
            ## is it the start of a message?
            groundTester = re.findall("^.{0,2}\d\d/\d\d/\d\d.{0,2}, \d?\d\:\d\d(?: ?[a|p]m)?(?: -)",k[:30]) ## ensuring not finding in message body
            if len(groundTester)>0:
                messageTime = textTimeFormat(groundTester[0][12:])
                messageDate = groundTester[0][:10]
                datetimeLocalString = " ".join([messageDate,messageTime])
                if ord(messageDate[2]) == 47: ## confirms dd/mm/yyyy (possibly more common)
                    strpFormat = "%d/%m/%Y %H:%M"
                else: ## yyyy/mm/dd
                    strpFormat = "%Y/%m/%d %H:%M"
                datetimeLocalUnix = int(datetime.datetime.strptime(datetimeLocalString, strpFormat).timestamp())

                senderRaw = re.findall("\:\d\d(?: ?[a|p]m)? - (.*?)\: ",k)

                if len(senderRaw)>0:
                    if "‪" in senderRaw[0]: ## phone number flag
                        sender = senderRaw[0][1:-1]
                        findBytes = "‬\: (.*)\n"
                    else:
                        sender = senderRaw[0]
                        findBytes = " - .*?\: (.*)\n"
                else:
                    sender = appName
                    findBytes = "\:\d\d(?: [a|p]m)? - (.*)"

                message = re.findall(findBytes,k)[0]

                exportArray.append([datetimeLocalUnix,sender,message])
            else: ## this handles multiline entries
                exportArray[-1][-1]=exportArray[-1][-1]+k

        print(str(len(exportArray)) + " messages.")

        tableName = j[19:-4].replace(" ","_")
        databaseConnection = sqlite3.connect(directory+os.sep+appName+".db", isolation_level=None) ##autocommit
        databaseDesign = "CREATE TABLE [{0}] ([{1}] INT,[{2}] TEXT,[{3}] TEXT)".format(tableName,"_datetimeLocal","_sender","_message")
        databaseCursor=databaseConnection.cursor()
        databaseCursor.execute(databaseDesign)

        print("Table created. Adding messages.")

        databaseConnection.executemany("INSERT INTO {0}(_datetimeLocal,_sender,_message) values (?, ?, ?)".format(tableName), exportArray)
        ## a progress counter could be built in, but would be far more verbose

        print("Entries added")
        databaseConnection.close()
    print("\nConversion complete.")
import re, os, sqlite3, sys, datetime

__author__ = "James G. Watson"
__copyright__ = "Copyright 2018, James G. Watson"
__version__ = "1.0"
__license__ = "MIT License"

directory=input("Exported text files directory: ")
appName = "WhatsApp"

for i in os.walk(directory):
    for j in i[2]:
        print("Processing: " + j)
        byteArrays = []
        exportArray=[]
        
        with open(os.sep.join([directory,j]), 'rb') as chat:
            ## read as binary to preserve emoji encoding in messages
            ##  else remove the 'b' and switch encoding to UTF-8
            chatBytes = chat.read()

        for k in range(0,len(chatBytes)):
            if chatBytes[k] == 10: ## EOL
                item = chatBytes[sum([len(x) for x in byteArrays]):k+1]
                byteArrays.append(item)
        ## EOF - don't want to miss the last line
        item = chatBytes[sum([len(x) for x in byteArrays]):len(chatBytes)]
        byteArrays.append(item)

        print(str(len(byteArrays)) + " lines.")

        for k in byteArrays:
            groundTester = re.findall(b"^.{0,2}\d\d/\d\d/\d\d.{0,2}, \d\d\:\d\d -",k)
            if len(groundTester)>0:
                datetimeLocalString = b" ".join([groundTester[0][:10],re.findall(b", (\d\d\:\d\d) -",k)[0]]).decode("latin-1") 
                if groundTester[0][2] == 47: ## confirms dd/mm/yyyy (possibly more common)
                    datetimeLocalUnix = int(datetime.datetime.strptime(datetimeLocalString, "%d/%m/%Y %H:%M").timestamp())
                else: ## yyyy/mm/dd
                    datetimeLocalUnix = int(datetime.datetime.strptime(datetimeLocalString, "%Y/%m/%d %H:%M").timestamp())
                ## either variable is usable - it depends on intended use
      
                senderRaw = re.findall(b"\:\d\d - (.*?)\: ",k)

                if len(senderRaw)>0:
                    if b'\xe2\x80\xaa' in senderRaw[0]: ## phone number flag
                        sender = senderRaw[0][3:-3]
                        findBytes = b"\xe2\x80\xac\: (.*)\n"
                    else:
                        sender = senderRaw[0]
                        findBytes = b" - " + sender + b"\: (.*)\n"
                else:
                    sender = bytes(appName,encoding="latin-1")
                    findBytes = b"\:\d\d - (.*)"

                message = re.findall(findBytes,k)[0] 
                sender=sender.decode("latin-1") ## omit the conversion if encoding issues

                exportArray.append([datetimeLocalUnix,sender,message])
            else: ## this handles multiline entries
                exportArray[-1][-1]=exportArray[-1][-1]+k

        print(str(len(exportArray)) + " messages.")

        tableName = j[19:-4].replace(" ","_")
        databaseConnection = sqlite3.connect(directory+os.sep+appName+".db", isolation_level=None) ##autocommit
        databaseDesign = "CREATE TABLE [{0}] ([{1}] INT,[{2}] TEXT,[{3}] BLOB)".format(tableName,"_datetimeLocal","_sender","_message")
        databaseCursor=databaseConnection.cursor()
        databaseCursor.execute(databaseDesign)

        print("Table created. Adding messages.")

        databaseConnection.executemany("INSERT INTO {0}(_datetimeLocal,_sender,_message) values (?, ?, ?)".format(tableName), exportArray)
        ## a progress counter could be built in, but would be far more verbose

        print("Entries added")
        databaseConnection.close()
    print("\nConversion complete.")


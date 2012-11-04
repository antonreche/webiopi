#First import webiopi
import webiopi
import time

#I use the integrated GPIO lib, but you can use RPi.GPIO
GPIO = webiopi.GPIO

#A custom macro which prints out the args sent and return OK
def myMacro(data):
    print "myMacro (%s)" % data
    return "OK"

#Instantiate the server on the port 8000, it starts immediately in its own thread
server = webiopi.Server(port=8000, login="admin", password="p@ssw0rd")

#Register the macro so you can call it through the [RESTAPI] or [JAVASCRIPT]
server.addMacro("myMacro", myMacro)

#Setup GPIO 0 and 7
GPIO.setFunction(0, GPIO.IN)
GPIO.setFunction(7, GPIO.OUT)

#Example loop which toggle GPIO 7 each 5 seconds
try:
    while True:
        GPIO.output(7, not GPIO.input(7))
        time.sleep(5)

#Break the loop by pressing CTRL-C
except KeyboardInterrupt:
    pass

#Stops the server
server.stop()
GPIO.setFunction(7, GPIO.IN)

from printrun.pronsole import pronsole
import time
p = pronsole()

#This file connects to the BTT motor driver board through pronsole, which is 
#just pronterface through commands instead of a GUI
print("Loading...")
p.load_rc("/home/imvx02/.config/Printrun/pronsolerc")

print(f"Connecting to {p.settings.port} at {p.settings.baudrate} baudrate")
p.do_connect("")

timeout = 15
start_time = time.time()
while not p.p.online:
	if time.time() - start_time > timeout:
		print("Connection failed")
		exit(1)
	time.sleep(0.5)
	
print("Connected")

#this command runs the macro for a medium scan
p.onecmd("ScanMedium")
while p.queue or p.sending:
	time.sleep(0.1)
p.onecmd("disconnect")



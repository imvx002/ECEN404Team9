
from printrun.pronsole import pronsole
import time
p = pronsole()

print("Loading...")
p.load_rc("/home/imvx02/.config/Printrun/pronsolerc")

print(f"Connecting to {p.settings.port} at {p.settings.baudrate} baudrate")
p.do_connect("")

timeout = 50
start_time = time.time()
while not p.p.online:
	if time.time() - start_time > timeout:
		print("Connection failed")
		exit(1)
	time.sleep(0.5)
	
print("Connected")

	
p.onecmd("ScanLarge")
while p.queue or p.sending:
	time.sleep(0.1)
p.onecmd("disconnect")



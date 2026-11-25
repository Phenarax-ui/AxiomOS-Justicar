import time

def check_temp(temp):
	if temp > 90:
		print(f"ALERT {temp}")
	else:
		print(f"temp normal {temp} ")
while True:
	with open("/sys/class/thermal/thermal_zone0/temp") as f:
		reading = f.read()
	temp = int(reading) / 1000
	check_temp(temp)
	time.sleep(5)

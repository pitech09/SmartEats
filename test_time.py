
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo

def get_localTime():
	
    
    return datetime.now()

print(get_localTime().strftime('%H:%M'))
print(datetime.utcnow().strftime('%H:%M'))
get_localTime

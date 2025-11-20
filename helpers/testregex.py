import re
# ութե(ան) -> <expan><abbr>ութե</abbr><ex>ան</ex></expan>
print(re.sub(r'(\w+)\((.*?)\)', r'<expan><abbr>\g<1></abbr><ex>\g<2></ex></expan>','ութե(ան)'))
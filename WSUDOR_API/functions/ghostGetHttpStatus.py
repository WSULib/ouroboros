import sys
# Ghost.py
from ghost import Ghost

# instantiate and retrieve
ghost = Ghost()
URL = sys.argv[1]
page,resource = ghost.open(URL)

# return
print page.http_status
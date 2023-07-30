import sys, difflib
import os.path 
from os import path

if len(sys.argv) != 3:
	print("Requires 2 filenames")
	sys.exit()
elif not path.exists(sys.argv[1]) and not path.exists(sys.argv[2]):
	print("Not exist file : %s, %s" % (sys.argv[1], sys.argv[2]) )
	sys.exit()
elif not path.exists(sys.argv[1]):
	print("Not exist file : %s" % sys.argv[1])
	sys.exit()
elif not path.exists(sys.argv[2]):
	print("Not exist file : %s" % sys.argv[2])
	sys.exit()


file1 = open(sys.argv[1], "r")
file2 = open(sys.argv[2], "r")
result = difflib.SequenceMatcher(None, file1.read(), file2.read()).ratio()
 
print(result)

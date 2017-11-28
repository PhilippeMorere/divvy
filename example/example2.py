import sys
import random

a = float(sys.argv[1])
b = float(sys.argv[2])
method = sys.argv[3]
x = float(sys.argv[4])
y = float(sys.argv[5])
score = 0
if method == "methodA":
    score = x*y + random.random()
elif method == "methodB":
    score = x/y + 3 * random.random()
print("{}".format(score))

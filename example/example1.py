import sys
import random

a = float(sys.argv[1])
b = float(sys.argv[2])
method = sys.argv[3]
score = 0
if method == "methodA":
    score = 1 + random.random()
elif method == "methodB":
    score = 10 + 3 * random.random()
print("{}".format(score))

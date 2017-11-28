import sys
import random

a = float(sys.argv[1])
method = sys.argv[2]
u = float(sys.argv[3])
y = float(sys.argv[4])
z = float(sys.argv[5])

score = 0
if method == "methodA":
    score = (y ** u) / z + random.random()
elif method == "methodB":
    score = y * u + z + 0.3 * random.random()
elif method == "methodC":
    score = abs(y - u) ** (1/z) + 10.0 * random.random()

print(score)

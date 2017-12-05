import sys
import random

x = float(sys.argv[1])
y = float(sys.argv[2])
score = -(x**2 + y**2) + 4 + 0.0 * random.random()
print(score)

"""
This is a dummy experiment file
"""
import sys
import math

x = float(sys.argv[1])
y = float(sys.argv[2])
z = float(sys.argv[3])
print("args: ", x, y, z)
ret = math.sin(z*x + y)
print(ret)

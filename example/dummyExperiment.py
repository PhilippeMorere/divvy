### This is a dummy experiment file
# This program takes one argument, computes its square and logs it to a file
import sys

print "Arguments are: {}".format(sys.argv)
x = float(sys.argv[1])
y = x * x
sys.exit("result: {}".format(y))

#!/usr/bin/env python
import argparse
import os
import yaml
import sys
import numpy as np
from ParallelTasks import ParallelTasks
from TaskTree import ComparisonNode, OptimisedNode
from utils import pprinttable
from collections import namedtuple


def checkNodeExists(config, name):
    if name not in config:
        raise ValueError("Tag {} must be specified.".format(name))


def checkConfig(config):
    """ Check config file for correct syntax """
    # Mandatory nodes
    checkNodeExists(config, "name")
    checkNodeExists(config, "workers")

    # Fill in default values
    if "workers" not in config:
        config["workers"] = 1


def parseParams(elem):
    """Parses the params of the program."""
    params = {}
    for key, val in elem.items():
        if isinstance(val, str):
            # Escape string so that it is not divided into multiple command
            # arguments
            params[key] = "\"{}\"".format(val)
        else:
            params[key] = val
    return params


def parseNode(elem, optimisedNode=False):
    # Check structure
    checkNodeExists(elem, "params")
    if "optimised" not in elem and "commands" not in elem:
        raise ValueError("All leaf nodes must include a \"commands\" tag.")
    if optimisedNode and "optimiser" not in elem:
        raise ValueError("Optimiser nodes must include an \"optimiser\" tag")

    # Parse
    repeat = 1
    if "repeat" in elem:
        repeat = elem["repeat"]
    commands = None
    if "commands" in elem:
        commands = elem["commands"]
    optParams = None
    if "opt_params" in elem:
        optParams = elem["opt_params"]
    params = elem["params"]

    children = None
    if "optimised" in elem:
        if isinstance(elem["optimised"], list):
            children = [parseNode(e, True) for e in elem["optimised"]]
        else:
            children = [parseNode(elem["optimised"], True)]

    if optimisedNode:
        optimiser = elem["optimiser"]
        return OptimisedNode(optimiser, optParams, params, children, commands,
                             repeat)
    else:
        return ComparisonNode(params, children, commands, repeat)


def parseToTaskTree(config):
    # Parse fixed parameters
    fixedParams = parseParams(config["fixed"] if "fixed" in config else {})

    # Parse tree root
    if "comparison" in config:
        return parseNode(config["comparison"]), fixedParams
    elif "optimised" in config:
        return parseNode(config["optimised"], True), fixedParams
    else:
        raise ValueError("Could not either elements \"comparison\" or " +
                         "\"optimised\" in \"experiment\"")


def printComparisonSummary(root):
    paramVals = [None] * len(root.allParamVals)
    scores = [[] for _ in range(len(root.allParamVals))]

    # Populate param and score list
    lenParamVals = 0
    for task in root.finishedTasks:
        if task.params in paramVals:
            idx = paramVals.index(task.params)
        else:
            idx = lenParamVals
            lenParamVals += 1
            paramVals[idx] = task.params
        scores[idx].append(task.score)

    # Compute mean and std
    means = [0.0] * len(scores)
    stds = [0.0] * len(scores)
    for i, scoreList in enumerate(scores):
        means[i] = np.mean(scoreList)
        stds[i] = np.std(scoreList)

    # Sort by mean socre
    sortedIdx = np.argsort(means)[::-1]

    # Column names
    keys = list(paramVals[0].keys())
    colNames = keys + ['score', 'sd']
    Row = namedtuple('Row', colNames)

    print(paramVals)
    # Populate table
    data = []
    for i in sortedIdx:
        cells = []
        for k in keys:
            cells.append("{}".format(paramVals[i][k]))
        cells.append("{0:0.4f}".format(means[i]))
        cells.append("{0:0.4f}".format(stds[i]))
        data.append(Row(*cells))

    # Print table
    print("\n#####################\n# Comparison summary:" +
          "\n#####################\n")
    pprinttable(data)


def printOptimisationSummary(root):
    pass


def main():
    # Parse argument(s)
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Experiment configuration file (YAML)')
    args = parser.parse_args()

    # Check if config file exists
    if not os.path.isfile(args.config):
        print("Error: configuration file {} does not exist.".
              format(args.config))
        sys.exit()

    # Parse Yaml file and verify config
    yamlTree = yaml.safe_load(open(args.config))
    config = yamlTree["experiment"]
    checkConfig(config)

    # Parse Yaml config to tree
    root, fixedParams = parseToTaskTree(config)

    # TODO: Change working directory if workdir specified
    # TODO: print info and start time
    # TODO: There's a bug with using multiple workers!
    print("Starting experiment.")

    # Run all commands
    pt = ParallelTasks(config["workers"])
    while True:
        # Add all parallel tasks
        while root.isTaskReady():
            tasks = root.getNextTasks(fixedParams)
            pt.addTasks(tasks)

        # If there is nothing else to run, stop workers
        if root.isDone():
            pt.end()
            # Gather remaining unfinished tasks
            for task in pt.getFinishedTask():
                root.updateFinishedTask(task)
            break

        # Wait for tasks to finish
        try:
            task = next(pt.getFinishedTask())
            root.updateFinishedTask(task)
        except StopIteration:
            # All workers are node
            break

    print("All done.")

    # Print summary information
    if isinstance(root, ComparisonNode):
        printComparisonSummary(root)
    else:
        printOptimisationSummary(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())

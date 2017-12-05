from itertools import product
from ParallelTasks import Task
from Optimisers import getOptimiser
import numbers
import re
from utils import pprinttable
from collections import namedtuple


class Node:
    def __init__(self, children, commands, repeat, wd):
        self.children = [] if children is None else children
        self.repeat = repeat
        self.commands = commands
        self.runningTasks = []
        self.finishedTasks = []
        self.wd = wd

    def isTaskReady(self):
        """
        Whether a taks is ready in the tree. If a task is ready, method
        getNextTask will return tasks immediately.
        """
        raise NotImplementedError

    def getNextTasks(self, parentParams=None):
        """
        Returns a list of tasks
        """
        raise NotImplementedError

    def isDone(self):
        """
        Whether this node and all its children are finished
        """
        raise NotImplementedError

    def _parseCommands(self, params, commands):
        """
        Replaces parameters with their value in commands
        """
        filledCommands = [None] * len(commands)
        for i, command in enumerate(commands):
            for k, v in params.items():
                command = re.sub("\$\{%s\}" % k, str(v), command)
            filledCommands[i] = command
        return filledCommands

    def _joinParams(self, paramsA, paramsB):
        newParams = {}
        newParams.update(paramsA)
        newParams.update(paramsB)
        return newParams

    def _createTask(self, params, commands=None, loc=None):
        # Get nearest command
        if commands is None:
            node = self
            while node.commands is None:
                node = node.children[0]
            commands = node.commands

        # Parse command and create task
        return Task(self._parseCommands(params, commands), params,
                    loc=loc, wd=self.wd)


class ComparisonNode(Node):
    def __init__(self, params, children, commands, repeat, workdir):
        super().__init__(children, commands, repeat, workdir)
        # if len(params) == 1:
        #    self.allParamVals = list(params.values())[0]
        # else:
        self.allParamVals = list(product(*params.values()))
        self.paramNames = params.keys()
        self.done = False
        self.paramValsId = -1

        # Create an optimisation node per param value
        self.children = []
        if children is not None and len(children) > 0:
            for child in children:
                for i, paramsNode in enumerate(self._nextParamVals()):
                    joinedParams = self._joinParams(paramsNode, child.params)
                    self.children.append(OptimisedNode(
                        child.optimiserName, child.optParams, joinedParams,
                        child.children, child.commands, child.repeat, workdir))

    def getNextTasks(self, parentParams):
        # If node is a leaf, return all tasks
        if len(self.children) == 0:
            tasks = [None] * (self.repeat * len(self.allParamVals))
            for i, paramsNode in enumerate(self._nextParamVals()):
                # Combine node parameters with parent
                joinedParams = self._joinParams(parentParams, paramsNode)
                for j in range(self.repeat):
                    idt = j * len(self.allParamVals) + i
                    t = self._createTask(joinedParams)
                    self.runningTasks.append(t)
                    tasks[idt] = t
            # Node is done here.
            self.done = True
            return tasks

        # If node has children, return one task per child and param value
        else:
            tasks = []
            for i in range(len(self.children)-1, -1, -1):
                child = self.children[i]
                if child.isTaskReady():
                    # TODO: shouldn't these params be joinedParams?
                    tasks.extend(child.getNextTasks(parentParams))
                elif child.isDone():
                    # Repeat experiment with best params N times, and remove
                    # child from tree.
                    bestParams = child.getBestParams()
                    t = self._createTask(bestParams, child.commands)
                    self.runningTasks.append(t)
                    tasks.append(t)
                    for _ in range(self.repeat - 1):
                        newT = t.clone()
                        self.runningTasks.append(newT)
                        tasks.append(newT)
                    del self.children[i]
            # If last done was removed, mark as done
            if len(self.children) == 0:
                self.done = True

            return tasks

    def _nextParamVals(self):
        while self.paramValsId < len(self.allParamVals) - 1:
            self.paramValsId += 1
            yield dict(zip(self.paramNames,
                           self.allParamVals[self.paramValsId]))

    def isTaskReady(self):
        if len(self.children) == 0:
            return not self.done
        for child in self.children:
            if child.isTaskReady():
                return True
        for child in self.children:
            if child.isDone():
                return True
        return False

    def isDone(self):
        return len(self.children) == 0 and self.done

    def updateFinishedTask(self, task):
        """
        Updates a task in the tree starting from this node
        """
        # Search this node
        for t in self.runningTasks:
            if t.uniqueId == task.uniqueId:
                self.finishedTasks.append(task)
                self.runningTasks.remove(t)
                return True
        # ...or Delegate to children
        for child in self.children:
            if child.updateFinishedTask(task):
                return True


class OptimisedNode(Node):
    def __init__(self, optimiserName, optParams, params, children, commands,
                 repeat, workdir):
        super().__init__(children, commands, repeat, workdir)
        self.optimiserName = optimiserName
        self.optParams = optParams
        self.params = params
        self.childrenOpt = []
        self.optimiser = None
        self.isInit = False
        self.bestChildParams = None
        self.summaryPrinted = False

    def _init(self, parentParams):
        self.isInit = True

        # Fixed params
        self.fixedParams = dict(parentParams)

        # Categorical variables
        catNames = []
        catVals = []

        # Continuous variables
        low = []
        high = []
        logScale = []
        self.varNames = []

        # Parse parameters
        for k, v in self.params.items():
            # A number
            if isinstance(v, numbers.Number):
                self.fixedParams[k] = "{}".format(v)
            # List
            elif isinstance(v, list):
                catVals.append(v)
                catNames.append(k)
            # Linear/Logscale
            elif "linear" in v or "logscale" in v:
                items = re.split("\(|[ ]*,[ ]*|\)", v)
                logScale.append(True if items[0] == "logscale" else False)
                low.append(float(items[1]))
                high.append(float(items[2]))
                self.varNames.append(k)
            # Fixed params
            else:
                self.fixedParams[k] = v
        self.varNames.extend(catNames)

        self.optimiser = getOptimiser(self.optimiserName, self.optParams,
                                      low, high, logScale, catVals)

    def getNextTasks(self, parentParams):
        if not self.isInit:
            self._init(parentParams)

        # If child still running, defer next task to it
        for i in range(len(self.childrenOpt)-1, -1, -1):
            childOpt = self.childrenOpt[i]
            if childOpt.isTaskReady():
                # Get next task from child
                return childOpt.getNextTasks({})

        # Otherwise, get next location from this node
        if not self.isDone():
            loc = self.optimiser.nextLocation()
            if loc is None:
                self._printOptimisationSummary()
                return []
            paramVals = dict(zip(self.varNames, loc))

        allFixedParams = self._joinParams(self.fixedParams, parentParams)
        newParams = self._joinParams(allFixedParams, paramVals)

        # If node has children, create new optimisers
        if len(self.children) > 0 and not self.isDone():
            self.runningTasks.append(Task([], "", loc))
            for child in self.children:
                # joinedParams = self._joinParams(self.params, child.params)
                optNode = OptimisedNode(
                        child.optimiserName, child.optParams, child.params,
                        child.children, child.commands, child.repeat, self.wd)
                optNode._init(newParams)
                self.childrenOpt.append(optNode)
            return []

        # Otherwise, create task
        else:
            t = self._createTask(newParams, loc=loc)
            self.runningTasks.append(t)
            return [t]

    def getBestParams(self):
        """
        Returns best parameters after optimisation is finished
        """
        loc = self.optimiser.getBestLocation()
        allParams = dict(self.fixedParams)
        bestParams = dict(zip(self.varNames, loc))
        allParams.update(bestParams)
        if self.bestChildParams is not None:
            allParams.update(self.bestChildParams)
        return allParams

    def isTaskReady(self):
        # Check children first
        if len(self.childrenOpt) > 0:
            for child in self.childrenOpt:
                if child.isTaskReady() or child.isDone():
                    return True
            return False

        # Check this node
        if self.optimiser is None:
            return True
        return len(self.runningTasks) == 0 and not self.optimiser.isDone()

    def isDone(self):
        if self.optimiser is None:
            return False

        # If one child is not done, node is not done
        if len(self.childrenOpt) > 0:
            for child in self.childrenOpt:
                if not child.isDone():
                    return False

            # If all children are done. Only done if optimiser is done
            return self.optimiser.isDone()

        # When no children. Only done if optimiser is done
        return len(self.childrenOpt) == 0 and self.optimiser.isDone()

    def updateFinishedTask(self, task):
        # Search this node
        for t in self.runningTasks:
            if t.uniqueId == task.uniqueId:
                self._updateNodeFinishedTask(task.loc, task.score)
                self.runningTasks.remove(t)
                return

        # ...or Delegate to children
        for child in self.childrenOpt:
            child.updateFinishedTask(task)

        # If node has children and all are done, update this node with children
        # best locations
        if len(self.childrenOpt) > 0:
            for child in self.childrenOpt:
                if not child.isDone():
                    return
            score = 0
            bestChildParams = {}
            for i in range(len(self.childrenOpt)-1, -1, -1):
                childOpt = self.childrenOpt[i]
                if childOpt.isDone():
                    # Get child best location and score to update this node
                    score += childOpt.optimiser.getBestScore()
                    bestChildParams.update(childOpt.getBestParams())
                    # TODO: multi-input optimisation with additive scores?
                    del self.childrenOpt[i]
            self.bestChildParams = bestChildParams
            t = self.runningTasks[0]
            self.runningTasks.remove(t)
            self._updateNodeFinishedTask(t.loc, score)

    def _updateNodeFinishedTask(self, loc, score):
        self.optimiser.update(loc, score)
        if self.optimiser.isDone():
            self._printOptimisationSummary()

    def _printOptimisationSummary(self):
        if self.summaryPrinted:
            return
        self.summaryPrinted = True
        print("\n#######################\n# Optimisation summary:" +
              "\n#######################")
        print("Parent parameters:")
        if len(self.fixedParams) > 0:
            Row = namedtuple('Row', self.fixedParams.keys())
            pprinttable([Row(*self.fixedParams.values())])

        print("Optimal values:")
        bestLoc = self.optimiser.getBestLocation()
        prettyLoc = ["{:0.4f}".format(e) if isinstance(e, numbers.Number)
                     else e for e in bestLoc]
        Row = namedtuple('Row', self.varNames)
        pprinttable([Row(*prettyLoc)])

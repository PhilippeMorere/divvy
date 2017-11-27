from itertools import product
from ParallelTasks import Task
from Optimisers import GridSearchOptimiser
import numbers
import re


class Node:
    def __init__(self, children, commands, repeat):
        self.children = [] if children is None else children
        self.repeat = repeat
        self.commands = commands
        self.runningTasks = []
        self.finishedTasks = []

    def isTaskReady(self):
        """
        Whether a taks is ready in the tree. Method getNextTask will return
        task immediately.
        """
        if self._isNodeTaskReady():
            return True

        if len(self.children) > 0:
            for child in self.children:
                if child.isTaskReady():
                    return True
        return False

    def getNextTasks(self, parentParams=None):
        """
        Returns a list of tasks
        """
        raise NotImplementedError

    def updateFinishedTask(self, task):
        """
        Updates a task in the tree starting from this node
        """
        # Search this node
        for t in self.runningTasks:
            if t.uniqueId == task.uniqueId:
                self._updateNodeFinishedTask(task)
                self.runningTasks.remove(t)
                return
        # ...or Delegate to children
        for child in self.children:
            child.updateFinishedTask(task)

    def isDone(self):
        """
        Whether this node and all its children are finished
        """
        if len(self.children) > 0:
            for child in self.children:
                if not child.isDone():
                    return False
        return self._isNodeDone()

    def _isNodeDone(self):
        """
        Whether this node is finished
        """
        raise NotImplementedError

    def _isNodeTaskReady(self):
        """
        Whether this node has a taks ready
        """
        raise NotImplementedError

    def _updateNodeFinishedTask(self, task):
        """
        Updates a task from this node
        """
        raise NotImplementedError

    def _parseCommand(self, params, commands=None):
        """
        Replaces parameters with their value in commands
        """
        if commands is None:
            commands = self.commands
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


class ComparisonNode(Node):
    def __init__(self, params, children, commands, repeat):
        super().__init__(children, commands, repeat)
        # if len(params) == 1:
        #    self.allParamVals = list(params.values())[0]
        # else:
        self.allParamVals = list(product(*params.values()))
        self.paramNames = params.keys()
        self.done = False
        self.paramValsId = -1

        # Create an optimisation node per param value
        self.children = []
        if len(children) > 0:
            for child in children:
                for i, paramsNode in enumerate(self._nextParamVals()):
                    joinedParams = self._joinParams(paramsNode, child.params)
                    self.children.append(OptimisedNode(
                        child.optimiserName, child.optParams, joinedParams,
                        child.children, child.commands, child.repeat))

    def getNextTasks(self, parentParams):
        # If node is a leaf, return all tasks
        if len(self.children) == 0:
            tasks = [None] * (self.repeat * len(self.allParamVals))
            for i, paramsNode in enumerate(self._nextParamVals()):
                # Combine node parameters with parent
                joinedParams = self._joinParams(parentParams, paramsNode)
                for j in range(self.repeat):
                    idt = i * len(self.allParamVals) + j
                    t = Task(self._parseCommand(joinedParams))
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
                    tasks.extend(child.getNextTasks(parentParams))
                elif child.isDone():
                    # Repeat experiment with best params N times, and remove
                    # child from tree.
                    bestParams = child.getBestParams()
                    print("Optimisation done. Best parameters are {}".format(
                        bestParams))
                    for _ in range(self.repeat):
                        t = Task(self._parseCommand(
                            bestParams, child.commands), bestParams)
                        self.runningTasks.append(t)
                        tasks.append(t)
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
            return not self._isNodeDone()
        for child in self.children:
            if child.isTaskReady():
                return True
        for child in self.children:
            if child.isDone():
                return True
        return False

    def _isNodeDone(self):
        return self.done

    def _updateNodeFinishedTask(self, task):
        self.finishedTasks.append(task)


class OptimisedNode(Node):
    def __init__(self, optimiserName, optParams, params, children, commands,
                 repeat):
        super().__init__(children, commands, repeat)
        self.optimiserName = optimiserName
        self.optParams = optParams
        self.params = params
        self.optimiser = None
        self.isInit = False

    def _init(self):
        self.isInit = True

        # Fixed params
        self.fixedParams = {}

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
            elif re.match("\[(\d+\.?\d*)(,\s*\d+\.?\d*)*\]", v):
                items = re.split("\[|,\s?|\]", v)[1:-1]
                print(items)
                print("Warning: this is not supported yet!")
                # TODO: support this
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

        if self.optimiserName == "GridSearch":
            if self.optParams is None or "gridRes" not in self.optParams:
                raise ValueError("tag \"gridRes\" required in \"opt_params\"" +
                                 " tag for GridSearch optimiser")
            gridRes = self.optParams["gridRes"]
            self.optimiser = GridSearchOptimiser(gridRes, low, high, logScale)
        else:
            raise ValueError("Unknown optimiser \"{}\"".
                             format(self.optimiserName))

    def getNextTasks(self, parentParams):
        if not self.isInit:
            self._init()
        if not self.isDone():
            loc = self.optimiser.nextLocation().reshape(-1)
            paramVals = dict(zip(self.varNames, loc))
        else:
            loc = self.optimiser.getBestLocation().reshape(-1)
            paramVals = dict(zip(self.varNames, loc))

        allFixedParams = self._joinParams(self.fixedParams, parentParams)
        newParams = self._joinParams(allFixedParams, paramVals)

        # Create task
        t = Task(self._parseCommand(newParams), newParams, loc)
        self.runningTasks.append(t)
        return [t]

    def getBestParams(self):
        """
        Returns best parameters after optimisation is finished
        """
        loc = self.optimiser.getBestLocation()
        bestParams = dict(zip(self.varNames, loc))
        bestParams.update(self.fixedParams)
        return bestParams

    def _isNodeTaskReady(self):
        return len(self.runningTasks) == 0 and not self.isDone()

    def _isNodeDone(self):
        return self.optimiser is not None and self.optimiser.isDone()

    def _updateNodeFinishedTask(self, task):
        self.optimiser.update(task.loc, task.score)

from multiprocessing import Process, Queue, Manager
import bayesopt
from swarmops.Problem import Problem
from swarmops.PSO import PSO
from swarmops.PSO import MOL
from swarmops.DE import DE
from swarmops.PS import PS
from swarmops.LUS import LUS
import numpy as np
import math


swarmopsOptimisers = {"ParticleSwarmOptimisation": PSO,
                      "DifferentialEvolution": DE,
                      "ManyOptimisingLiaisons": MOL,
                      "PatternSearch": PS,
                      "LocalUnimodalSampling": LUS}


def getOptimiser(optName, optParams, varLow, varHigh, varLogScale, catVals):
    if optName == "GridSearch":
        if optParams is None or "gridRes" not in optParams:
            raise ValueError("tag \"gridRes\" required in \"opt_params\"" +
                             " tag for GridSearch optimiser")
        gridRes = optParams["gridRes"]
        return GridSearchOptimiser(optName, gridRes, varLow, varHigh,
                                   varLogScale, catVals)
    elif optName == "BayesianOptimisation":
        if len(catVals) > 0:
            raise ValueError("\"BayesianOptimisation\" optimiser cannot " +
                             "handle categorical variables.")
        return BayesianOptimisationOptimiser(optName, optParams, varLow,
                                             varHigh, varLogScale, None)
    elif optName in swarmopsOptimisers.keys():
        if len(catVals) > 0:
            raise ValueError("\"{}\" optimiser".format(optName) +
                             " cannot handle categorical variables.")
        return SwarmOpsOptimiser(optName, optParams, varLow, varHigh,
                                 varLogScale, catVals)
    else:
        raise ValueError("Unknown optimiser \"{}\"".format(optName))


class AbsOptimiser:
    def __init__(self, optName, low, high, logScale=False, catVals=[]):
        """
        :param logScale: Mask specifying if corresponding dimension is on a
        log scale.
        """
        self.optName = optName

        self.logScale = logScale
        if not isinstance(logScale, list):
            self.logScale = [logScale] * len(high)

        # Log scaling if necessary
        self.low = self._toNewScale(low)
        self.high = self._toNewScale(high)

        # Keep track of best location
        self.bestLocation = None
        self.bestLocationVal = 0.0

        # Categorical variables
        self.catVals = catVals

    def _toOriginalScale(self, loc):
        if loc is None:
            return None
        newLoc = list(loc)
        for i in range(len(self.logScale)):
            if self.logScale[i]:
                newLoc[i] = math.exp(loc[i])
            else:
                newLoc[i] = loc[i]
        return newLoc

    def _toNewScale(self, loc):
        newLoc = list(loc)
        for i in range(len(self.logScale)):
            if self.logScale[i]:
                newLoc[i] = math.log(loc[i])
            else:
                newLoc[i] = loc[i]
        return newLoc

    def nextLocation(self):
        loc = self._nextLocation()
        return self._toOriginalScale(loc)

    def _nextLocation(self):
        """
        Returns next location to try
        """
        raise NotImplementedError

    def update(self, loc, val):
        # Check if this is a new best location
        if val > self.bestLocationVal or self.bestLocation is None:
            self.bestLocationVal = val
            self.bestLocation = loc

        loc = self._toNewScale(loc)
        self._update(loc, val)

    def _update(self, loc, val):
        """
        Updates location with corresponding value
        """
        raise NotImplementedError

    def getBestLocation(self):
        return self.bestLocation

    def getBestScore(self):
        return self.bestLocationVal

    def isDone(self):
        """
        Whether the optimiser is finished
        """
        raise NotImplementedError


class GridSearchOptimiser(AbsOptimiser):
    def __init__(self, optName, gridRes, *args, **kwargs):
        super().__init__(optName, *args, **kwargs)
        self.gridRes = gridRes
        self.gridDims = []

        # Continuous variables
        for i in range(len(self.low)):
            gridDim = np.linspace(self.low[i], self.high[i], gridRes)
            self.gridDims.append(gridDim)

        # Categorical variables
        for i in range(len(self.catVals)):
            self.gridDims.append(self.catVals[i])

        self.locId = 0

    def _nextLocation(self):
        loc = [None] * len(self.gridDims)
        restId = self.locId
        for i in range(len(self.gridDims)):
            dimId = restId % len(self.gridDims[i])
            restId = restId // len(self.gridDims[i])
            loc[i] = self.gridDims[i][dimId]

        return loc

    def _update(self, loc, val):
        self.locId += 1

    def isDone(self):
        noPoints = np.prod([len(self.gridDims[i])
                           for i in range(len(self.gridDims))])
        return self.locId >= noPoints


class ThreadedOptimiser(AbsOptimiser):
    def __init__(self, optName, optParams, *args, **kwargs):
        super().__init__(optName, *args, **kwargs)
        self.optFctr = 1.0  # Changed for minimisation/maximisation

        # Managing workers
        self.m = Manager()
        self.availableUpdateEvent = self.m.Event()
        self.updateFoundEvent = self.m.Event()
        self.scoreDict = self.m.dict()
        self.managerLock = self.m.Lock()

        # For communication
        self.locationQueue = Queue()
        self.doneQueue = Queue()

        # Start worker
        p = Process(target=self.worker, args=[optParams])
        p.start()

    def _hashLoc(self, loc):
        locStr = ' '.join(['{:0.9f}'.format(l) for l in loc])
        return locStr

    def _objectiveFunction(self, loc):
        # Register with manager dictionary
        locStr = self._hashLoc(loc)
        with self.managerLock:
            if locStr in self.scoreDict:
                if isinstance(self.scoreDict[locStr], list):
                    self.scoreDict.extend([None])
                else:
                    self.scoreDict[locStr] = [self.scoreDict[locStr], None]
            else:
                self.scoreDict[locStr] = None
        # Add new loc to location queue
        self.locationQueue.put(loc)

        # Wait for socre with corresponding loc to arrive
        foundUpdate = False
        score = None
        while not foundUpdate:
            self.availableUpdateEvent.wait()
            # Try and retrieve socre. If score found, unregister
            with self.managerLock:
                if isinstance(self.scoreDict[locStr], list):
                    score = self.scoreDict[locStr][0]
                    if score is not None:
                        foundUpdate = True
                        if len(self.scoreDict[locStr]) == 1:
                            del self.scoreDict[locStr]
                        else:
                            del self.scoreDict[locStr][0]
                else:
                    score = self.scoreDict[locStr]
                    if score is not None:
                        foundUpdate = True
                        del self.scoreDict[locStr]
                if foundUpdate:
                    self.availableUpdateEvent.clear()
                    self.updateFoundEvent.set()
                    break
            self.updateFoundEvent.wait()

        return self.optFctr * score

    def worker(self, optParams):
        self._worker(optParams)
        self.doneQueue.put("DONE")
        self.locationQueue.put(None)

    def _worker(self, optParams):
        """
        Worker calling any "blocking" optimisation library.
        """
        raise NotImplementedError

    def _nextLocation(self):
        v = self.locationQueue.get()
        if v is None:
            return None
        else:
            return v

    def _update(self, loc, val):
        # Find the right worker
        locStr = self._hashLoc(loc)
        with self.managerLock:
            # Give worker the score
            if isinstance(self.scoreDict[locStr], list):
                self.scoreDict[locStr][0] = val
            else:
                self.scoreDict[locStr] = val
            self.updateFoundEvent.clear()
            self.availableUpdateEvent.set()

    def isDone(self):
        return self.doneQueue.qsize() > 0


class BayesianOptimisationOptimiser(ThreadedOptimiser):
    def _worker(self, optParams):
        dim = len(self.low)
        lb = np.array(self.low)
        ub = np.array(self.high)
        self.optFctr = -1  # Because bayesopt does minimisation
        y, x, err = bayesopt.optimize(self._objectiveFunction, dim, lb, ub,
                                      optParams)


class SwarmOpsOptimiser(ThreadedOptimiser):
    class SwarmOpsProblem(Problem):
        def __init__(self, objFn, *args, **kwargs):
            super().__init__(*args,  **kwargs)
            self.objFn = objFn

        def fitness(self, x, limit=np.Infinity):
            return self.objFn(x)

    def _worker(self, optParams):
        dim = len(self.low)
        lb = np.array(self.low)
        ub = np.array(self.high)
        self.optFctr = -1  # Because swarmops does minimisation
        minVal = optParams["max_score"] if "max_score" in optParams \
            else np.Infinity
        prob = SwarmOpsOptimiser.SwarmOpsProblem(self._objectiveFunction,
                                                 "SwarmOps problem", dim,
                                                 minVal, lb, ub)

        if "n_iterations" not in optParams.keys():
            raise ValueError("Specify 'n_iterations' tag for optimiser {}".
                             format(self.optName))
        n_iter = optParams["n_iterations"]
        opt = swarmopsOptimisers[self.optName]
        opt(problem=prob, max_evaluations=n_iter)

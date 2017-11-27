import numpy as np
import math


# TODO: Add BO

class AbsOptimiser:
    def __init__(self, low, high, logScale=False):
        """
        :param logScale: Mask specifying if corresponding dimension is on a
        log scale.
        """
        self.logScale = logScale
        if not isinstance(logScale, list):
            self.logScale = [logScale] * len(high)

        # Log scaling if necessary
        self.low = self._toNewScale(low)
        self.high = self._toNewScale(high)

        # Keep track of best location
        self.bestLocation = None
        self.bestLocationVal = 0.0

    def _toOriginalScale(self, loc):
        newLoc = np.zeros(loc.shape)
        for i in range(len(self.logScale)):
            if self.logScale[i]:
                newLoc[i] = math.exp(loc[i])
            else:
                newLoc[i] = loc[i]
        return newLoc

    def _toNewScale(self, loc):
        newLoc = np.zeros((len(loc), 1))
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

    def isDone(self):
        """
        Whether the optimiser is finished
        """
        raise NotImplementedError


class GridSearchOptimiser(AbsOptimiser):
    def __init__(self, gridRes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gridRes = gridRes
        self.gridDims = []
        for i in range(len(self.low)):
            gridDim = np.linspace(self.low[i], self.high[i], gridRes)
            self.gridDims.append(gridDim)
        self.locId = 0

    def _nextLocation(self):
        loc = np.zeros((len(self.low), 1))
        restId = self.locId
        for i in range(len(self.low)):
            dimId = restId % self.gridRes
            restId = restId // self.gridRes
            loc[i] = self.gridDims[i][dimId]
        self.locId += 1
        return loc

    def _update(self, loc, val):
        # Nothing to do
        pass

    def isDone(self):
        return self.locId >= self.gridRes ** len(self.low)

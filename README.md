Divvy
==========================
Divvy is a Python library for parallelized optimisation of multiple experiments - if you can execute your experiment with commandline you can Divvy it!. It allows for efficient testing by allowing smarter optimisation of experimental parameters in a distribution fashion. Divvy supports a generic interface to a variety of standard optimisers with a focus on Bayesian Optimisation for data efficient parameter learning. 

## Installation
### Dependencies
* python-yaml
* numpy
* bayesopt (https://bitbucket.org/rmcantin/bayesopt)
* swarmops (https://github.com/Hvass-Labs/swarmops)

### Divvy
Global installation:
```
sudo python setup.py install
```
User installation:
```
python setup.py install --user
```

## Running
```
divvy <path/to/config/file.yaml>
```

## Config file syntax
Examples of configuration files and scripts are given in the `examples` directory.

### List of supported optimisers
#### Continuous and/or discrete variables
* GridSearch

#### Continuous variables variables only
* BayesianOptimisation
* ParticleSwarmOptimisation
* DifferentialEvolution
* ManyOptimisingLiaisons
* PatternSearch
* LocalUnimodalSampling

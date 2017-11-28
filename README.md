Divvy
==========================
Divvy is a Python library for parallelized optimisation of multiple experiments - if you can execute your experiment with commandline you can Divvy it!. It allows for efficient testing by allowing smarter optimisation of experimental parameters in a distribution fashion. Divvy supports a generic interface to a variety of standard optimisers with a focus on Bayesian Optimisation for data efficient parameter learning. 

## Installation
### Dependencies
* python-yaml

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
divvy <path/to/config/file>
```
## Config file syntax
An example of configuration file file is given in `examples/config.yaml`.

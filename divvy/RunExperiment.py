#!/usr/bin/env python
from multiprocessing import freeze_support
import argparse
import os
import re
import yaml
import sys
import numbers
from ParallelTasks import ParallelTasks

Possible_options = ["outdir", "workdir"]

def checkNodeExists(config, name):
    if not name in config:
        print(r"Error: configuration file must include a \"{}\" node.".format(name))
        sys.exit()

def checkConfig(config):
    """ Check config file for missing nodes """
    checkNodeExists(config, "name")
    checkNodeExists(config, "options")
    checkNodeExists(config["options"], "outdir")
    checkNodeExists(config, "commands")
    if not "repeat" in config:
        config["repeat"] = 1
    if not "cpus" in config:
        config["cpus"] = 1

def parseReplacements(config):
    """Parses the replacements of the program."""
    replacements = {}
    for key, val in config.items():
        if isinstance(val, str):
            # Escape string so that it is not divided into multiple command arguments
            replacements[key] = "\"{}\"".format(val)
        else:
            replacements[key] = val
    return replacements

def parseCommands(config, replacements):
    """Parses the commands of the program."""
    commands = [c for c in config]
    for key, val in replacements.items():
        # This is the case for regular number parameters
        if isinstance(val, (numbers.Number, str)):
            for i in range(len(commands)):
                commands[i] = re.sub("\$\{%s\}" % key, str(val), commands[i])
        else: # This is the case for trying several parameter values
            newCommands = []
            for cmd in commands:
                if cmd.find(key) == -1:
                    newCommands.append(cmd)
                else:
                    for v in val:
                        newCmd = re.sub("\$\{%s\}" % key, str(v), cmd)
                        newCommands.append(newCmd)
            commands = newCommands

    return commands

def parseOptions(config, replacements):
    """Parses the options of the program."""
    params = {}
    for opt in Possible_options:
        if opt in config:
            opt_value = config[opt]
            for key, val in replacements.items():
                if isinstance(val, numbers.Number):
                    opt_value = re.sub("\$\{%s\}" % key, str(val), opt_value)
                    params[opt] = opt_value
                    replacements[opt] = opt_value
        else:
            params[opt] = None

    for opt in config:
        if opt not in Possible_options:
            print("Error: Unrecognized option \"{0}\" enountered".format(opt))
            sys.exit()
    return params

def parseToTasks(config):
    """ Parses commands from config file to a list of tasks to be executed"""
    replacements = parseReplacements(config["replacements"] if "replacements" in config else {})
    params = parseOptions(config["options"], replacements)
    commands = parseCommands(config["commands"], replacements)
    
    if params["workdir"] is not None:
        os.chdir(params["workdir"])
    return [tuple(commands)] * config["repeat"]

def main():
    # Parse argument(s)
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Experiment configuration file (YAML)')
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.isfile(args.config):
        print("Error: configuration file {} does not exist.".format(args.config))
        sys.exit()
    
    # Parse Yaml file and verify config
    yamlTree = yaml.safe_load(open(args.config))
    config = yamlTree["experiment"]
    checkConfig(config)
    
    # Parse Yaml config to task list
    tasks = parseToTasks(config)

    #TODO: print info and start time
    print("Starting experiment.")
    
    # Run the taks in parallel
    pt = ParallelTasks()
    pt.run(tasks, config["cpus"])

    print("All done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

from multiprocessing import Process, Queue
from subprocess import check_output
import shlex


class Task():
    idn = 0

    def __init__(self, commands):
        self.uniqueId = Task.idn
        Task.idn += 1
        self.commands = commands
        self.results = None


class ParallelTasks():
    def __init__(self, noWorkers=3):
        self.noWorkers = noWorkers

        # Create worker queues
        self.taskQueues = []
        self.doneQueue = Queue()

        # Start worker processes
        for i in range(noWorkers):
            self.taskQueues.append(Queue())
            p = Process(target=self._worker,
                        args=(self.taskQueues[i], self.doneQueue, None))
            p.start()

    def _execute(self, cmd):
        """ Executes system call with proper arguments"""
        args = shlex.split(cmd)
        ret = check_output(args, shell=True)
        return ret

    def _worker(self, inputQueue, outputQueue, args):
        """ Function run by worker processes """
        for task in iter(inputQueue.get, 'STOP'):
            print("Got command", task.commands)
            # Arguments are commands to execute
            results = []

            # Single command case
            if isinstance(task.commands, str):
                results.append(self._execute(task.commands))
            # Multiple commands case
            else:
                for command in task.commands:
                    results.append(self._execute(command))

            # TODO: Parse output
            task.results = results
            outputQueue.put(task)

        # Notify worker is done
        self.doneQueue.put('DONE')

    def addTasks(self, tasks):
        for task in tasks:
            self.addTask(task)

    def addTask(self, task):
        minSize = self.taskQueues[0].qsize()
        minQueue = self.taskQueues

        # Find an free worker
        for q in self.taskQueues:
            if q.empty():
                # Add to empty queue
                q.put(task)
                return
            # Keep track of smallest queue
            if q.qsize() < minSize:
                minSize = min(minSize, q.qsize())
                minQueue = q

        # Add job to smallest queue
        minQueue.put(task)

    def getFinishedTask(self):
        for _ in range(self.noWorkers):
            for task in iter(self.doneQueue.get, 'DONE'):
                yield task

    def end(self):
        # Make them stooop!
        for q in self.taskQueues:
            q.put('STOP')


if __name__ == '__main__':
    pt = ParallelTasks()

    # Add tasks
    tasks = [Task(("ls", "ls", "ls")), Task("pwd")]
    pt.addTasks(tasks)

    # End
    pt.end()

    # Get results
    for task in pt.getFinishedTask():
        print(task.results)

from multiprocessing import Process, Queue
from subprocess import check_output


class Task():
    idn = 0

    def __init__(self, commands, params, loc=None, wd=None):
        self.uniqueId = Task.idn  # Unique identifier
        Task.idn += 1
        self.commands = commands  # List of commands
        self.params = params  # Parameter dictionary corresponding to commands
        self.score = None  # Score after command was run
        self.wd = wd  # Working directory
        self.loc = loc  # Location used by optimisers (parameter values)


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

    def _execute(self, cmd, wd):
        """
        Executes system call with given command and working directory
        """
        # Run commmand
        if wd is None:
            ret = check_output(cmd, shell=True)
        else:
            ret = check_output(cmd, shell=True, cwd=wd)

        # Parse score
        score = 0
        items = ret.split(b"\n")
        score = float(items[-2])
        return score

    def _worker(self, inputQueue, outputQueue, args):
        """
        Function run by worker processes
        """
        for task in iter(inputQueue.get, 'STOP'):
            # Arguments are commands to execute
            scores = []

            # Single command case
            if isinstance(task.commands, str):
                scores.append(self._execute(task.commands, task.wd))
            # Multiple commands case
            else:
                for command in task.commands:
                    scores.append(self._execute(command, task.wd))

            # Only keep last score
            task.score = scores[-1]
            outputQueue.put(task)

        # Notify worker is done
        self.doneQueue.put('DONE')

    def addTasks(self, tasks):
        for task in tasks:
            self.addTask(task)

    def addTask(self, task):
        minSize = self.taskQueues[0].qsize()
        minQueue = self.taskQueues[0]

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

from multiprocessing import Process, Queue, current_process, freeze_support
from subprocess import call

class ParallelTasks():
    def __init__(self):
        pass
    
    def execute(self, cmd):
        """ Executes system call with proper arguments"""
        args = cmd.split(" ")
        res = call(args)
        return res

    def worker(self, input, output, args):
        """ Function run by worker processes """
        for expArgs in iter(input.get, 'STOP'):
            # Arguments are commands to execute
            result = []
            if isinstance(expArgs, str):
                result.append(self.execute(expArgs))
            else:
                for cmd in expArgs:
                    result.append(self.execute(cmd))
            output.put(str(result))

    def run(self, tasks, noProcs=4):
        """ Distributes the given tasks on available CPUs using a queue system """
        # Create queues
        task_queue = Queue()
        done_queue = Queue()
    
        # Submit tasks
        for task in tasks:
            task_queue.put(task)
        nbTasks = task_queue.qsize()
    
        # Start worker processes
        for i in range(noProcs):
            Process(target=self.worker, args=(task_queue, done_queue, None)).start()
    
        # Printing results on screen and completion
        print('Results:')
        for i in range(nbTasks):
            r = done_queue.get()
            print '\t(Progress: {:>4.4}%)'.format(100.0 * i / float(nbTasks))
    
        # Tell child processes to stop
        for i in range(noProcs):
            task_queue.put('STOP')


if __name__ == '__main__':
    pt = ParallelTasks()
    tasks = [("ls", "ls", "ls"), ("pwd")]
    pt.run(tasks, 3)


"""
Function handlers as part of flow
"""
from viewflow.flow.base import Event, Edge
from viewflow.activation import StartActivation, TaskActivation


class StartFunction(Event):
    """
    def create_requst(activation):
        activation.done()

    class MyFlow(Flow):
        start_request = flow.StartFunction(create_request)

    MyFlow.create_request.run()
    """

    task_type = 'START'
    activation_cls = StartActivation

    def __init__(self, func, **kwargs):
        self.func = func
        super(StartFunction, self).__init__(**kwargs)
        self._activate_next = []

    def _outgoing(self):
        for next_node in self._activate_next:
            yield Edge(src=self, dst=next_node, edge_class='next')

    def run(self, *args, **kwargs):
        if isinstance(self.func, type) and issubclass(self.func, StartActivation):
            receiver = self.func()
            receiver.initialize(self)
            receiver(*args, **kwargs)
        else:
            activation = self.activation_cls()
            activation.initialize(self)
            self.func(activation, *args, **kwargs)

    def Next(self, node):
        self._activate_next.append(node)
        return self

    def has_perm(self, user):
        return False


class FlowFunc(object):
    def get_task(self, flow_task, *func_args, **func_kwars):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


def flow_func(task_loader=None, **lock_args):
    """
    Decorator for flow functions
    """
    def decorator(func_or_cls):
        def wrapper(flow_task, *func_args, **func_kwargs):
            if isinstance(func_or_cls, type) and issubclass(func_or_cls, FlowFunc):
                receiver_cls = func_or_cls
            else:
                class FuncWrapper(FlowFunc):
                    def get_task(self, flow_task, *func_args, **func_kwargs):
                        return task_loader(flow_task, *func_args, **func_kwargs)

                    def __call__(self, activation, *func_args, **func_kwargs):
                        return func_or_cls(activation, *func_args, **func_kwargs)

                receiver_cls = FuncWrapper

            receiver = receiver_cls()

            task = receiver.get_task(flow_task, *func_args, **func_kwargs)
            lock = flow_task.flow_cls.lock_impl(**lock_args)

            with lock(flow_task, task.process_id):
                task = flow_task.flow_cls.task_cls._default_manager.get(pk=task.pk)
                if isinstance(receiver, TaskActivation):
                    receiver.initialize(flow_task, task)
                    receiver(*func_args, **func_kwargs)
                else:
                    activation = flow_task.activation_cls()
                    activation.initialize(flow_task, task)
                    receiver(activation, *func_args, **func_kwargs)

        return wrapper

    return decorator


class Function(Event):
    task_type = 'FUNC'
    activation_cls = TaskActivation

    def __init__(self, func, **kwargs):
        self.func = func
        super(Function, self).__init__(**kwargs)
        self._activate_next = []

    def _outgoing(self):
        for next_node in self._activate_next:
            yield Edge(src=self, dst=next_node, edge_class='next')

    def run(self, *args, **kwargs):
        self.func(self, *args, **kwargs)

    def Next(self, node):
        self._activate_next.append(node)
        return self

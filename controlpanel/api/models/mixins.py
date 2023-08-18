class TaskModelMixin:

    TASK_MAPPING = {}

    def get_task_class(self, task_name):
        return self.TASK_MAPPING[task_name]

    class Meta:
        abstract = True

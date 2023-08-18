class TaskModelMixin:

    TASK_MAPPING = {}

    def get_task_class(self, task_name):
        if task_name not in self.TASK_MAPPING:
            raise Exception(
                f"Task does not exist with this name for {self.__class__.__name__}"
            )
        return self.TASK_MAPPING[task_name]

    class Meta:
        abstract = True

# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api.models import Task
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler, BaseTaskHandler


@pytest.mark.parametrize(
    "handler_cls, args",
    [
        (BaseTaskHandler, (None,)),
        (BaseModelTaskHandler, (1, 1)),
    ],
)
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.handle")
def test_completed_task_handle_not_run(handle, handler_cls, args):
    completed_task = MagicMock(spec=Task, completed=True)
    base_task_handler = handler_cls()

    with patch.object(base_task_handler, "get_task_obj", return_value=completed_task):
        base_task_handler.run(*args)

    handle.assert_not_called()


@pytest.mark.parametrize(
    "handler_cls, args",
    [
        (BaseTaskHandler, (None,)),
        (BaseModelTaskHandler, (1, 1)),
    ],
)
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.handle")
@patch(
    "controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.get_object",
    new=MagicMock,
)
def test_uncompleted_task_handle_is_run(handle, handler_cls, args):
    completed_task = MagicMock(spec=Task, completed=False)
    base_task_handler = handler_cls()

    with patch.object(base_task_handler, "get_task_obj", return_value=completed_task):
        base_task_handler.run(*args)

    handle.assert_called_once()


@pytest.mark.parametrize(
    "handler_cls, args",
    [
        (BaseTaskHandler, (None,)),
        (BaseModelTaskHandler, (1, 1)),
    ],
)
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.handle")
@patch(
    "controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.get_object",
    new=MagicMock,
)
def test_no_task_obj_handle_is_run(handle, handler_cls, args):
    base_task_handler = handler_cls()
    with patch.object(base_task_handler, "get_task_obj", return_value=None):
        base_task_handler.run(*args)

    handle.assert_called_once()

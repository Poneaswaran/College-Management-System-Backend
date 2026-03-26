import importlib
import threading
import uuid


def _resolve_callable(target):
    if callable(target):
        return target
    if isinstance(target, str):
        module_name, func_name = target.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, func_name)
    raise TypeError("Unsupported task target type")


def async_task(func, *args, hook=None, **kwargs):
    """
    Compatibility wrapper:
    - Uses django_q async_task when available and compatible.
    - Falls back to background thread execution when django_q is unavailable.
    """
    try:
        from django_q.tasks import async_task as django_q_async_task

        return django_q_async_task(func, *args, hook=hook, **kwargs)
    except Exception:
        task_id = str(uuid.uuid4())

        def runner():
            success = True
            result = None
            try:
                target = _resolve_callable(func)
                result = target(*args, **kwargs)
            except Exception as exc:
                success = False
                result = str(exc)
            if hook:
                try:
                    hook_fn = _resolve_callable(hook)
                    task_obj = type("TaskResult", (), {"success": success, "result": result, "args": args})
                    hook_fn(task_obj)
                except Exception:
                    pass

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return task_id

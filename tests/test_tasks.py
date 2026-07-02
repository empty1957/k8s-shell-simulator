from app.tasks import task_store


def test_initial_tasks_load():
    tasks = task_store.list_tasks()
    assert [task.id for task in tasks] == [
        "001-create-namespace",
        "002-nginx-deployment",
        "003-service",
    ]
    assert all(task.check.type == "script" for task in tasks)

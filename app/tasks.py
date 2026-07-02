from dataclasses import dataclass
from pathlib import Path

import yaml

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class TaskNotFoundError(KeyError):
    pass


@dataclass
class TaskCheck:
    type: str
    script: str


@dataclass
class Task:
    id: str
    title: str
    difficulty: str
    description: str
    setup_manifests: list[str]
    check: TaskCheck

    def to_public_dict(self, include_description: bool = True) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "difficulty": self.difficulty,
            "setup": {"manifests": self.setup_manifests},
            "check": {"type": self.check.type, "script": self.check.script},
        }
        if include_description:
            data["description"] = self.description
        return data


class TaskStore:
    def __init__(self, tasks_dir: Path = TASKS_DIR) -> None:
        self.tasks_dir = tasks_dir

    def list_tasks(self) -> list[Task]:
        return sorted(
            [self._load_task(path) for path in self.tasks_dir.glob("*.yaml")],
            key=lambda task: task.id,
        )

    def get_task(self, task_id: str) -> Task:
        for task in self.list_tasks():
            if task.id == task_id:
                return task
        raise TaskNotFoundError(f"Task '{task_id}' was not found.")

    def _load_task(self, path: Path) -> Task:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        check = data.get("check", {})
        setup = data.get("setup", {})
        return Task(
            id=data["id"],
            title=data["title"],
            difficulty=data.get("difficulty", "unknown"),
            description=data.get("description", ""),
            setup_manifests=setup.get("manifests", []) or [],
            check=TaskCheck(type=check["type"], script=check["script"]),
        )


task_store = TaskStore()

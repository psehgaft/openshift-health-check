from __future__ import annotations

import os
import sys
from typing import Iterable

import yaml

from ansible.plugins.callback.default import CallbackModule as DefaultCallbackModule
from ansible.playbook.block import Block


DOCUMENTATION = r"""
    callback: task_progress
    type: stdout
    short_description: Show task-count progress while preserving default stdout output
    description:
      - Extends Ansible's default stdout callback with a single-line progress bar.
      - The total starts from the statically compiled play task list and grows when include_tasks discovers more tasks.
    extends_documentation_fragment:
      - default_callback
      - result_format_callback
"""


class CallbackModule(DefaultCallbackModule):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "task_progress"

    def __init__(self) -> None:
        super().__init__()
        disable_progress = str(os.getenv("OHC_DISABLE_TASK_PROGRESS", "")).strip().lower() in {"1", "true", "yes", "on"}
        self._progress_enabled = not disable_progress
        self._progress_total = 0
        self._progress_completed = 0
        self._known_task_keys: set[str] = set()
        self._completed_task_keys: set[str] = set()
        self._discovered_include_keys: set[str] = set()
        self._current_task_name = ""
        self._current_play_name = ""
        self._progress_drawn = False

    def _task_key(self, task) -> str:
        return str(getattr(task, "_uuid", "") or "")

    def _is_countable_task(self, task) -> bool:
        action = str(getattr(task, "action", "") or "")
        if not action:
            return False
        if action == "meta" and getattr(task, "implicit", False):
            return False
        return True

    def _iter_nested_tasks(self, task_objects: Iterable) -> Iterable:
        for item in task_objects or []:
            if isinstance(item, Block):
                yield from self._iter_nested_tasks(item.block)
                yield from self._iter_nested_tasks(item.rescue)
                yield from self._iter_nested_tasks(item.always)
            else:
                yield item

    def _register_task(self, task) -> None:
        key = self._task_key(task)
        if not key or key in self._known_task_keys or not self._is_countable_task(task):
            return
        self._known_task_keys.add(key)
        self._progress_total += 1

    def _register_play_tasks(self, play) -> None:
        compiled = []
        try:
            compiled.extend(play.compile())
        except Exception:
            compiled.extend(play.get_tasks())
        try:
            compiled.extend(play.compile_roles_handlers())
        except Exception:
            pass
        for task in self._iter_nested_tasks(compiled):
            self._register_task(task)

    def _count_tasks_in_yaml_node(self, node) -> int:
        if isinstance(node, list):
            return sum(self._count_tasks_in_yaml_node(item) for item in node)
        if not isinstance(node, dict):
            return 0
        count = 1
        for key in ("block", "rescue", "always"):
            count += self._count_tasks_in_yaml_node(node.get(key) or [])
        return count

    def _count_tasks_in_include_file(self, filename: str) -> int:
        if not filename or not os.path.exists(filename):
            return 0
        try:
            with open(filename, "r", encoding="utf-8") as handle:
                content = yaml.safe_load(handle)
        except Exception:
            return 0
        return self._count_tasks_in_yaml_node(content)

    def _discover_include_tasks(self, included_file) -> None:
        filename = str(getattr(included_file, "_filename", "") or "")
        parent = getattr(included_file, "_task", None)
        parent_key = self._task_key(parent)
        include_key = f"{parent_key}:{filename}"
        if not filename or include_key in self._discovered_include_keys:
            return
        self._discovered_include_keys.add(include_key)
        discovered = self._count_tasks_in_include_file(filename)
        if discovered > 0:
            self._progress_total += discovered

    def _truncate(self, value: str, max_len: int) -> str:
        text = " ".join((value or "").split())
        if len(text) <= max_len:
            return text
        if max_len <= 3:
            return text[:max_len]
        return text[: max_len - 3] + "..."

    def _progress_line(self) -> str:
        total = max(self._progress_total, 0)
        completed = min(self._progress_completed, total) if total > 0 else 0
        percent = int((completed / total) * 100) if total > 0 else 0
        width = 24
        filled = min(width, int((completed / total) * width)) if total > 0 else 0
        bar = "#" * filled + "-" * (width - filled)
        segments = [f"[{bar}] {percent:3d}% ({completed}/{total})"]
        if self._current_play_name:
            segments.append(f"play={self._truncate(self._current_play_name, 28)}")
        if self._current_task_name:
            segments.append(f"task={self._truncate(self._current_task_name, 56)}")
        return " ".join(segments)

    def _clear_progress(self) -> None:
        if not self._progress_enabled or not self._progress_drawn:
            return
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()
        self._progress_drawn = False

    def _render_progress(self) -> None:
        if not self._progress_enabled:
            return
        line = self._progress_line()
        sys.stdout.write("\r\033[2K" + line)
        sys.stdout.flush()
        self._progress_drawn = True

    def _complete_task(self, task) -> None:
        key = self._task_key(task)
        if not key or key in self._completed_task_keys or not self._is_countable_task(task):
            return
        self._completed_task_keys.add(key)
        if key not in self._known_task_keys:
            self._known_task_keys.add(key)
            self._progress_total += 1
        self._progress_completed += 1

    def v2_playbook_on_start(self, playbook):
        self._clear_progress()
        super().v2_playbook_on_start(playbook)
        self._render_progress()

    def v2_playbook_on_play_start(self, play):
        self._current_play_name = play.get_name().strip() or "unnamed-play"
        self._register_play_tasks(play)
        self._clear_progress()
        super().v2_playbook_on_play_start(play)
        self._render_progress()

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._current_task_name = task.get_name().strip() or task.action or "unnamed-task"
        self._register_task(task)
        self._clear_progress()
        super().v2_playbook_on_task_start(task, is_conditional)
        self._render_progress()

    def v2_playbook_on_handler_task_start(self, task):
        self._current_task_name = task.get_name().strip() or task.action or "unnamed-handler"
        self._register_task(task)
        self._clear_progress()
        super().v2_playbook_on_handler_task_start(task)
        self._render_progress()

    def v2_playbook_on_include(self, included_file):
        self._discover_include_tasks(included_file)
        self._clear_progress()
        super().v2_playbook_on_include(included_file)
        self._render_progress()

    def v2_runner_on_ok(self, result):
        self._complete_task(result._task)
        self._clear_progress()
        super().v2_runner_on_ok(result)
        self._render_progress()

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._complete_task(result._task)
        self._clear_progress()
        super().v2_runner_on_failed(result, ignore_errors=ignore_errors)
        self._render_progress()

    def v2_runner_on_skipped(self, result):
        self._complete_task(result._task)
        self._clear_progress()
        super().v2_runner_on_skipped(result)
        self._render_progress()

    def v2_runner_on_unreachable(self, result):
        self._complete_task(result._task)
        self._clear_progress()
        super().v2_runner_on_unreachable(result)
        self._render_progress()

    def v2_playbook_on_stats(self, stats):
        self._progress_completed = max(self._progress_completed, self._progress_total)
        self._render_progress()
        if self._progress_enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._progress_drawn = False
        super().v2_playbook_on_stats(stats)

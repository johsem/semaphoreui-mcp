"""Named tool profiles for everyday operations and complete API access."""

TOOL_PROFILES = ("full", "core")
CORE_TOOLS = frozenset(
  {
    "ping",
    "get_system_info",
    "list_projects",
    "get_project",
    "list_templates",
    "get_template",
    "list_template_tasks",
    "list_recent_template_tasks",
    "list_tasks",
    "list_recent_tasks",
    "get_task",
    "get_task_output",
    "get_task_raw_output",
    "list_task_stages",
    "list_task_ansible_errors",
    "list_task_ansible_hosts",
    "create_task",
    "stop_task",
    "wait_for_task",
    "list_inventories",
    "get_inventory",
    "list_repositories",
    "get_repository",
    "list_repository_playbooks",
    "list_environments",
    "get_environment",
    "list_schedules",
    "get_schedule",
  }
)


def normalize_tool_profile(value: str) -> str:
  if not isinstance(value, str) or value.strip().lower() not in TOOL_PROFILES:
    raise ValueError("SEMAPHORE_TOOL_PROFILE must be full or core")
  return value.strip().lower()


def tool_in_profile(name: str, profile: str) -> bool:
  return profile == "full" or (profile == "core" and name in CORE_TOOLS)

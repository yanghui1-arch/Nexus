from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field

from src.logger import logger
from src.sandbox import Sandbox


AGENT_SKILL_DIRECTORIES = {"tela", "sophie", "jules", "marc", "assistant"}


class ReadSkill(BaseModel):
    """Read the full SKILL.md instructions for an available skill."""

    name: str = Field(description="Exact skill name from the <skills> system prompt catalog")


READ_SKILL = pydantic_function_tool(ReadSkill, name="read_skill")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    directory: str
    content: str


class SkillRegistry:
    def __init__(self, skills: Iterable[Skill] = ()) -> None:
        self._skills_by_name = {skill.name: skill for skill in skills}

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills_by_name.values())

    def __bool__(self) -> bool:
        return bool(self._skills_by_name)

    @classmethod
    def from_paths(cls, paths: Iterable[str]) -> "SkillRegistry":
        skills: dict[str, Skill] = {}
        for raw_path in paths:
            skill_dir = _skill_dir(raw_path)
            if skill_dir is None:
                logger.warning("Skipping skill directory without SKILL.md: %s", raw_path)
                continue

            try:
                content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
                skill = _parse_skill(
                    content,
                    directory=str(skill_dir),
                )
            except ValueError as exc:
                logger.warning("Skipping invalid skill manifest %s: %s", skill_dir / "SKILL.md", exc)
                continue
            except OSError:
                logger.exception("Failed to read skill manifest %s.", skill_dir / "SKILL.md")
                continue

            if skill.name in skills:
                logger.warning("Skipping duplicate skill `%s` from %s.", skill.name, skill.directory)
                continue
            skills[skill.name] = skill

        return cls(skills.values())

    @classmethod
    async def from_sandbox_project(
        cls,
        sandbox: Sandbox,
        *,
        project_path: str,
        agent_name: str,
    ) -> "SkillRegistry":
        """Load project skills from /workspace/<repo>/.nexus/skills."""
        base_path = f"{project_path.rstrip('/')}/.nexus/skills"
        candidate_dirs: list[str] = []

        candidate_dirs.extend(await _sandbox_child_dirs(sandbox, f"{base_path}/{agent_name}"))

        for directory in await _sandbox_child_dirs(sandbox, base_path):
            name = directory.rsplit("/", 1)[-1]
            if name in AGENT_SKILL_DIRECTORIES:
                continue
            candidate_dirs.append(directory)

        skills: dict[str, Skill] = {}
        for directory in candidate_dirs:
            content = await _sandbox_read_skill_manifest(sandbox, directory)
            if content is None:
                continue

            try:
                skill = _parse_skill(content, directory=directory)
            except ValueError as exc:
                logger.warning("Skipping invalid skill manifest %s/SKILL.md: %s", directory, exc)
                continue

            if skill.name in skills:
                logger.warning("Skipping duplicate skill `%s` from %s.", skill.name, directory)
                continue
            skills[skill.name] = skill

        return cls(skills.values())

    def read_skill(self, name: str) -> str:
        skill = self._skills_by_name.get(name)
        if skill is None:
            available_skills = ", ".join(sorted(self._skills_by_name)) or "none"
            return (
                f"Skill `{name}` is not available.\n"
                f"Available skills: {available_skills}"
            )

        return (
            f'<skill_content name="{skill.name}">\n'
            f"{skill.content.strip()}\n"
            "</skill_content>"
        )


class SkillToolKit:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    @track(step_type="tool")
    def read_skill(self, name: str) -> str:
        return self._registry.read_skill(name)

    @property
    def all_tools(self) -> dict[str, Callable]:
        return {"read_skill": self.read_skill}


def build_skills_system_prompt(registry: SkillRegistry) -> str:
    if not registry:
        return ""

    entries = []
    for skill in registry.skills:
        entries.append(
            "\n".join(
                [
                    "  <skill>",
                    f"    <name>{skill.name}</name>",
                    f"    <description>{skill.description}</description>",
                    "  </skill>",
                ]
            )
        )

    return (
        "<skills>\n"
        "The following skills provide specialized instructions for specific tasks.\n"
        "When a task matches a skill's description, call `read_skill` with that skill name before proceeding.\n"
        f"{'\n'.join(entries)}\n"
        "</skills>"
    )


def append_skills_system_prompt(system_prompt: str, registry: SkillRegistry) -> str:
    skills_prompt = build_skills_system_prompt(registry)
    if not skills_prompt:
        return system_prompt
    return f"{system_prompt.rstrip()}\n\n{skills_prompt}\n"


def _skill_dir(raw_path: str) -> Path | None:
    path = Path(raw_path).expanduser()
    if path.is_dir() and (path / "SKILL.md").is_file():
        return path
    return None


def project_path_for_repo(github_repo: str) -> str:
    repo_name = github_repo.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return f"/workspace/{repo_name}"


def _parse_skill(content: str, *, directory: str) -> Skill:
    frontmatter = _read_frontmatter(content)
    fields = _parse_frontmatter(frontmatter)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    if not name:
        raise ValueError("missing required `name` field")
    if not description:
        raise ValueError("missing required `description` field")
    return Skill(name=name, description=description, directory=directory, content=content)


def _read_frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    raise ValueError("SKILL.md frontmatter is not closed")


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        fields[key.strip()] = _unquote(value.strip())
    return fields


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


async def _sandbox_child_dirs(sandbox: Sandbox, path: str) -> list[str]:
    result = await sandbox.list_files(path)
    if not isinstance(result, dict):
        return []
    if not result.get("success"):
        return []
    return [
        f"{path.rstrip('/')}/{entry['name']}"
        for entry in result.get("files", [])
        if entry.get("type") == "directory"
    ]


async def _sandbox_read_skill_manifest(sandbox: Sandbox, directory: str) -> str | None:
    result = await sandbox.read_file(f"{directory.rstrip('/')}/SKILL.md")
    if not isinstance(result, dict):
        return None
    if not result.get("success"):
        return None
    content = result.get("content")
    return content if isinstance(content, str) else None

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sirius.agents.files_agent import FilesAgent
from sirius.agents.knowledge_agent import KnowledgeAgent
from sirius.agents.memory_agent import MemoryAgent
from sirius.agents.notes_agent import NotesAgent
from sirius.agents.orchestrator import Orchestrator
from sirius.agents.research_agent import ResearchAgent
from sirius.agents.study_agent import StudyAgent
from sirius.agents.task_agent import TaskAgent
from sirius.agents.utility_agent import UtilityAgent
from sirius.config import Settings, get_settings
from sirius.db.database import Database
from sirius.files.service import FileService
from sirius.knowledge.service import KnowledgeBase
from sirius.llm.factory import create_provider
from sirius.logging_setup import setup_logging
from sirius.memory.manager import MemoryManager
from sirius.notes.service import NoteService
from sirius.study.service import StudyService
from sirius.tasks import scheduler as sched
from sirius.tasks.service import TaskService


@dataclass
class SiriusApp:
    """Composition root: builds and wires every component once per process."""

    settings: Settings
    db: Database
    memory: MemoryManager
    tasks: TaskService
    notes: NoteService
    study: StudyService
    knowledge: KnowledgeBase
    files: FileService
    orchestrator: Orchestrator


def build_app(settings: Settings | None = None) -> SiriusApp:
    settings = settings or get_settings()
    setup_logging(settings)

    db = Database(settings.database_url)
    db.create_all()

    memory = MemoryManager(settings, db)
    tasks = TaskService(db, schedule_fn=sched.schedule_reminder, cancel_fn=sched.cancel_reminder)
    notes = NoteService(db)
    study = StudyService(db)
    knowledge = KnowledgeBase(settings)
    files = FileService(settings)

    llm = create_provider(settings)
    orchestrator = Orchestrator(settings, db, llm, memory)
    orchestrator.register(MemoryAgent(memory))
    orchestrator.register(TaskAgent(tasks))
    orchestrator.register(NotesAgent(notes))
    orchestrator.register(StudyAgent(study))
    orchestrator.register(KnowledgeAgent(knowledge))
    orchestrator.register(ResearchAgent())
    orchestrator.register(UtilityAgent(files))
    orchestrator.register(FilesAgent(files))

    return SiriusApp(
        settings=settings,
        db=db,
        memory=memory,
        tasks=tasks,
        notes=notes,
        study=study,
        knowledge=knowledge,
        files=files,
        orchestrator=orchestrator,
    )


@lru_cache
def get_app() -> SiriusApp:
    return build_app()

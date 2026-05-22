from __future__ import annotations

import uuid
from typing import Callable

from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field

from src.server.postgres.database import Database
from src.server.postgres.models import ProductProposalStatus
from src.server.postgres.repositories import FeatureItemRepository, FeatureRepository, ProductProposalRepository
from src.tools.nexus import NexusTaskContext


class CreateProductProposal(BaseModel):
    """Create a product proposal for human review."""

    title: str = Field(description="Short proposal title")
    plan_type: str = Field(description="Proposal type, such as feature, fix, patch, or growth")
    summary: str = Field(description="Brief business summary of the proposal")
    answer: str = Field(description="Full proposal details, evidence, risks, and suggested breakdown")
    project: str | None = Field(default=None, description="Optional project name")
    repo: str | None = Field(default=None, description="Optional repository, such as owner/repo")


class CreateFeatureForProductProposal(BaseModel):
    """Create a feature from an approved proposal."""

    proposal_id: uuid.UUID = Field(description="Approved proposal id")
    title: str = Field(description="Feature title")
    description: str = Field(description="Feature description")


class CreateFeatureItem(BaseModel):
    """Create a feature item from a feature."""

    feature_id: uuid.UUID = Field(description="Feature id")
    title: str = Field(description="Feature item title")
    description: str = Field(description="Feature item description")


CREATE_PRODUCT_PROPOSAL = pydantic_function_tool(CreateProductProposal, name="create_proposal")
CREATE_FEATURE_FOR_PRODUCT_PROPOSAL = pydantic_function_tool(
    CreateFeatureForProductProposal,
    name="create_feature_for_product_proposal",
)
CREATE_FEATURE_ITEM = pydantic_function_tool(CreateFeatureItem, name="create_feature_item")
PRODUCT_TOOL_DEFINITIONS = [
    CREATE_PRODUCT_PROPOSAL,
    CREATE_FEATURE_FOR_PRODUCT_PROPOSAL,
    CREATE_FEATURE_ITEM,
]


class ProductTools:
    def __init__(
        self,
        *,
        database: Database,
        context: NexusTaskContext | None = None,
    ) -> None:
        """Initialize the object."""
        self._database = database
        self._context = context

    @property
    def all_tools(self) -> dict[str, Callable]:
        """Return all tools exposed by this toolkit."""
        return {
            "create_proposal": self.create_proposal,
            "create_feature_for_product_proposal": self.create_feature_for_product_proposal,
            "create_feature_item": self.create_feature_item,
        }

    @track(step_type="tool")
    async def create_proposal(
        self,
        *,
        title: str,
        plan_type: str,
        summary: str,
        answer: str,
        project: str | None = None,
        repo: str | None = None,
    ) -> dict:
        """Create a product proposal."""
        proposal_repo = repo
        if not proposal_repo and self._context and self._context.repo:
            proposal_repo = self._context.repo
        proposal_source_task_id = self._context.task_id if self._context else None

        async with self._database.session() as session:
            proposal = await ProductProposalRepository.create(
                session,
                title=title,
                plan_type=plan_type,
                summary=summary,
                answer=answer,
                project=project,
                repo=proposal_repo,
                source_task_id=proposal_source_task_id,
            )

        return {
            "success": True,
            "proposal_id": str(proposal.id),
            "status": proposal.status.value,
            "title": proposal.title,
            "project": proposal.project,
            "repo": proposal.repo,
            "message": "Product proposal was created for human review.",
        }

    @track(step_type="tool")
    async def create_feature_for_product_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
        title: str,
        description: str,
    ) -> dict:
        """Create a feature for a product proposal."""
        async with self._database.session() as session:
            proposal = await ProductProposalRepository.get(session, proposal_id)
            if proposal is None:
                return {"success": False, "message": "Proposal not found."}
            if proposal.status not in {
                ProductProposalStatus.approved,
                ProductProposalStatus.planned,
            }:
                return {
                    "success": False,
                    "message": "Only approved or planned proposals can become features.",
                }

            feature = await FeatureRepository.create(
                session,
                proposal_id=proposal_id,
                title=title,
                description=description,
                project=proposal.project,
            )

        return {
            "success": True,
            "feature_id": str(feature.id),
            "proposal_id": str(feature.proposal_id) if feature.proposal_id else None,
            "status": feature.status.value,
            "title": feature.title,
            "project": feature.project,
            "message": "Feature was created for planning.",
        }

    @track(step_type="tool")
    async def create_feature_item(
        self,
        *,
        feature_id: uuid.UUID,
        title: str,
        description: str,
    ) -> dict:
        """Create a feature item."""
        async with self._database.session() as session:
            feature = await FeatureRepository.get(session, feature_id)
            if feature is None:
                return {"success": False, "message": "Feature not found."}

            item = await FeatureItemRepository.create(
                session,
                feature_id=feature_id,
                title=title,
                description=description,
            )

        return {
            "success": True,
            "feature_item_id": str(item.id),
            "feature_id": str(item.feature_id),
            "order_index": item.order_index,
            "title": item.title,
            "description": item.description,
            "status": item.status.value,
        }

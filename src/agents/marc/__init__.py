"""
temporary don't delete it.
PM Run process
    -> Proposal
    -> Human Approval
    -> Feature
    -> Feature Items
    -> Tasks
    -> Coding Agent Execution

 Marc PM task
    -> Marc 调用 CreateProductProposal 工具
    -> proposal.status = proposed
    -> Human Approval
    -> approved proposal 触发/调用规划流程
    -> CreateFeature + CreateFeatureItems
    -> feature items 后续再生成 coding tasks
"""

from src.agents.marc.agent import Marc

__all__ = ["Marc"]

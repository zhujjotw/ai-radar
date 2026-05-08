from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.models import Evaluation, GraphEdge, GraphNode, Project, Share, Trial


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, project_id: int) -> Project | None:
        return self.session.get(Project, project_id)

    def get_by_repo_full_name(self, repo_full_name: str) -> Project | None:
        statement = select(Project).where(Project.repo_full_name == repo_full_name)
        return self.session.exec(statement).first()

    def list(
        self,
        *,
        pool: str | None = None,
        decision: str | None = None,
        filter_status: str | None = None,
    ) -> list[Project]:
        statement = select(Project)
        if pool:
            statement = statement.where(Project.pool == pool)
        if filter_status:
            statement = statement.where(Project.filter_status == filter_status)
        if decision:
            statement = statement.join(Evaluation).where(Evaluation.decision == decision)
        return list(self.session.exec(statement).all())

    def upsert(self, project: Project) -> Project:
        existing = self.get_by_repo_full_name(project.repo_full_name)
        if existing:
            for field, value in project.model_dump(exclude={"id"}).items():
                setattr(existing, field, value)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        self.session.add(project)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.get_by_repo_full_name(project.repo_full_name)
            if existing is None:
                raise
            return existing
        self.session.refresh(project)
        return project


class EvaluationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, evaluation: Evaluation) -> Evaluation:
        self.session.add(evaluation)
        self.session.commit()
        self.session.refresh(evaluation)
        return evaluation

    def list_by_project(self, project_id: int) -> list[Evaluation]:
        statement = select(Evaluation).where(Evaluation.project_id == project_id)
        return list(self.session.exec(statement).all())


class TrialRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, trial: Trial) -> Trial:
        self.session.add(trial)
        self.session.commit()
        self.session.refresh(trial)
        return trial

    def update_status(self, trial_id: int, status: str, *, blockers: str | None = None) -> Trial:
        trial = self.session.get(Trial, trial_id)
        if trial is None:
            raise ValueError(f"Trial {trial_id} not found")
        trial.status = status
        if blockers is not None:
            trial.blockers = blockers
        self.session.add(trial)
        self.session.commit()
        self.session.refresh(trial)
        return trial


class ShareRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, share: Share) -> Share:
        self.session.add(share)
        self.session.commit()
        self.session.refresh(share)
        return share


class GraphRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_node(self, node: GraphNode) -> GraphNode:
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    def create_edge(self, edge: GraphEdge) -> GraphEdge:
        self.session.add(edge)
        self.session.commit()
        self.session.refresh(edge)
        return edge

    def get_project_node(self, project_id: int) -> GraphNode | None:
        statement = select(GraphNode).where(
            GraphNode.node_type == "Project",
            GraphNode.ref_table == "projects",
            GraphNode.ref_id == project_id,
        )
        return self.session.exec(statement).first()

    def get_one_hop(self, project_id: int) -> tuple[list[GraphNode], list[GraphEdge]]:
        project_node = self.get_project_node(project_id)
        if project_node is None or project_node.id is None:
            return [], []

        edge_statement = select(GraphEdge).where(
            (GraphEdge.source_node_id == project_node.id)
            | (GraphEdge.target_node_id == project_node.id)
        )
        edges = list(self.session.exec(edge_statement).all())
        node_ids = {project_node.id}
        for edge in edges:
            node_ids.add(edge.source_node_id)
            node_ids.add(edge.target_node_id)

        node_statement = select(GraphNode).where(GraphNode.id.in_(node_ids))
        nodes = list(self.session.exec(node_statement).all())
        return nodes, edges

    def find_projects_by_related_node(self, node_type: str, name: str) -> Sequence[Project]:
        target_statement = select(GraphNode).where(
            GraphNode.node_type == node_type,
            GraphNode.name == name,
        )
        target = self.session.exec(target_statement).first()
        if target is None or target.id is None:
            return []

        edge_statement = select(GraphEdge).where(
            (GraphEdge.source_node_id == target.id) | (GraphEdge.target_node_id == target.id)
        )
        edges = list(self.session.exec(edge_statement).all())
        related_node_ids = {
            edge.source_node_id if edge.target_node_id == target.id else edge.target_node_id
            for edge in edges
        }
        if not related_node_ids:
            return []

        node_statement = select(GraphNode).where(
            GraphNode.id.in_(related_node_ids),
            GraphNode.node_type == "Project",
        )
        project_nodes = list(self.session.exec(node_statement).all())
        project_ids = [node.ref_id for node in project_nodes if node.ref_id is not None]
        if not project_ids:
            return []

        project_statement = select(Project).where(Project.id.in_(project_ids))
        return self.session.exec(project_statement).all()


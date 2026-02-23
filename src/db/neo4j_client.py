"""Neo4j connection and graph operations for User–Campaign–Intent."""
from neo4j import GraphDatabase
from src.utils.config import settings


class Neo4jClient:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self._driver.close()

    def ensure_constraints(self):
        with self._driver.session() as session:
            session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE")
            session.run("CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (c:Campaign) REQUIRE c.campaign_id IS UNIQUE")
            session.run("CREATE CONSTRAINT intent_name IF NOT EXISTS FOR (i:Intent) REQUIRE i.name IS UNIQUE")

    def upsert_user_campaign_intent(self, user_id: str, campaign_id: str, intent: str, engagement_count: int = 1):
        with self._driver.session() as session:
            session.run(
                """
                MERGE (u:User {user_id: $user_id})
                MERGE (c:Campaign {campaign_id: $campaign_id})
                MERGE (i:Intent {name: $intent})
                MERGE (u)-[:ENGAGED_WITH {count: $engagement_count}]->(c)
                MERGE (u)-[:HAS_INTENT]->(i)
                MERGE (c)-[:TARGETS]->(i)
                """,
                user_id=user_id,
                campaign_id=campaign_id,
                intent=intent,
                engagement_count=engagement_count,
            )

    def get_campaigns_for_users(self, user_ids: list[str], limit: int = 20) -> list[dict]:
        if not user_ids:
            return []
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (u:User)-[r:ENGAGED_WITH]->(c:Campaign)
                WHERE u.user_id IN $user_ids
                RETURN c.campaign_id AS campaign_id, sum(r.count) AS total_engagement
                ORDER BY total_engagement DESC
                LIMIT $limit
                """,
                user_ids=user_ids,
                limit=limit,
            )
            return [{"campaign_id": r["campaign_id"], "engagement": r["total_engagement"]} for r in result]


def get_neo4j_client() -> Neo4jClient:
    return Neo4jClient()

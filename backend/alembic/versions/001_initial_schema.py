"""Initial schema for paraglide-backend.

Creates all core tables: site_profiles, launches, landings, terrain_features,
weather_snapshots, cloud_observations, historical_flight_tracks, flight_segments,
knowledge_items, expert_interviews, agent_claims, negotiation_sessions,
recommendations, and model_versions.

Revision ID: 001
Revises:
Create Date: 2024-07-15 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # -------------------------------------------------------------------------
    # site_profiles
    # -------------------------------------------------------------------------
    op.create_table(
        "site_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("boundary_geojson", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_profiles_slug", "site_profiles", ["slug"])

    # -------------------------------------------------------------------------
    # launches
    # -------------------------------------------------------------------------
    op.create_table(
        "launches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("point_geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # landings
    # -------------------------------------------------------------------------
    op.create_table(
        "landings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("point_geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # terrain_features
    # -------------------------------------------------------------------------
    op.create_table(
        "terrain_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("feature_type", sa.Enum("ridge", "valley", "bowl", "riverbed", "tree_line", "rotor_zone", "sink_zone", name="terrain_feature_type", create_type=False), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("geom", geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True),
        sa.Column("attributes_json", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_terrain_features_site_id", "terrain_features", ["site_id"])

    # -------------------------------------------------------------------------
    # weather_snapshots
    # -------------------------------------------------------------------------
    op.create_table(
        "weather_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weather_snapshots_site_id_fetched", "weather_snapshots", ["site_id", "fetched_at"])

    # -------------------------------------------------------------------------
    # cloud_observations
    # -------------------------------------------------------------------------
    op.create_table(
        "cloud_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # historical_flight_tracks
    # -------------------------------------------------------------------------
    op.create_table(
        "historical_flight_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("source_format", sa.Enum("igc", "gpx", name="source_format_type", create_type=False), nullable=False),
        sa.Column("filename", sa.String(512), nullable=True),
        sa.Column("pilot_name", sa.String(256), nullable=True),
        sa.Column("flight_date", sa.Date(), nullable=True),
        sa.Column("track_geojson", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flight_tracks_site_id", "historical_flight_tracks", ["site_id"])

    # -------------------------------------------------------------------------
    # flight_segments
    # -------------------------------------------------------------------------
    op.create_table(
        "flight_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("segment_type", sa.Enum("climb", "glide", "sink", "thermal_core", name="segment_type", create_type=False), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_point_geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("end_point_geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("path_geojson", sa.Text(), nullable=True),
        sa.Column("avg_vario_ms", sa.Float(), nullable=True),
        sa.Column("max_altitude_m", sa.Float(), nullable=True),
        sa.Column("attributes_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["track_id"], ["historical_flight_tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flight_segments_track_id", "flight_segments", ["track_id"])
    op.create_index("ix_flight_segments_type", "flight_segments", ["segment_type"])

    # -------------------------------------------------------------------------
    # knowledge_items
    # -------------------------------------------------------------------------
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("sub_region", sa.String(256), nullable=True),
        sa.Column("wind_condition", sa.String(256), nullable=True),
        sa.Column("time_of_day", sa.String(128), nullable=True),
        sa.Column("season", sa.String(64), nullable=True),
        sa.Column("cloud_condition", sa.String(256), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("exception_statement", sa.Text(), nullable=True),
        sa.Column("risk_note", sa.Text(), nullable=True),
        sa.Column("source_expert", sa.String(256), nullable=True),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("provenance_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_items_site_id", "knowledge_items", ["site_id"])

    # -------------------------------------------------------------------------
    # expert_interviews
    # -------------------------------------------------------------------------
    op.create_table(
        "expert_interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("expert_name", sa.String(256), nullable=False),
        sa.Column("interview_date", sa.Date(), nullable=True),
        sa.Column("raw_transcript", sa.Text(), nullable=True),
        sa.Column("structured_json", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # negotiation_sessions
    # -------------------------------------------------------------------------
    op.create_table(
        "negotiation_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("weather_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "complete", "failed", name="session_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("inputs_json", sa.Text(), nullable=True),
        sa.Column("outputs_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["weather_snapshot_id"], ["weather_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_negotiation_sessions_site_id", "negotiation_sessions", ["site_id"])

    # -------------------------------------------------------------------------
    # agent_claims
    # -------------------------------------------------------------------------
    op.create_table(
        "agent_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("assumptions_json", sa.Text(), nullable=True),
        sa.Column("spatial_scope_json", sa.Text(), nullable=True),
        sa.Column("temporal_validity_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["negotiation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_claims_session_id", "agent_claims", ["session_id"])

    # -------------------------------------------------------------------------
    # recommendations
    # -------------------------------------------------------------------------
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("rec_type", sa.Enum("launch_window", "trigger_zone", "ridge_corridor", "caution_zone", name="rec_type", create_type=False), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("uncertainty_note", sa.Text(), nullable=True),
        sa.Column("evidence_summary_json", sa.Text(), nullable=True),
        sa.Column("spatial_ref_json", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["negotiation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_session_id", "recommendations", ["session_id"])

    # -------------------------------------------------------------------------
    # model_versions
    # -------------------------------------------------------------------------
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_type", sa.String(128), nullable=False),
        sa.Column("version_tag", sa.String(64), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("artifact_path", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["site_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("recommendations")
    op.drop_table("agent_claims")
    op.drop_table("negotiation_sessions")
    op.drop_table("expert_interviews")
    op.drop_table("knowledge_items")
    op.drop_table("flight_segments")
    op.drop_table("historical_flight_tracks")
    op.drop_table("cloud_observations")
    op.drop_table("weather_snapshots")
    op.drop_table("terrain_features")
    op.drop_table("landings")
    op.drop_table("launches")
    op.drop_table("site_profiles")

    # Drop enums
    for enum_name in ["terrain_feature_type", "source_format_type", "segment_type", "session_status", "rec_type"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

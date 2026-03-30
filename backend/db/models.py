"""
SQLAlchemy ORM models for paraglide-backend.

All models use the DeclarativeBase with async support. Geometry columns use
GeoAlchemy2 for PostGIS integration. All tables include full relationships
and type annotations.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

TerrainFeatureType = Enum(
    "ridge", "valley", "bowl", "riverbed", "tree_line", "rotor_zone", "sink_zone",
    name="terrain_feature_type",
)

SourceFormatType = Enum("igc", "gpx", name="source_format_type")

SegmentType = Enum("climb", "glide", "sink", "thermal_core", name="segment_type")

SessionStatus = Enum("pending", "running", "complete", "failed", name="session_status")

RecType = Enum(
    "launch_window", "trigger_zone", "ridge_corridor", "caution_zone",
    name="rec_type",
)


# ---------------------------------------------------------------------------
# SiteProfile
# ---------------------------------------------------------------------------

class SiteProfile(Base):
    __tablename__ = "site_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    boundary_geojson: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    launches: Mapped[list["Launch"]] = relationship("Launch", back_populates="site", cascade="all, delete-orphan")
    landings: Mapped[list["Landing"]] = relationship("Landing", back_populates="site", cascade="all, delete-orphan")
    terrain_features: Mapped[list["TerrainFeature"]] = relationship("TerrainFeature", back_populates="site", cascade="all, delete-orphan")
    weather_snapshots: Mapped[list["WeatherSnapshot"]] = relationship("WeatherSnapshot", back_populates="site", cascade="all, delete-orphan")
    cloud_observations: Mapped[list["CloudObservation"]] = relationship("CloudObservation", back_populates="site", cascade="all, delete-orphan")
    flight_tracks: Mapped[list["HistoricalFlightTrack"]] = relationship("HistoricalFlightTrack", back_populates="site", cascade="all, delete-orphan")
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship("KnowledgeItem", back_populates="site", cascade="all, delete-orphan")
    expert_interviews: Mapped[list["ExpertInterview"]] = relationship("ExpertInterview", back_populates="site", cascade="all, delete-orphan")
    negotiation_sessions: Mapped[list["NegotiationSession"]] = relationship("NegotiationSession", back_populates="site", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SiteProfile id={self.id} slug={self.slug!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

class Launch(Base):
    __tablename__ = "launches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    point_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="launches")

    def __repr__(self) -> str:
        return f"<Launch id={self.id} name={self.name!r} elevation={self.elevation_m}m>"


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

class Landing(Base):
    __tablename__ = "landings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    point_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="landings")

    def __repr__(self) -> str:
        return f"<Landing id={self.id} name={self.name!r} elevation={self.elevation_m}m>"


# ---------------------------------------------------------------------------
# TerrainFeature
# ---------------------------------------------------------------------------

class TerrainFeature(Base):
    __tablename__ = "terrain_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_type: Mapped[str] = mapped_column(TerrainFeatureType, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    geom = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    attributes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="terrain_features")

    def __repr__(self) -> str:
        return f"<TerrainFeature id={self.id} type={self.feature_type!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# WeatherSnapshot
# ---------------------------------------------------------------------------

class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="weather_snapshots")
    negotiation_sessions: Mapped[list["NegotiationSession"]] = relationship(
        "NegotiationSession", back_populates="weather_snapshot"
    )

    def __repr__(self) -> str:
        return f"<WeatherSnapshot id={self.id} provider={self.provider!r} fetched={self.fetched_at}>"


# ---------------------------------------------------------------------------
# CloudObservation
# ---------------------------------------------------------------------------

class CloudObservation(Base):
    __tablename__ = "cloud_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_json: Mapped[str] = mapped_column(Text, nullable=False)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="cloud_observations")

    def __repr__(self) -> str:
        return f"<CloudObservation id={self.id} provider={self.provider!r} at={self.observed_at}>"


# ---------------------------------------------------------------------------
# HistoricalFlightTrack
# ---------------------------------------------------------------------------

class HistoricalFlightTrack(Base):
    __tablename__ = "historical_flight_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    source_format: Mapped[str] = mapped_column(SourceFormatType, nullable=False)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pilot_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    flight_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    track_geojson: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="flight_tracks")
    segments: Mapped[list["FlightSegment"]] = relationship("FlightSegment", back_populates="track", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<HistoricalFlightTrack id={self.id} pilot={self.pilot_name!r} date={self.flight_date}>"


# ---------------------------------------------------------------------------
# FlightSegment
# ---------------------------------------------------------------------------

class FlightSegment(Base):
    __tablename__ = "flight_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(Integer, ForeignKey("historical_flight_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_type: Mapped[str] = mapped_column(SegmentType, nullable=False, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_point_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    end_point_geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    path_geojson: Mapped[str | None] = mapped_column(Text, nullable=True)
    avg_vario_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    attributes_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    track: Mapped["HistoricalFlightTrack"] = relationship("HistoricalFlightTrack", back_populates="segments")

    def __repr__(self) -> str:
        return f"<FlightSegment id={self.id} type={self.segment_type!r} vario={self.avg_vario_ms}m/s>"


# ---------------------------------------------------------------------------
# KnowledgeItem
# ---------------------------------------------------------------------------

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_region: Mapped[str | None] = mapped_column(String(256), nullable=True)
    wind_condition: Mapped[str | None] = mapped_column(String(256), nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(128), nullable=True)
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cloud_condition: Mapped[str | None] = mapped_column(String(256), nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    exception_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_expert: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="knowledge_items")

    def __repr__(self) -> str:
        return f"<KnowledgeItem id={self.id} region={self.sub_region!r} confidence={self.confidence}>"


# ---------------------------------------------------------------------------
# ExpertInterview
# ---------------------------------------------------------------------------

class ExpertInterview(Base):
    __tablename__ = "expert_interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    expert_name: Mapped[str] = mapped_column(String(256), nullable=False)
    interview_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="expert_interviews")

    def __repr__(self) -> str:
        return f"<ExpertInterview id={self.id} expert={self.expert_name!r} date={self.interview_date}>"


# ---------------------------------------------------------------------------
# NegotiationSession
# ---------------------------------------------------------------------------

class NegotiationSession(Base):
    __tablename__ = "negotiation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    weather_snapshot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("weather_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(SessionStatus, nullable=False, default="pending")
    inputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    outputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["SiteProfile"] = relationship("SiteProfile", back_populates="negotiation_sessions")
    weather_snapshot: Mapped["WeatherSnapshot | None"] = relationship(
        "WeatherSnapshot", back_populates="negotiation_sessions"
    )
    agent_claims: Mapped[list["AgentClaim"]] = relationship("AgentClaim", back_populates="session", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NegotiationSession id={self.id} status={self.status!r} at={self.requested_at}>"


# ---------------------------------------------------------------------------
# AgentClaim
# ---------------------------------------------------------------------------

class AgentClaim(Base):
    __tablename__ = "agent_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("negotiation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    assumptions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    spatial_scope_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_validity_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["NegotiationSession"] = relationship("NegotiationSession", back_populates="agent_claims")

    def __repr__(self) -> str:
        return f"<AgentClaim id={self.id} agent={self.agent_name!r} type={self.claim_type!r} confidence={self.confidence}>"


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("negotiation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    rec_type: Mapped[str] = mapped_column(RecType, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    spatial_ref_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["NegotiationSession"] = relationship("NegotiationSession", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<Recommendation id={self.id} rank={self.rank} type={self.rec_type!r} confidence={self.confidence}>"


# ---------------------------------------------------------------------------
# ModelVersion
# ---------------------------------------------------------------------------

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    site_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("site_profiles.id", ondelete="SET NULL"), nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return f"<ModelVersion id={self.id} type={self.model_type!r} version={self.version_tag!r}>"

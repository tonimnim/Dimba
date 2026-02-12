from app.schemas.region import RegionSchema
from app.schemas.county import CountySchema
from app.schemas.season import SeasonSchema, CreateSeasonSchema, UpdateSeasonSchema
from app.schemas.competition import (
    CompetitionSchema,
    CreateCompetitionSchema,
    UpdateCompetitionSchema,
)
from app.schemas.team import TeamSchema, CreateTeamSchema, UpdateTeamSchema
from app.schemas.player import PlayerSchema, CreatePlayerSchema, UpdatePlayerSchema
from app.schemas.user import UserSchema, RegisterSchema
from app.schemas.match import (
    MatchSchema,
    CreateMatchSchema,
    SubmitResultSchema,
    GenerateFixturesSchema,
    GenerateCupDrawSchema,
    GenerateKnockoutSchema,
)
from app.schemas.standing import StandingSchema
from app.schemas.transfer import TransferSchema, CreateTransferSchema

__all__ = [
    "RegionSchema",
    "CountySchema",
    "SeasonSchema",
    "CreateSeasonSchema",
    "UpdateSeasonSchema",
    "CompetitionSchema",
    "CreateCompetitionSchema",
    "UpdateCompetitionSchema",
    "TeamSchema",
    "CreateTeamSchema",
    "UpdateTeamSchema",
    "PlayerSchema",
    "CreatePlayerSchema",
    "UpdatePlayerSchema",
    "UserSchema",
    "RegisterSchema",
    "MatchSchema",
    "CreateMatchSchema",
    "SubmitResultSchema",
    "GenerateFixturesSchema",
    "GenerateCupDrawSchema",
    "GenerateKnockoutSchema",
    "StandingSchema",
    "TransferSchema",
    "CreateTransferSchema",
]

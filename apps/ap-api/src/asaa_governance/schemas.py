from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MasterDataDomainCreate(StrictModel):
    domain_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    authoritative_source: str = Field(min_length=2, max_length=160)
    owner_subject: str = Field(min_length=1, max_length=128)
    steward_subject: str = Field(min_length=1, max_length=128)


class MasterDataDomainUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    authoritative_source: str | None = Field(default=None, min_length=2, max_length=160)
    owner_subject: str | None = Field(default=None, min_length=1, max_length=128)
    steward_subject: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def reject_null_required_updates(self):
        for field in ("name", "authoritative_source", "owner_subject", "steward_subject"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class MasterDataRecordCreate(StrictModel):
    record_type: str = Field(min_length=2, max_length=80)
    record_id: str = Field(min_length=1, max_length=128)
    source_system: str = Field(min_length=2, max_length=120)
    source_record_id: str = Field(min_length=1, max_length=160)
    # HMAC-SHA256 or equivalent keyed fingerprint; never submit raw personal/business identifiers.
    match_key_fingerprint: str | None = Field(default=None, min_length=32, max_length=128,
                                              pattern=r"^[a-fA-F0-9]+$")


class MasterDataSupersede(StrictModel):
    canonical_record_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=1000)

from typing import Any, Literal

from pydantic import BaseModel, Field


class SellerAsset(BaseModel):
    listing_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class OrderHandoff(BaseModel):
    order_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    asset: SellerAsset
    state: Literal["ready_for_pickup", "handed_off"]


class PublishedUpdate(BaseModel):
    audience: Literal["seller", "buyer"]
    channel: str
    event: str


class HandoffResult(BaseModel):
    order_id: str
    state: Literal["ready_for_pickup", "handed_off"]
    updates: list[PublishedUpdate]


class ClientTokenRequest(BaseModel):
    client_id: str = Field(min_length=1)
    channels: list[str] = Field(min_length=1)


class ClientToken(BaseModel):
    data: dict[str, Any]


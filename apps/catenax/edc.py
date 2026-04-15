"""Catena-X style EDC connector helpers with AAS integration for cobot data.

This module provides a practical starting point for a manufacturing data space
integration:

- Registers assets and policies to an EDC management API
- Negotiates simple contract offers for data sharing
- Normalizes collaborative robot telemetry
- Maps telemetry into an AAS submodel payload
- Pushes the payload to an AAS-compatible HTTP endpoint

The implementation is intentionally lightweight so it can run on edge devices
such as Raspberry Pi while still being easy to adapt to a real Catena-X setup.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional
from urllib import error, request


LOGGER = logging.getLogger("catenax.edc")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class HttpJsonClient:
    """Small JSON-over-HTTP client based on the standard library."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def request_json(
        self,
        method: str,
        url: str,
        payload: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        body = None
        final_headers = {"Content-Type": "application/json"}
        if headers:
            final_headers.update(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(url, data=body, headers=final_headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8").strip()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {exc.code} calling {url}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc

        if not raw:
            return {}
        return json.loads(raw)


@dataclass(slots=True)
class EDCAsset:
    """Asset definition exposed through the connector."""

    asset_id: str
    name: str
    base_url: str
    data_path: str
    description: str
    content_type: str = "application/json"
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_management_payload(self) -> Dict[str, Any]:
        return {
            "asset": {
                "properties": {
                    "asset:prop:id": self.asset_id,
                    "asset:prop:name": self.name,
                    "asset:prop:contenttype": self.content_type,
                    "asset:prop:description": self.description,
                    **self.properties,
                }
            },
            "dataAddress": {
                "type": "HttpData",
                "baseUrl": self.base_url.rstrip("/"),
                "path": self.data_path,
                "proxyMethod": "true",
                "proxyPath": "true",
                "proxyQueryParams": "true",
                "proxyBody": "true",
            },
        }


@dataclass(slots=True)
class EDCPolicy:
    """Simplified access policy for a data offering."""

    policy_id: str
    assignee: str
    target: str
    action: str = "USE"
    left_operand: str = "BusinessPartnerNumber"
    operator: str = "EQ"

    def to_management_payload(self) -> Dict[str, Any]:
        return {
            "@context": {
                "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
                "odrl": "http://www.w3.org/ns/odrl/2/",
            },
            "@id": self.policy_id,
            "@type": "PolicyDefinition",
            "policy": {
                "@context": "http://www.w3.org/ns/odrl.jsonld",
                "@type": "Set",
                "permission": [
                    {
                        "action": self.action,
                        "constraint": {
                            "leftOperand": self.left_operand,
                            "operator": self.operator,
                            "rightOperand": self.assignee,
                        },
                        "target": self.target,
                    }
                ],
            },
        }


@dataclass(slots=True)
class ContractDefinition:
    """Relationship between an asset selector and access policies."""

    contract_definition_id: str
    access_policy_id: str
    contract_policy_id: str
    asset_id: str

    def to_management_payload(self) -> Dict[str, Any]:
        return {
            "@id": self.contract_definition_id,
            "@type": "ContractDefinition",
            "accessPolicyId": self.access_policy_id,
            "contractPolicyId": self.contract_policy_id,
            "assetsSelector": [
                {
                    "@type": "Criterion",
                    "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                    "operator": "=",
                    "operandRight": self.asset_id,
                }
            ],
        }


@dataclass(slots=True)
class FactoryCobotTelemetry:
    """Normalized collaborative robot telemetry."""

    robot_id: str
    line_id: str
    station_id: str
    cycle_time_ms: float
    power_watts: float
    program_name: str
    status: str
    good_parts: int
    reject_parts: int
    temperature_c: Optional[float] = None
    vibration_mm_s: Optional[float] = None
    pose: Dict[str, float] = field(default_factory=dict)
    joint_positions_deg: Dict[str, float] = field(default_factory=dict)
    alarms: list[str] = field(default_factory=list)
    produced_at: str = field(default_factory=_utc_now)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FactoryCobotTelemetry":
        return cls(
            robot_id=str(raw["robot_id"]),
            line_id=str(raw["line_id"]),
            station_id=str(raw["station_id"]),
            cycle_time_ms=float(raw["cycle_time_ms"]),
            power_watts=float(raw["power_watts"]),
            program_name=str(raw["program_name"]),
            status=str(raw["status"]),
            good_parts=int(raw.get("good_parts", 0)),
            reject_parts=int(raw.get("reject_parts", 0)),
            temperature_c=(
                float(raw["temperature_c"]) if raw.get("temperature_c") is not None else None
            ),
            vibration_mm_s=(
                float(raw["vibration_mm_s"]) if raw.get("vibration_mm_s") is not None else None
            ),
            pose={str(k): float(v) for k, v in raw.get("pose", {}).items()},
            joint_positions_deg={
                str(k): float(v) for k, v in raw.get("joint_positions_deg", {}).items()
            },
            alarms=[str(item) for item in raw.get("alarms", [])],
            produced_at=str(raw.get("produced_at", _utc_now())),
        )


class AASBridge:
    """Maps cobot telemetry to an AAS submodel payload and uploads it."""

    def __init__(
        self,
        aas_base_url: str,
        submodel_id: str,
        client: Optional[HttpJsonClient] = None,
        auth_key: Optional[str] = None,
    ):
        self.aas_base_url = aas_base_url.rstrip("/")
        self.submodel_id = submodel_id
        self.client = client or HttpJsonClient()
        self.auth_key = auth_key

    def telemetry_to_submodel(self, telemetry: FactoryCobotTelemetry) -> Dict[str, Any]:
        flattened: MutableMapping[str, Any] = {
            "robotId": telemetry.robot_id,
            "lineId": telemetry.line_id,
            "stationId": telemetry.station_id,
            "cycleTimeMs": telemetry.cycle_time_ms,
            "powerWatts": telemetry.power_watts,
            "programName": telemetry.program_name,
            "status": telemetry.status,
            "goodParts": telemetry.good_parts,
            "rejectParts": telemetry.reject_parts,
            "temperatureC": telemetry.temperature_c,
            "vibrationMmPerSec": telemetry.vibration_mm_s,
            "alarms": telemetry.alarms,
            "producedAt": telemetry.produced_at,
        }

        for axis, value in telemetry.pose.items():
            flattened[f"pose_{axis}"] = value
        for joint, value in telemetry.joint_positions_deg.items():
            flattened[f"joint_{joint}_deg"] = value

        return {
            "idShort": "CobotOperationalData",
            "modelType": "Submodel",
            "id": self.submodel_id,
            "submodelElements": [
                {
                    "modelType": "Property",
                    "idShort": key,
                    "valueType": self._value_type(value),
                    "value": value,
                }
                for key, value in flattened.items()
                if value is not None
            ],
        }

    def upsert_telemetry(self, telemetry: FactoryCobotTelemetry) -> Dict[str, Any]:
        payload = self.telemetry_to_submodel(telemetry)
        headers = {}
        if self.auth_key:
            headers["X-Api-Key"] = self.auth_key
        url = f"{self.aas_base_url}/submodels/{self.submodel_id}/$value"
        LOGGER.info("Updating AAS submodel for robot_id=%s", telemetry.robot_id)
        return self.client.request_json("PUT", url, payload=payload, headers=headers)

    @staticmethod
    def _value_type(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "double"
        if isinstance(value, list):
            return "string"
        return "string"


class EDCConnectorService:
    """Thin wrapper around commonly used EDC management APIs."""

    def __init__(
        self,
        management_url: str,
        client: Optional[HttpJsonClient] = None,
        api_key: Optional[str] = None,
    ):
        self.management_url = management_url.rstrip("/")
        self.client = client or HttpJsonClient()
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    def register_asset(self, asset: EDCAsset) -> Dict[str, Any]:
        url = f"{self.management_url}/v3/assets"
        return self.client.request_json(
            "POST",
            url,
            payload=asset.to_management_payload(),
            headers=self._headers(),
        )

    def create_policy(self, policy: EDCPolicy) -> Dict[str, Any]:
        url = f"{self.management_url}/v3/policydefinitions"
        return self.client.request_json(
            "POST",
            url,
            payload=policy.to_management_payload(),
            headers=self._headers(),
        )

    def create_contract_definition(
        self, definition: ContractDefinition
    ) -> Dict[str, Any]:
        url = f"{self.management_url}/v3/contractdefinitions"
        return self.client.request_json(
            "POST",
            url,
            payload=definition.to_management_payload(),
            headers=self._headers(),
        )

    def request_catalog(
        self,
        counter_party_protocol_url: str,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "counterPartyAddress": counter_party_protocol_url,
            "protocol": "dataspace-protocol-http",
        }
        if asset_id:
            payload["querySpec"] = {
                "filterExpression": [
                    {
                        "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                        "operator": "=",
                        "operandRight": asset_id,
                    }
                ]
            }

        url = f"{self.management_url}/v3/catalog/request"
        return self.client.request_json("POST", url, payload=payload, headers=self._headers())

    def negotiate_contract(
        self,
        counter_party_protocol_url: str,
        asset_id: str,
        offer_id: str,
        provider_participant_id: str,
        consumer_participant_id: str,
    ) -> Dict[str, Any]:
        payload = {
            "@type": "ContractRequest",
            "counterPartyAddress": counter_party_protocol_url,
            "protocol": "dataspace-protocol-http",
            "providerId": provider_participant_id,
            "connectorId": consumer_participant_id,
            "offer": {
                "@id": offer_id,
                "assetId": asset_id,
                "providerId": provider_participant_id,
            },
        }
        url = f"{self.management_url}/v3/contractnegotiations"
        return self.client.request_json("POST", url, payload=payload, headers=self._headers())


class CobotEDCPipeline:
    """High-level orchestration for EDC registration and AAS synchronization."""

    def __init__(self, connector: EDCConnectorService, aas_bridge: AASBridge):
        self.connector = connector
        self.aas_bridge = aas_bridge

    def onboard_cobot_asset(
        self,
        asset_id: str,
        provider_bpn: str,
        cobot_api_base_url: str,
        cobot_data_path: str = "/api/v1/cobot/telemetry",
    ) -> Dict[str, Dict[str, Any]]:
        asset = EDCAsset(
            asset_id=asset_id,
            name=f"Cobot telemetry {asset_id}",
            base_url=cobot_api_base_url,
            data_path=cobot_data_path,
            description="Operational telemetry stream from a collaborative robot",
            properties={
                "catenax:providerBpn": provider_bpn,
                "catenax:assetType": "factory-cobot-telemetry",
                "catenax:semanticId": self.aas_bridge.submodel_id,
            },
        )
        access_policy = EDCPolicy(
            policy_id=f"{asset_id}-access-policy",
            assignee=provider_bpn,
            target=asset_id,
        )
        contract_policy = EDCPolicy(
            policy_id=f"{asset_id}-contract-policy",
            assignee=provider_bpn,
            target=asset_id,
        )
        contract = ContractDefinition(
            contract_definition_id=f"{asset_id}-contract",
            access_policy_id=access_policy.policy_id,
            contract_policy_id=contract_policy.policy_id,
            asset_id=asset_id,
        )

        LOGGER.info("Onboarding EDC asset asset_id=%s provider_bpn=%s", asset_id, provider_bpn)

        return {
            "asset": self.connector.register_asset(asset),
            "access_policy": self.connector.create_policy(access_policy),
            "contract_policy": self.connector.create_policy(contract_policy),
            "contract_definition": self.connector.create_contract_definition(contract),
        }

    def publish_telemetry_to_aas(
        self, telemetry: Mapping[str, Any] | FactoryCobotTelemetry
    ) -> Dict[str, Any]:
        if not isinstance(telemetry, FactoryCobotTelemetry):
            telemetry = FactoryCobotTelemetry.from_dict(telemetry)
        return self.aas_bridge.upsert_telemetry(telemetry)


def build_pipeline_from_env() -> CobotEDCPipeline:
    management_url = os.environ["CATENAX_EDC_MANAGEMENT_URL"]
    aas_base_url = os.environ["CATENAX_AAS_BASE_URL"]
    submodel_id = os.environ["CATENAX_AAS_SUBMODEL_ID"]
    edc_api_key = os.environ.get("CATENAX_EDC_API_KEY")
    aas_api_key = os.environ.get("CATENAX_AAS_API_KEY")

    connector = EDCConnectorService(management_url=management_url, api_key=edc_api_key)
    aas_bridge = AASBridge(
        aas_base_url=aas_base_url,
        submodel_id=submodel_id,
        auth_key=aas_api_key,
    )
    return CobotEDCPipeline(connector=connector, aas_bridge=aas_bridge)


def _load_telemetry(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Catena-X EDC connector helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    onboard = subparsers.add_parser("onboard", help="register cobot asset in EDC")
    onboard.add_argument("--asset-id", required=True)
    onboard.add_argument("--provider-bpn", required=True)
    onboard.add_argument("--cobot-api-base-url", required=True)
    onboard.add_argument(
        "--cobot-data-path",
        default="/api/v1/cobot/telemetry",
        help="relative path used by the EDC HttpData address",
    )

    sync = subparsers.add_parser("sync-aas", help="push a telemetry JSON file to AAS")
    sync.add_argument("--telemetry-json", required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    pipeline = build_pipeline_from_env()

    if args.command == "onboard":
        result = pipeline.onboard_cobot_asset(
            asset_id=args.asset_id,
            provider_bpn=args.provider_bpn,
            cobot_api_base_url=args.cobot_api_base_url,
            cobot_data_path=args.cobot_data_path,
        )
    else:
        telemetry = _load_telemetry(args.telemetry_json)
        result = pipeline.publish_telemetry_to_aas(telemetry)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

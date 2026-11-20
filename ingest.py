import os
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from typing import Any

import requests
from azure.core import exceptions
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

from lib import dairy_net
from lib.azure import authenticate_by_access_key

load_dotenv()

# Parameters passed to each endpoint function in lib/dairy_net.py
ENDPOINT_PARAMETERS: dict[str, dict[str, Any]] = {
    "daily_milk_simple_list": {
        "from_date": "2026-01-01T21:23",
        "to_date": "2026-11-17T21:23",
    },
    "cow_monitor": {
        "page_index": 1,
        "page_size": 30000,
    },
    "process_report": {
        "milking_parlors": "775502b4-40cf-48d3-bf59-1e464a0a45c1#1#2#3",
        "report_date_from": "2026-01-01",
        "report_date_until": "2026-11-18",
        "sort_column": "reportDate",
        "sort_descending": True,
    },
    "conspicuous_conductivity_alarms": {
        "number_alarms": 1,
        "number_visits": 5,
        "date_of_alarm": 3,
    },
    "cattle_view": {
        "cattle_id": "5288cd84-46af-496e-8cdf-ae198ede22fe",
        "selected_tab": "coreData",
    },
    "cattle_by_id": {
        "cattle_id": "5288cd84-46af-496e-8cdf-ae198ede22fe",
    },
    "herd_info": {
        "preset_id": "ac13dd8b-ca1f-43ee-8dbe-4668a66dbcd2",
        "herd_selection": {
            "name": "Ganze Herde",
            "groupType": "WholeHerd",
            "groupUsage": None,
            "animalChoiceColumnPreset": None,
            "animalChoicePresetDefinitionId": None,
            "id": None,
        },
    },
    "cow_milk_visits": {
        "initial_page_size": 100,
    },
}

# Mapping of folder/endpoint names to their fetch functions in lib/dairy_net.py
ENDPOINT_FUNCTIONS: dict[str, Callable[..., requests.Response]] = {
    "daily_milk_simple_list": dairy_net.fetch_daily_milk_simple_list,
    "cow_monitor": dairy_net.fetch_cow_monitor,
    "process_report": dairy_net.fetch_process_report,
    "conspicuous_conductivity_alarms": dairy_net.fetch_conspicuous_conductivity_alarms,
    "cattle_view": dairy_net.fetch_cattle_view,
    "cattle_by_id": dairy_net.fetch_cattle_by_id,
    "herd_info": dairy_net.fetch_herd_info,
    "cow_milk_visits": dairy_net.fetch_milk_visits_for_single_cattle,
}


CATTLE_ID_NOT_APPLICABLE = "cattleIdNotApplicable"
START_DATE_NOT_APPLICABLE = "startDateNotApplicable"
END_DATE_NOT_APPLICABLE = "endDateNotApplicable"


def _to_camel_case(snake_str: str) -> str:
    """Convert a snake_case string to camelCase (so endpointName contains no underscores)."""
    parts = snake_str.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def build_blob_filename(
    endpoint_name: str,
    cattle_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    upload_date: str | None = None,
) -> str:
    """Build filename following uploadDate_endpointName_cattleId_startDate_endDate.json."""
    upload_date_str = upload_date or datetime.now().strftime("%Y-%m-%d")
    endpoint_part = _to_camel_case(endpoint_name)
    cattle_part = cattle_id if cattle_id else CATTLE_ID_NOT_APPLICABLE
    start_part = start_date.split("T", 1)[0] if start_date else START_DATE_NOT_APPLICABLE
    end_part = end_date.split("T", 1)[0] if end_date else END_DATE_NOT_APPLICABLE
    return f"{upload_date_str}_{endpoint_part}_{cattle_part}_{start_part}_{end_part}.json"


def _iter_daily_milk_timestamps(
    from_date: str,
    to_date: str,
    default_time: str = "21:23",
) -> Iterator[tuple[str, str]]:
    """Yield (YYYY-MM-DD, YYYY-MM-DDTHH:MM) for every day in [from_date, to_date] inclusive."""
    from_parts = from_date.split("T", 1)
    to_parts = to_date.split("T", 1)

    start_day = date.fromisoformat(from_parts[0])
    end_day = date.fromisoformat(to_parts[0])
    if start_day > end_day:
        raise ValueError(f"from_date ({from_date}) must not be after to_date ({to_date})")

    time_part = (
        from_parts[1]
        if len(from_parts) > 1
        else (to_parts[1] if len(to_parts) > 1 else default_time)
    )

    current_day = start_day
    while current_day <= end_day:
        day_str = current_day.isoformat()
        yield day_str, f"{day_str}T{time_part}"
        current_day += timedelta(days=1)


def _extract_cattle_ids_from_herd_info(response: requests.Response) -> list[str]:
    """Extract all cattle IDs from a herd_info JSON response."""
    data = response.json()
    items: list[Any] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("content", "elements", "data", "items"):
            if isinstance(data.get(key), list):
                items = data[key]
                break

    cattle_ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            raw_id = item.get("CATTLE_ID") or item.get("cattleId") or item.get("id")
            if raw_id:
                cattle_id = str(raw_id)
                if cattle_id not in seen:
                    seen.add(cattle_id)
                    cattle_ids.append(cattle_id)
    return cattle_ids


def _extract_response_list_length(response: requests.Response) -> int:
    """Return the number of items in a JSON list or paginated JSON object response."""
    data = response.json()
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("content", "elements", "data", "items", "milkVisits"):
            if isinstance(data.get(key), list):
                return len(data[key])
        if isinstance(data.get("numberOfElements"), int):
            return data["numberOfElements"]
        for value in data.values():
            if isinstance(value, list):
                return len(value)
    return 0


def fetch_all_milk_visits_for_cattle(
    session: requests.Session,
    cattle_id: str,
    initial_page_size: int = 100,
    fetch_fn: Callable[..., requests.Response] = dairy_net.fetch_milk_visits_for_single_cattle,
    **extra_kwargs: Any,
) -> requests.Response:
    """Fetch all milk visits for a single cattle ID by keeping page_index=1 and doubling page_size until the response list size stops growing."""
    page_size = max(1, initial_page_size)
    prev_count: int | None = None
    best_response: requests.Response | None = None

    while True:
        response = fetch_fn(
            session=session,
            cattle_id=cattle_id,
            page_index=1,
            page_size=page_size,
            **extra_kwargs,
        )
        current_count = _extract_response_list_length(response)
        if prev_count is not None and current_count <= prev_count:
            return best_response if (best_response is not None and current_count < prev_count) else response

        best_response = response
        prev_count = current_count
        page_size *= 2


def upload_endpoint_response_to_folder(
    blob_service_client: BlobServiceClient,
    container_name: str,
    folder_name: str,
    response: requests.Response,
    cattle_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filename: str | None = None,
) -> str:
    """Upload an endpoint response into its own folder inside the Azure Blob container."""
    resolved_filename = filename or build_blob_filename(
        endpoint_name=folder_name,
        cattle_id=cattle_id,
        start_date=start_date,
        end_date=end_date,
    )
    blob_path = f"{folder_name}/{resolved_filename}"

    blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob=blob_path,
    )
    blob_client.upload_blob(
        response.content,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    return blob_path


def ingest_all_endpoints(
    parameters: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Fetch all DairyNet endpoints and upload each response to its own Azure Blob folder."""
    print("Starting DairyNet ingestion...", flush=True)
    container_name = os.environ["container_name"]
    account_name = os.environ["account_name"]
    key = os.environ["key"]

    service_client = authenticate_by_access_key(account_name, key)
    try:
        service_client.create_container(container_name)
        print(f"Created Azure Blob container: {container_name}", flush=True)
    except exceptions.ResourceExistsError:
        print(f"Using existing Azure Blob container: {container_name}", flush=True)

    print("Authenticating with DairyNet...", flush=True)
    session = dairy_net.authenticate_dairynet_session()
    print("Authenticated with DairyNet successfully.", flush=True)
    endpoint_params = parameters if parameters is not None else ENDPOINT_PARAMETERS

    uploaded_blobs: list[str] = []
    herd_cattle_ids: list[str] | None = None

    for folder_name, fetch_fn in ENDPOINT_FUNCTIONS.items():
        params = endpoint_params.get(folder_name, {})

        if folder_name == "daily_milk_simple_list" and "from_date" in params and "to_date" in params:
            extra_kwargs = {
                k: v for k, v in params.items() if k not in {"from_date", "to_date"}
            }
            for day_str, day_timestamp in _iter_daily_milk_timestamps(
                params["from_date"], params["to_date"]
            ):
                print(
                    f"Fetching '{folder_name}' for {day_timestamp}...",
                    flush=True,
                )
                try:
                    response = fetch_fn(
                        session=session,
                        timestamp=day_timestamp,
                        **extra_kwargs,
                    )
                    blob_path = upload_endpoint_response_to_folder(
                        blob_service_client=service_client,
                        container_name=container_name,
                        folder_name=folder_name,
                        response=response,
                        cattle_id=params.get("cattle_id"),
                        start_date=day_str,
                        end_date=day_str,
                    )
                    print(
                        f"Uploaded '{folder_name}' ({day_str}) -> {container_name}/{blob_path}",
                        flush=True,
                    )
                    uploaded_blobs.append(blob_path)
                except Exception as exc:
                    print(
                        f"Failed to ingest '{folder_name}' for {day_timestamp}: {exc}",
                        flush=True,
                    )
            continue

        if folder_name == "cow_milk_visits":
            if herd_cattle_ids is None:
                herd_info_params = endpoint_params.get("herd_info", {})
                print(
                    f"Fetching 'herd_info' for cattle IDs with params={herd_info_params}...",
                    flush=True,
                )
                try:
                    herd_response = dairy_net.fetch_herd_info(
                        session=session,
                        **herd_info_params,
                    )
                    herd_cattle_ids = _extract_cattle_ids_from_herd_info(herd_response)
                except Exception as exc:
                    print(
                        f"Failed to fetch cattle IDs from 'herd_info': {exc}",
                        flush=True,
                    )
                    herd_cattle_ids = []

            initial_page_size = int(
                params.get("initial_page_size") or params.get("page_size") or 100
            )
            extra_kwargs = {
                k: v
                for k, v in params.items()
                if k not in {"cattle_id", "page_index", "page_size", "initial_page_size"}
            }

            print(
                f"Fetching '{folder_name}' for {len(herd_cattle_ids)} cattle (initial_page_size={initial_page_size}, page_index=1)...",
                flush=True,
            )
            for cattle_id in herd_cattle_ids:
                print(
                    f"Fetching '{folder_name}' for cattle_id={cattle_id}...",
                    flush=True,
                )
                try:
                    response = fetch_all_milk_visits_for_cattle(
                        session=session,
                        cattle_id=cattle_id,
                        initial_page_size=initial_page_size,
                        fetch_fn=fetch_fn,
                        **extra_kwargs,
                    )
                    blob_path = upload_endpoint_response_to_folder(
                        blob_service_client=service_client,
                        container_name=container_name,
                        folder_name=folder_name,
                        response=response,
                        cattle_id=cattle_id,
                        filename=f"{cattle_id}.json",
                    )
                    print(
                        f"Uploaded '{folder_name}' ({cattle_id}) -> {container_name}/{blob_path}",
                        flush=True,
                    )
                    uploaded_blobs.append(blob_path)
                except Exception as exc:
                    print(
                        f"Failed to ingest '{folder_name}' for cattle_id={cattle_id}: {exc}",
                        flush=True,
                    )
            continue

        cattle_id = params.get("cattle_id")
        start_date = (
            params.get("report_date_from")
            or params.get("from_date")
            or params.get("start_date")
            or params.get("timestamp")
        )
        end_date = (
            params.get("report_date_until")
            or params.get("to_date")
            or params.get("end_date")
            or params.get("timestamp")
        )

        print(f"Fetching '{folder_name}' with params={params}...", flush=True)
        try:
            response = fetch_fn(session=session, **params)
            if folder_name == "herd_info":
                try:
                    herd_cattle_ids = _extract_cattle_ids_from_herd_info(response)
                    print(
                        f"Extracted {len(herd_cattle_ids)} cattle IDs from 'herd_info'.",
                        flush=True,
                    )
                except Exception as exc:
                    print(
                        f"Failed to parse cattle IDs from 'herd_info': {exc}",
                        flush=True,
                    )
            blob_path = upload_endpoint_response_to_folder(
                blob_service_client=service_client,
                container_name=container_name,
                folder_name=folder_name,
                response=response,
                cattle_id=cattle_id,
                start_date=start_date,
                end_date=end_date,
            )
            print(f"Uploaded '{folder_name}' -> {container_name}/{blob_path}", flush=True)
            uploaded_blobs.append(blob_path)
        except Exception as exc:
            print(f"Failed to ingest '{folder_name}': {exc}", flush=True)

    print(f"Finished ingestion. Uploaded {len(uploaded_blobs)} files.", flush=True)
    return uploaded_blobs


def main() -> None:
    ingest_all_endpoints()


if __name__ == "__main__":
    main()

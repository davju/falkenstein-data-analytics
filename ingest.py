import os
from collections.abc import Callable
from typing import Any

import requests
from azure.core import exceptions
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

from lib import dairy_net
from lib.azure import authenticate_by_access_key
from lib.file_handling import rename_with_current_timestamp

load_dotenv()

# Parameters passed to each endpoint function in lib/dairy_net.py
ENDPOINT_PARAMETERS: dict[str, dict[str, Any]] = {
    "daily_milk_simple_list": {
        "timestamp": "2026-10-11T21:23",
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
    "milk_visits_for_single_cattle": {
        "cattle_id": "5288cd84-46af-496e-8cdf-ae198ede22fe",
        "page_index": 2,
        "page_size": 20,
    },
    "cattle_custom_preset": {
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
}

# Mapping of folder/endpoint names to their fetch functions in lib/dairy_net.py
ENDPOINT_FUNCTIONS: dict[str, Callable[..., requests.Response]] = {
    "daily_milk_simple_list": dairy_net.fetch_daily_milk_simple_list,
    "cow_monitor": dairy_net.fetch_cow_monitor,
    "process_report": dairy_net.fetch_process_report,
    "conspicuous_conductivity_alarms": dairy_net.fetch_conspicuous_conductivity_alarms,
    "cattle_view": dairy_net.fetch_cattle_view,
    "cattle_by_id": dairy_net.fetch_cattle_by_id,
    "milk_visits_for_single_cattle": dairy_net.fetch_milk_visits_for_single_cattle,
    "cattle_custom_preset": dairy_net.fetch_cattle_custom_preset,
}


def _extension_for_response(response: requests.Response) -> tuple[str, str]:
    """Return file extension and MIME type based on the HTTP response Content-Type."""
    content_type = response.headers.get("Content-Type", "application/json").lower()
    if "text/html" in content_type:
        return ".html", "text/html"
    if "text/csv" in content_type:
        return ".csv", "text/csv"
    return ".json", "application/json"


def upload_endpoint_response_to_folder(
    blob_service_client: BlobServiceClient,
    container_name: str,
    folder_name: str,
    response: requests.Response,
) -> str:
    """Upload an endpoint response into its own folder inside the Azure Blob container."""
    ext, mime_type = _extension_for_response(response)
    filename = rename_with_current_timestamp(f"{folder_name}{ext}")
    blob_path = f"{folder_name}/{filename}"

    blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob=blob_path,
    )
    blob_client.upload_blob(
        response.content,
        overwrite=True,
        content_settings=ContentSettings(content_type=mime_type),
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
    for folder_name, fetch_fn in ENDPOINT_FUNCTIONS.items():
        params = endpoint_params.get(folder_name, {})
        print(f"Fetching '{folder_name}' with params={params}...", flush=True)
        try:
            response = fetch_fn(session=session, **params)
            blob_path = upload_endpoint_response_to_folder(
                blob_service_client=service_client,
                container_name=container_name,
                folder_name=folder_name,
                response=response,
            )
            print(f"Uploaded '{folder_name}' -> {container_name}/{blob_path}", flush=True)
            uploaded_blobs.append(blob_path)
        except Exception as exc:
            print(f"Failed to ingest '{folder_name}': {exc}", flush=True)

    print(f"Finished ingestion. Uploaded {len(uploaded_blobs)}/{len(ENDPOINT_FUNCTIONS)} files.", flush=True)
    return uploaded_blobs


def main() -> None:
    ingest_all_endpoints()


if __name__ == "__main__":
    main()

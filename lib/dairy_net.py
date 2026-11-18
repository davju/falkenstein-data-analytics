import json
import os
from typing import Any
from urllib.parse import quote, unquote, urlencode

import requests
from dotenv import load_dotenv

DEFAULT_BASE_URL = "http://10.150.1.246"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

_TOKEN_COOKIE_HEADERS = (
    ("XSRF-TOKEN", "X-XSRF-TOKEN"),
    ("X-DAIRYNET-TOKEN", "X-DAIRYNET-TOKEN"),
)

DEFAULT_HERD_SELECTION: dict[str, Any] = {
    "name": "Ganze Herde",
    "groupType": "WholeHerd",
    "groupUsage": None,
    "animalChoiceColumnPreset": None,
    "animalChoicePresetDefinitionId": None,
    "id": None,
}


def _sync_token_headers(session: requests.Session) -> None:
    """Mirror auth/CSRF cookies into request headers for Spring/Angular endpoints."""
    for cookie_name, header_name in _TOKEN_COOKIE_HEADERS:
        if cookie_name in session.cookies:
            session.headers[header_name] = session.cookies[cookie_name]


def _build_url(path: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Build a full URL for a DairyNet endpoint."""
    normalized_base = base_url.rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    if clean_path.startswith(("/dairynetbackend/", "/dairynet/", "/service-")):
        return f"{normalized_base}{clean_path}"
    return f"{normalized_base}/dairynetbackend{clean_path}"


def authenticate_dairynet_session(
    username: str | None = None,
    password: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Session:
    """Authenticate against DairyNet and return an authorized requests.Session.

    Falls back to ``dairynet_username`` and ``dairynet_password`` from ``.env``
    or the environment when credentials are not passed explicitly.
    """
    if username is None or password is None:
        load_dotenv()
        if username is None:
            username = os.environ["dairynet_username"]
        if password is None:
            password = os.environ["dairynet_password"]

    normalized_base_url = base_url.rstrip("/")
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    login_url = f"{normalized_base_url}/dairynetbackend/platform/user/authenticate"
    login_payload = {
        "username": username,
        "password": password,
    }
    auth_headers = {
        "Origin": normalized_base_url,
        "Referer": f"{normalized_base_url}/dairynet/login",
        "Accept": "application/json, text/plain, */*",
    }

    auth_response = session.post(
        login_url,
        data=login_payload,
        headers=auth_headers,
        timeout=timeout,
    )
    auth_response.raise_for_status()
    _sync_token_headers(session)
    return session


def _ensure_session(
    session: requests.Session | None,
    base_url: str = DEFAULT_BASE_URL,
) -> requests.Session:
    if session is not None:
        return session
    return authenticate_dairynet_session(base_url=base_url)


def dairynet_get(
    path: str,
    *,
    session: requests.Session | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Send an authenticated GET request to DairyNet and raise on HTTP error."""
    active_session = _ensure_session(session, base_url=base_url)
    url = _build_url(path, base_url=base_url)
    req_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{base_url.rstrip('/')}/dairynet/",
    }
    if headers:
        req_headers.update(headers)

    encoded_params = (
        urlencode(params, doseq=True, quote_via=quote)
        if isinstance(params, dict)
        else params
    )

    response = active_session.get(
        url=url,
        params=encoded_params,
        headers=req_headers,
        timeout=timeout,
    )
    response.raise_for_status()
    _sync_token_headers(active_session)
    return response


# =============================================================================
# REST GET Endpoints from important_endpoints.txt
# =============================================================================


def fetch_daily_milk_simple_list(
    session: requests.Session | None = None,
    timestamp: str = "2026-10-11T21:23",
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the 24h daily milk simple list for a given ISO timestamp.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/analysis/dailymilk/simpleList/{timestamp}
    """
    path = f"/dairynetbackend/analysis/dailymilk/simpleList/{quote(timestamp, safe=':')}"
    return dairynet_get(
        path,
        session=session,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cow_monitor(
    session: requests.Session | None = None,
    page_index: int = 1,
    page_size: int = 300,
    *,
    extra_params: dict[str, Any] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a paginated list of cows from the Cow Monitor.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/herdmanagement/cowmonitor?pageIndex=1&pageSize=300
    """
    params: dict[str, Any] = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if extra_params:
        params.update(extra_params)

    return dairynet_get(
        "/dairynetbackend/herdmanagement/cowmonitor",
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_process_report(
    session: requests.Session | None = None,
    milking_parlors: str = "775502b4-40cf-48d3-bf59-1e464a0a45c1#1#2#3",
    report_date_from: str = "2026-10-18",
    report_date_until: str = "2026-11-17",
    sort_column: str = "reportDate",
    sort_descending: bool = True,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the milking process report for the given parlor(s) and date range.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/analysis/processreport
            ?milkingParlors=775502b4-40cf-48d3-bf59-1e464a0a45c1%231%232%233
            &reportDateFrom=2026-10-18
            &reportDateUntil=2026-11-17
            &sortColumn=reportDate
            &sortDescending=true
    """
    params = {
        "milkingParlors": unquote(milking_parlors),
        "reportDateFrom": report_date_from,
        "reportDateUntil": report_date_until,
        "sortColumn": sort_column,
        "sortDescending": str(sort_descending).lower(),
    }
    return dairynet_get(
        "/dairynetbackend/analysis/processreport",
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_conspicuous_conductivity_alarms(
    session: requests.Session | None = None,
    number_alarms: int = 1,
    number_visits: int = 5,
    date_of_alarm: int = 3,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch conspicuous milk conductivity alarms across the herd.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/milking/alarm/conspicuousConductivity
            ?numberAlarms=1&numberVisits=5&dateOfAlarm=3
    """
    params = {
        "numberAlarms": number_alarms,
        "numberVisits": number_visits,
        "dateOfAlarm": date_of_alarm,
    }
    return dairynet_get(
        "/dairynetbackend/milking/alarm/conspicuousConductivity",
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_view(
    session: requests.Session | None = None,
    cattle_id: str = "5288cd84-46af-496e-8cdf-ae198ede22fe",
    selected_tab: str = "coreData",
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the cattle view endpoint for a given cattle ID and selected tab.

    Endpoint:
        GET http://10.150.1.246/dairynet/herdmanagement/cattle
            ?id=5288cd84-46af-496e-8cdf-ae198ede22fe&selectedtab=coreData
    """
    params = {
        "id": cattle_id,
        "selectedtab": selected_tab,
    }
    return dairynet_get(
        "/dairynet/herdmanagement/cattle",
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_by_id(
    session: requests.Session | None = None,
    cattle_id: str = "5288cd84-46af-496e-8cdf-ae198ede22fe",
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch master data for a single animal by cattle UUID.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/herdmanagement/cattle/{cattle_id}
    """
    path = f"/dairynetbackend/herdmanagement/cattle/{quote(cattle_id, safe='')}"
    return dairynet_get(
        path,
        session=session,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visits_for_single_cattle(
    session: requests.Session | None = None,
    cattle_id: str = "5288cd84-46af-496e-8cdf-ae198ede22fe",
    page_index: int = 2,
    page_size: int = 20,
    *,
    extra_params: dict[str, Any] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch paginated milk visits for a single animal by cattle UUID.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/dairybox.milking/v1.0/milkvisit/listForSingleCattle/{cattle_id}
            ?pageIndex=2&pageSize=20
    """
    params: dict[str, Any] = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if extra_params:
        params.update(extra_params)

    path = (
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/listForSingleCattle/"
        f"{quote(cattle_id, safe='')}"
    )
    return dairynet_get(
        path,
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_custom_preset(
    session: requests.Session | None = None,
    preset_id: str = "ac13dd8b-ca1f-43ee-8dbe-4668a66dbcd2",
    herd_selection: dict[str, Any] | str | None = None,
    *,
    extra_params: dict[str, Any] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch cattle list data using a custom column preset ID and herd selection filter.

    Endpoint:
        GET http://10.150.1.246/dairynetbackend/herdmanagement/cattle/customPreset/{preset_id}
            ?herdSelection=%7B%22name%22%3A%22Ganze%20Herde%22%2C%22groupType%22%3A%22WholeHerd%22%2C%22groupUsage%22%3Anull%2C%22animalChoiceColumnPreset%22%3Anull%2C%22animalChoicePresetDefinitionId%22%3Anull%2C%22id%22%3Anull%7D
    """
    if herd_selection is None:
        herd_selection_str = json.dumps(DEFAULT_HERD_SELECTION, separators=(",", ":"))
    elif isinstance(herd_selection, str):
        herd_selection_str = unquote(herd_selection)
    else:
        herd_selection_str = json.dumps(herd_selection, separators=(",", ":"))

    params: dict[str, Any] = {
        "herdSelection": herd_selection_str,
    }
    if extra_params:
        params.update(extra_params)

    path = f"/dairynetbackend/herdmanagement/cattle/customPreset/{quote(preset_id, safe='')}"
    return dairynet_get(
        path,
        session=session,
        params=params,
        base_url=base_url,
        timeout=timeout,
    )

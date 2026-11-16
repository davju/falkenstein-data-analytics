import json
import os
from typing import Any
from urllib.parse import quote

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


def _sync_token_headers(session: requests.Session) -> None:
    """Mirror auth/CSRF cookies into request headers for Spring/Angular endpoints."""
    for cookie_name, header_name in _TOKEN_COOKIE_HEADERS:
        if cookie_name in session.cookies:
            session.headers[header_name] = session.cookies[cookie_name]


def _build_backend_url(path: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Build a full URL for a DairyNet backend or federated service endpoint."""
    normalized_base = base_url.rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    if clean_path.startswith(("/dairynetbackend/", "/service-", "/dairynet/")):
        return f"{normalized_base}{clean_path}"
    return f"{normalized_base}/dairynetbackend{clean_path}"


def dairynet_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    data: Any = None,
    headers: dict[str, str] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Send an authenticated request to DairyNet and raise on HTTP error."""
    url = _build_backend_url(path, base_url=base_url)
    req_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{base_url.rstrip('/')}/dairynet/",
    }
    if method.upper() in {"POST", "PUT", "DELETE", "PATCH"}:
        req_headers["Origin"] = base_url.rstrip("/")
    if headers:
        req_headers.update(headers)

    response = session.request(
        method=method.upper(),
        url=url,
        params=params,
        json=json_body,
        data=data,
        headers=req_headers,
        timeout=timeout,
    )
    response.raise_for_status()
    _sync_token_headers(session)
    return response


# =============================================================================
# 1. Authentication, Session, Navigation & System APIs
# =============================================================================


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


def logout_dairynet_session(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Log out an active DairyNet session (POST /platform/user/logout)."""
    return dairynet_request(
        session, "POST", "/platform/user/logout", base_url=base_url, timeout=timeout
    )


def fetch_platform_credentials(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch current user credentials, farm/company IDs, rights, and JWT token.

    Endpoint: GET /dairynetbackend/platform/credentials
    """
    return dairynet_request(
        session, "GET", "/platform/credentials", base_url=base_url, timeout=timeout
    )


def fetch_version(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch DairyNetBox and backend module API versions.

    Endpoint: GET /dairynetbackend/version
    """
    return dairynet_request(
        session, "GET", "/version", base_url=base_url, timeout=timeout
    )


def fetch_current_dairynet_release(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch the current DairyNet release string.

    Endpoint: GET /dairynetbackend/systemsettings/current-dairynet-release
    """
    return dairynet_request(
        session,
        "GET",
        "/systemsettings/current-dairynet-release",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_system_settings(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch global DairyNetBox feature flags (CowScout, AFS feeding, DNList, etc.).

    Endpoint: GET /dairynetbackend/systemsettings
    """
    return dairynet_request(
        session, "GET", "/systemsettings", base_url=base_url, timeout=timeout
    )


def fetch_active_topics(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch all active module/feature topics enabled on the DairyNetBox.

    Endpoint: GET /dairynetbackend/admin/topic/allActive
    """
    return dairynet_request(
        session, "GET", "/admin/topic/allActive", base_url=base_url, timeout=timeout
    )


def fetch_enums(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all backend enumeration definitions and option keys.

    Endpoint: GET /dairynetbackend/enums
    """
    return dairynet_request(
        session, "GET", "/enums", base_url=base_url, timeout=timeout
    )


def fetch_locales(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch available UI locales.

    Endpoint: GET /dairynetbackend/platform/localize/locales
    """
    return dairynet_request(
        session, "GET", "/platform/localize/locales", base_url=base_url, timeout=timeout
    )


def fetch_localization(
    session: requests.Session,
    locale: str = "de-DE",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch i18n translation dictionary for a given locale or 'default' (English).

    Endpoint: GET /dairynetbackend/platform/localize/{locale}
    """
    return dairynet_request(
        session,
        "GET",
        f"/platform/localize/{quote(locale, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_topbar_navigation(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch the full topbar navigation structure (Herd, Milking, Repro, Health, Feeding).

    Endpoint: GET /dairynetbackend/navigation/topbar
    """
    return dairynet_request(
        session, "GET", "/navigation/topbar", base_url=base_url, timeout=timeout
    )


def fetch_sidebar_navigation(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch the settings/administration sidebar navigation structure.

    Endpoint: GET /dairynetbackend/navigation/sidebar
    """
    return dairynet_request(
        session, "GET", "/navigation/sidebar", base_url=base_url, timeout=timeout
    )


def fetch_mymenu_navigation(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch user-configured 'My Menu' navigation tabs.

    Endpoint: GET /dairynetbackend/navigation/mymenu
    """
    return dairynet_request(
        session, "GET", "/navigation/mymenu", base_url=base_url, timeout=timeout
    )


def fetch_cattle_details_navigation(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch available navigation tabs for the single-cattle details view.

    Endpoint: GET /dairynetbackend/navigation/cattle-details
    """
    return dairynet_request(
        session, "GET", "/navigation/cattle-details", base_url=base_url, timeout=timeout
    )


def fetch_local_system_time(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch local system timestamp from DairyNetBox.

    Endpoint: GET /dairynetbackend/systemadministration/localSystemTime
    """
    return dairynet_request(
        session,
        "GET",
        "/systemadministration/localSystemTime",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_utc_system_time(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch UTC system timestamp from DairyNetBox.

    Endpoint: GET /dairynetbackend/systemadministration/utcSystemTime
    """
    return dairynet_request(
        session,
        "GET",
        "/systemadministration/utcSystemTime",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_country_or_region(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch configured country/region (e.g. 'GERMANY').

    Endpoint: GET /dairynetbackend/settings/countryorregion
    """
    return dairynet_request(
        session, "GET", "/settings/countryorregion", base_url=base_url, timeout=timeout
    )


def fetch_measurement_system(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch configured measurement system (e.g. 'METRIC').

    Endpoint: GET /dairynetbackend/settings/measurementsystem
    """
    return dairynet_request(
        session,
        "GET",
        "/settings/measurementsystem",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_currency(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch configured currency (e.g. 'EUR').

    Endpoint: GET /dairynetbackend/settings/currency
    """
    return dairynet_request(
        session, "GET", "/settings/currency", base_url=base_url, timeout=timeout
    )


def fetch_system_control_parameters(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch system control parameters.

    Endpoint: GET /dairynetbackend/settings/systemcontrolparameter
    """
    return dairynet_request(
        session,
        "GET",
        "/settings/systemcontrolparameter",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_farm_site(
    session: requests.Session,
    farm_site_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch farm site details by ID.

    Endpoint: GET /dairynetbackend/core/farmsite/{farm_site_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/core/farmsite/{quote(farm_site_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_notifications(
    session: requests.Session,
    locale: str = "de-DE",
    include_confirmed: bool = False,
    include_read: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch system and animal notifications.

    Endpoint: GET /dairynetbackend/notification/read/{locale}/{includeConfirmed}/{includeRead}
    """
    path = (
        f"/notification/read/{quote(locale, safe='')}/"
        f"{str(include_confirmed).lower()}/{str(include_read).lower()}"
    )
    return dairynet_request(session, "GET", path, base_url=base_url, timeout=timeout)


def fetch_notifications_for_reference(
    session: requests.Session,
    reference_id: str,
    locale: str = "de-DE",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch notifications for a specific reference entity ID.

    Endpoint: GET /dairynetbackend/notification/notificationsForReference/{reference_id}/{locale}
    """
    path = (
        f"/notification/notificationsForReference/"
        f"{quote(reference_id, safe='')}/{quote(locale, safe='')}"
    )
    return dairynet_request(session, "GET", path, base_url=base_url, timeout=timeout)


def fetch_module_federation_services(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch registered micro-frontend/adapter services (e.g. LKV, CowScout).

    Endpoint: GET /dairynetbackend/module-federation-info/services
    """
    return dairynet_request(
        session,
        "GET",
        "/module-federation-info/services",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_federated_service_info(
    session: requests.Session,
    service_name: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch info metadata for a federated service (e.g. 'service-lkv-adapter', 'service-cowscout-integration').

    Endpoint: GET /{service_name}/api/info
    """
    clean_service = service_name.strip("/")
    return dairynet_request(
        session,
        "GET",
        f"/{clean_service}/api/info",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_websocket_info(
    session: requests.Session,
    timestamp_ms: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 10,
) -> requests.Response:
    """Fetch SockJS/WebSocket handshake info.

    Endpoint: GET /dairynetbackend/ws/info
    """
    params = {"t": str(timestamp_ms)} if timestamp_ms is not None else None
    return dairynet_request(
        session, "GET", "/ws/info", params=params, base_url=base_url, timeout=timeout
    )


# =============================================================================
# 2. Cattle, Herd Management, Groups, Animal Choice, Actions & Sorting APIs
# =============================================================================


def fetch_cattle_page(
    session: requests.Session,
    page_index: int = 1,
    page_size: int = 240,
    sort_column: str | None = None,
    sort_descending: bool = False,
    herd_group_filter: dict[str, Any] | None = None,
    extra_filters: dict[str, Any] | None = None,
    subpath: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch a paginated list of cattle from the Herd Management cattle table.

    Endpoint: GET /dairynetbackend/herdmanagement/cattle
    """
    params: dict[str, Any] = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if sort_column is not None:
        params["sortColumn"] = sort_column
        params["sortDescending"] = str(sort_descending).lower()
    if herd_group_filter is not None:
        filter_copy = dict(herd_group_filter)
        filter_copy.pop("complexFilterType", None)
        params["herdGroupSelect"] = json.dumps(filter_copy)
    if extra_filters:
        params.update(extra_filters)

    path = "/herdmanagement/cattle"
    if subpath:
        path = f"{path}/{subpath.lstrip('/')}"
    return dairynet_request(
        session, "GET", path, params=params, base_url=base_url, timeout=timeout
    )


def fetch_cattle_by_id(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch master data for a single animal by cattle UUID.

    Endpoint: GET /dairynetbackend/herdmanagement/cattle/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/cattle/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_information(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch status and animal action summary information for a single animal.

    Endpoint: GET /dairynetbackend/herdmanagement/cattle/information/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/cattle/information/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_by_ids_including_inactive(
    session: requests.Session,
    cattle_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch full cattle records for a list of cattle UUIDs (including inactive animals).

    Endpoint: POST /dairynetbackend/herdmanagement/cattle/animalsByCattleIdListIncludingInactive
    """
    return dairynet_request(
        session,
        "POST",
        "/herdmanagement/cattle/animalsByCattleIdListIncludingInactive",
        json_body=cattle_ids,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_identifiers_by_ids_including_inactive(
    session: requests.Session,
    cattle_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch animal identifiers (number, ear tag, name) for a list of cattle UUIDs.

    Endpoint: POST /dairynetbackend/herdmanagement/cattle/animalIdentifiersByCattleIdListIncludingInactive
    """
    return dairynet_request(
        session,
        "POST",
        "/herdmanagement/cattle/animalIdentifiersByCattleIdListIncludingInactive",
        json_body=cattle_ids,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_by_animal_numbers(
    session: requests.Session,
    animal_numbers: list[int | str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch cattle records for a list of animal numbers.

    Endpoint: POST /dairynetbackend/herdmanagement/cattle/animalsByAnimalNumberList
    """
    return dairynet_request(
        session,
        "POST",
        "/herdmanagement/cattle/animalsByAnimalNumberList",
        json_body=animal_numbers,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_without_mother(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all cattle that do not have a mother assigned.

    Endpoint: GET /dairynetbackend/herdmanagement/cattle/cattleWithoutMother
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattle/cattleWithoutMother",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_system_parameters(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch system parameters (including expectedMilkVisitTimeStamp) for a cow.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlesystemparameters/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/cattlesystemparameters/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_navigation_details(
    session: requests.Session,
    cattle_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch header/navigation details (animalNumber, name, cattleType, cowStatus, lactationNumber) for cattle IDs.

    Endpoint: POST /dairynetbackend/cattleinfo/navigation-details
    """
    return dairynet_request(
        session,
        "POST",
        "/cattleinfo/navigation-details",
        json_body=cattle_ids,
        base_url=base_url,
        timeout=timeout,
    )


def search_global_text(
    session: requests.Session,
    search_text: str,
    scopes: list[str] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Search across cattle, pages, and lists using global search.

    Endpoint: GET /dairynetbackend/search/globalsearch/textSearch
    """
    params: dict[str, Any] = {"searchText": search_text}
    if scopes is not None:
        params["scopes"] = scopes
    return dairynet_request(
        session,
        "GET",
        "/search/globalsearch/textSearch",
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_groups_by_usage(
    session: requests.Session,
    usage: str = "Milking",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch cattle groups by usage type (e.g. 'Milking', 'Barn', 'Feeding', 'Administrative').

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/findAllByGroupUsage?param={usage}
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattlegroup/findAllByGroupUsage",
        params={"param": usage},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_administrative_cattle_groups_by_topic(
    session: requests.Session,
    topic_name: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch administrative cattle groups by topic name.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/findAdministrativeByTopicName
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattlegroup/findAdministrativeByTopicName",
        params={"topicName": topic_name},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_groups_simple_list(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the simple list of all cattle groups.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/simpleList
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattlegroup/simpleList",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_group_by_id(
    session: requests.Session,
    group_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a single cattle group by ID.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/{group_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/cattlegroup/{quote(group_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_group_memberships(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all cattle group memberships for a given animal.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/memberships/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/cattlegroup/memberships/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_barn_groups_with_rotary_values(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all barn groups with rotary parlor values.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/findAllBarnGroupsWithRotaryValues
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattlegroup/findAllBarnGroupsWithRotaryValues",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_herd_and_group_select_options(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all herd, group, and animal-choice filter options used by the cattle list selector.

    Endpoint: GET /dairynetbackend/herdmanagement/cattlegroup/herdandgroupselect
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/cattlegroup/herdandgroupselect",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_group_statistics(
    session: requests.Session,
    group_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch basic milking statistics for a cattle group.

    Endpoint: GET /dairynetbackend/dairynet.herdmanagement/v1.0/milkinggroupstatistics/basic/{group_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairynet.herdmanagement/v1.0/milkinggroupstatistics/basic/{quote(group_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_preset_definitions_simple_list(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch available column preset definitions for cattle lists.

    Endpoint: GET /dairynetbackend/herdmanagement/presetdefinitions/simpleList
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/presetdefinitions/simpleList",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_preset_definitions_flat(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch flat-mapped column preset definitions.

    Endpoint: GET /dairynetbackend/herdmanagement/presetdefinitions/flat
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/presetdefinitions/flat",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_preset_available_columns(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all available table columns for cattle preset definitions.

    Endpoint: GET /dairynetbackend/herdmanagement/presetdefinitions/availablecolumns
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/presetdefinitions/availablecolumns",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_preset_definition_by_id(
    session: requests.Session,
    preset_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a specific column preset definition by ID.

    Endpoint: GET /dairynetbackend/herdmanagement/presetdefinitions/{preset_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/presetdefinitions/{quote(preset_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_choice_simple_list(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all animal choice rule sets (simple list).

    Endpoint: GET /dairynetbackend/herdmanagement/animalchoice/simpleList
    """
    return dairynet_request(
        session,
        "GET",
        "/herdmanagement/animalchoice/simpleList",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_choice_by_id(
    session: requests.Session,
    rule_set_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a specific animal choice rule set by ID.

    Endpoint: GET /dairynetbackend/herdmanagement/animalchoice/{rule_set_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/animalchoice/{quote(rule_set_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_dnlist_definitions(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all dynamic list (DNList) definitions.

    Endpoint: GET /dairynetbackend/dnlist/definition
    """
    return dairynet_request(
        session, "GET", "/dnlist/definition", base_url=base_url, timeout=timeout
    )


def fetch_animal_action_list_count(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch counts of planned, saved, and booked animal actions.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/listcount
    """
    return dairynet_request(
        session,
        "GET",
        "/dairybox.herdmanagement/v1.0/animalaction/listcount",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_possible_animal_action_names(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all possible animal action type names.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getPossibleAnimalActionNames
    """
    return dairynet_request(
        session,
        "GET",
        "/dairybox.herdmanagement/v1.0/animalaction/getPossibleAnimalActionNames",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_related_animal_actions(
    session: requests.Session,
    action_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch related animal actions for a given animal action ID.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getRelatedActions/{action_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.herdmanagement/v1.0/animalaction/getRelatedActions/{quote(action_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_action_calendar(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the full animal action calendar (columns and scheduled actions).

    Endpoint: GET /dairynetbackend/animalaction/calendar
    """
    return dairynet_request(
        session, "GET", "/animalaction/calendar", base_url=base_url, timeout=timeout
    )


def fetch_last_successful_insemination(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the last successful insemination action for a cow.

    Endpoint: GET /dairynetbackend/herdmanagement/animalaction/insemination/findLastSuccessfulInsemination/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/herdmanagement/animalaction/insemination/findLastSuccessfulInsemination/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_possible_successful_inseminations(
    session: requests.Session,
    cattle_id: str,
    reference_date: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch possible successful inseminations for a cow relative to a date.

    Endpoint: GET /dairynetbackend/herdmanagement/animalaction/insemination/findPossibleSuccessfulInseminations/{cattle_id}/{reference_date}
    """
    path = (
        "/herdmanagement/animalaction/insemination/findPossibleSuccessfulInseminations/"
        f"{quote(cattle_id, safe='')}/{quote(reference_date, safe='')}"
    )
    return dairynet_request(session, "GET", path, base_url=base_url, timeout=timeout)


def fetch_sorting_areas_simple_list(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all sorting/selection areas (simple list).

    Endpoint: GET /dairynetbackend/sorting/sortingarea/simpleList
    """
    return dairynet_request(
        session,
        "GET",
        "/sorting/sortingarea/simpleList",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_sorting_areas_by_ids(
    session: requests.Session,
    sorting_area_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch sorting areas by a list of sorting area IDs.

    Endpoint: GET /dairynetbackend/sorting/sortingarea/byIds
    """
    return dairynet_request(
        session,
        "GET",
        "/sorting/sortingarea/byIds",
        params={"sortingAreaIds": sorting_area_ids},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_sorting_timeframe_options(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch available sorting command timeframe options for a given cow.

    Endpoint: GET /dairynetbackend/sorting/sortingcommand/timeframe-options/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/sorting/sortingcommand/timeframe-options/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


# =============================================================================
# 3. Dashboard & Herd KPI Widget APIs (Cattle, Milking, Repro, BCS, Breeds)
# =============================================================================


def fetch_dashboard_settings(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch configured dashboard widgets and their widget UUIDs.

    Endpoint: GET /dairynetbackend/dashboard/settings
    """
    return dairynet_request(
        session, "GET", "/dashboard/settings", base_url=base_url, timeout=timeout
    )


def fetch_available_dashboard_widgets(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all available dashboard widget types.

    Endpoint: GET /dairynetbackend/dashboard/availableWidgets
    """
    return dairynet_request(
        session,
        "GET",
        "/dashboard/availableWidgets",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_avmlk_statistic_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch per-cow average milk weight (g), lactation number, and days in milk for the herd.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/avmlkStatistic
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/avmlkStatistic",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_yield_overview_widget(
    session: requests.Session,
    days: int = 7,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch daily average milk yield by lactation group (1st, 2nd, 3rd+, overall) over N days.

    Endpoint: GET /dairynetbackend/dashboard/widgets/milkyieldoverview/{days}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dashboard/widgets/milkyieldoverview/{days}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_avg_milk_yield_per_session_widget_settings(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch settings for the average milk yield per session overview widget.

    Endpoint: GET /dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview?widgetId={widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        "/dashboard/widgets/avgmilkyieldpersessionoverview",
        params={"widgetId": widget_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_avg_milk_yield_per_session_widget_data(
    session: requests.Session,
    days_back: int,
    barn_group_name: str,
    calculation_type: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch session-by-session average milk yield data for a barn group.

    Endpoint: GET /dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview/data
    """
    params = {
        "daysBack": days_back,
        "barnGroupName": barn_group_name,
        "calculationTypeEnum": calculation_type,
    }
    return dairynet_request(
        session,
        "GET",
        "/dashboard/widgets/avgmilkyieldpersessionoverview/data",
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_reproduction_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch herd reproduction KPIs (DIM, days open, insemination/calving intervals, pregnancy rates).

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/reproduction
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/reproduction",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_stall_performance_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch 24h milk weight and milking duration per milking box.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/stallperformance
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/stallperformance",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_stall_performance_details(
    session: requests.Session,
    box_id: int | str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch detailed box attachment performance and problematic milkings for a box.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/stallperformance/details?boxId={box_id}
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/stallperformance/details",
        params={"boxId": box_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_farm_performance_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch monobox farm performance KPIs (milk yield, yield/box, yield/cow, cows milked, milkings).

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/performance/farm
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/performance/farm",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_box_performance_widget(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch monobox box-level performance comparison widget data.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/performance/box?widgetId={widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/performance/box",
        params={"widgetId": widget_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_monobox_performance_widget_settings(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch monobox performance widget box selection settings.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/monoboxPerformance?widgetId={widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/monoboxPerformance",
        params={"widgetId": widget_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_process_performance_widget(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milking process performance KPIs (attachment time, incomplete milkings, milkings/h/box).

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/milking-process-performance/{widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/home/dashboard/widgets/milking-process-performance/{quote(widget_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_yield_kpi_widget(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milk yield KPI widget data (total milk yield, yield per cow, number of milkings).

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/milkyieldkpi/{widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/home/dashboard/widgets/milkyieldkpi/{quote(widget_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_quality_kpi_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milk quality KPI widget data.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/milkqualitykpi
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/milkqualitykpi",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_productivity_parlor_settings(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch parlor selection settings for a milk productivity KPI widget.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor/{widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/home/dashboard/widgets/milk-productivity-settings/parlor/{quote(widget_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def save_milk_productivity_parlor_settings(
    session: requests.Session,
    widget_id: str,
    milking_parlor_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Save parlor selection settings for a milk productivity KPI widget.

    Endpoint: POST /dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor
    """
    payload = {
        "widgetId": widget_id,
        "milkingParlorIds": milking_parlor_ids,
    }
    return dairynet_request(
        session,
        "POST",
        "/home/dashboard/widgets/milk-productivity-settings/parlor",
        json_body=payload,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_choice_widget(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch configured animal choice rule sets for an Animal Choice dashboard widget.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/animalchoice?widgetId={widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/animalchoice",
        params={"widgetId": widget_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_choice_cattle_count(
    session: requests.Session,
    animal_choice_rule_set_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the number of cattle matching an animal choice rule set.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/animalchoice/cattlecount
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/animalchoice/cattlecount",
        params={"animalChoiceRuleSetId": animal_choice_rule_set_id},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_choice_widget_rulesets(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch available rule sets for the animal choice dashboard widget.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/animalchoice/rulesets
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/animalchoice/rulesets",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_dnlist_widget_settings(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch configured list IDs for a DNList dashboard widget.

    Endpoint: GET /dairynetbackend/dnlist/dashboard/widget/list/settings/{widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dnlist/dashboard/widget/list/settings/{quote(widget_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_dnlist_widget_data(
    session: requests.Session,
    widget_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch list names and KPI counts for a DNList dashboard widget.

    Endpoint: GET /dairynetbackend/dnlist/dashboard/widget/list/data/{widget_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dnlist/dashboard/widget/list/data/{quote(widget_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_bcs_development_widget(
    session: requests.Session,
    milking_group_id: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch per-cow Body Condition Score (BCS) vs. day of lactation data.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/bcsDevelopment
    """
    params = {"milkingGroupId": milking_group_id} if milking_group_id else None
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/bcsDevelopment",
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_calving_statistic_widget(
    session: requests.Session,
    days_back: int = 7,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch calving statistics over the past N days.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/calvingStatistic/{days_back}
    """
    return dairynet_request(
        session,
        "GET",
        f"/home/dashboard/widgets/calvingStatistic/{days_back}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_status_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch herd cattle status distribution (lactating, dry, inseminated, pregnant, etc.).

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/cattleStatus
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/cattleStatus",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_breed_performance_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch daily average milk performance by cattle breed and lactation.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/cattlebreedperformance
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/cattlebreedperformance",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_cattle_breed_proportion_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch cattle headcount breakdown by breed.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/cattlebreedproportion
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/cattlebreedproportion",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_animal_action_calendar_widget(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the dashboard animal action calendar widget overview.

    Endpoint: GET /dairynetbackend/home/dashboard/widgets/animalactioncalendar
    """
    return dairynet_request(
        session,
        "GET",
        "/home/dashboard/widgets/animalactioncalendar",
        base_url=base_url,
        timeout=timeout,
    )


# =============================================================================
# 4. Milking, Parlor, Sessions, Milk Visits & Reports APIs
# =============================================================================


def fetch_available_parlor_types(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch available milking parlor types configured on the farm (e.g. ['AUTOMATED_MONOBOX']).

    Endpoint: GET /dairynetbackend/milking/milkingparlor/availableParlorTypes
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingparlor/availableParlorTypes",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_parlors_simple_list(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all milking parlors and their individual boxes/stalls.

    Endpoint: GET /dairynetbackend/milking/milkingparlor/simpleList
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingparlor/simpleList",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_parlor_by_id(
    session: requests.Session,
    parlor_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a specific milking parlor by ID.

    Endpoint: GET /dairynetbackend/milking/milkingparlor/{parlor_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkingparlor/{quote(parlor_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_parlors_by_type(
    session: requests.Session,
    parlor_type: str = "AUTOMATED_MONOBOX",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milking parlors filtered by parlor type.

    Endpoint: GET /dairynetbackend/milking/milkingparlor/byType?param={parlor_type}
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingparlor/byType",
        params={"param": parlor_type},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_monobox_parlor_boxes(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch available DairyRobot monobox stalls/boxes.

    Endpoint: GET /dairynetbackend/milking/milkingparlor/monobox/boxes
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingparlor/monobox/boxes",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_latest_monobox_session(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the latest automated monobox milking session summary.

    Endpoint: GET /dairynetbackend/milking/milkingsession/latestMonoboxSession
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingsession/latestMonoboxSession",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_session_by_id(
    session: requests.Session,
    session_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch a milking session by session UUID.

    Endpoint: GET /dairynetbackend/milking/milkingsession/{session_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkingsession/{quote(session_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_monobox_session_status(
    session: requests.Session,
    session_id: str,
    cattle_group: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch monobox session visit & yield status (optionally filtered by cattle group name).

    Endpoint: GET /dairynetbackend/milking/milkingsession/{session_id}/status/monobox
    """
    params = (
        {"cattleGroup": cattle_group}
        if cattle_group and cattle_group != "ALL_ANIMALS"
        else None
    )
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkingsession/{quote(session_id, safe='')}/status/monobox",
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_rotary_session_status(
    session: requests.Session,
    session_id: str,
    cattle_group: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch rotary parlor session status (optionally filtered by cattle group name).

    Endpoint: GET /dairynetbackend/milking/milkingsession/{session_id}/status/rotary
    """
    params = (
        {"cattleGroup": cattle_group}
        if cattle_group and cattle_group != "ALL_ANIMALS"
        else None
    )
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkingsession/{quote(session_id, safe='')}/status/rotary",
        params=params,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_session_plans(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch configured milking session plans.

    Endpoint: GET /dairynetbackend/milking/milkingsession/plans
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingsession/plans",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_sessions_for_plan(
    session: requests.Session,
    plan_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milking sessions belonging to a specific session plan ID.

    Endpoint: GET /dairynetbackend/milking/milkingsession/sessions/{plan_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkingsession/sessions/{quote(plan_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milking_sessions_without_plan(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milking sessions that do not belong to a session plan.

    Endpoint: GET /dairynetbackend/milking/milkingsession/sessions/sessionsWithoutPlan
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingsession/sessions/sessionsWithoutPlan",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_virtual_automated_monobox_sessions(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch virtual automated monobox milking sessions.

    Endpoint: GET /dairynetbackend/milking/milkingsession/sessions/virtualAutomatedMonoboxSessions
    """
    return dairynet_request(
        session,
        "GET",
        "/milking/milkingsession/sessions/virtualAutomatedMonoboxSessions",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visit_by_id(
    session: requests.Session,
    milk_visit_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch details for a single milk visit by visit UUID.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/{milk_visit_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/{quote(milk_visit_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visits_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all milk visits displayed on a cow's milking info page.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsForCattleInfoPage/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/milkVisitsForCattleInfoPage/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visits_last_x_days(
    session: requests.Session,
    cattle_id: str,
    days_back: int = 7,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milk visits for a single cow over the last X days.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsLastXDays/{cattle_id}?daysBack={days_back}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/milkVisitsLastXDays/{quote(cattle_id, safe='')}",
        params={"daysBack": str(days_back)},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visit_process_result_parameters(
    session: requests.Session,
    milk_visit_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch process result parameters (and sampling results) for a milk visit.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultParameter/{milk_visit_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/processResultParameter/{quote(milk_visit_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visit_process_result_unknown_parameters(
    session: requests.Session,
    milk_visit_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch unknown process result parameters for a milk visit.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultUnknownParameter/{milk_visit_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/processResultUnknownParameter/{quote(milk_visit_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_visit_process_control_parameters(
    session: requests.Session,
    milk_visit_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch process control parameters (and sampling control settings) for a milk visit.

    Endpoint: GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processControlParameter/{milk_visit_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/v1.0/milkvisit/processControlParameter/{quote(milk_visit_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_conspicuous_cell_count_graph(
    session: requests.Session,
    cattle_id: str,
    days_back: int = 7,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch quarter-level cell count / conductivity graph values for a cow.

    Endpoint: GET /dairynetbackend/milking/alarm/conspicuousCellCount/graph/{cattle_id}?daysBack={days_back}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/alarm/conspicuousCellCount/graph/{quote(cattle_id, safe='')}",
        params={"daysBack": str(days_back)},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_control_settings_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch current milking allowance and milk control settings for a cow.

    Endpoint: GET /dairynetbackend/milking/milkcontrolsettings/forFrontend/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkcontrolsettings/forFrontend/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_milk_control_plans_by_parlor_type(
    session: requests.Session,
    parlor_type: str = "AUTOMATED_MONOBOX",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milk control plans by parlor type ('AUTOMATED_MONOBOX', 'AUTOMATED_ROTARY', 'CONVENTIONAL_ROTARY').

    Endpoint: GET /dairynetbackend/milking/milkcontrolplan/by-milking-parlor-type/{parlor_type}
    """
    return dairynet_request(
        session,
        "GET",
        f"/milking/milkcontrolplan/by-milking-parlor-type/{quote(parlor_type, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_manual_milking_parlors_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch parlors available for recording manual milk visits for a cow.

    Endpoint: GET /dairynetbackend/dairybox.milking/manual/parlorsForCattle/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/manual/parlorsForCattle/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_manual_milking_information_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch manual milking information for a cow.

    Endpoint: GET /dairynetbackend/dairybox.milking/manual/informationForCattle/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.milking/manual/informationForCattle/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_autodry_default_settings(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch default settings for milk-reduced auto-dry.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/defaultSettings
    """
    return dairynet_request(
        session,
        "GET",
        "/dairybox.herdmanagement/v1.0/milking/autodry/defaultSettings",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_autodry_plan_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch milk-reduced auto-dry plan for a cow.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.herdmanagement/v1.0/milking/autodry/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_autodry_repro_for_cattle(
    session: requests.Session,
    cattle_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch reproduction context for auto-dry of a cow.

    Endpoint: GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/repro/{cattle_id}
    """
    return dairynet_request(
        session,
        "GET",
        f"/dairybox.herdmanagement/v1.0/milking/autodry/repro/{quote(cattle_id, safe='')}",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_process_report(
    session: requests.Session,
    milking_parlors: str,
    report_date_from: str,
    report_date_until: str,
    sort_column: str = "reportDate",
    sort_descending: bool = True,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch the DairyNet process report using an authenticated session."""
    normalized_base_url = base_url.rstrip("/")
    report_url = f"{normalized_base_url}/dairynetbackend/analysis/processreport"
    params = {
        "milkingParlors": milking_parlors,
        "reportDateFrom": report_date_from,
        "reportDateUntil": report_date_until,
        "sortColumn": sort_column,
        "sortDescending": str(sort_descending).lower(),
    }
    report_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    report_response = session.get(
        report_url,
        params=params,
        headers=report_headers,
        timeout=timeout,
    )
    report_response.raise_for_status()
    return report_response


def pull_process_report(
    milking_parlors: str,
    report_date_from: str,
    report_date_until: str,
    username: str | None = None,
    password: str | None = None,
    sort_column: str = "reportDate",
    sort_descending: bool = True,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Authenticate and fetch the DairyNet process report in one call."""
    session = authenticate_dairynet_session(
        username=username,
        password=password,
        base_url=base_url,
    )
    return fetch_process_report(
        session=session,
        milking_parlors=milking_parlors,
        report_date_from=report_date_from,
        report_date_until=report_date_until,
        sort_column=sort_column,
        sort_descending=sort_descending,
        base_url=base_url,
        timeout=timeout,
    )


# =============================================================================
# 5. Feeding & Concentrate / Ration Performance APIs
# =============================================================================


def fetch_feeding_overview_preview(
    session: requests.Session,
    time_range: str = "LAST72HOURS",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch per-cow individual feeding & milk performance preview (claims, consumed, rest %, milk 24h/7d).

    Endpoint: GET /dairynetbackend/feeding/feedingoverview/preview?timeRange={time_range}
    """
    return dairynet_request(
        session,
        "GET",
        "/feeding/feedingoverview/preview",
        params={"timeRange": time_range},
        base_url=base_url,
        timeout=timeout,
    )


def fetch_all_feeds_in_use(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch all feeds currently in use on the farm.

    Endpoint: GET /dairynetbackend/feeding/feedconsumptionreport/allFeedsInUse
    """
    return dairynet_request(
        session,
        "GET",
        "/feeding/feedconsumptionreport/allFeedsInUse",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_group_feed_consumption_compare(
    session: requests.Session,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch group feed consumption comparison data.

    Endpoint: GET /dairynetbackend/feeding/feedconsumptionreport/getGroupFeedConsumptionCompare
    """
    return dairynet_request(
        session,
        "GET",
        "/feeding/feedconsumptionreport/getGroupFeedConsumptionCompare",
        base_url=base_url,
        timeout=timeout,
    )


def fetch_feed_efficiency_report(
    session: requests.Session,
    filter_payload: dict[str, Any],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch feed efficiency and milk weight report data.

    Endpoint: POST /dairynetbackend/feeding/feedconsumptionreport/feedEfficiency
    """
    return dairynet_request(
        session,
        "POST",
        "/feeding/feedconsumptionreport/feedEfficiency",
        json_body=filter_payload,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_feed_consumption_ingredients_report(
    session: requests.Session,
    filter_payload: dict[str, Any],
    report_mode: str = "HISTORY",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch feed consumption ingredients report ('HISTORY' or 'COST').

    Endpoint: POST /dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportIngredients
              or /feeding/feedconsumptionreport/feedCostReportIngredients
    """
    endpoint = (
        "feedCostReportIngredients"
        if report_mode.upper() == "COST"
        else "feedHistoryReportIngredients"
    )
    return dairynet_request(
        session,
        "POST",
        f"/feeding/feedconsumptionreport/{endpoint}",
        json_body=filter_payload,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_feed_consumption_rations_report(
    session: requests.Session,
    filter_payload: dict[str, Any],
    report_mode: str = "HISTORY",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Fetch feed consumption rations report ('HISTORY' or 'COST').

    Endpoint: POST /dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportRations
              or /feeding/feedconsumptionreport/feedCostReportRations
    """
    endpoint = (
        "feedCostReportRations"
        if report_mode.upper() == "COST"
        else "feedHistoryReportRations"
    )
    return dairynet_request(
        session,
        "POST",
        f"/feeding/feedconsumptionreport/{endpoint}",
        json_body=filter_payload,
        base_url=base_url,
        timeout=timeout,
    )


def export_feed_consumption_csv(
    session: requests.Session,
    filter_payload: dict[str, Any],
    export_type: str = "rations",
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 20,
) -> requests.Response:
    """Export feed consumption report as CSV ('rations' or 'ingredients').

    Endpoint: POST /dairynetbackend/feeding/feedconsumptionreport/exportRations
              or /feeding/feedconsumptionreport/exportIngredients
    """
    endpoint = (
        "exportRations" if export_type.lower() == "rations" else "exportIngredients"
    )
    return dairynet_request(
        session,
        "POST",
        f"/feeding/feedconsumptionreport/{endpoint}",
        json_body=filter_payload,
        base_url=base_url,
        timeout=timeout,
    )


def fetch_feed_ration_changes(
    session: requests.Session,
    query_period: str,
    barn_group_ids: list[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 15,
) -> requests.Response:
    """Fetch group feeding ration changes for a query period ('SEVEN_DAYS', 'TWENTYONE_DAYS', 'EIGHT_WEEKS', 'ONE_YEAR').

    Endpoint: GET /dairynetbackend/group-feeding/feeding/feed-ration/feed-ration-changes
    """
    return dairynet_request(
        session,
        "GET",
        "/group-feeding/feeding/feed-ration/feed-ration-changes",
        params={"queryPeriod": query_period, "barnGroupIds": barn_group_ids},
        base_url=base_url,
        timeout=timeout,
    )

import os

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

    # Mirror auth/CSRF cookies into headers for Spring/Angular endpoints.
    for cookie_name, header_name in _TOKEN_COOKIE_HEADERS:
        if cookie_name in session.cookies:
            session.headers[header_name] = session.cookies[cookie_name]

    return session


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

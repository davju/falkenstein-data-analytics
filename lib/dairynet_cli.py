#!/usr/bin/env python3
"""Interactive and command-line tool for DairyNet API endpoints in ``lib/dairynet.py``.

Features:
- Automatic authentication against DairyNet (via ``.env`` / environment variables
  ``dairynet_username`` and ``dairynet_password`` or CLI flags).
- Groups all 126 DairyNet functions into 9 logical categories.
- Lists categories and endpoints with filtering and search.
- Provides detailed explanations, HTTP methods/paths, parameter specs, response
  summaries, and usage examples for every endpoint.
- Allows choosing and executing individual endpoints either via CLI arguments
  or through an interactive menu.
"""

from __future__ import annotations

import argparse
import datetime as dt
import inspect
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

import lib.dairynet as dn


@dataclass(frozen=True)
class CategoryInfo:
    """Metadata for an endpoint category."""

    number: int
    slug: str
    title: str
    description: str


@dataclass(frozen=True)
class ParameterSpec:
    """Metadata for a single endpoint function parameter."""

    name: str
    type_str: str
    required: bool
    default: Any
    description: str
    example: str = ""


@dataclass(frozen=True)
class EndpointInfo:
    """Complete metadata for a single endpoint function in ``lib/dairynet.py``."""

    index: int
    name: str
    short_name: str
    category: CategoryInfo
    func: Callable[..., Any]
    http_method: str
    http_path: str
    summary: str
    explanation: str
    response_summary: str
    parameters: tuple[ParameterSpec, ...] = field(default_factory=tuple)


CATEGORIES: tuple[CategoryInfo, ...] = (
    CategoryInfo(
        number=1,
        slug="auth",
        title="Authentication, Session & Core Request",
        description=(
            "Session login/logout, user credentials & permissions, and the low-level "
            "authenticated request helper."
        ),
    ),
    CategoryInfo(
        number=2,
        slug="system",
        title="System Settings, Versions, Localization, Navigation & Notifications",
        description=(
            "DairyNetBox software versions, feature flags, active topics, backend enums, "
            "i18n dictionaries, UI navigation trees, system clocks, regional/unit settings, "
            "notifications, micro-frontend services, and WebSocket info."
        ),
    ),
    CategoryInfo(
        number=3,
        slug="cattle",
        title="Cattle & Herd Master Data",
        description=(
            "Paginated herd cattle tables, single-animal master data, animal status summaries, "
            "batch lookups by UUID or barn animal number, cows without assigned mother, "
            "per-cow system parameters, and global search."
        ),
    ),
    CategoryInfo(
        number=4,
        slug="groups",
        title="Cattle Groups, Table Presets, Animal Choice & Dynamic Lists (DNList)",
        description=(
            "Milking/barn/feeding/administrative cattle groups, group memberships, "
            "group milking statistics, cattle table column presets, Animal Choice "
            "(Tierauswahl) rule sets, and DNList dynamic list definitions."
        ),
    ),
    CategoryInfo(
        number=5,
        slug="actions",
        title="Animal Actions, Reproduction/Insemination & Sorting",
        description=(
            "Planned/saved/booked animal action counts, action types, action calendar, "
            "insemination history lookups, and sorting/selection area configurations."
        ),
    ),
    CategoryInfo(
        number=6,
        slug="dashboard",
        title="Dashboard & Herd KPI Widgets",
        description=(
            "Dashboard layout settings and KPI widgets for herd-wide per-cow milk yield, "
            "lactation overview, session milk yield, reproduction KPIs, stall/box performance, "
            "farm monobox performance, milk quality, BCS development, calvings, and breeds."
        ),
    ),
    CategoryInfo(
        number=7,
        slug="parlors",
        title="Milking Parlors & Milking Sessions",
        description=(
            "Milking parlor configurations, DairyRobot monobox stalls, latest automated "
            "monobox sessions, monobox/rotary session statuses, and session plans."
        ),
    ),
    CategoryInfo(
        number=8,
        slug="milking",
        title="Milk Visits, Milk Control, Auto-Dry & Process Reports",
        description=(
            "Individual cow milk visits, quarter cell-count/conductivity graphs, process "
            "result & control parameters, milking allowances/plans, manual milking entry, "
            "auto-dry plans, and milking process reports."
        ),
    ),
    CategoryInfo(
        number=9,
        slug="feeding",
        title="Feeding, Concentrate & Ration Performance",
        description=(
            "Per-cow concentrate feeding overview (claims, consumed, rest %, milk 24h/7d), "
            "active feeds, group feed consumption comparisons, feed efficiency/cost/history "
            "reports, CSV exports, and ration change history."
        ),
    ),
)

CATEGORY_BY_SLUG: dict[str, CategoryInfo] = {c.slug: c for c in CATEGORIES}
CATEGORY_BY_NUMBER: dict[int, CategoryInfo] = {c.number: c for c in CATEGORIES}


PARAMETER_HELP: dict[str, tuple[str, str]] = {
    "method": ("HTTP method ('GET', 'POST', 'PUT', 'DELETE', 'PATCH').", "GET"),
    "path": ("Backend API path (relative to /dairynetbackend or full service path).", "/version"),
    "params": ("Optional query string parameters as a JSON object.", '{"pageIndex": 1}'),
    "json_body": ("Optional JSON request body payload.", '["uuid-1"]'),
    "data": ("Optional form/raw request body.", ""),
    "headers": ("Optional extra HTTP headers as a JSON object.", '{"Accept": "application/json"}'),
    "username": ("DairyNet username (defaults to dairynet_username in .env).", ""),
    "password": ("DairyNet password (defaults to dairynet_password in .env).", ""),
    "locale": ("Locale code for translations/notifications (e.g. 'de-DE', 'en-US', 'default').", "de-DE"),
    "farm_site_id": (
        "Farm site UUID (discoverable via fetch_platform_credentials -> person.farmId).",
        "17bc3185-8e2c-4742-8e6a-e142e6afb71a",
    ),
    "include_confirmed": ("Whether to include already-confirmed notifications.", "false"),
    "include_read": ("Whether to include already-read notifications.", "false"),
    "reference_id": ("Reference entity UUID to fetch notifications for.", ""),
    "service_name": (
        "Federated micro-frontend service name ('service-lkv-adapter' or 'service-cowscout-integration').",
        "service-lkv-adapter",
    ),
    "timestamp_ms": ("Optional epoch timestamp in milliseconds for SockJS info check.", "1763300000000"),
    "page_index": ("1-based page number to fetch.", "1"),
    "page_size": ("Number of cattle rows per page.", "240"),
    "sort_column": ("Column name to sort results by.", "animalnumber"),
    "sort_descending": ("Whether to sort in descending order.", "false"),
    "herd_group_filter": ("Optional herd/group filter object as JSON.", ""),
    "extra_filters": ("Optional extra query filter key-value pairs as JSON.", ""),
    "subpath": ("Optional subpath appended to /herdmanagement/cattle.", ""),
    "cattle_id": (
        "Single animal UUID (discoverable via fetch_cattle_page or fetch_avmlk_statistic_widget).",
        "",
    ),
    "cattle_ids": (
        "List of animal UUIDs (comma-separated or JSON array, e.g. 'uuid1,uuid2').",
        '["uuid1", "uuid2"]',
    ),
    "animal_numbers": (
        "List of barn animal numbers (comma-separated or JSON array, e.g. '32,92,146').",
        "[32, 92, 146]",
    ),
    "search_text": ("Free-text query (animal number, ear tag, or cow name).", "32"),
    "scopes": (
        "Optional list of search scopes (e.g. 'CATTLE,CATTLE_DETAILS_PAGES').",
        '["CATTLE", "CATTLE_DETAILS_PAGES"]',
    ),
    "usage": (
        "Cattle group usage type ('Milking', 'Barn', 'Feeding', 'Administrative').",
        "Milking",
    ),
    "topic_name": ("Topic name for administrative cattle groups (e.g. 'CATTLE', 'MILKING_ALL').", "CATTLE"),
    "group_id": (
        "Cattle group UUID (discoverable via fetch_cattle_groups_simple_list).",
        "",
    ),
    "preset_id": (
        "Column preset definition UUID (discoverable via fetch_preset_definitions_simple_list).",
        "",
    ),
    "rule_set_id": (
        "Animal choice rule set UUID (discoverable via fetch_animal_choice_simple_list).",
        "",
    ),
    "action_id": ("Animal action UUID to find related actions for.", ""),
    "reference_date": ("ISO reference date (YYYY-MM-DD) for candidate inseminations.", "2026-11-16"),
    "sorting_area_ids": (
        "List of sorting area UUIDs (discoverable via fetch_sorting_areas_simple_list).",
        "",
    ),
    "days": ("Number of days for milk yield overview (e.g. 7).", "7"),
    "widget_id": (
        "Dashboard widget UUID (discoverable via fetch_dashboard_settings).",
        "0303ffdd-3ce2-436e-9506-6861d9f972ba",
    ),
    "days_back": ("Number of past days to query (e.g. 3, 7, 14, 30).", "7"),
    "barn_group_name": ("Name of the barn group to query.", ""),
    "calculation_type": ("Calculation type enum for session milk yield widget.", "PER_COW"),
    "box_id": ("Milking box number or ID (e.g. 1, 2, 3).", "1"),
    "milking_parlor_ids": (
        "List of milking parlor UUIDs (discoverable via fetch_milking_parlors_simple_list).",
        '["775502b4-40cf-48d3-bf59-1e464a0a45c1"]',
    ),
    "animal_choice_rule_set_id": (
        "Animal choice rule set UUID (discoverable via fetch_animal_choice_widget_rulesets).",
        "",
    ),
    "milking_group_id": ("Optional milking group UUID to filter BCS development data.", ""),
    "parlor_id": (
        "Milking parlor UUID (discoverable via fetch_milking_parlors_simple_list).",
        "775502b4-40cf-48d3-bf59-1e464a0a45c1",
    ),
    "parlor_type": (
        "Milking parlor type ('AUTOMATED_MONOBOX', 'AUTOMATED_ROTARY', 'CONVENTIONAL_ROTARY').",
        "AUTOMATED_MONOBOX",
    ),
    "session_id": (
        "Milking session UUID (discoverable via fetch_latest_monobox_session).",
        "",
    ),
    "cattle_group": ("Optional cattle group filter name (or 'ALL_ANIMALS').", "ALL_ANIMALS"),
    "plan_id": ("Milking session plan UUID (discoverable via fetch_milking_session_plans).", ""),
    "milk_visit_id": (
        "Milk visit UUID (discoverable via fetch_milk_visits_for_cattle).",
        "",
    ),
    "milking_parlors": (
        "Milking parlor UUID(s) for the process report (e.g. '775502b4-40cf-48d3-bf59-1e464a0a45c1').",
        "775502b4-40cf-48d3-bf59-1e464a0a45c1",
    ),
    "report_date_from": ("Start date for process report (YYYY-MM-DD).", "2026-11-09"),
    "report_date_until": ("End date for process report (YYYY-MM-DD).", "2026-11-16"),
    "time_range": ("Feeding overview time window (e.g. 'LAST72HOURS', 'LAST24HOURS').", "LAST72HOURS"),
    "filter_payload": (
        "JSON filter payload object for feeding consumption/efficiency reports.",
        '{"startDate": "2026-11-09", "endDate": "2026-11-16"}',
    ),
    "report_mode": ("Feeding report mode ('HISTORY' or 'COST').", "HISTORY"),
    "export_type": ("CSV export target ('rations' or 'ingredients').", "rations"),
    "query_period": (
        "Ration change period ('SEVEN_DAYS', 'TWENTYONE_DAYS', 'EIGHT_WEEKS', 'ONE_YEAR').",
        "SEVEN_DAYS",
    ),
    "barn_group_ids": (
        "List of barn group UUIDs (discoverable via fetch_cattle_groups_by_usage with usage='Barn').",
        "",
    ),
}


# Mapping of function_name -> (category_slug, http_method, http_path, response_summary_and_explanation)
_ENDPOINT_METADATA: dict[str, tuple[str, str, str, str]] = {
    # 1. Authentication, Session & Core Request
    "dairynet_request": (
        "auth",
        "ANY",
        "/dairynetbackend/{path}",
        "Low-level helper that sends an authenticated HTTP request (GET/POST/PUT/DELETE/PATCH) "
        "to any DairyNet backend or federated service path, automatically syncing XSRF-TOKEN and "
        "X-DAIRYNET-TOKEN headers and raising on HTTP errors.",
    ),
    "authenticate_dairynet_session": (
        "auth",
        "POST",
        "/dairynetbackend/platform/user/authenticate",
        "Authenticates the user with form-urlencoded username and password (falling back to "
        "dairynet_username and dairynet_password in .env), sets JSESSIONID, XSRF-TOKEN, and "
        "X-DAIRYNET-TOKEN cookies/headers, and returns an authorized requests.Session.",
    ),
    "logout_dairynet_session": (
        "auth",
        "POST",
        "/dairynetbackend/platform/user/logout",
        "Terminates the active DairyNet user session on the server.",
    ),
    "fetch_platform_credentials": (
        "auth",
        "GET",
        "/dairynetbackend/platform/credentials",
        "Returns current user profile, userId, rights (READ, WRITE, BOOK_ANIMAL_ACTION, etc.), "
        "company (companyId), person (farmId), module versions, buildInfo, and JWT token.",
    ),
    # 2. System Settings, Versions, Localization, Navigation & Notifications
    "fetch_version": (
        "system",
        "GET",
        "/dairynetbackend/version",
        "Returns version strings for dairynetbox (e.g. 46.0.10), commonApi, processControlApi, "
        "mobileApi, cowScoutApi, farmViewApi, icarProviderApi, groupFeedingApi, processManagerApi, "
        "parlorViewApi, and cattleEyeApi.",
    ),
    "fetch_current_dairynet_release": (
        "system",
        "GET",
        "/dairynetbackend/systemsettings/current-dairynet-release",
        "Returns the current DairyNet release version string (e.g. '47.0.24').",
    ),
    "fetch_system_settings": (
        "system",
        "GET",
        "/dairynetbackend/systemsettings",
        "Returns global system feature flags: afsFeedingEnabled, dairyNetBoxStandaloneWithoutAnimals, "
        "dairyNetBoxComplete, latestInstallationDate, moduleSecurityEnabled, cowScoutActive, dnListEnabled.",
    ),
    "fetch_active_topics": (
        "system",
        "GET",
        "/dairynetbackend/admin/topic/allActive",
        "Returns a JSON list of all licensed and enabled feature topics on the DairyNetBox "
        "(e.g. CATTLE, COWSCOUT, MILKING_ALL, FEEDING_ALL, HEALTH_HERD).",
    ),
    "fetch_enums": (
        "system",
        "GET",
        "/dairynetbackend/enums",
        "Returns all backend enumeration definitions (AnimalActionType, AllowanceReasonEnum, "
        "AttentionType, CattleType, CowStatus, etc.) with their i18nPrefix and option keys.",
    ),
    "fetch_locales": (
        "system",
        "GET",
        "/dairynetbackend/platform/localize/locales",
        "Returns a dictionary mapping supported UI locale codes (DE_DE, EN_US, etc.) to display names.",
    ),
    "fetch_localization": (
        "system",
        "GET",
        "/dairynetbackend/platform/localize/{locale}",
        "Returns the full i18n key-to-label translation dictionary (~840 KB) for the given locale "
        "(e.g. 'de-DE' or 'default' for English), used to translate enum keys, column headers, and KPI names.",
    ),
    "fetch_topbar_navigation": (
        "system",
        "GET",
        "/dairynetbackend/navigation/topbar",
        "Returns the full topbar navigation tree grouped by category (HERDMANAGEMENT, MILKING, "
        "REPRODUCTION, HEALTH, FEEDING) with page routes and required feature topics.",
    ),
    "fetch_sidebar_navigation": (
        "system",
        "GET",
        "/dairynetbackend/navigation/sidebar",
        "Returns the settings and system administration sidebar navigation tree.",
    ),
    "fetch_mymenu_navigation": (
        "system",
        "GET",
        "/dairynetbackend/navigation/mymenu",
        "Returns user-configured custom 'My Menu' navigation tabs.",
    ),
    "fetch_cattle_details_navigation": (
        "system",
        "GET",
        "/dairynetbackend/navigation/cattle-details",
        "Returns the available sub-navigation tabs for the single-cow detail view.",
    ),
    "fetch_local_system_time": (
        "system",
        "GET",
        "/dairynetbackend/systemadministration/localSystemTime",
        "Returns the DairyNetBox local ISO timestamp as plain text (e.g. '2026-11-16T15:17:08.271').",
    ),
    "fetch_utc_system_time": (
        "system",
        "GET",
        "/dairynetbackend/systemadministration/utcSystemTime",
        "Returns the DairyNetBox UTC ISO timestamp as plain text.",
    ),
    "fetch_country_or_region": (
        "system",
        "GET",
        "/dairynetbackend/settings/countryorregion",
        "Returns the configured country or region setting (e.g. 'GERMANY').",
    ),
    "fetch_measurement_system": (
        "system",
        "GET",
        "/dairynetbackend/settings/measurementsystem",
        "Returns the configured unit measurement system (e.g. 'METRIC').",
    ),
    "fetch_currency": (
        "system",
        "GET",
        "/dairynetbackend/settings/currency",
        "Returns the configured currency code (e.g. 'EUR').",
    ),
    "fetch_system_control_parameters": (
        "system",
        "GET",
        "/dairynetbackend/settings/systemcontrolparameter",
        "Returns farm-wide system control parameters.",
    ),
    "fetch_farm_site": (
        "system",
        "GET",
        "/dairynetbackend/core/farmsite/{farm_site_id}",
        "Returns details for a specific farm site by UUID (e.g. '17bc3185-8e2c-4742-8e6a-e142e6afb71a').",
    ),
    "fetch_notifications": (
        "system",
        "GET",
        "/dairynetbackend/notification/read/{locale}/{includeConfirmed}/{includeRead}",
        "Returns {'nbrOfNotifications': N, 'elements': [...]} containing active system and animal notifications.",
    ),
    "fetch_notifications_for_reference": (
        "system",
        "GET",
        "/dairynetbackend/notification/notificationsForReference/{reference_id}/{locale}",
        "Returns notifications linked to a specific reference entity UUID.",
    ),
    "fetch_module_federation_services": (
        "system",
        "GET",
        "/dairynetbackend/module-federation-info/services",
        "Returns registered external micro-frontend services and ports (e.g. service-lkv-adapter "
        "on 3001, service-cowscout-integration on 8089).",
    ),
    "fetch_federated_service_info": (
        "system",
        "GET",
        "/{service_name}/api/info",
        "Returns metadata (label, menuCategory, requiredUserRight, topics) for a federated service.",
    ),
    "fetch_websocket_info": (
        "system",
        "GET",
        "/dairynetbackend/ws/info",
        "Returns SockJS/WebSocket handshake metadata (websocket: true, cookie_needed: true, entropy).",
    ),
    # 3. Cattle & Herd Master Data
    "fetch_cattle_page": (
        "cattle",
        "GET",
        "/dairynetbackend/herdmanagement/cattle",
        "Paginated cattle table endpoint. Returns {content: [...], totalElements, currentPage, "
        "pageSize, totalPages, queryTimeInMilliSeconds} with full herd management row attributes.",
    ),
    "fetch_cattle_by_id": (
        "cattle",
        "GET",
        "/dairynetbackend/herdmanagement/cattle/{cattle_id}",
        "Returns the complete master data record for a single animal by its cattle UUID.",
    ),
    "fetch_cattle_information": (
        "cattle",
        "GET",
        "/dairynetbackend/herdmanagement/cattle/information/{cattle_id}",
        "Returns animal status, reproductive state, and action summary information for a single cow.",
    ),
    "fetch_cattle_by_ids_including_inactive": (
        "cattle",
        "POST",
        "/dairynetbackend/herdmanagement/cattle/animalsByCattleIdListIncludingInactive",
        "Batch-fetches full cattle objects for a list of cattle UUIDs, including inactive/culled animals.",
    ),
    "fetch_cattle_identifiers_by_ids_including_inactive": (
        "cattle",
        "POST",
        "/dairynetbackend/herdmanagement/cattle/animalIdentifiersByCattleIdListIncludingInactive",
        "Batch-fetches lightweight identifier objects (animalnumber, officialEarTag, animalName) "
        "for a list of cattle UUIDs, including inactive animals.",
    ),
    "fetch_cattle_by_animal_numbers": (
        "cattle",
        "POST",
        "/dairynetbackend/herdmanagement/cattle/animalsByAnimalNumberList",
        "Batch-fetches full cattle records for a list of barn animal numbers (e.g. [32, 92, 146]).",
    ),
    "fetch_cattle_without_mother": (
        "cattle",
        "GET",
        "/dairynetbackend/herdmanagement/cattle/cattleWithoutMother",
        "Returns all cattle records in the herd that do not have a mother assigned.",
    ),
    "fetch_cattle_system_parameters": (
        "cattle",
        "GET",
        "/dairynetbackend/herdmanagement/cattlesystemparameters/{cattle_id}",
        "Returns system parameters for a single cow, including expectedMilkVisitTimeStamp "
        "(next milk allowance timestamp).",
    ),
    "fetch_cattle_navigation_details": (
        "cattle",
        "POST",
        "/dairynetbackend/cattleinfo/navigation-details",
        "Batch-fetches header/navigation summary (id, animalnumber, animalName, cattleType, "
        "cowStatus, lactationNumber) for a list of cattle UUIDs.",
    ),
    "search_global_text": (
        "cattle",
        "GET",
        "/dairynetbackend/search/globalsearch/textSearch",
        "Global text search across cattle, pages, and lists by ear tag, animal number, or name. "
        "Returns {searchResultByCategory: ...}.",
    ),
    # 4. Cattle Groups, Table Presets, Animal Choice & Dynamic Lists (DNList)
    "fetch_cattle_groups_by_usage": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/findAllByGroupUsage",
        "Returns cattle groups for the specified usage type ('Milking', 'Barn', 'Feeding', "
        "'Administrative'), including id, name, color, and cattleGroupMembersCount.",
    ),
    "fetch_administrative_cattle_groups_by_topic": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/findAdministrativeByTopicName",
        "Returns administrative cattle groups filtered by topic name.",
    ),
    "fetch_cattle_groups_simple_list": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/simpleList",
        "Returns a simple list of all cattle groups configured on the farm.",
    ),
    "fetch_cattle_group_by_id": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/{group_id}",
        "Returns full configuration and details for a specific cattle group by UUID.",
    ),
    "fetch_cattle_group_memberships": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/memberships/{cattle_id}",
        "Returns all cattle groups that a specific cow currently belongs to.",
    ),
    "fetch_barn_groups_with_rotary_values": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/findAllBarnGroupsWithRotaryValues",
        "Returns all barn groups along with their rotary parlor configuration values.",
    ),
    "fetch_herd_and_group_select_options": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/cattlegroup/herdandgroupselect",
        "Returns all selectable herd, group, and animal-choice filter objects used by the "
        "cattle list selector dropdown.",
    ),
    "fetch_milking_group_statistics": (
        "groups",
        "GET",
        "/dairynetbackend/dairynet.herdmanagement/v1.0/milkinggroupstatistics/basic/{group_id}",
        "Returns basic milking statistics for a specific cattle group UUID.",
    ),
    "fetch_preset_definitions_simple_list": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/presetdefinitions/simpleList",
        "Returns available column preset definitions for cattle tables.",
    ),
    "fetch_preset_definitions_flat": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/presetdefinitions/flat",
        "Returns flat-mapped column preset definitions for cattle tables.",
    ),
    "fetch_preset_available_columns": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/presetdefinitions/availablecolumns",
        "Returns every available data column that can be included in a cattle table preset.",
    ),
    "fetch_preset_definition_by_id": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/presetdefinitions/{preset_id}",
        "Returns a single column preset definition by its preset UUID.",
    ),
    "fetch_animal_choice_simple_list": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/animalchoice/simpleList",
        "Returns all configured Animal Choice (Tierauswahl) rule sets in a simple list.",
    ),
    "fetch_animal_choice_by_id": (
        "groups",
        "GET",
        "/dairynetbackend/herdmanagement/animalchoice/{rule_set_id}",
        "Returns the full rule/criterion definition and matching animals for an Animal Choice rule set.",
    ),
    "fetch_dnlist_definitions": (
        "groups",
        "GET",
        "/dairynetbackend/dnlist/definition",
        "Returns all configured DNList dynamic list definitions (id, name, nameI18nKey).",
    ),
    # 5. Animal Actions, Reproduction/Insemination & Sorting
    "fetch_animal_action_list_count": (
        "actions",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/listcount",
        "Returns the count of planned, saved, and booked animal actions across action states.",
    ),
    "fetch_possible_animal_action_names": (
        "actions",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getPossibleAnimalActionNames",
        "Returns all possible animal action type names supported by the DairyNet backend.",
    ),
    "fetch_related_animal_actions": (
        "actions",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getRelatedActions/{action_id}",
        "Returns related planned or booked actions linked to a specific animal action UUID.",
    ),
    "fetch_animal_action_calendar": (
        "actions",
        "GET",
        "/dairynetbackend/animalaction/calendar",
        "Returns the full animal action calendar (columns, scheduled actions, existingAnimalActionTypes).",
    ),
    "fetch_last_successful_insemination": (
        "actions",
        "GET",
        "/dairynetbackend/herdmanagement/animalaction/insemination/findLastSuccessfulInsemination/{cattle_id}",
        "Returns the most recent successful insemination action for a specific cow.",
    ),
    "fetch_possible_successful_inseminations": (
        "actions",
        "GET",
        "/dairynetbackend/herdmanagement/animalaction/insemination/findPossibleSuccessfulInseminations/{cattle_id}/{reference_date}",
        "Returns candidate inseminations relative to a reference date that could have resulted in a pregnancy/calving.",
    ),
    "fetch_sorting_areas_simple_list": (
        "actions",
        "GET",
        "/dairynetbackend/sorting/sortingarea/simpleList",
        "Returns a simple list of all sorting/selection areas on the farm.",
    ),
    "fetch_sorting_areas_by_ids": (
        "actions",
        "GET",
        "/dairynetbackend/sorting/sortingarea/byIds",
        "Returns sorting areas matching the given list of sorting area UUIDs.",
    ),
    "fetch_sorting_timeframe_options": (
        "actions",
        "GET",
        "/dairynetbackend/sorting/sortingcommand/timeframe-options/{cattle_id}",
        "Returns valid sorting timeframe options (validFrom, validUntil) for sorting a specific cow.",
    ),
    # 6. Dashboard & Herd KPI Widgets
    "fetch_dashboard_settings": (
        "dashboard",
        "GET",
        "/dairynetbackend/dashboard/settings",
        "Returns the dashboard layout and widgetSettings array (containing each configured widget's "
        "id and widgetName). Use this to look up widget_id values for widget endpoints.",
    ),
    "fetch_available_dashboard_widgets": (
        "dashboard",
        "GET",
        "/dairynetbackend/dashboard/availableWidgets",
        "Returns all widget types that can be added to the DairyNet dashboard.",
    ),
    "fetch_avmlk_statistic_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/avmlkStatistic",
        "Herd-wide per-cow milk yield & lactation list. Returns an array of all lactating cows with "
        "cattleId, animalNumber, lactation, dateOfAverage, dayOfLactation, and averageMilkWeightInGram.",
    ),
    "fetch_milk_yield_overview_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/dashboard/widgets/milkyieldoverview/{days}",
        "Returns daily average milk yield in grams broken down by 1st, 2nd, 3rd+ lactation and "
        "overall herd average over N days, plus comparison to the previous period.",
    ),
    "fetch_avg_milk_yield_per_session_widget_settings": (
        "dashboard",
        "GET",
        "/dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview",
        "Returns configured barn groups and settings for the session milk yield overview widget.",
    ),
    "fetch_avg_milk_yield_per_session_widget_data": (
        "dashboard",
        "GET",
        "/dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview/data",
        "Returns session-by-session average milk yield points (avgMilkYieldOfXSessionsOverviewWidgetPointDTOList) "
        "for a barn group.",
    ),
    "fetch_reproduction_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/reproduction",
        "Returns herd reproduction KPIs: averageDaysInMilk, daysOpen, inseminationInterval, "
        "calvingInterval, inseminationIndexDairyCow, inseminationIndexHeifer, pregnancyRateDairyCow, "
        "pregnancyRateHeifer.",
    ),
    "fetch_stall_performance_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/stallperformance",
        "Returns 24h milk yield and milking duration per milking box (absoluteBoxNumber, "
        "milkingWeight24HoursInGram, milkingWeightDayBefor24HoursInGram, milkingDuration24HoursInSeconds).",
    ),
    "fetch_stall_performance_details": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/stallperformance/details",
        "Returns detailed attachment performance (attachPerformance) and problematicMilkings for a specific box.",
    ),
    "fetch_farm_performance_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/performance/farm",
        "Returns farm-wide monobox KPIs (milkYield, milkYieldPerBox, milkYieldPerCow, cowsMilked, "
        "numberOfMilkings, numberOfMilkingsPerCow) with deltas to yesterday, 7-day, and 30-day averages.",
    ),
    "fetch_box_performance_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/performance/box",
        "Returns per-box performance comparison values (parlorNames, boxValues) for a widget UUID.",
    ),
    "fetch_monobox_performance_widget_settings": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/monoboxPerformance",
        "Returns box selection settings for the monobox performance dashboard widget.",
    ),
    "fetch_milking_process_performance_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/milking-process-performance/{widget_id}",
        "Returns milking process KPIs (attachmentTime, numberOfIncompleteMilkings, "
        "milkingsPerHourAndBox) and overallTargetReachedInPercent.",
    ),
    "fetch_milk_yield_kpi_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/milkyieldkpi/{widget_id}",
        "Returns milk yield KPIs (totalMilkYield, milkYieldCow, numberOfMilkings) and target percentages.",
    ),
    "fetch_milk_quality_kpi_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/milkqualitykpi",
        "Returns milk quality KPI widget data for the dashboard.",
    ),
    "fetch_milk_productivity_parlor_settings": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor/{widget_id}",
        "Returns milkingParlorIds bound to a milk productivity KPI widget.",
    ),
    "save_milk_productivity_parlor_settings": (
        "dashboard",
        "POST",
        "/dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor",
        "Updates the milking parlors bound to a milk productivity KPI widget.",
    ),
    "fetch_animal_choice_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/animalchoice",
        "Returns the list of animalChoiceRuleSetId items (e.g. Zellzahl, Leitwert, Melkbesuch überfällig, "
        "Milchmengenalarm) configured on an Animal Choice dashboard widget.",
    ),
    "fetch_animal_choice_cattle_count": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/animalchoice/cattlecount",
        "Returns the integer count of cattle currently matching an Animal Choice rule set.",
    ),
    "fetch_animal_choice_widget_rulesets": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/animalchoice/rulesets",
        "Returns all rule sets available for selection in the Animal Choice dashboard widget.",
    ),
    "fetch_dnlist_widget_settings": (
        "dashboard",
        "GET",
        "/dairynetbackend/dnlist/dashboard/widget/list/settings/{widget_id}",
        "Returns configured listDefinitionIds for a DNList dashboard widget.",
    ),
    "fetch_dnlist_widget_data": (
        "dashboard",
        "GET",
        "/dairynetbackend/dnlist/dashboard/widget/list/data/{widget_id}",
        "Returns listId, listName, and listKPI entries for a DNList dashboard widget.",
    ),
    "fetch_bcs_development_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/bcsDevelopment",
        "Returns per-cow Body Condition Score (bcsScore), dayOfLactation, and lactationNumber.",
    ),
    "fetch_calving_statistic_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/calvingStatistic/{days_back}",
        "Returns calving counts grouped by CalvingStatisticWidgetEnum over the past days_back days.",
    ),
    "fetch_cattle_status_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/cattleStatus",
        "Returns herd cattle headcounts grouped by reproductive and lactation status (lactating, "
        "dry, inseminated, pregnant, etc.).",
    ),
    "fetch_cattle_breed_performance_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/cattlebreedperformance",
        "Returns daily average milk weight in grams by cattle breed and lactation "
        "(dailyAverageFirstLactation, dailyAverageSecondLactation, etc.).",
    ),
    "fetch_cattle_breed_proportion_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/cattlebreedproportion",
        "Returns cattle headcount breakdown per breed (cattleBreedName, cattleCount).",
    ),
    "fetch_animal_action_calendar_widget": (
        "dashboard",
        "GET",
        "/dairynetbackend/home/dashboard/widgets/animalactioncalendar",
        "Returns scheduled animal actions for the dashboard animal action calendar widget.",
    ),
    # 7. Milking Parlors & Milking Sessions
    "fetch_available_parlor_types": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingparlor/availableParlorTypes",
        "Returns milking parlor types present on the farm (e.g. ['AUTOMATED_MONOBOX']).",
    ),
    "fetch_milking_parlors_simple_list": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingparlor/simpleList",
        "Returns all milking parlors (e.g. Dairyrobot), farm site mapping, and all individual "
        "milkingParlorBoxes (stalls 1, 2, 3).",
    ),
    "fetch_milking_parlor_by_id": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingparlor/{parlor_id}",
        "Returns details for a specific milking parlor by UUID.",
    ),
    "fetch_milking_parlors_by_type": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingparlor/byType",
        "Returns milking parlors matching the specified parlor type (e.g. 'AUTOMATED_MONOBOX').",
    ),
    "fetch_monobox_parlor_boxes": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingparlor/monobox/boxes",
        "Returns all DairyRobot monobox stalls/boxes configured on the farm.",
    ),
    "fetch_latest_monobox_session": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/latestMonoboxSession",
        "Returns the active/latest automated monobox milking session summary (id, startTime, "
        "endTime, milkPerSessionInGram, cowsPerSession, milkPerHourInGram, milkings, "
        "automaticMilkings, manualMilkings, milkingsPerCow, cattleGroupIds, milkingParlors).",
    ),
    "fetch_milking_session_by_id": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/{session_id}",
        "Returns details for a specific milking session by session UUID.",
    ),
    "fetch_monobox_session_status": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/{session_id}/status/monobox",
        "Returns current vs. previous session visit counts and yields (actualProcessedAutomaticVisitCount, "
        "actualProcessedManualVisitCount, actualProcessedMilkYield, existsRejectedVisits).",
    ),
    "fetch_rotary_session_status": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/{session_id}/status/rotary",
        "Returns rotary parlor session status, optionally filtered by cattle group name.",
    ),
    "fetch_milking_session_plans": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/plans",
        "Returns configured milking session plans.",
    ),
    "fetch_milking_sessions_for_plan": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/sessions/{plan_id}",
        "Returns milking sessions belonging to a given session plan UUID.",
    ),
    "fetch_milking_sessions_without_plan": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/sessions/sessionsWithoutPlan",
        "Returns milking sessions recorded without a session plan.",
    ),
    "fetch_virtual_automated_monobox_sessions": (
        "parlors",
        "GET",
        "/dairynetbackend/milking/milkingsession/sessions/virtualAutomatedMonoboxSessions",
        "Returns virtual daily automated monobox milking sessions.",
    ),
    # 8. Milk Visits, Milk Control, Auto-Dry & Process Reports
    "fetch_milk_visit_by_id": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/{milk_visit_id}",
        "Returns full details for a single milk visit by visit UUID.",
    ),
    "fetch_milk_visits_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsForCattleInfoPage/{cattle_id}",
        "Returns all milk visits displayed on a specific cow's milking info page.",
    ),
    "fetch_milk_visits_last_x_days": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsLastXDays/{cattle_id}",
        "Returns a cow's milk visits over the last daysBack days.",
    ),
    "fetch_milk_visit_process_result_parameters": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultParameter/{milk_visit_id}",
        "Returns milkVisitGenericParameters and milkVisitSamplingResult for a milk visit.",
    ),
    "fetch_milk_visit_process_result_unknown_parameters": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultUnknownParameter/{milk_visit_id}",
        "Returns unknown process result parameters for a milk visit.",
    ),
    "fetch_milk_visit_process_control_parameters": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/v1.0/milkvisit/processControlParameter/{milk_visit_id}",
        "Returns milkVisitGenericParameters and milkControlSettingsSampling used during a milk visit.",
    ),
    "fetch_conspicuous_cell_count_graph": (
        "milking",
        "GET",
        "/dairynetbackend/milking/alarm/conspicuousCellCount/graph/{cattle_id}",
        "Returns quarter-level cell count and conductivity time-series values for a cow over daysBack days.",
    ),
    "fetch_milk_control_settings_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/milking/milkcontrolsettings/forFrontend/{cattle_id}",
        "Returns a cow's current milking allowance and milk control settings (milkAnimal, "
        "allowanceReason, rejectionReason).",
    ),
    "fetch_milk_control_plans_by_parlor_type": (
        "milking",
        "GET",
        "/dairynetbackend/milking/milkcontrolplan/by-milking-parlor-type/{parlor_type}",
        "Returns milk control plans configured for the given parlor type ('AUTOMATED_MONOBOX', "
        "'AUTOMATED_ROTARY', 'CONVENTIONAL_ROTARY').",
    ),
    "fetch_manual_milking_parlors_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/manual/parlorsForCattle/{cattle_id}",
        "Returns milking parlors available for recording manual milk visits for a cow.",
    ),
    "fetch_manual_milking_information_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.milking/manual/informationForCattle/{cattle_id}",
        "Returns manual milking information for a cow.",
    ),
    "fetch_autodry_default_settings": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/defaultSettings",
        "Returns default settings for milk-reduced auto-dry.",
    ),
    "fetch_autodry_plan_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/{cattle_id}",
        "Returns the milk-reduced auto-dry plan for a specific cow.",
    ),
    "fetch_autodry_repro_for_cattle": (
        "milking",
        "GET",
        "/dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/repro/{cattle_id}",
        "Returns reproduction dates and context relevant to auto-dry for a cow.",
    ),
    "fetch_process_report": (
        "milking",
        "GET",
        "/dairynetbackend/analysis/processreport",
        "Fetches the milking process report for the specified milking parlor(s) and date range "
        "(reportDateFrom to reportDateUntil).",
    ),
    "pull_process_report": (
        "milking",
        "GET",
        "/dairynetbackend/analysis/processreport",
        "Convenience wrapper that authenticates a fresh session and fetches the milking process "
        "report for the specified parlor(s) and date range in one call.",
    ),
    # 9. Feeding, Concentrate & Ration Performance
    "fetch_feeding_overview_preview": (
        "feeding",
        "GET",
        "/dairynetbackend/feeding/feedingoverview/preview",
        "Per-cow concentrate feed & milk summary. Returns an array of cows with cattleId, "
        "animalNumber, feedControlPlanName, daysInMilk, dailyMilkVisitCount, dailyMilkWeight24hInGram, "
        "dailyMilkWeight7dInGram, dailyFeedClaimInGram, dailyFeedConsumedInGram, dailyRestAmountInGram, "
        "dailyRestPercentageOf24h, dailyRestPercentageOf72h, feedingOverviewFeeds, and "
        "feedAmountPerProducedMilkInGram.",
    ),
    "fetch_all_feeds_in_use": (
        "feeding",
        "GET",
        "/dairynetbackend/feeding/feedconsumptionreport/allFeedsInUse",
        "Returns all feed types and concentrate components currently in use on the farm.",
    ),
    "fetch_group_feed_consumption_compare": (
        "feeding",
        "GET",
        "/dairynetbackend/feeding/feedconsumptionreport/getGroupFeedConsumptionCompare",
        "Returns group-level feed consumption comparison metrics.",
    ),
    "fetch_feed_efficiency_report": (
        "feeding",
        "POST",
        "/dairynetbackend/feeding/feedconsumptionreport/feedEfficiency",
        "Returns feed efficiency and milk weight report data for the given filter payload.",
    ),
    "fetch_feed_consumption_ingredients_report": (
        "feeding",
        "POST",
        "/dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportIngredients",
        "Returns ingredient-level feed history ('HISTORY') or feed cost ('COST') report data.",
    ),
    "fetch_feed_consumption_rations_report": (
        "feeding",
        "POST",
        "/dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportRations",
        "Returns ration-level feed history ('HISTORY') or feed cost ('COST') report data.",
    ),
    "export_feed_consumption_csv": (
        "feeding",
        "POST",
        "/dairynetbackend/feeding/feedconsumptionreport/exportRations",
        "Exports ration ('rations') or ingredient ('ingredients') feed consumption data as a CSV payload.",
    ),
    "fetch_feed_ration_changes": (
        "feeding",
        "GET",
        "/dairynetbackend/group-feeding/feeding/feed-ration/feed-ration-changes",
        "Returns group feeding ration change events for the specified barnGroupIds and queryPeriod "
        "('SEVEN_DAYS', 'TWENTYONE_DAYS', 'EIGHT_WEEKS', 'ONE_YEAR').",
    ),
}


def _format_annotation(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, type):
        return annotation.__name__
    text = str(annotation)
    return text.replace("typing.", "").replace("requests.sessions.", "requests.")


def _build_short_name(fn_name: str) -> str:
    for prefix in ("fetch_", "get_"):
        if fn_name.startswith(prefix):
            return fn_name[len(prefix) :]
    return fn_name


def _build_endpoint_catalog() -> tuple[EndpointInfo, ...]:
    funcs = [
        (name, obj)
        for name, obj in inspect.getmembers(dn, inspect.isfunction)
        if obj.__module__ == dn.__name__ and not name.startswith("_")
    ]
    funcs.sort(key=lambda item: inspect.getsourcelines(item[1])[1])

    catalog: list[EndpointInfo] = []
    for idx, (fn_name, fn_obj) in enumerate(funcs, 1):
        meta = _ENDPOINT_METADATA.get(fn_name)
        if meta is not None:
            cat_slug, method, path, response_summary = meta
        else:
            cat_slug, method, path, response_summary = (
                "system",
                "GET",
                "/dairynetbackend/...",
                "",
            )
        category = CATEGORY_BY_SLUG[cat_slug]

        doc = inspect.getdoc(fn_obj) or ""
        doc_lines = [line.strip() for line in doc.splitlines() if line.strip()]
        summary = doc_lines[0] if doc_lines else fn_name

        sig = inspect.signature(fn_obj)
        params: list[ParameterSpec] = []
        for param in sig.parameters.values():
            if param.name in ("session", "base_url", "timeout"):
                continue
            required = param.default is inspect.Parameter.empty
            default_val = None if required else param.default
            p_desc, p_example = PARAMETER_HELP.get(
                param.name, (f"Parameter '{param.name}'.", "")
            )
            params.append(
                ParameterSpec(
                    name=param.name,
                    type_str=_format_annotation(param.annotation),
                    required=required,
                    default=default_val,
                    description=p_desc,
                    example=p_example,
                )
            )

        explanation_parts = [summary]
        if response_summary and response_summary != summary:
            explanation_parts.append(response_summary)
        explanation = " ".join(explanation_parts)

        catalog.append(
            EndpointInfo(
                index=idx,
                name=fn_name,
                short_name=_build_short_name(fn_name),
                category=category,
                func=fn_obj,
                http_method=method,
                http_path=path,
                summary=summary,
                explanation=explanation,
                response_summary=response_summary or summary,
                parameters=tuple(params),
            )
        )
    return tuple(catalog)


ENDPOINTS: tuple[EndpointInfo, ...] = _build_endpoint_catalog()
ENDPOINT_BY_INDEX: dict[int, EndpointInfo] = {ep.index: ep for ep in ENDPOINTS}
ENDPOINT_BY_NAME: dict[str, EndpointInfo] = {ep.name.lower(): ep for ep in ENDPOINTS}
ENDPOINT_BY_SHORT_NAME: dict[str, EndpointInfo] = {
    ep.short_name.lower(): ep for ep in ENDPOINTS
}


def resolve_category(identifier: str) -> CategoryInfo | None:
    """Resolve a category by number (1-9), slug, or title substring."""
    clean = identifier.strip().lower()
    if clean.isdigit():
        return CATEGORY_BY_NUMBER.get(int(clean))
    if clean in CATEGORY_BY_SLUG:
        return CATEGORY_BY_SLUG[clean]
    for cat in CATEGORIES:
        if clean in cat.title.lower() or clean in cat.slug.lower():
            return cat
    return None


def resolve_endpoint(identifier: str) -> EndpointInfo | None:
    """Resolve an endpoint by numeric index (1-126), function name, short name, or HTTP path."""
    clean = identifier.strip()
    if clean.isdigit():
        return ENDPOINT_BY_INDEX.get(int(clean))
    lower = clean.lower()
    if lower in ENDPOINT_BY_NAME:
        return ENDPOINT_BY_NAME[lower]
    if lower in ENDPOINT_BY_SHORT_NAME:
        return ENDPOINT_BY_SHORT_NAME[lower]
    for ep in ENDPOINTS:
        if ep.http_path.lower() == lower or ep.http_path.lower().endswith(lower):
            return ep
    # Fuzzy match if unambiguous
    matches = [
        ep
        for ep in ENDPOINTS
        if lower in ep.name.lower() or lower in ep.short_name.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def coerce_parameter_value(raw_value: Any, param_spec: ParameterSpec) -> Any:
    """Convert a string CLI/prompt parameter value into the expected Python type."""
    if not isinstance(raw_value, str):
        return raw_value

    text = raw_value.strip()
    type_str = param_spec.type_str

    if text.lower() in ("none", "null") and "None" in type_str:
        return None

    if "bool" in type_str:
        if text.lower() in ("true", "1", "yes", "y"):
            return True
        if text.lower() in ("false", "0", "no", "n"):
            return False
        raise ValueError(
            f"Invalid boolean value '{raw_value}' for '{param_spec.name}' (use true/false)."
        )

    if type_str in ("int", "int | None"):
        return int(text)

    if type_str == "int | str":
        return int(text) if text.isdigit() else text

    if type_str.startswith("list"):
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError(f"Expected a JSON list for '{param_spec.name}'.")
            return parsed
        items = [item.strip() for item in text.split(",") if item.strip()]
        if "int" in type_str:
            return [int(x) if x.isdigit() else x for x in items]
        return items

    if type_str.startswith("dict") or param_spec.name in ("json_body",):
        if not text:
            return None
        return json.loads(text)

    return text


def auto_discover_parameter(
    session: requests.Session | None,
    param_name: str,
    base_url: str = dn.DEFAULT_BASE_URL,
    timeout: int = 10,
) -> Any:
    """Attempt to resolve a sensible default or live ID for a required parameter."""
    today = dt.date.today()
    if param_name == "reference_date" or param_name == "report_date_until":
        return today.isoformat()
    if param_name == "report_date_from":
        return (today - dt.timedelta(days=7)).isoformat()
    if param_name == "days" or param_name == "days_back":
        return 7
    if param_name == "box_id":
        return 1
    if param_name == "service_name":
        return "service-lkv-adapter"
    if param_name == "topic_name":
        return "CATTLE"
    if param_name == "search_text":
        return "32"
    if param_name == "query_period":
        return "SEVEN_DAYS"
    if param_name == "calculation_type":
        return "PER_COW"
    if param_name == "filter_payload":
        return {
            "startDate": (today - dt.timedelta(days=7)).isoformat(),
            "endDate": today.isoformat(),
        }

    if session is None:
        return None

    try:
        if param_name == "farm_site_id":
            resp = dn.fetch_platform_credentials(session, base_url=base_url, timeout=timeout)
            data = resp.json()
            return (data.get("person") or {}).get("farmId") or "17bc3185-8e2c-4742-8e6a-e142e6afb71a"

        if param_name in ("cattle_id", "cattle_ids"):
            resp = dn.fetch_avmlk_statistic_widget(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                if param_name == "cattle_id":
                    return items[0].get("cattleId")
                return [item.get("cattleId") for item in items[:3] if item.get("cattleId")]

        if param_name == "animal_numbers":
            resp = dn.fetch_avmlk_statistic_widget(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return [item.get("animalNumber") for item in items[:3] if item.get("animalNumber") is not None]
            return [32, 92, 146]

        if param_name == "group_id":
            resp = dn.fetch_cattle_groups_simple_list(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return items[0].get("id")

        if param_name in ("barn_group_name", "barn_group_ids"):
            resp = dn.fetch_cattle_groups_by_usage(
                session, usage="Barn", base_url=base_url, timeout=timeout
            )
            items = resp.json()
            if isinstance(items, list) and items:
                if param_name == "barn_group_name":
                    return items[0].get("name")
                return [item.get("id") for item in items if item.get("id")]

        if param_name == "preset_id":
            resp = dn.fetch_preset_definitions_simple_list(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return items[0].get("id")

        if param_name in ("rule_set_id", "animal_choice_rule_set_id"):
            resp = dn.fetch_animal_choice_simple_list(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return items[0].get("id")

        if param_name == "sorting_area_ids":
            resp = dn.fetch_sorting_areas_simple_list(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return [item.get("id") for item in items if item.get("id")]

        if param_name == "widget_id":
            resp = dn.fetch_dashboard_settings(session, base_url=base_url, timeout=timeout)
            data = resp.json()
            widgets = data.get("widgetSettings") if isinstance(data, dict) else None
            if isinstance(widgets, list) and widgets:
                return widgets[0].get("id")
            return "0303ffdd-3ce2-436e-9506-6861d9f972ba"

        if param_name in ("parlor_id", "milking_parlors", "milking_parlor_ids"):
            resp = dn.fetch_milking_parlors_simple_list(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                pid = items[0].get("id")
                if param_name == "milking_parlor_ids":
                    return [pid]
                return pid
            default_pid = "775502b4-40cf-48d3-bf59-1e464a0a45c1"
            return [default_pid] if param_name == "milking_parlor_ids" else default_pid

        if param_name == "session_id":
            resp = dn.fetch_latest_monobox_session(session, base_url=base_url, timeout=timeout)
            data = resp.json()
            if isinstance(data, dict):
                return data.get("id")

        if param_name == "plan_id":
            resp = dn.fetch_milking_session_plans(session, base_url=base_url, timeout=timeout)
            items = resp.json()
            if isinstance(items, list) and items:
                return items[0].get("id")

        if param_name == "milk_visit_id":
            cattle_id = auto_discover_parameter(session, "cattle_id", base_url=base_url, timeout=timeout)
            if cattle_id:
                resp = dn.fetch_milk_visits_for_cattle(
                    session, cattle_id=cattle_id, base_url=base_url, timeout=timeout
                )
                items = resp.json()
                if isinstance(items, list) and items:
                    return items[0].get("id")
    except Exception:
        return None

    return None


class SessionManager:
    """Manages lazy or immediate auto-authentication with DairyNet."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        base_url: str = dn.DEFAULT_BASE_URL,
        timeout: int = 15,
    ) -> None:
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session: requests.Session | None = None
        self.last_error: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None

    def get_session(self, force_reauth: bool = False, quiet: bool = False) -> requests.Session:
        """Return an authenticated requests.Session, authenticating automatically if needed."""
        if self._session is not None and not force_reauth:
            return self._session

        if not quiet:
            print(
                f"Auto-authenticating with DairyNet at {self.base_url} ...",
                file=sys.stderr,
            )
        try:
            self._session = dn.authenticate_dairynet_session(
                username=self.username,
                password=self.password,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            self.last_error = None
            if not quiet:
                token_present = "X-DAIRYNET-TOKEN" in self._session.cookies
                print(
                    f"Authenticated successfully (session cookies: {len(self._session.cookies)}, "
                    f"token: {'yes' if token_present else 'no'}).",
                    file=sys.stderr,
                )
            return self._session
        except Exception as exc:
            self.last_error = str(exc)
            raise


# =============================================================================
# Formatting & Display Helpers
# =============================================================================


def print_categories() -> None:
    """Print all endpoint categories and their descriptions."""
    print("=" * 88)
    print(f"DairyNet CLI — Endpoint Categories ({len(CATEGORIES)} categories, {len(ENDPOINTS)} endpoints)")
    print("=" * 88)
    for cat in CATEGORIES:
        count = sum(1 for ep in ENDPOINTS if ep.category.slug == cat.slug)
        print(f"\n[{cat.number}] {cat.title} ({cat.slug}) — {count} endpoints")
        print(f"    {cat.description}")
    print("\n" + "=" * 88)
    print("Tip: Run `list -c <slug|number>` to list endpoints in a category, or `explain <endpoint>`.")


def print_endpoints_list(
    category_filter: CategoryInfo | None = None,
    search_query: str | None = None,
    verbose: bool = False,
) -> None:
    """Print endpoints grouped by category."""
    query = search_query.strip().lower() if search_query else None
    matched_endpoints: list[EndpointInfo] = []

    for ep in ENDPOINTS:
        if category_filter and ep.category.slug != category_filter.slug:
            continue
        if query:
            haystack = (
                f"{ep.name} {ep.short_name} {ep.http_method} {ep.http_path} "
                f"{ep.summary} {ep.explanation} {ep.category.title}"
            ).lower()
            if query not in haystack:
                continue
        matched_endpoints.append(ep)

    if not matched_endpoints:
        print("No endpoints matched the given filter.")
        return

    print("=" * 96)
    header = f"DairyNet API Endpoints ({len(matched_endpoints)} of {len(ENDPOINTS)} shown)"
    if category_filter:
        header += f" | Category: [{category_filter.number}] {category_filter.title}"
    if query:
        header += f" | Search: '{search_query}'"
    print(header)
    print("=" * 96)

    for cat in CATEGORIES:
        cat_eps = [ep for ep in matched_endpoints if ep.category.slug == cat.slug]
        if not cat_eps:
            continue
        print(f"\n### [{cat.number}] {cat.title} ({cat.slug}) — {len(cat_eps)} endpoint(s)")
        print(f"    {cat.description}")
        print("-" * 96)
        for ep in cat_eps:
            req_params = [p.name for p in ep.parameters if p.required]
            opt_params = [f"{p.name}={p.default!r}" for p in ep.parameters if not p.required]
            param_badge = ""
            if req_params or opt_params:
                joined = ", ".join(req_params + opt_params)
                param_badge = f"({joined})"
            else:
                param_badge = "()"
            print(
                f"  [{ep.index:3d}] {ep.name}{param_badge}\n"
                f"        {ep.http_method:4s} {ep.http_path}\n"
                f"        -> {ep.summary}"
            )
            if verbose and ep.response_summary and ep.response_summary != ep.summary:
                print(f"        Details: {ep.response_summary}")
    print("\n" + "=" * 96)
    print(
        "Use `explain <number|name>` for full details or `call <number|name>` to execute an endpoint."
    )


def print_endpoint_explanation(ep: EndpointInfo) -> None:
    """Print a detailed explanation card for a single endpoint."""
    print("=" * 92)
    print(f"[{ep.index}] {ep.name}")
    print("=" * 92)
    print(f"Category      : [{ep.category.number}] {ep.category.title} ({ep.category.slug})")
    print(f"Short Alias   : {ep.short_name}")
    print(f"HTTP Endpoint : {ep.http_method} {ep.http_path}")
    sig = inspect.signature(ep.func)
    print(f"Python Sig    : {ep.name}{sig}")
    print("-" * 92)
    print("Summary:")
    print(f"  {ep.summary}")
    print("\nDetailed Explanation & Response Summary:")
    print(f"  {ep.response_summary}")
    print("-" * 92)
    if not ep.parameters:
        print("Parameters    : None (only requires authenticated session, handled automatically)")
    else:
        print("Parameters (session is injected automatically):")
        for p in ep.parameters:
            req_label = "REQUIRED" if p.required else f"optional, default={p.default!r}"
            print(f"  - {p.name} ({p.type_str}) [{req_label}]")
            print(f"      {p.description}")
            if p.example:
                print(f"      Example: {p.example}")

    print("-" * 92)
    example_args = []
    for p in ep.parameters:
        if p.required:
            val = p.example or f"<{p.name}>"
            example_args.append(f"-p {p.name}={val!r}" if " " in val or "{" in val or "[" in val else f"-p {p.name}={val}")
    args_str = (" " + " ".join(example_args)) if example_args else ""
    print("CLI Usage Examples:")
    print(f"  python dairynet_cli.py call {ep.name}{args_str}")
    print(f"  python dairynet_cli.py call {ep.index}{args_str}")
    print("=" * 92)


def format_and_output_result(
    ep: EndpointInfo,
    result: Any,
    elapsed_sec: float,
    *,
    raw: bool = False,
    compact: bool = False,
    max_items: int | None = None,
    output_file: str | None = None,
) -> None:
    """Format and display/save the return value of an endpoint call."""
    if isinstance(result, requests.Response):
        content_type = result.headers.get("Content-Type", "")
        print(
            f"\n[HTTP {result.status_code}] {ep.http_method} {result.url} "
            f"({elapsed_sec * 1000:.0f} ms, {len(result.content):,} bytes, {content_type})",
            file=sys.stderr,
        )
        if raw:
            body_text = result.text
        else:
            try:
                parsed = result.json()
                if max_items is not None:
                    if isinstance(parsed, list) and len(parsed) > max_items:
                        print(
                            f"(Showing first {max_items} of {len(parsed)} list items; omit --max-items for full output)",
                            file=sys.stderr,
                        )
                        parsed = parsed[:max_items]
                    elif (
                        isinstance(parsed, dict)
                        and isinstance(parsed.get("content"), list)
                        and len(parsed["content"]) > max_items
                    ):
                        total = len(parsed["content"])
                        print(
                            f"(Showing first {max_items} of {total} page items; omit --max-items for full output)",
                            file=sys.stderr,
                        )
                        parsed = dict(parsed)
                        parsed["content"] = parsed["content"][:max_items]
                indent = None if compact else 2
                body_text = json.dumps(parsed, indent=indent, ensure_ascii=False)
            except ValueError:
                body_text = result.text

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(body_text)
                if not body_text.endswith("\n"):
                    f.write("\n")
            print(f"Saved response output to {output_file}", file=sys.stderr)
        else:
            print(body_text)

    elif isinstance(result, requests.Session):
        cookies_dict = result.cookies.get_dict()
        summary_obj = {
            "authenticated": True,
            "base_url": dn.DEFAULT_BASE_URL,
            "cookies": list(cookies_dict.keys()),
            "headers_synced": [
                h for h in ("X-XSRF-TOKEN", "X-DAIRYNET-TOKEN") if h in result.headers
            ],
        }
        text = json.dumps(summary_obj, indent=None if compact else 2, ensure_ascii=False)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"Saved session summary to {output_file}", file=sys.stderr)
        else:
            print(text)


def execute_endpoint(
    ep: EndpointInfo,
    session_mgr: SessionManager,
    provided_params: dict[str, Any],
    *,
    auto_params: bool = False,
    interactive_prompt: bool = False,
    raw: bool = False,
    compact: bool = False,
    max_items: int | None = None,
    output_file: str | None = None,
) -> int:
    """Resolve parameters, auto-authenticate, invoke the endpoint function, and print output."""
    sig = inspect.signature(ep.func)
    needs_session = "session" in sig.parameters
    session: requests.Session | None = None

    if needs_session or ep.name == "authenticate_dairynet_session":
        try:
            session = session_mgr.get_session()
        except Exception as exc:
            print(f"Authentication failed: {exc}", file=sys.stderr)
            return 1

    call_kwargs: dict[str, Any] = {}
    if needs_session and session is not None:
        call_kwargs["session"] = session
    if "base_url" in sig.parameters:
        call_kwargs["base_url"] = session_mgr.base_url
    if "timeout" in sig.parameters:
        call_kwargs["timeout"] = session_mgr.timeout

    for p in ep.parameters:
        if p.name in provided_params:
            try:
                call_kwargs[p.name] = coerce_parameter_value(provided_params[p.name], p)
            except Exception as exc:
                print(f"Error parsing parameter '{p.name}': {exc}", file=sys.stderr)
                return 2
            continue

        if auto_params and p.required:
            discovered = auto_discover_parameter(
                session,
                p.name,
                base_url=session_mgr.base_url,
                timeout=session_mgr.timeout,
            )
            if discovered is not None:
                print(
                    f"Auto-resolved parameter {p.name} = {discovered!r}",
                    file=sys.stderr,
                )
                call_kwargs[p.name] = discovered
                continue

        if interactive_prompt:
            if p.required:
                discovered = auto_discover_parameter(
                    session,
                    p.name,
                    base_url=session_mgr.base_url,
                    timeout=session_mgr.timeout,
                )
                hint = f" [default/auto: {discovered!r}]" if discovered is not None else (
                    f" [example: {p.example}]" if p.example else ""
                )
                while True:
                    user_in = input(
                        f"  Enter REQUIRED '{p.name}' ({p.type_str}) — {p.description}{hint}: "
                    ).strip()
                    if not user_in and discovered is not None:
                        call_kwargs[p.name] = discovered
                        break
                    if not user_in:
                        print(f"  '{p.name}' is required. Please enter a value.")
                        continue
                    try:
                        call_kwargs[p.name] = coerce_parameter_value(user_in, p)
                        break
                    except Exception as exc:
                        print(f"  Invalid value: {exc}")
            else:
                user_in = input(
                    f"  Enter optional '{p.name}' ({p.type_str}, Enter for default={p.default!r}): "
                ).strip()
                if user_in:
                    try:
                        call_kwargs[p.name] = coerce_parameter_value(user_in, p)
                    except Exception as exc:
                        print(f"  Invalid value ({exc}), keeping default {p.default!r}.")
        else:
            if p.required:
                print(
                    f"Error: Missing required parameter '{p.name}' ({p.type_str}) for {ep.name}.\n"
                    f"  Description: {p.description}",
                    file=sys.stderr,
                )
                if p.example:
                    print(f"  Example    : -p {p.name}={p.example}", file=sys.stderr)
                print(
                    f"  Tip        : Pass `-p {p.name}=<value>`, `--auto-params`, or `-i` to prompt interactively.",
                    file=sys.stderr,
                )
                return 2

    start = time.monotonic()
    try:
        result = ep.func(**call_kwargs)
    except requests.HTTPError as exc:
        elapsed = time.monotonic() - start
        resp = exc.response
        status = resp.status_code if resp is not None else "ERR"
        body = resp.text[:500] if resp is not None else ""
        print(
            f"\n[HTTP {status}] Request failed after {elapsed * 1000:.0f} ms: {exc}",
            file=sys.stderr,
        )
        if body:
            print(f"Response body: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error calling {ep.name}: {exc}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - start
    format_and_output_result(
        ep,
        result,
        elapsed,
        raw=raw,
        compact=compact,
        max_items=max_items,
        output_file=output_file,
    )
    return 0


# =============================================================================
# Interactive Menu Loop
# =============================================================================


def run_interactive_mode(session_mgr: SessionManager) -> int:
    """Run an interactive CLI session for browsing categories, explaining, and calling endpoints."""
    print("=" * 88)
    print("  DairyNet Interactive CLI (`lib/dairynet.py`)")
    print(f"  Base URL : {session_mgr.base_url}")
    print(f"  Catalog  : {len(ENDPOINTS)} endpoints across {len(CATEGORIES)} categories")
    print("=" * 88)

    # Attempt auto-authentication upfront
    try:
        session_mgr.get_session()
    except Exception as exc:
        print(
            f"Note: Initial auto-authentication did not complete ({exc}).\n"
            "You can still browse categories, list endpoints, and read explanations offline.\n"
            "Authentication will be retried automatically when you call an endpoint.",
            file=sys.stderr,
        )

    while True:
        auth_badge = (
            "Authenticated"
            if session_mgr.is_authenticated
            else "Not connected (will auto-auth on call)"
        )
        print("\n" + "-" * 88)
        print(f"Main Menu  [Status: {auth_badge}]")
        print("-" * 88)
        print("  [c] Browse endpoints by Category (1-9)")
        print("  [l] List all endpoints grouped by category")
        print("  [s] Search endpoints by keyword")
        print("  [e] Explain an endpoint (by number 1-126 or name)")
        print("  [r] Run / Call an endpoint (by number 1-126 or name)")
        print("  [a] Re-authenticate session now")
        print("  [q] Quit")
        print("-" * 88)

        try:
            choice = input("Select an action (or enter an endpoint number/name directly): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        if not choice:
            continue
        low = choice.lower()

        if low in ("q", "quit", "exit"):
            print("Goodbye!")
            return 0

        if low in ("a", "auth"):
            try:
                session_mgr.get_session(force_reauth=True)
            except Exception as exc:
                print(f"Authentication failed: {exc}")
            continue

        if low in ("l", "list"):
            print_endpoints_list()
            continue

        if low in ("s", "search"):
            try:
                query = input("Enter search keyword (e.g. 'milk', 'cattle', 'feed', 'widget'): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if query:
                print_endpoints_list(search_query=query, verbose=True)
            continue

        if low in ("c", "cat", "categories"):
            _interactive_category_menu(session_mgr)
            continue

        if low in ("e", "explain", "info"):
            try:
                target = input("Enter endpoint number (1-126) or function name: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            ep = resolve_endpoint(target)
            if ep is None:
                print(f"Could not find endpoint '{target}'.")
            else:
                _interactive_endpoint_actions(ep, session_mgr)
            continue

        if low in ("r", "run", "call"):
            try:
                target = input("Enter endpoint number (1-126) or function name to call: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            ep = resolve_endpoint(target)
            if ep is None:
                print(f"Could not find endpoint '{target}'.")
            else:
                print_endpoint_explanation(ep)
                execute_endpoint(ep, session_mgr, {}, interactive_prompt=True)
            continue

        # Direct endpoint number or name entered at main prompt
        ep = resolve_endpoint(choice)
        if ep is not None:
            _interactive_endpoint_actions(ep, session_mgr)
            continue

        # Or category slug/name
        cat = resolve_category(choice)
        if cat is not None:
            _interactive_single_category(cat, session_mgr)
            continue

        print(f"Unrecognized selection '{choice}'. Enter c, l, s, e, r, a, q, or an endpoint number (1-126).")


def _interactive_category_menu(session_mgr: SessionManager) -> None:
    while True:
        print_categories()
        try:
            sel = input("\nChoose a category number (1-9) or slug (or 'b' to go back): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not sel or sel.lower() in ("b", "back", "q"):
            return
        cat = resolve_category(sel)
        if cat is None:
            print(f"Unknown category '{sel}'.")
            continue
        _interactive_single_category(cat, session_mgr)


def _interactive_single_category(cat: CategoryInfo, session_mgr: SessionManager) -> None:
    while True:
        print_endpoints_list(category_filter=cat, verbose=True)
        try:
            sel = input(
                f"\nEnter an endpoint number/name in [{cat.number}] {cat.title} (or 'b' to go back): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not sel or sel.lower() in ("b", "back", "q"):
            return
        ep = resolve_endpoint(sel)
        if ep is None:
            print(f"Could not find endpoint '{sel}'.")
            continue
        _interactive_endpoint_actions(ep, session_mgr)


def _interactive_endpoint_actions(ep: EndpointInfo, session_mgr: SessionManager) -> None:
    print_endpoint_explanation(ep)
    while True:
        try:
            action = input(
                f"\nAction for [{ep.index}] {ep.name}: [r]un endpoint, [a]uto-params run, [b]ack (default=b): "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not action or action in ("b", "back", "q"):
            return
        if action in ("r", "run", "c", "call"):
            execute_endpoint(ep, session_mgr, {}, interactive_prompt=True)
            return
        if action in ("a", "auto"):
            execute_endpoint(
                ep, session_mgr, {}, auto_params=True, interactive_prompt=True
            )
            return
        print("Please enter 'r' to run, 'a' to run with auto-resolved parameters, or 'b' to go back.")


# =============================================================================
# CLI Argument Parsing
# =============================================================================


def _parse_key_value_pairs(pairs: list[str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not pairs:
        return result
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Invalid parameter '{item}': expected KEY=VALUE format.")
        key, val = item.split("=", 1)
        result[key.strip().replace("-", "_")] = val
    return result


def _parse_extra_flag_args(extra_args: list[str]) -> dict[str, Any]:
    """Allow passing `--<param-name> <value>` or `--<param-name>=<value>` on the CLI."""
    parsed: dict[str, Any] = {}
    i = 0
    while i < len(extra_args):
        token = extra_args[i]
        if token.startswith("--"):
            key_part = token[2:]
            if "=" in key_part:
                k, v = key_part.split("=", 1)
                parsed[k.replace("-", "_")] = v
                i += 1
            else:
                k = key_part.replace("-", "_")
                if i + 1 < len(extra_args) and not extra_args[i + 1].startswith("--"):
                    parsed[k] = extra_args[i + 1]
                    i += 2
                else:
                    parsed[k] = "true"
                    i += 1
        else:
            i += 1
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dairynet_cli",
        description=(
            "CLI tool for lib/dairynet.py — auto-authenticates, lists endpoints grouped by "
            "category, explains endpoints & parameters, and invokes individual endpoints."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python dairynet_cli.py categories\n"
            "  python dairynet_cli.py list\n"
            "  python dairynet_cli.py list -c dashboard\n"
            "  python dairynet_cli.py list -s milk -v\n"
            "  python dairynet_cli.py explain fetch_avmlk_statistic_widget\n"
            "  python dairynet_cli.py explain 64\n"
            "  python dairynet_cli.py call fetch_version\n"
            "  python dairynet_cli.py call fetch_milk_yield_overview_widget -p days=7\n"
            "  python dairynet_cli.py call 29 --auto-params\n"
            "  python dairynet_cli.py interactive\n"
        ),
    )

    # Global authentication & connection options
    parser.add_argument(
        "--base-url",
        default=dn.DEFAULT_BASE_URL,
        help=f"DairyNetBox base URL (default: {dn.DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="DairyNet username (defaults to dairynet_username in .env).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="DairyNet password (defaults to dairynet_password in .env).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP request timeout in seconds (default: 15).",
    )

    # Convenience top-level flags (in addition to subcommands)
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="flag_list",
        help="List all endpoints grouped by category.",
    )
    parser.add_argument(
        "--categories",
        action="store_true",
        dest="flag_categories",
        help="List all endpoint categories with explanations.",
    )
    parser.add_argument(
        "-c",
        "--category",
        default=None,
        help="Filter endpoints by category number (1-9) or slug (auth, system, cattle, groups, actions, dashboard, parlors, milking, feeding).",
    )
    parser.add_argument(
        "-s",
        "--search",
        default=None,
        help="Search endpoints by keyword across names, paths, and explanations.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed explanations when listing endpoints.",
    )
    parser.add_argument(
        "--explain",
        metavar="ENDPOINT",
        default=None,
        help="Show full explanation for an endpoint (by number 1-126, function name, or 'all').",
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        metavar="ENDPOINT",
        default=None,
        help="Auto-authenticate and call the specified endpoint (by number 1-126 or function name).",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Launch interactive menu mode.",
    )
    parser.add_argument(
        "-p",
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Parameter for endpoint call in KEY=VALUE format (repeatable).",
    )
    parser.add_argument(
        "--params-json",
        default=None,
        metavar="JSON",
        help="JSON object of parameters to pass to the endpoint.",
    )
    parser.add_argument(
        "--auto-params",
        action="store_true",
        help="Automatically resolve missing required parameters (e.g. cattle_id, widget_id, session_id) from live API or defaults.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw HTTP response text without JSON pretty-printing.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact single-line JSON output.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Truncate JSON list/page responses to at most N items.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="Save endpoint response output to a file.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", title="subcommands")

    # categories
    subparsers.add_parser(
        "categories",
        aliases=["cats"],
        help="List all 9 endpoint categories and their descriptions.",
    )

    # list
    p_list = subparsers.add_parser(
        "list",
        aliases=["ls"],
        help="List endpoints grouped by category.",
    )
    p_list.add_argument(
        "category_arg",
        nargs="?",
        default=None,
        help="Optional category number (1-9) or slug to filter by.",
    )
    p_list.add_argument(
        "-c",
        "--category",
        dest="sub_category",
        default=None,
        help="Filter by category number (1-9) or slug.",
    )
    p_list.add_argument(
        "-s",
        "--search",
        dest="sub_search",
        default=None,
        help="Filter endpoints matching keyword.",
    )
    p_list.add_argument(
        "-v",
        "--verbose",
        dest="sub_verbose",
        action="store_true",
        help="Include full response explanations in the list.",
    )

    # explain
    p_explain = subparsers.add_parser(
        "explain",
        aliases=["info", "describe"],
        help="Show detailed explanation, HTTP path, and parameters for one or more endpoints.",
    )
    p_explain.add_argument(
        "targets",
        nargs="*",
        help="Endpoint number(s) (1-126), function name(s), category slug, or 'all'.",
    )
    p_explain.add_argument(
        "-c",
        "--category",
        dest="explain_category",
        default=None,
        help="Explain all endpoints in a category.",
    )

    # call
    p_call = subparsers.add_parser(
        "call",
        aliases=["run", "invoke"],
        help="Auto-authenticate and execute a specific endpoint.",
    )
    p_call.add_argument(
        "target",
        help="Endpoint number (1-126), function name (e.g. fetch_version), or short name (e.g. version).",
    )
    p_call.add_argument(
        "-p",
        "--param",
        dest="call_params",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Endpoint parameter in KEY=VALUE format (repeatable).",
    )
    p_call.add_argument(
        "--params-json",
        dest="call_params_json",
        default=None,
        metavar="JSON",
        help="JSON object of parameters to pass to the endpoint.",
    )
    p_call.add_argument(
        "--auto-params",
        dest="call_auto_params",
        action="store_true",
        help="Auto-resolve missing required parameters (e.g. cattle_id, widget_id, session_id).",
    )
    p_call.add_argument(
        "--prompt",
        dest="call_prompt",
        action="store_true",
        help="Interactively prompt for any missing parameters.",
    )
    p_call.add_argument(
        "--raw",
        dest="call_raw",
        action="store_true",
        help="Output raw response text.",
    )
    p_call.add_argument(
        "--compact",
        dest="call_compact",
        action="store_true",
        help="Output compact single-line JSON.",
    )
    p_call.add_argument(
        "--max-items",
        dest="call_max_items",
        type=int,
        default=None,
        help="Truncate JSON list/page responses to at most N items.",
    )
    p_call.add_argument(
        "-o",
        "--output",
        dest="call_output",
        default=None,
        metavar="FILE",
        help="Write response to a file.",
    )

    # auth
    subparsers.add_parser(
        "auth",
        help="Test automatic authentication against DairyNet and display session details.",
    )

    # interactive
    subparsers.add_parser(
        "interactive",
        aliases=["menu"],
        help="Start interactive menu to browse categories, view explanations, and call endpoints.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args, extra_args = parser.parse_known_args(argv)

    session_mgr = SessionManager(
        username=args.username,
        password=args.password,
        base_url=args.base_url,
        timeout=args.timeout,
    )

    # 1. Subcommand: categories or --categories
    if args.subcommand in ("categories", "cats") or args.flag_categories:
        print_categories()
        return 0

    # 2. Subcommand: auth
    if args.subcommand == "auth":
        ep = ENDPOINT_BY_NAME["authenticate_dairynet_session"]
        return execute_endpoint(
            ep,
            session_mgr,
            {},
            raw=args.raw,
            compact=args.compact,
            output_file=args.output,
        )

    # 3. Subcommand: explain or --explain
    if args.subcommand in ("explain", "info", "describe") or args.explain:
        targets: list[str] = []
        if args.explain:
            targets.append(args.explain)
        if getattr(args, "targets", None):
            targets.extend(args.targets)
        cat_arg = getattr(args, "explain_category", None) or args.category

        if cat_arg:
            cat = resolve_category(cat_arg)
            if cat is None:
                print(f"Error: Unknown category '{cat_arg}'.", file=sys.stderr)
                return 2
            for ep in ENDPOINTS:
                if ep.category.slug == cat.slug:
                    print_endpoint_explanation(ep)
            return 0

        if not targets:
            print(
                "Error: Specify at least one endpoint number/name, `-c <category>`, or `all`.",
                file=sys.stderr,
            )
            return 2

        for t in targets:
            if t.lower() == "all":
                for ep in ENDPOINTS:
                    print_endpoint_explanation(ep)
                return 0
            ep = resolve_endpoint(t)
            if ep is not None:
                print_endpoint_explanation(ep)
                continue
            cat = resolve_category(t)
            if cat is not None:
                for ep_item in ENDPOINTS:
                    if ep_item.category.slug == cat.slug:
                        print_endpoint_explanation(ep_item)
                continue
            print(f"Error: Unknown endpoint or category '{t}'.", file=sys.stderr)
            return 2
        return 0

    # 4. Subcommand: list or --list
    if (
        args.subcommand in ("list", "ls")
        or args.flag_list
        or (
            args.subcommand is None
            and not args.endpoint
            and not args.interactive
            and (args.category is not None or args.search is not None)
        )
    ):
        cat_str = (
            getattr(args, "sub_category", None)
            or getattr(args, "category_arg", None)
            or args.category
        )
        search_str = getattr(args, "sub_search", None) or args.search
        verbose = getattr(args, "sub_verbose", False) or args.verbose

        cat_obj: CategoryInfo | None = None
        if cat_str:
            cat_obj = resolve_category(cat_str)
            if cat_obj is None:
                print(
                    f"Error: Unknown category '{cat_str}'. Run `categories` to see valid categories.",
                    file=sys.stderr,
                )
                return 2

        print_endpoints_list(
            category_filter=cat_obj,
            search_query=search_str,
            verbose=verbose,
        )
        return 0

    # 5. Subcommand: call or --endpoint
    if args.subcommand in ("call", "run", "invoke") or args.endpoint:
        target_name = getattr(args, "target", None) or args.endpoint
        ep = resolve_endpoint(target_name)
        if ep is None:
            print(
                f"Error: Unknown endpoint '{target_name}'. Run `list` to view available endpoints.",
                file=sys.stderr,
            )
            return 2

        combined_params: dict[str, Any] = {}
        json_str = getattr(args, "call_params_json", None) or args.params_json
        if json_str:
            try:
                loaded = json.loads(json_str)
                if not isinstance(loaded, dict):
                    raise ValueError("--params-json must be a JSON object.")
                combined_params.update(loaded)
            except Exception as exc:
                print(f"Error parsing --params-json: {exc}", file=sys.stderr)
                return 2

        kv_list = list(args.param) + list(getattr(args, "call_params", []))
        try:
            combined_params.update(_parse_key_value_pairs(kv_list))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

        if extra_args:
            combined_params.update(_parse_extra_flag_args(extra_args))

        auto_params = getattr(args, "call_auto_params", False) or args.auto_params
        prompt_flag = getattr(args, "call_prompt", False) or args.interactive
        raw = getattr(args, "call_raw", False) or args.raw
        compact = getattr(args, "call_compact", False) or args.compact
        max_items = getattr(args, "call_max_items", None) or args.max_items
        output_file = getattr(args, "call_output", None) or args.output

        return execute_endpoint(
            ep,
            session_mgr,
            combined_params,
            auto_params=auto_params,
            interactive_prompt=prompt_flag,
            raw=raw,
            compact=compact,
            max_items=max_items,
            output_file=output_file,
        )

    # 6. Interactive mode (explicit `interactive` / `-i` or no arguments passed)
    if args.subcommand in ("interactive", "menu") or args.interactive or len(sys.argv) == 1:
        return run_interactive_mode(session_mgr)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# DairyNet API Documentation (`diary_docs.md`)

This document describes every API endpoint reverse-engineered from [`data/diary_net.har`](file:///Users/davidjung/code/ross-falkenstein/data/diary_net.har) (both from recorded HTTP traffic and from the 85 Angular JavaScript bundles embedded in the HAR) and mapped to functions in [`lib/dairynet.py`](file:///Users/davidjung/code/ross-falkenstein/lib/dairynet.py).

---

## Base URL, Authentication & Headers

- **Default Base URL:** `http://10.150.1.246`
- **Backend Prefix:** Almost all API endpoints are served under `/dairynetbackend/...` (an Angular HTTP interceptor automatically prepends `/dairynetbackend` to relative paths). Micro-frontend services (`service-lkv-adapter`, `service-cowscout-integration`) are served at `/service-<name>/...`.
- **Authentication & CSRF:**
  1. `POST /dairynetbackend/platform/user/authenticate` with form-urlencoded `username` and `password`.
  2. The server sets session/token cookies (`JSESSIONID`, `XSRF-TOKEN`, `X-DAIRYNET-TOKEN`).
  3. Subsequent requests mirror `XSRF-TOKEN` into the `X-XSRF-TOKEN` header and `X-DAIRYNET-TOKEN` into the `X-DAIRYNET-TOKEN` header (handled automatically by `authenticate_dairynet_session` and `dairynet_request` in [`lib/dairynet.py`](file:///Users/davidjung/code/ross-falkenstein/lib/dairynet.py)).

---

## 1. Authentication, Session, Navigation & System APIs

| Python Function in `lib/dairynet.py` | HTTP Method & Path | Parameters / Body | Description & Response Summary |
| :--- | :--- | :--- | :--- |
| `authenticate_dairynet_session(username, password)` | `POST /dairynetbackend/platform/user/authenticate` | Form data: `username`, `password` | Authenticates the user, sets session/CSRF cookies, and returns an authorized `requests.Session`. |
| `logout_dairynet_session(session)` | `POST /dairynetbackend/platform/user/logout` | None | Terminates the current DairyNet user session. |
| `fetch_platform_credentials(session)` | `GET /dairynetbackend/platform/credentials` | None | Returns current user profile, `userId`, `rights` (`READ`, `WRITE`, `BOOK_ANIMAL_ACTION`, etc.), `company` (`companyId`), `person` (`farmId`), module `versions`, `buildInfo`, and JWT `token`. |
| `fetch_version(session)` | `GET /dairynetbackend/version` | None | Returns version strings for `dairynetbox` (`46.0.10`), `commonApi`, `processControlApi`, `mobileApi`, `cowScoutApi`, `farmViewApi`, `icarProviderApi`, `groupFeedingApi`, `processManagerApi`, `parlorViewApi`, and `cattleEyeApi`. |
| `fetch_current_dairynet_release(session)` | `GET /dairynetbackend/systemsettings/current-dairynet-release` | None | Returns the current release string (e.g. `"47.0.24"`). |
| `fetch_system_settings(session)` | `GET /dairynetbackend/systemsettings` | None | Returns global system flags: `afsFeedingEnabled`, `dairyNetBoxStandaloneWithoutAnimals`, `dairyNetBoxComplete`, `latestInstallationDate`, `moduleSecurityEnabled`, `cowScoutActive`, `dnListEnabled`. |
| `fetch_active_topics(session)` | `GET /dairynetbackend/admin/topic/allActive` | None | Returns a JSON list of all licensed/enabled feature topics on the box (e.g. `CATTLE`, `COWSCOUT`, `MILKING_ALL`, `FEEDING_ALL`, `HEALTH_HERD`). |
| `fetch_enums(session)` | `GET /dairynetbackend/enums` | None | Returns all backend enum definitions (`AnimalActionType`, `AllowanceReasonEnum`, `AttentionType`, `CattleType`, `CowStatus`, etc.) with `i18nPrefix` and `options`. |
| `fetch_locales(session)` | `GET /dairynetbackend/platform/localize/locales` | None | Returns a dictionary of supported locale codes (`DE_DE`, `EN_US`, etc.) to display names. |
| `fetch_localization(session, locale="de-DE")` | `GET /dairynetbackend/platform/localize/{locale}` | Path: `locale` (`de-DE`, `default`, etc.) | Returns the full i18n key-to-label translation dictionary (~840 KB) used to translate enum keys, column headers, and KPI names. |
| `fetch_topbar_navigation(session)` | `GET /dairynetbackend/navigation/topbar` | None | Returns the full navigation tree grouped by category (`HERDMANAGEMENT`, `MILKING`, `REPRODUCTION`, `HEALTH`, `FEEDING`) with page links and required topics. |
| `fetch_sidebar_navigation(session)` | `GET /dairynetbackend/navigation/sidebar` | None | Returns the settings/administration sidebar navigation tree. |
| `fetch_mymenu_navigation(session)` | `GET /dairynetbackend/navigation/mymenu` | None | Returns user-configured custom menu tabs. |
| `fetch_cattle_details_navigation(session)` | `GET /dairynetbackend/navigation/cattle-details` | None | Returns the available sub-navigation tabs for the single-cow detail view. |
| `fetch_local_system_time(session)` | `GET /dairynetbackend/systemadministration/localSystemTime` | None | Returns the DairyNetBox local ISO timestamp as plain text (e.g. `2026-11-16T15:17:08.271`). |
| `fetch_utc_system_time(session)` | `GET /dairynetbackend/systemadministration/utcSystemTime` | None | Returns the DairyNetBox UTC ISO timestamp as plain text. |
| `fetch_country_or_region(session)` | `GET /dairynetbackend/settings/countryorregion` | None | Returns the configured country/region (e.g. `"GERMANY"`). |
| `fetch_measurement_system(session)` | `GET /dairynetbackend/settings/measurementsystem` | None | Returns the configured unit system (e.g. `"METRIC"`). |
| `fetch_currency(session)` | `GET /dairynetbackend/settings/currency` | None | Returns the configured currency (e.g. `"EUR"`). |
| `fetch_system_control_parameters(session)` | `GET /dairynetbackend/settings/systemcontrolparameter` | None | Returns farm-wide system control parameters. |
| `fetch_farm_site(session, farm_site_id)` | `GET /dairynetbackend/core/farmsite/{farm_site_id}` | Path: `farm_site_id` (UUID) | Returns details for a specific farm site (e.g. `17bc3185-8e2c-4742-8e6a-e142e6afb71a`). |
| `fetch_notifications(session, locale, include_confirmed, include_read)` | `GET /dairynetbackend/notification/read/{locale}/{includeConfirmed}/{includeRead}` | Path: `locale`, `includeConfirmed` (`true`/`false`), `includeRead` (`true`/`false`) | Returns `{"nbrOfNotifications": 0, "elements": [...]}` containing active system/animal notifications. |
| `fetch_notifications_for_reference(session, reference_id, locale)` | `GET /dairynetbackend/notification/notificationsForReference/{reference_id}/{locale}` | Path: `reference_id`, `locale` | Returns notifications linked to a specific entity UUID. |
| `fetch_module_federation_services(session)` | `GET /dairynetbackend/module-federation-info/services` | None | Returns external micro-frontend services and ports (`service-lkv-adapter` on `3001`, `service-cowscout-integration` on `8089`). |
| `fetch_federated_service_info(session, service_name)` | `GET /{service_name}/api/info` | Path: `service_name` | Returns metadata (`label`, `menuCategory`, `requiredUserRight`, `topics`) for a federated service. |
| `fetch_websocket_info(session, timestamp_ms)` | `GET /dairynetbackend/ws/info` | Query: `t` (epoch ms) | SockJS handshake info endpoint (`websocket: true`, `cookie_needed: true`). |

---

## 2. Cattle, Herd Management, Groups, Animal Choice, Actions & Sorting APIs

| Python Function in `lib/dairynet.py` | HTTP Method & Path | Parameters / Body | Description & Response Summary |
| :--- | :--- | :--- | :--- |
| `fetch_cattle_page(session, page_index=1, page_size=240, sort_column=None, sort_descending=False, herd_group_filter=None, extra_filters=None)` | `GET /dairynetbackend/herdmanagement/cattle` | Query: `pageIndex` (1-based), `pageSize`, `sortColumn`, `sortDescending`, `herdGroupSelect` (JSON), plus column filters | Paginated cattle table endpoint. Returns `{content: [...], totalElements, currentPage, pageSize, totalPages, queryTimeInMilliSeconds}`. |
| `fetch_cattle_by_id(session, cattle_id)` | `GET /dairynetbackend/herdmanagement/cattle/{cattle_id}` | Path: `cattle_id` (UUID) | Returns full master data record for a single animal. |
| `fetch_cattle_information(session, cattle_id)` | `GET /dairynetbackend/herdmanagement/cattle/information/{cattle_id}` | Path: `cattle_id` (UUID) | Returns animal status and action summary information for a single cow. |
| `fetch_cattle_by_ids_including_inactive(session, cattle_ids)` | `POST /dairynetbackend/herdmanagement/cattle/animalsByCattleIdListIncludingInactive` | JSON body: `["<cattle_uuid>", ...]` | Batch-fetches full cattle objects for a list of cattle UUIDs (including inactive/left-herd animals). |
| `fetch_cattle_identifiers_by_ids_including_inactive(session, cattle_ids)` | `POST /dairynetbackend/herdmanagement/cattle/animalIdentifiersByCattleIdListIncludingInactive` | JSON body: `["<cattle_uuid>", ...]` | Batch-fetches lightweight identifier objects (`animalnumber`, `officialEarTag`, `animalName`) for cattle UUIDs. |
| `fetch_cattle_by_animal_numbers(session, animal_numbers)` | `POST /dairynetbackend/herdmanagement/cattle/animalsByAnimalNumberList` | JSON body: `[32, 92, 146, ...]` | Batch-fetches cattle objects by their barn animal numbers. |
| `fetch_cattle_without_mother(session)` | `GET /dairynetbackend/herdmanagement/cattle/cattleWithoutMother` | None | Returns all cattle records that do not have a mother assigned. |
| `fetch_cattle_system_parameters(session, cattle_id)` | `GET /dairynetbackend/herdmanagement/cattlesystemparameters/{cattle_id}` | Path: `cattle_id` (UUID) | Returns system parameters for a cow, including `expectedMilkVisitTimeStamp` (next milk allowance time). |
| `fetch_cattle_navigation_details(session, cattle_ids)` | `POST /dairynetbackend/cattleinfo/navigation-details` | JSON body: `["<cattle_uuid>", ...]` | Batch-fetches header/navigation summary (`id`, `animalnumber`, `animalName`, `cattleType`, `cowStatus`, `lactationNumber`). |
| `search_global_text(session, search_text, scopes=None)` | `GET /dairynetbackend/search/globalsearch/textSearch` | Query: `searchText`, `scopes` (e.g. `["CATTLE_DETAILS_PAGES", "CATTLE"]`) | Global text search for finding cattle by ear tag, animal number, or name. Returns `{searchResultByCategory: ...}`. |
| `fetch_cattle_groups_by_usage(session, usage="Milking")` | `GET /dairynetbackend/herdmanagement/cattlegroup/findAllByGroupUsage` | Query: `param` (`Milking`, `Barn`, `Feeding`, `Administrative`) | Returns cattle groups for the given usage, including `id`, `name`, `color`, and `cattleGroupMembersCount`. |
| `fetch_administrative_cattle_groups_by_topic(session, topic_name)` | `GET /dairynetbackend/herdmanagement/cattlegroup/findAdministrativeByTopicName` | Query: `topicName` | Returns administrative cattle groups filtered by topic name. |
| `fetch_cattle_groups_simple_list(session)` | `GET /dairynetbackend/herdmanagement/cattlegroup/simpleList` | None | Returns a simple list of all cattle groups on the farm. |
| `fetch_cattle_group_by_id(session, group_id)` | `GET /dairynetbackend/herdmanagement/cattlegroup/{group_id}` | Path: `group_id` (UUID) | Returns details for a specific cattle group. |
| `fetch_cattle_group_memberships(session, cattle_id)` | `GET /dairynetbackend/herdmanagement/cattlegroup/memberships/{cattle_id}` | Path: `cattle_id` (UUID) | Returns all cattle groups a specific cow currently belongs to. |
| `fetch_barn_groups_with_rotary_values(session)` | `GET /dairynetbackend/herdmanagement/cattlegroup/findAllBarnGroupsWithRotaryValues` | None | Returns all barn groups along with rotary parlor configuration values. |
| `fetch_herd_and_group_select_options(session)` | `GET /dairynetbackend/herdmanagement/cattlegroup/herdandgroupselect` | None | Returns all selectable herd/group/animal-choice filter objects used by the cattle list dropdown. |
| `fetch_milking_group_statistics(session, group_id)` | `GET /dairynetbackend/dairynet.herdmanagement/v1.0/milkinggroupstatistics/basic/{group_id}` | Path: `group_id` (UUID) | Returns basic milking statistics for a specific cattle group. |
| `fetch_preset_definitions_simple_list(session)` | `GET /dairynetbackend/herdmanagement/presetdefinitions/simpleList` | None | Returns available column preset definitions for cattle tables. |
| `fetch_preset_definitions_flat(session)` | `GET /dairynetbackend/herdmanagement/presetdefinitions/flat` | None | Returns flat-mapped preset definitions. |
| `fetch_preset_available_columns(session)` | `GET /dairynetbackend/herdmanagement/presetdefinitions/availablecolumns` | None | Returns every available data column that can be included in a cattle table preset. |
| `fetch_preset_definition_by_id(session, preset_id)` | `GET /dairynetbackend/herdmanagement/presetdefinitions/{preset_id}` | Path: `preset_id` | Returns a single column preset definition by ID. |
| `fetch_animal_choice_simple_list(session)` | `GET /dairynetbackend/herdmanagement/animalchoice/simpleList` | None | Returns all configured Animal Choice (`Tierauswahl`) rule sets. |
| `fetch_animal_choice_by_id(session, rule_set_id)` | `GET /dairynetbackend/herdmanagement/animalchoice/{rule_set_id}` | Path: `rule_set_id` (UUID) | Returns the full rule and criterion definition (and matching animals) for an Animal Choice rule set. |
| `fetch_dnlist_definitions(session)` | `GET /dairynetbackend/dnlist/definition` | None | Returns all configured DNList dynamic list definitions (`id`, `name`, `nameI18nKey`). |
| `fetch_animal_action_list_count(session)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/listcount` | None | Returns the count of animal actions across action states. |
| `fetch_possible_animal_action_names(session)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getPossibleAnimalActionNames` | None | Returns all possible animal action type names supported by the backend. |
| `fetch_related_animal_actions(session, action_id)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/animalaction/getRelatedActions/{action_id}` | Path: `action_id` (UUID) | Returns related planned/booked actions linked to a specific animal action. |
| `fetch_animal_action_calendar(session)` | `GET /dairynetbackend/animalaction/calendar` | None | Returns the full animal action calendar (`columns`, `existingAnimalActionTypes`). |
| `fetch_last_successful_insemination(session, cattle_id)` | `GET /dairynetbackend/herdmanagement/animalaction/insemination/findLastSuccessfulInsemination/{cattle_id}` | Path: `cattle_id` (UUID) | Returns the most recent successful insemination for a cow. |
| `fetch_possible_successful_inseminations(session, cattle_id, reference_date)` | `GET /dairynetbackend/herdmanagement/animalaction/insemination/findPossibleSuccessfulInseminations/{cattle_id}/{reference_date}` | Path: `cattle_id`, `reference_date` | Returns candidate inseminations that could have resulted in a pregnancy/calving. |
| `fetch_sorting_areas_simple_list(session)` | `GET /dairynetbackend/sorting/sortingarea/simpleList` | None | Returns all sorting/selection areas on the farm. |
| `fetch_sorting_areas_by_ids(session, sorting_area_ids)` | `GET /dairynetbackend/sorting/sortingarea/byIds` | Query: `sortingAreaIds` | Returns sorting areas matching the given IDs. |
| `fetch_sorting_timeframe_options(session, cattle_id)` | `GET /dairynetbackend/sorting/sortingcommand/timeframe-options/{cattle_id}` | Path: `cattle_id` (UUID) | Returns valid sorting timeframe options (`validFrom`, `validUntil`) for sorting a cow. |

---

## 3. Dashboard & Herd KPI Widget APIs

| Python Function in `lib/dairynet.py` | HTTP Method & Path | Parameters / Body | Description & Response Summary |
| :--- | :--- | :--- | :--- |
| `fetch_dashboard_settings(session)` | `GET /dairynetbackend/dashboard/settings` | None | Returns the layout and `widgetSettings` array (containing each widget's `id` and `widgetName`). |
| `fetch_available_dashboard_widgets(session)` | `GET /dairynetbackend/dashboard/availableWidgets` | None | Returns all widget types that can be placed on the dashboard. |
| `fetch_avmlk_statistic_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/avmlkStatistic` | None | **Herd-wide per-cow milk yield & lactation list.** Returns an array of all lactating cows: `[{"cattleId": "...", "animalNumber": 32, "lactation": 4, "dateOfAverage": "2026-11-16", "dayOfLactation": 210, "averageMilkWeightInGram": 33789}, ...]`. |
| `fetch_milk_yield_overview_widget(session, days=7)` | `GET /dairynetbackend/dashboard/widgets/milkyieldoverview/{days}` | Path: `days` (e.g. `7`) | Returns daily average milk yield in grams broken down by 1st, 2nd, 3rd+ lactation and overall herd average, plus comparison to the previous period. |
| `fetch_avg_milk_yield_per_session_widget_settings(session, widget_id)` | `GET /dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview` | Query: `widgetId` | Returns configured barn groups for the session milk yield widget. |
| `fetch_avg_milk_yield_per_session_widget_data(session, days_back, barn_group_name, calculation_type)` | `GET /dairynetbackend/dashboard/widgets/avgmilkyieldpersessionoverview/data` | Query: `daysBack`, `barnGroupName`, `calculationTypeEnum` | Returns session-level average milk yield points (`avgMilkYieldOfXSessionsOverviewWidgetPointDTOList`). |
| `fetch_reproduction_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/reproduction` | None | Returns herd reproduction KPIs: `averageDaysInMilk`, `daysOpen`, `inseminationInterval`, `calvingInterval`, `inseminationIndexDairyCow`, `inseminationIndexHeifer`, `pregnancyRateDairyCow`, `pregnancyRateHeifer`. |
| `fetch_stall_performance_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/stallperformance` | None | Returns 24h milk yield and milking duration per box: `[{"absoluteBoxNumber": 1, "milkingWeight24HoursInGram": 1217362, "milkingWeightDayBefor24HoursInGram": 1000344, "milkingDuration24HoursInSeconds": 51749}, ...]`. |
| `fetch_stall_performance_details(session, box_id)` | `GET /dairynetbackend/home/dashboard/widgets/stallperformance/details` | Query: `boxId` | Returns detailed `attachPerformance` and `problematicMilkings` for a milking box. |
| `fetch_farm_performance_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/performance/farm` | None | Returns farm-wide monobox KPIs (`milkYield`, `milkYieldPerBox`, `milkYieldPerCow`, `cowsMilked`, `numberOfMilkings`, `numberOfMilkingsPerCow`) with deltas to yesterday, 7-day average, and 30-day average. |
| `fetch_box_performance_widget(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/performance/box` | Query: `widgetId` | Returns per-box performance comparison values (`parlorNames`, `boxValues`). |
| `fetch_monobox_performance_widget_settings(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/monoboxPerformance` | Query: `widgetId` | Returns box selection settings for the monobox performance widget. |
| `fetch_milking_process_performance_widget(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/milking-process-performance/{widget_id}` | Path: `widget_id` (e.g. `a6e95845-c543-4138-acfd-8c4a390007e4`) | Returns process KPIs (`attachmentTime`, `numberOfIncompleteMilkings`, `milkingsPerHourAndBox`) and `overallTargetReachedInPercent`. |
| `fetch_milk_yield_kpi_widget(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/milkyieldkpi/{widget_id}` | Path: `widget_id` (e.g. `0303ffdd-3ce2-436e-9506-6861d9f972ba`) | Returns milk yield KPIs (`totalMilkYield`, `milkYieldCow`, `numberOfMilkings`) and target percentages. |
| `fetch_milk_quality_kpi_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/milkqualitykpi` | None | Returns milk quality KPIs for the dashboard. |
| `fetch_milk_productivity_parlor_settings(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor/{widget_id}` | Path: `widget_id` | Returns `milkingParlorIds` bound to a KPI widget. |
| `save_milk_productivity_parlor_settings(session, widget_id, milking_parlor_ids)` | `POST /dairynetbackend/home/dashboard/widgets/milk-productivity-settings/parlor` | JSON body: `{"widgetId": "...", "milkingParlorIds": [...]}` | Updates the milking parlors bound to a KPI widget. |
| `fetch_animal_choice_widget(session, widget_id)` | `GET /dairynetbackend/home/dashboard/widgets/animalchoice` | Query: `widgetId` (e.g. `953cf4fd-cebd-4498-8560-249ff23f3095`) | Returns the list of `animalChoiceRuleSetId` items (`Zellzahl`, `Leitwert`, `Melkbesuch überfällig`, `Milchmengenalarm`, etc.) configured on the widget. |
| `fetch_animal_choice_cattle_count(session, animal_choice_rule_set_id)` | `GET /dairynetbackend/home/dashboard/widgets/animalchoice/cattlecount` | Query: `animalChoiceRuleSetId` | Returns the integer count of cattle currently matching the rule set. |
| `fetch_animal_choice_widget_rulesets(session)` | `GET /dairynetbackend/home/dashboard/widgets/animalchoice/rulesets` | None | Returns all rule sets available for selection in the Animal Choice widget. |
| `fetch_dnlist_widget_settings(session, widget_id)` | `GET /dairynetbackend/dnlist/dashboard/widget/list/settings/{widget_id}` | Path: `widget_id` (`985f4910-7277-4c8a-8ea8-b4bdde3b2a5e`) | Returns `{"id": 1, "widgetId": "...", "listDefinitionIds": [29, 4]}`. |
| `fetch_dnlist_widget_data(session, widget_id)` | `GET /dairynetbackend/dnlist/dashboard/widget/list/data/{widget_id}` | Path: `widget_id` (`985f4910-7277-4c8a-8ea8-b4bdde3b2a5e`) | Returns `[{"listId": 29, "listName": "Leitwert >1000", "listKPI": null}, {"listId": 4, "listName": "Holen Kühe", "listKPI": null}]`. |
| `fetch_bcs_development_widget(session, milking_group_id=None)` | `GET /dairynetbackend/home/dashboard/widgets/bcsDevelopment` | Query: optional `milkingGroupId` | Returns per-cow `bcsScore`, `dayOfLactation`, and `lactationNumber`. |
| `fetch_calving_statistic_widget(session, days_back=7)` | `GET /dairynetbackend/home/dashboard/widgets/calvingStatistic/{days_back}` | Path: `days_back` | Returns calving counts grouped by `CalvingStatisticWidgetEnum` over the past `days_back` days. |
| `fetch_cattle_status_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/cattleStatus` | None | Returns cattle headcounts grouped by reproductive/lactation status. |
| `fetch_cattle_breed_performance_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/cattlebreedperformance` | None | Returns daily average milk weight in grams by breed and lactation (`dailyAverageFirstLactation`, `dailyAverageSecondLactation`, etc.). |
| `fetch_cattle_breed_proportion_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/cattlebreedproportion` | None | Returns headcount per cattle breed (`cattleBreedName`, `cattleCount`). |
| `fetch_animal_action_calendar_widget(session)` | `GET /dairynetbackend/home/dashboard/widgets/animalactioncalendar` | None | Returns scheduled animal actions for the dashboard calendar widget. |

---

## 4. Milking, Parlors, Sessions, Milk Visits & Reports APIs

| Python Function in `lib/dairynet.py` | HTTP Method & Path | Parameters / Body | Description & Response Summary |
| :--- | :--- | :--- | :--- |
| `fetch_available_parlor_types(session)` | `GET /dairynetbackend/milking/milkingparlor/availableParlorTypes` | None | Returns parlor types present on the farm (e.g. `["AUTOMATED_MONOBOX"]`). |
| `fetch_milking_parlors_simple_list(session)` | `GET /dairynetbackend/milking/milkingparlor/simpleList` | None | Returns all milking parlors (`Dairyrobot`, ID `775502b4-40cf-48d3-bf59-1e464a0a45c1`), farm site mapping, and all `milkingParlorBoxes` (stalls 1, 2, 3). |
| `fetch_milking_parlor_by_id(session, parlor_id)` | `GET /dairynetbackend/milking/milkingparlor/{parlor_id}` | Path: `parlor_id` (UUID) | Returns details for a single milking parlor. |
| `fetch_milking_parlors_by_type(session, parlor_type="AUTOMATED_MONOBOX")` | `GET /dairynetbackend/milking/milkingparlor/byType` | Query: `param` (`AUTOMATED_MONOBOX`) | Returns parlors matching the specified parlor type. |
| `fetch_monobox_parlor_boxes(session)` | `GET /dairynetbackend/milking/milkingparlor/monobox/boxes` | None | Returns all DairyRobot monobox stalls. |
| `fetch_latest_monobox_session(session)` | `GET /dairynetbackend/milking/milkingsession/latestMonoboxSession` | None | Returns the active/latest monobox session (`id`, `startTime`, `endTime`, `milkPerSessionInGram`, `cowsPerSession`, `milkPerHourInGram`, `milkings`, `automaticMilkings`, `manualMilkings`, `milkingsPerCow`, `cattleGroupIds`, `milkingParlors`). |
| `fetch_milking_session_by_id(session, session_id)` | `GET /dairynetbackend/milking/milkingsession/{session_id}` | Path: `session_id` (UUID) | Returns details for a specific milking session. |
| `fetch_monobox_session_status(session, session_id, cattle_group=None)` | `GET /dairynetbackend/milking/milkingsession/{session_id}/status/monobox` | Path: `session_id`; Query: optional `cattleGroup` | Returns current vs. previous session visit counts and yields (`actualProcessedAutomaticVisitCount`, `actualProcessedManualVisitCount`, `actualProcessedMilkYield`, `existsRejectedVisits`). |
| `fetch_rotary_session_status(session, session_id, cattle_group=None)` | `GET /dairynetbackend/milking/milkingsession/{session_id}/status/rotary` | Path: `session_id`; Query: optional `cattleGroup` | Returns rotary session status. |
| `fetch_milking_session_plans(session)` | `GET /dairynetbackend/milking/milkingsession/plans` | None | Returns milking session plans. |
| `fetch_milking_sessions_for_plan(session, plan_id)` | `GET /dairynetbackend/milking/milkingsession/sessions/{plan_id}` | Path: `plan_id` (UUID) | Returns sessions for a given session plan. |
| `fetch_milking_sessions_without_plan(session)` | `GET /dairynetbackend/milking/milkingsession/sessions/sessionsWithoutPlan` | None | Returns sessions recorded without a session plan. |
| `fetch_virtual_automated_monobox_sessions(session)` | `GET /dairynetbackend/milking/milkingsession/sessions/virtualAutomatedMonoboxSessions` | None | Returns virtual daily automated monobox sessions. |
| `fetch_milk_visit_by_id(session, milk_visit_id)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/{milk_visit_id}` | Path: `milk_visit_id` (UUID) | Returns full details for a single milk visit. |
| `fetch_milk_visits_for_cattle(session, cattle_id)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsForCattleInfoPage/{cattle_id}` | Path: `cattle_id` (UUID) | Returns all milk visits for a specific cow's milking info page. |
| `fetch_milk_visits_last_x_days(session, cattle_id, days_back=7)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/milkVisitsLastXDays/{cattle_id}` | Path: `cattle_id`; Query: `daysBack` | Returns a cow's milk visits over the last `daysBack` days. |
| `fetch_milk_visit_process_result_parameters(session, milk_visit_id)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultParameter/{milk_visit_id}` | Path: `milk_visit_id` (UUID) | Returns `milkVisitGenericParameters` and `milkVisitSamplingResult` for a milk visit. |
| `fetch_milk_visit_process_result_unknown_parameters(session, milk_visit_id)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processResultUnknownParameter/{milk_visit_id}` | Path: `milk_visit_id` (UUID) | Returns unknown process result parameters for a milk visit. |
| `fetch_milk_visit_process_control_parameters(session, milk_visit_id)` | `GET /dairynetbackend/dairybox.milking/v1.0/milkvisit/processControlParameter/{milk_visit_id}` | Path: `milk_visit_id` (UUID) | Returns `milkVisitGenericParameters` and `milkControlSettingsSampling` used during a milk visit. |
| `fetch_conspicuous_cell_count_graph(session, cattle_id, days_back=7)` | `GET /dairynetbackend/milking/alarm/conspicuousCellCount/graph/{cattle_id}` | Path: `cattle_id`; Query: `daysBack` (`3`, `7`, etc.) | Returns quarter-level cell count / conductivity time-series values for a cow. |
| `fetch_milk_control_settings_for_cattle(session, cattle_id)` | `GET /dairynetbackend/milking/milkcontrolsettings/forFrontend/{cattle_id}` | Path: `cattle_id` (UUID) | Returns a cow's current milk control settings (`milkAnimal`, `allowanceReason`, `rejectionReason`). |
| `fetch_milk_control_plans_by_parlor_type(session, parlor_type="AUTOMATED_MONOBOX")` | `GET /dairynetbackend/milking/milkcontrolplan/by-milking-parlor-type/{parlor_type}` | Path: `parlor_type` | Returns milk control plans configured for the given parlor type. |
| `fetch_manual_milking_parlors_for_cattle(session, cattle_id)` | `GET /dairynetbackend/dairybox.milking/manual/parlorsForCattle/{cattle_id}` | Path: `cattle_id` (UUID) | Returns parlors available for manual milk visit entry for a cow. |
| `fetch_manual_milking_information_for_cattle(session, cattle_id)` | `GET /dairynetbackend/dairybox.milking/manual/informationForCattle/{cattle_id}` | Path: `cattle_id` (UUID) | Returns manual milking information for a cow. |
| `fetch_autodry_default_settings(session)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/defaultSettings` | None | Returns default milk-reduced auto-dry settings. |
| `fetch_autodry_plan_for_cattle(session, cattle_id)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/{cattle_id}` | Path: `cattle_id` (UUID) | Returns the milk-reduced auto-dry plan for a cow. |
| `fetch_autodry_repro_for_cattle(session, cattle_id)` | `GET /dairynetbackend/dairybox.herdmanagement/v1.0/milking/autodry/repro/{cattle_id}` | Path: `cattle_id` (UUID) | Returns reproduction dates/info relevant to auto-dry for a cow. |
| `fetch_process_report(session, milking_parlors, report_date_from, report_date_until, ...)` | `GET /dairynetbackend/analysis/processreport` | Query: `milkingParlors`, `reportDateFrom`, `reportDateUntil`, `sortColumn`, `sortDescending` | Fetches the milking process report for the specified parlor(s) and date range. |
| `pull_process_report(milking_parlors, report_date_from, report_date_until, ...)` | `POST /platform/user/authenticate` + `GET /analysis/processreport` | Credentials + report query params | Convenience wrapper that authenticates and fetches the process report in one call. |

---

## 5. Feeding & Concentrate / Ration Performance APIs

| Python Function in `lib/dairynet.py` | HTTP Method & Path | Parameters / Body | Description & Response Summary |
| :--- | :--- | :--- | :--- |
| `fetch_feeding_overview_preview(session, time_range="LAST72HOURS")` | `GET /dairynetbackend/feeding/feedingoverview/preview` | Query: `timeRange` (`LAST72HOURS`, etc.) | **Per-cow concentrate feed & milk summary.** Returns `[{"cattleId": "...", "animalNumber": 289, "feedControlPlanName": "Kalbinnen", "daysInMilk": 309, "dailyMilkVisitCount": 1.7, "dailyMilkWeight24hInGram": 29310, "dailyMilkWeight7dInGram": 30606, "dailyFeedClaimInGram": 4200, "dailyFeedConsumedInGram": 2418, "dailyRestAmountInGram": 1782, "dailyRestPercentageOf24h": 47.31, "dailyRestPercentageOf72h": 42.43, "feedingOverviewFeeds": [...], "feedAmountPerProducedMilkInGram": 0.079}, ...]`. |
| `fetch_all_feeds_in_use(session)` | `GET /dairynetbackend/feeding/feedconsumptionreport/allFeedsInUse` | None | Returns all feed types/components currently in use. |
| `fetch_group_feed_consumption_compare(session)` | `GET /dairynetbackend/feeding/feedconsumptionreport/getGroupFeedConsumptionCompare` | None | Returns group-level feed consumption comparison metrics. |
| `fetch_feed_efficiency_report(session, filter_payload)` | `POST /dairynetbackend/feeding/feedconsumptionreport/feedEfficiency` | JSON body: filter object | Returns feed efficiency and milk weight report data. |
| `fetch_feed_consumption_ingredients_report(session, filter_payload, report_mode="HISTORY")` | `POST /dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportIngredients` (or `feedCostReportIngredients`) | JSON body: filter object | Returns ingredient-level feed history or feed cost report data. |
| `fetch_feed_consumption_rations_report(session, filter_payload, report_mode="HISTORY")` | `POST /dairynetbackend/feeding/feedconsumptionreport/feedHistoryReportRations` (or `feedCostReportRations`) | JSON body: filter object | Returns ration-level feed history or feed cost report data. |
| `export_feed_consumption_csv(session, filter_payload, export_type="rations")` | `POST /dairynetbackend/feeding/feedconsumptionreport/exportRations` (or `exportIngredients`) | JSON body: filter object | Exports ration or ingredient feed consumption data as a CSV blob. |
| `fetch_feed_ration_changes(session, query_period, barn_group_ids)` | `GET /dairynetbackend/group-feeding/feeding/feed-ration/feed-ration-changes` | Query: `queryPeriod` (`SEVEN_DAYS`, `TWENTYONE_DAYS`, `EIGHT_WEEKS`, `ONE_YEAR`), `barnGroupIds` | Returns ration change events for the specified barn groups and period. |

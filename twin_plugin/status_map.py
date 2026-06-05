# coding: utf-8
"""Cerebro status name -> Yandex Tracker status key mapping."""

# Cerebro status name (normalized) -> Tracker status API key (Keys column)
DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY = {
    "open": "open",
    "opened": "open",
    "not started": "open",
    "открыт": "open",
    "new": "new",
    "новый": "new",
    "backlog": "backlog",
    "беклог": "backlog",
    "ready to start": "selectedForDev",
    "selected for dev": "selectedForDev",
    "будем делать": "selectedForDev",
    "in progress": "inProgress",
    "in_progress": "inProgress",
    "in work": "inProgress",
    "в работе": "inProgress",
    "testing": "testing",
    "тестируется": "testing",
    "tested": "tested",
    "протестировано": "tested",
    "review": "inReview",
    "in review": "inReview",
    "ревью": "inReview",
    "ready for test": "readyForTest",
    "можно тестировать": "readyForTest",
    "need info": "needInfo",
    "требуется информация": "needInfo",
    "need acceptance": "needAcceptance",
    "ждем подтверждения": "needAcceptance",
    "completed": "resolved",
    "complete": "resolved",
    "done": "resolved",
    "resolved": "resolved",
    "решён": "resolved",
    "решен": "resolved",
    "решено": "resolved",
    "closed": "closed",
    "закрыт": "closed",
    "cancelled": "cancelled",
    "отменено": "cancelled",
    "on hold": "onHold",
    "приостановлено": "onHold",
    "paused": "onHold",
    "need estimate": "needEstimate",
    "оценка задачи": "needEstimate",
    "confirmed": "confirmed",
    "подтверждён": "confirmed",
    "подтвержден": "confirmed",
    "ready for release": "rc",
    "готово к релизу": "rc",
    "demonstration to customer": "demoToCustomer",
    "демонстрация заказчику": "demoToCustomer",
    "first line of support": "firstSupportLine",
    "первая линия поддержки": "firstSupportLine",
    "second line of support": "secondSupportLine",
    "вторая линия поддержки": "secondSupportLine",
    "with risks": "withRisks",
    "есть риски": "withRisks",
    "blocked goal": "blockedGoal",
    "цель заблокирована": "blockedGoal",
    "achieved": "achieved",
    "достигнута": "achieved",
    "as planned": "asPlanned",
    "по плану": "asPlanned",
    "documents prepared": "documentsPrepared",
    "документы подготовлены": "documentsPrepared",
    "result acceptance": "resultAcceptance",
    "согласование результата": "resultAcceptance",
    "new goal": "newGoal",
    "новая цель": "newGoal",
}


def normalize_cerebro_status_name(name):
    if not name:
        return ""
    s = str(name).strip().lower().replace("_", " ")
    return " ".join(s.split())


def _status_map_patterns(status_map):
    return sorted(status_map.items(), key=lambda x: -len(x[0]))


def cerebro_status_to_tracker_key(status_info, status_map=None):
    if not status_info:
        return None
    status_map = status_map or DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY
    name = normalize_cerebro_status_name(status_info.get("name"))
    if not name:
        return None
    if name in status_map:
        return status_map[name]
    for pattern, key in _status_map_patterns(status_map):
        if pattern in name:
            return key
    return None

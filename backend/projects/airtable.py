import time
from django.conf import settings
from pyairtable import Api


TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
PERMANENT_STATUS_CODES = {400, 401, 403, 404, 413, 422}
MAX_ATTEMPTS = 3


class TransientAirtableError(Exception):
    pass


class PermanentAirtableError(Exception):
    pass


def get_table():
    api_key = settings.AIRTABLE_API_KEY
    base_id = settings.AIRTABLE_BASE_ID
    table_name = settings.AIRTABLE_TABLE_NAME
    if not api_key or not base_id or not table_name:
        raise ValueError('Airtable is not configured')
    return Api(api_key).table(base_id, table_name)


def task_fields(task):
    return {
        'TaskId': str(task.id),
        'Title': task.title,
        'Description': task.description or '',
        'Status': task.status,
        'Assignee': task.assignee.email if task.assignee else '',
        'Project': task.project.name,
    }


def _status_code(exc):
    code = getattr(exc, 'status_code', None)
    if code:
        return int(code)
    response = getattr(exc, 'response', None)
    if response is not None:
        code = getattr(response, 'status_code', None)
        if code:
            return int(code)
    return None


def _classify(exc):
    code = _status_code(exc)
    if code in PERMANENT_STATUS_CODES:
        return PermanentAirtableError(str(exc))
    if code in TRANSIENT_STATUS_CODES or code is None:
        return TransientAirtableError(str(exc))
    return PermanentAirtableError(str(exc))


def _call_with_retry(fn):
    last = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn()
        except PermanentAirtableError:
            raise
        except TransientAirtableError as exc:
            last = exc
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(0.2 * (2 ** attempt))
        except Exception as exc:
            classified = _classify(exc)
            if isinstance(classified, PermanentAirtableError):
                raise classified from exc
            last = classified
            if attempt == MAX_ATTEMPTS - 1:
                raise classified from exc
            time.sleep(0.2 * (2 ** attempt))
    raise last


def _formula_for_task(task_id):
    safe = str(task_id).replace('\\', '\\\\').replace("'", "\\'")
    return f"{{TaskId}}='{safe}'"


def _find_existing(table, task_id):
    def _lookup():
        return table.first(formula=_formula_for_task(task_id))
    return _call_with_retry(_lookup)


def _upsert_task(table, task):
    fields = task_fields(task)
    existing = _find_existing(table, task.id)
    if existing:
        def _update():
            return table.update(existing['id'], fields)
        record = _call_with_retry(_update)
        return 'updated', record
    def _create():
        return table.create(fields)
    record = _call_with_retry(_create)
    return 'created', record


def export_tasks(tasks):
    table = get_table()
    created = 0
    updated = 0
    failed = 0
    errors = []
    for task in tasks:
        try:
            action, _record = _upsert_task(table, task)
            if action == 'created':
                created += 1
            else:
                updated += 1
        except (TransientAirtableError, PermanentAirtableError, Exception) as exc:
            failed += 1
            errors.append({
                'task_id': str(task.id),
                'title': task.title,
                'error': str(exc),
            })
    return {
        'exported': created + updated,
        'created': created,
        'updated': updated,
        'failed': failed,
        'errors': errors,
    }

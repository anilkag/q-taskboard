"""Test double for Airtable.

Use this in unit tests (via monkeypatch of projects.airtable.get_table).
Do not import this module from production views.
"""
import re


class HttpishError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class MockAirtableTable:
    def __init__(self):
        self.created = []
        self.updated = []
        self.records = []
        self.fail_task_ids = set()
        self.transient_task_ids = {}

    def _task_id_from_formula(self, formula):
        match = re.search(r"TaskId\}='([^']+)'", formula or '')
        return match.group(1) if match else None

    def first(self, formula=None):
        task_id = self._task_id_from_formula(formula)
        for record in self.records:
            if record['fields'].get('TaskId') == task_id:
                return record
        return None

    def create(self, fields):
        self._maybe_fail(fields.get('TaskId'))
        record = {
            'id': f'rec{len(self.records) + 1:04d}',
            'fields': dict(fields),
        }
        self.created.append(record)
        self.records.append(record)
        return record

    def update(self, record_id, fields):
        self._maybe_fail(fields.get('TaskId'))
        for record in self.records:
            if record['id'] == record_id:
                record['fields'] = dict(fields)
                self.updated.append(record)
                return record
        raise HttpishError('not found', 404)

    def _maybe_fail(self, task_id):
        if task_id in self.fail_task_ids:
            raise HttpishError('unprocessable', 422)
        remaining = self.transient_task_ids.get(task_id)
        if remaining:
            self.transient_task_ids[task_id] = remaining - 1
            if remaining > 0:
                raise HttpishError('rate limited', 429)

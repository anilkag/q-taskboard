import pytest
from rest_framework.test import APIClient
from users.models import User
from projects.models import Project, Membership, Task, Comment, Activity
from projects.airtable_mock import MockAirtableTable


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email='meera@taskboard.dev', name='Meera Iyer', password='password123')


@pytest.fixture
def other(db):
    return User.objects.create_user(email='other@example.com', name='Other', password='password123')


@pytest.fixture
def auth_client(client, user):
    response = client.post('/api/auth/login', {
        'email': 'meera@taskboard.dev',
        'password': 'password123',
    }, format='json')
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['token']}")
    return client


def login_as(client, email, password='password123'):
    response = client.post('/api/auth/login', {'email': email, 'password': password}, format='json')
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['token']}")
    return client


@pytest.mark.django_db
class TestProjects:
    def test_unauthenticated_cannot_list_projects(self, client):
        response = client.get('/api/projects')
        assert response.status_code == 401

    def test_create_project(self, auth_client, user):
        response = auth_client.post('/api/projects', {'name': 'My Project'}, format='json')
        assert response.status_code == 201
        assert response.data['project']['name'] == 'My Project'
        membership = Membership.objects.get(user=user, project_id=response.data['project']['id'])
        assert membership.role == 'admin'

    def test_create_project_rejects_empty_name(self, auth_client):
        response = auth_client.post('/api/projects', {'name': '  '}, format='json')
        assert response.status_code == 400

    def test_list_only_returns_member_projects(self, auth_client, user):
        p1 = Project.objects.create(name='Mine', owner=user)
        Membership.objects.create(user=user, project=p1, role='admin')
        other = User.objects.create_user(email='other2@example.com', name='Other', password='password123')
        p2 = Project.objects.create(name='Not Mine', owner=other)
        Membership.objects.create(user=other, project=p2, role='admin')

        response = auth_client.get('/api/projects')
        assert response.status_code == 200
        names = [p['name'] for p in response.data['projects']]
        assert 'Mine' in names
        assert 'Not Mine' not in names

    def test_get_project_detail(self, auth_client, user):
        project = Project.objects.create(name='My Project', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        response = auth_client.get(f'/api/projects/{project.id}')
        assert response.status_code == 200
        assert response.data['project']['name'] == 'My Project'

    def test_non_member_cannot_view_project(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='Private', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')

        login_as(client, 'meera@taskboard.dev')
        response = client.get(f'/api/projects/{project.id}')
        assert response.status_code == 403

    def test_admin_can_update_project(self, auth_client, user):
        project = Project.objects.create(name='Old', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        response = auth_client.patch(f'/api/projects/{project.id}', {'name': 'New'}, format='json')
        assert response.status_code == 200
        project.refresh_from_db()
        assert project.name == 'New'

    def test_member_cannot_update_project(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='member')
        login_as(client, 'meera@taskboard.dev')
        response = client.patch(f'/api/projects/{project.id}', {'name': 'Hacked'}, format='json')
        assert response.status_code == 403

    def test_admin_can_delete_project(self, auth_client, user):
        project = Project.objects.create(name='Gone', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        response = auth_client.delete(f'/api/projects/{project.id}')
        assert response.status_code == 204
        assert not Project.objects.filter(id=project.id).exists()

    def test_member_cannot_delete_project(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='member')
        login_as(client, 'meera@taskboard.dev')
        response = client.delete(f'/api/projects/{project.id}')
        assert response.status_code == 403


@pytest.mark.django_db
class TestTasks:
    def test_create_task(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        response = auth_client.post(f'/api/projects/{project.id}/tasks', {'title': 'Do a thing'}, format='json')
        assert response.status_code == 201
        assert response.data['task']['title'] == 'Do a thing'

    def test_create_task_requires_title(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        response = auth_client.post(f'/api/projects/{project.id}/tasks', {'title': ''}, format='json')
        assert response.status_code == 400

    def test_viewers_cannot_create_tasks(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')

        login_as(client, 'meera@taskboard.dev')
        response = client.post(f'/api/projects/{project.id}/tasks', {'title': 'A task'}, format='json')
        assert response.status_code == 403

    def test_viewers_cannot_update_tasks(self, client, user):
        owner = User.objects.create_user(email='owner2@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')
        task = Task.objects.create(project=project, title='A task', created_by=owner)

        login_as(client, 'meera@taskboard.dev')
        response = client.patch(f'/api/tasks/{task.id}', {'title': 'Nope'}, format='json')
        assert response.status_code == 403

    def test_member_can_update_tasks(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='member')
        task = Task.objects.create(project=project, title='A task', created_by=other)

        login_as(client, 'meera@taskboard.dev')
        response = client.patch(f'/api/tasks/{task.id}', {'title': 'Updated', 'status': 'done'}, format='json')
        assert response.status_code == 200
        assert response.data['task']['title'] == 'Updated'
        assert response.data['task']['status'] == 'done'

    def test_delete_task_requires_membership(self, client, user):
        owner = User.objects.create_user(email='owner@example.com', name='Owner', password='password123')
        project = Project.objects.create(name='P', owner=owner)
        Membership.objects.create(user=owner, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=owner)

        login_as(client, 'meera@taskboard.dev')
        response = client.delete(f'/api/tasks/{task.id}')
        assert response.status_code == 403

    def test_non_member_cannot_list_tasks(self, auth_client, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        response = auth_client.get(f'/api/projects/{project.id}/tasks')
        assert response.status_code == 403


@pytest.mark.django_db
class TestTaskSearch:
    def test_search_filters_by_title(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        Task.objects.create(project=project, title='Set up analytics', created_by=user)
        Task.objects.create(project=project, title='Write docs', created_by=user)

        response = auth_client.get(f'/api/projects/{project.id}/tasks', {'q': 'analytics'})
        assert response.status_code == 200
        titles = [t['title'] for t in response.data['tasks']]
        assert titles == ['Set up analytics']

    def test_search_is_safe_against_sql_injection(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        Task.objects.create(project=project, title="O'Reilly landing page", created_by=user)
        Task.objects.create(project=project, title='Normal task', created_by=user)

        payload = "' OR 1=1 --"
        response = auth_client.get(f'/api/projects/{project.id}/tasks', {'q': payload})
        assert response.status_code == 200
        assert len(response.data['tasks']) == 0

        response = auth_client.get(f'/api/projects/{project.id}/tasks', {'q': "O'Reilly"})
        assert response.status_code == 200
        assert len(response.data['tasks']) == 1
        assert Project.objects.filter(id=project.id).exists()


@pytest.mark.django_db
class TestMembers:
    def test_admin_can_add_member(self, auth_client, user, other):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        response = auth_client.post(
            f'/api/projects/{project.id}/members',
            {'email': other.email, 'role': 'viewer'},
            format='json',
        )
        assert response.status_code == 201
        assert Membership.objects.filter(user=other, project=project, role='viewer').exists()

    def test_member_cannot_add_members(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='member')
        login_as(client, 'meera@taskboard.dev')
        response = client.post(
            f'/api/projects/{project.id}/members',
            {'email': 'lina@example.com', 'role': 'member'},
            format='json',
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestAirtableExport:
    def test_export_creates_airtable_records(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='Q3 Launch', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        Task.objects.create(project=project, title='Do a thing', description='Details', created_by=user, status='todo')

        mock = MockAirtableTable()
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)

        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 1
        assert mock.created[0]['fields']['Title'] == 'Do a thing'
        assert mock.created[0]['fields']['Project'] == 'Q3 Launch'

    def test_export_uses_mock_not_network(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='member')
        mock = MockAirtableTable()
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)
        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 0
        assert mock.created == []

    def test_viewer_cannot_export(self, client, user, other, monkeypatch):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')
        monkeypatch.setattr('projects.airtable.get_table', lambda: MockAirtableTable())
        login_as(client, 'meera@taskboard.dev')
        response = client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 403

    def test_export_requires_config_when_unpatched(self, auth_client, user, settings):
        settings.AIRTABLE_API_KEY = ''
        settings.AIRTABLE_BASE_ID = ''
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 400

    def test_export_is_idempotent_on_second_run(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='Q3 Launch', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        Task.objects.create(project=project, title='Do a thing', created_by=user)
        mock = MockAirtableTable()
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)

        first = auth_client.post(f'/api/projects/{project.id}/export')
        second = auth_client.post(f'/api/projects/{project.id}/export')
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data['created'] == 1
        assert second.data['updated'] == 1
        assert second.data['created'] == 0
        assert len(mock.records) == 1

    def test_export_continues_when_one_record_fails(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='Q3 Launch', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        good = Task.objects.create(project=project, title='Good', created_by=user)
        bad = Task.objects.create(project=project, title='Bad', created_by=user)
        mock = MockAirtableTable()
        mock.fail_task_ids.add(str(bad.id))
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)

        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 1
        assert response.data['failed'] == 1
        assert response.data['errors'][0]['task_id'] == str(bad.id)
        assert mock.created[0]['fields']['TaskId'] == str(good.id)

    def test_export_retries_transient_errors(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='Q3 Launch', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='Retry me', created_by=user)
        mock = MockAirtableTable()
        mock.transient_task_ids[str(task.id)] = 2
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)
        monkeypatch.setattr('projects.airtable.time.sleep', lambda *_: None)

        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 1
        assert response.data['failed'] == 0


@pytest.mark.django_db
class TestComments:
    def test_member_can_post_and_list_chronologically(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)

        first = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'first'}, format='json')
        second = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'second'}, format='json')
        assert first.status_code == 201
        assert second.status_code == 201

        listed = auth_client.get(f'/api/tasks/{task.id}/comments')
        assert listed.status_code == 200
        bodies = [c['body'] for c in listed.data['comments']]
        assert bodies == ['first', 'second']
        assert listed.data['comments'][0]['author']['email'] == 'meera@taskboard.dev'

    def test_viewer_can_read_but_not_post(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')
        task = Task.objects.create(project=project, title='A task', created_by=other)
        Comment.objects.create(task=task, author=other, body='hello')

        login_as(client, 'meera@taskboard.dev')
        listed = client.get(f'/api/tasks/{task.id}/comments')
        assert listed.status_code == 200
        assert len(listed.data['comments']) == 1

        posted = client.post(f'/api/tasks/{task.id}/comments', {'body': 'nope'}, format='json')
        assert posted.status_code == 403

    def test_comments_are_append_only(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)
        created = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'locked'}, format='json')
        comment_id = created.data['comment']['id']
        assert auth_client.patch(f'/api/tasks/{task.id}/comments', {'id': comment_id, 'body': 'edited'}, format='json').status_code in (405, 404)
        assert auth_client.delete(f'/api/tasks/{task.id}/comments').status_code in (405, 404)


@pytest.mark.django_db
class TestActivity:
    def test_task_create_and_status_change_are_logged(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        created = auth_client.post(f'/api/projects/{project.id}/tasks', {'title': 'Ship it'}, format='json')
        task_id = created.data['task']['id']
        auth_client.patch(f'/api/tasks/{task_id}', {'status': 'in_progress'}, format='json')

        feed = auth_client.get(f'/api/projects/{project.id}/activity')
        assert feed.status_code == 200
        actions = [a['action'] for a in feed.data['activities']]
        assert actions[0] == 'task_status_changed'
        assert 'task_created' in actions

    def test_comment_adds_activity(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)
        auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'note'}, format='json')
        feed = auth_client.get(f'/api/projects/{project.id}/activity')
        assert feed.data['activities'][0]['action'] == 'comment_added'
        assert Activity.objects.filter(project=project, action='comment_added').count() == 1

    def test_non_member_cannot_read_activity(self, auth_client, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        response = auth_client.get(f'/api/projects/{project.id}/activity')
        assert response.status_code == 403

    def test_export_is_idempotent_on_second_run(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='Q3 Launch', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        Task.objects.create(project=project, title='Do a thing', created_by=user)

        mock = MockAirtableTable()
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)

        first = auth_client.post(f'/api/projects/{project.id}/export')
        second = auth_client.post(f'/api/projects/{project.id}/export')
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data['created'] == 1
        assert second.data['updated'] == 1
        assert second.data['created'] == 0
        assert len(mock.records) == 1

    def test_export_continues_when_one_record_fails(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        ok = Task.objects.create(project=project, title='Ok task', created_by=user)
        bad = Task.objects.create(project=project, title='Bad task', created_by=user)

        mock = MockAirtableTable()
        mock.fail_task_ids.add(str(bad.id))
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)

        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 1
        assert response.data['failed'] == 1
        assert response.data['errors'][0]['task_id'] == str(bad.id)
        assert mock.records[0]['fields']['TaskId'] == str(ok.id)

    def test_export_retries_transient_errors(self, auth_client, user, monkeypatch):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='Retry me', created_by=user)

        mock = MockAirtableTable()
        mock.transient_task_ids[str(task.id)] = 2
        monkeypatch.setattr('projects.airtable.get_table', lambda: mock)
        monkeypatch.setattr('projects.airtable.time.sleep', lambda *_: None)

        response = auth_client.post(f'/api/projects/{project.id}/export')
        assert response.status_code == 200
        assert response.data['exported'] == 1
        assert response.data['failed'] == 0


@pytest.mark.django_db
class TestComments:
    def test_member_can_post_and_list_chronologically(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)

        first = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'first'}, format='json')
        second = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'second'}, format='json')
        assert first.status_code == 201
        assert second.status_code == 201

        listed = auth_client.get(f'/api/tasks/{task.id}/comments')
        assert listed.status_code == 200
        bodies = [c['body'] for c in listed.data['comments']]
        assert bodies == ['first', 'second']
        assert listed.data['comments'][0]['author']['email'] == 'meera@taskboard.dev'

    def test_viewer_can_read_but_not_post(self, client, user, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        Membership.objects.create(user=user, project=project, role='viewer')
        task = Task.objects.create(project=project, title='A task', created_by=other)
        Comment.objects.create(task=task, author=other, body='hello')

        login_as(client, 'meera@taskboard.dev')
        listed = client.get(f'/api/tasks/{task.id}/comments')
        assert listed.status_code == 200
        assert len(listed.data['comments']) == 1

        posted = client.post(f'/api/tasks/{task.id}/comments', {'body': 'nope'}, format='json')
        assert posted.status_code == 403

    def test_comments_are_append_only(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)
        created = auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'locked'}, format='json')
        comment_id = created.data['comment']['id']

        patch = auth_client.patch(f'/api/tasks/{task.id}/comments', {'body': 'edit'}, format='json')
        assert patch.status_code == 405
        delete = auth_client.delete(f'/api/tasks/{task.id}/comments')
        assert delete.status_code == 405
        assert Comment.objects.filter(id=comment_id, body='locked').exists()

    def test_non_member_cannot_read_comments(self, auth_client, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=other)
        response = auth_client.get(f'/api/tasks/{task.id}/comments')
        assert response.status_code == 403


@pytest.mark.django_db
class TestActivity:
    def test_task_create_and_status_change_are_logged(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')

        created = auth_client.post(f'/api/projects/{project.id}/tasks', {'title': 'Ship it'}, format='json')
        task_id = created.data['task']['id']
        auth_client.patch(f'/api/tasks/{task_id}', {'status': 'done'}, format='json')

        feed = auth_client.get(f'/api/projects/{project.id}/activity')
        assert feed.status_code == 200
        actions = [a['action'] for a in feed.data['activities']]
        assert actions[0] == 'task_status_changed'
        assert 'task_created' in actions

    def test_comment_adds_activity(self, auth_client, user):
        project = Project.objects.create(name='P', owner=user)
        Membership.objects.create(user=user, project=project, role='admin')
        task = Task.objects.create(project=project, title='A task', created_by=user)
        auth_client.post(f'/api/tasks/{task.id}/comments', {'body': 'note'}, format='json')

        feed = auth_client.get(f'/api/projects/{project.id}/activity')
        assert feed.data['activities'][0]['action'] == 'comment_added'
        assert Activity.objects.filter(project=project, action='comment_added').count() == 1

    def test_non_member_cannot_read_activity(self, auth_client, other):
        project = Project.objects.create(name='P', owner=other)
        Membership.objects.create(user=other, project=project, role='admin')
        response = auth_client.get(f'/api/projects/{project.id}/activity')
        assert response.status_code == 403

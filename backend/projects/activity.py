from .models import Activity


def log_activity(project_id, actor, action, task=None, metadata=None):
    return Activity.objects.create(
        project_id=project_id,
        actor=actor,
        action=action,
        task=task,
        metadata=metadata or {},
    )

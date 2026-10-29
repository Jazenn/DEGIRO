"""Resolve explicit broker timing evidence or the owner's Amsterdam convention."""


def source_timezone_policy(settings):
    timezone = settings.get('source_timezone', {})
    name, evidence = timezone.get('name'), timezone.get('evidence')
    if not isinstance(name, str) or not name or not isinstance(evidence, str) or not evidence.strip():
        return None
    if name and evidence and timezone.get('verified') is True:
        return {'name': name, 'status': 'verified', 'evidence': evidence}
    if (name == 'Europe/Amsterdam' and evidence
            and timezone.get('assumption_approved') is True):
        return {'name': name, 'status': 'owner_assumed', 'evidence': evidence}
    return None

"""Literal component identity with a narrow database-label spacing view."""
import re


def source_name_supported(component, text):
    name=component.get('name')
    if not isinstance(name,str) or not name:
        return False
    if name in text:
        return True
    if component.get('kind') not in {'internal_database','external_database'}:
        return False
    # A physical SQL identifier is unchanged by a space before the descriptive
    # Chinese table/database suffix. Never shorten names or fold identifiers.
    label=re.fullmatch(r'([A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*)[ \t]*(表|数据库)',name)
    if not label:
        return False
    identifier,suffix=label.groups()
    pattern=r'(?<![A-Za-z0-9_$.])'+re.escape(identifier)+r'[ \t]*'+re.escape(suffix)
    return any(re.search(pattern,line) for line in text.splitlines())

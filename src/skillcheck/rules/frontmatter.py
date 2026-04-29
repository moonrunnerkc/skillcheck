from __future__ import annotations

from skillcheck.rules.frontmatter_common import _field_line
from skillcheck.rules.frontmatter_description import (
    check_description_max_length,
    check_description_no_xml_tags,
    check_description_non_empty,
    check_description_person_voice,
    check_description_required,
    check_description_type,
)
from skillcheck.rules.frontmatter_fields import (
    check_unknown_fields,
    check_yaml_anchors,
)
from skillcheck.rules.frontmatter_name import (
    check_name_charset,
    check_name_consecutive_hyphens,
    check_name_directory_match,
    check_name_leading_trailing_hyphen,
    check_name_max_length,
    check_name_required,
    check_name_reserved_words,
    check_name_type,
)

__all__ = [
    "_field_line",
    "check_description_max_length",
    "check_description_no_xml_tags",
    "check_description_non_empty",
    "check_description_person_voice",
    "check_description_required",
    "check_description_type",
    "check_name_charset",
    "check_name_consecutive_hyphens",
    "check_name_directory_match",
    "check_name_leading_trailing_hyphen",
    "check_name_max_length",
    "check_name_required",
    "check_name_reserved_words",
    "check_name_type",
    "check_unknown_fields",
    "check_yaml_anchors",
]

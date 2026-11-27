"""Admin-controlled institution choices and source-label resolution."""

import re
import unicodedata

from django.conf import settings

from catalog.models import Institution, InstitutionFaculty


class InstitutionResolutionError(ValueError):
    pass


def _fold(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^A-Z0-9]+', '', text.upper())


def selectable_institutions():
    institutions = Institution.objects.filter(
        status=Institution.Status.ACTIVE,
        is_selectable=True,
    )
    if getattr(settings, 'UNEMI', False):
        institutions = institutions.filter(acronym__iexact='UNEMI')
    return institutions.prefetch_related('faculties').order_by('acronym', 'name')


def institution_catalog_payload():
    """Return the active admin catalog in the shape consumed by form widgets."""
    return [
        {
            'institution_id': institution.pk,
            'acronym': institution.acronym,
            'name': institution.name,
            'faculties': [
                {'value': faculty.code, 'label': faculty.name}
                for faculty in institution.faculties.filter(
                    status=InstitutionFaculty.Status.ACTIVE
                ).order_by('name')
            ],
        }
        for institution in selectable_institutions()
    ]


def resolve_selectable_institution(
    value=None,
    label=None,
    *,
    allow_single_default=False,
    institutions=None,
):
    """Resolve a form value or imported SPSS value label without guessing."""
    institutions = list(selectable_institutions() if institutions is None else institutions)
    if (allow_single_default and len(institutions) == 1
            and not str(label or '').strip() and not str(value or '').strip()):
        return institutions[0]
    candidates = [_fold(candidate) for candidate in (label, value) if str(candidate or '').strip()]

    # Exact acronym/name matching wins; imported labels can also include both.
    for candidate in candidates:
        exact_matches = [
            institution for institution in institutions
            if candidate in {_fold(institution.acronym), _fold(institution.name)}
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise InstitutionResolutionError('La institución coincide con varias entradas del catálogo.')

    for candidate in candidates:
        partial_matches = {
            institution.pk: institution for institution in institutions
            if (_fold(institution.acronym) and _fold(institution.acronym) in candidate)
            or (_fold(institution.name) and _fold(institution.name) in candidate)
        }
        if len(partial_matches) == 1:
            return next(iter(partial_matches.values()))
        if len(partial_matches) > 1:
            raise InstitutionResolutionError('La etiqueta coincide con varias instituciones habilitadas.')

    if not candidates and allow_single_default and len(institutions) == 1:
        return institutions[0]

    supplied = str(label or value or '').strip()
    if supplied:
        raise InstitutionResolutionError(
            f"No se pudo asociar el valor '{supplied}' a una institución activa del catálogo. "
            "Revise las etiquetas de UNIVERSIDAD del archivo o complete el catálogo en Admin."
        )
    raise InstitutionResolutionError(
        "No se indicó una institución y el catálogo no permite determinarla sin ambigüedad."
    )


def filter_to_selectable_institutions(queryset, relation='institution'):
    """Restrict a Patient or Visit queryset to institutions enabled by an admin."""
    return queryset.filter(**{f'{relation}__in': selectable_institutions()})


def institution_is_selectable(institution_id):
    return selectable_institutions().filter(pk=institution_id).exists()

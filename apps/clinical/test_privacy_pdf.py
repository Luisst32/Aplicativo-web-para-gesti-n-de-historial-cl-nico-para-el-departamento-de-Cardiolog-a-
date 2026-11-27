"""Modo de protección de datos: PDFs sin datos personales, solo con N.° de ficha."""
import base64
import hashlib
import io
import re
import zipfile
import zlib
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity
from clinical.models import Patient, Visit, SecureShare
from clinical.pdf import generate_clinical_sheet_pdf
from security.models import User

SENSITIVE = ('Zuleimar', 'Quintanilla', 'Barbosa', '0912345678', '0987654321', 'pdfpriv@example.invalid')
STUDY_CODE = 'FICHA7788'


def pdf_text(pdf_bytes):
    """Texto de los content streams (fuentes Type1 estándar) sin dependencias externas."""
    chunks = []
    pattern = rb'<<((?:(?!>>).)*)>>\s*stream\r?\n(.*?)\s*endstream'
    for match in re.finditer(pattern, pdf_bytes, re.S):
        header, raw = match.group(1), match.group(2)
        try:
            if b'ASCII85Decode' in header:
                data = raw.strip().removeprefix(b'<~').removesuffix(b'~>')
                raw = base64.a85decode(data)
            if b'FlateDecode' in header:
                raw = zlib.decompress(raw)
        except (ValueError, zlib.error):
            continue
        chunks.append(raw)
    return b'\n'.join(chunks).decode('latin-1')


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PrivacyModePdfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='privacy_pdf_actor', password='Synthetic-privacy-2026!',
                                            email='actor@example.invalid')
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        province, _ = Province.objects.get_or_create(country=country, iso_code='EC-G', defaults={'name': 'Guayas'})
        canton, _ = Canton.objects.get_or_create(province=province, dpa_code='0910', defaults={'name': 'Milagro'})
        sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        institution = Institution.objects.create(acronym='PRIV_PDF', name='Synthetic privacy institution')
        cls.patient = Patient.objects.create(
            id_card='0912345678', first_names='Zuleimar', last_name1='Quintanilla', last_name2='Barbosa',
            phone='0987654321', email='pdfpriv@example.invalid', birth_date=date(1990, 5, 17),
            birth_canton=canton, institution=institution, sex=sex, ethnicity=ethnicity, created_by=cls.user,
        )
        cls.visit = Visit.objects.create(patient=cls.patient, evaluator=cls.user, study_code=STUDY_CODE,
                                         visit_date=date(2026, 1, 1), residence_canton=canton)

    def setUp(self):
        self.client.force_login(self.user)

    def assert_redacted(self, pdf_bytes):
        text = pdf_text(pdf_bytes)
        for value in SENSITIVE:
            self.assertNotIn(value, text)
        self.assertNotIn('1990-05-17', text)
        self.assertIn(STUDY_CODE, text)
        self.assertIn('[Protegido]', text)

    def test_generator_includes_personal_data_only_without_privacy(self):
        full = pdf_text(generate_clinical_sheet_pdf(self.visit))
        for value in SENSITIVE:
            self.assertIn(value, full)
        self.assert_redacted(generate_clinical_sheet_pdf(self.visit, privacy_mode=True))

    def test_single_download_honours_privacy_flag(self):
        url = f'/clinical/ficha/pdf/?paciente={self.patient.pk}&download=1'
        normal = self.client.get(url)
        self.assertEqual(normal.status_code, 200)
        self.assertIn('Zuleimar', pdf_text(normal.content))
        private = self.client.get(url + '&privacidad=1')
        self.assertEqual(private.status_code, 200)
        self.assert_redacted(private.content)
        self.assertIn(STUDY_CODE, private['Content-Disposition'])

    def test_batch_download_single_and_zip_are_redacted(self):
        single = self.client.get(f'/clinical/api/ficha/descargar-seleccionados/?patient_ids={self.patient.pk}&privacidad=1')
        self.assertEqual(single.status_code, 200)
        self.assert_redacted(single.content)

        from clinical.views import _generate_zip_stream
        archive = zipfile.ZipFile(io.BytesIO(_generate_zip_stream([self.visit, self.visit], privacy_mode=True)))
        self.assertEqual(sorted(archive.namelist()),
                         [f'Ficha_Clinica_{STUDY_CODE}.pdf', f'Ficha_Clinica_{STUDY_CODE}_2.pdf'])
        for name in archive.namelist():
            self.assertNotIn('Zuleimar', name)
            self.assert_redacted(archive.read(name))

        normal = zipfile.ZipFile(io.BytesIO(_generate_zip_stream([self.visit])))
        self.assertIn('Zuleimar', normal.namelist()[0])

    def test_email_share_stores_privacy_and_recipient_gets_redacted_pdf(self):
        response = self.client.post('/clinical/api/ficha/enviar-correo/', {
            'patient_ids': [self.patient.pk],
            'recipients': ['destino@example.invalid'],
            'duration_hours': 48,
            'privacy_mode': True,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        share = SecureShare.objects.get(recipient_email='destino@example.invalid')
        self.assertTrue(share.privacy_mode)
        self.assertEqual(len(mail.outbox), 1)
        for value in SENSITIVE:
            self.assertNotIn(value, mail.outbox[0].body)

    def public_download(self, privacy_mode):
        token, code = f'synthetic-token-{privacy_mode}', '246810'
        share = SecureShare.objects.create(
            visit=self.visit, recipient_email='destino@example.invalid',
            token_hash=hashlib.sha256(token.encode()).hexdigest(), code_hash=make_password(code),
            expires_at=timezone.now() + timedelta(hours=2), created_by=self.user, privacy_mode=privacy_mode,
        )
        share.visits.set([self.visit])
        self.client.logout()
        page = self.client.post(f'/clinical/compartir/{token}/', {'code': code})
        self.assertEqual(page.status_code, 200)
        pdf = self.client.get(f'/clinical/compartir/{token}/?descarga=pdf&visit_id={self.visit.pk}')
        self.assertEqual(pdf.status_code, 200)
        return page, pdf

    def test_public_share_with_privacy_hides_name_and_redacts_pdf(self):
        page, pdf = self.public_download(privacy_mode=True)
        self.assertNotContains(page, 'Zuleimar')
        self.assertContains(page, STUDY_CODE)
        self.assert_redacted(pdf.content)

    def test_public_share_without_privacy_keeps_full_sheet(self):
        _, pdf = self.public_download(privacy_mode=False)
        self.assertIn('Zuleimar', pdf_text(pdf.content))

from django.db import models


class Country(models.Model):
    """
    Country catalog based on ISO 3166-1 alpha-3 (Mapped to catalog.country).
    """
    country_id = models.AutoField(primary_key=True, db_column='country_id')
    iso_alpha3 = models.CharField(max_length=3, db_column='iso_alpha3', help_text="ISO 3166-1 alpha-3 code")
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."country'
        constraints = [
            models.UniqueConstraint(fields=['iso_alpha3'], name='uq_country_code'),
            models.UniqueConstraint(fields=['name'], name='uq_country_name')
        ]
        verbose_name = "Country"
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"{self.name} ({self.iso_alpha3})"


class Province(models.Model):
    """
    Province / State catalog based on ISO 3166-2:EC (Mapped to catalog.province).
    """
    province_id = models.AutoField(primary_key=True, db_column='province_id')
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        db_column='country_id',
        related_name='provinces'
    )
    iso_code = models.CharField(max_length=6, blank=True, null=True, db_column='iso_code', help_text="ISO 3166-2 code (e.g., EC-G)")
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."province'
        constraints = [
            models.UniqueConstraint(fields=['country', 'name'], name='uq_province_country_name'),
            models.UniqueConstraint(fields=['country', 'province_id'], name='uq_province_country_id')
        ]
        verbose_name = "Province"
        verbose_name_plural = "Provinces"

    def __str__(self):
        return f"{self.name} ({self.country.iso_alpha3})"


class Canton(models.Model):
    """
    Canton / Municipality catalog based on Ecuadorian DPA codes (Mapped to catalog.canton).
    """
    canton_id = models.AutoField(primary_key=True, db_column='canton_id')
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        db_column='province_id',
        related_name='cantons'
    )
    dpa_code = models.CharField(max_length=4, blank=True, null=True, db_column='dpa_code', help_text="DPA code (e.g., 0901)")
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."canton'
        constraints = [
            models.UniqueConstraint(fields=['province', 'name'], name='uq_canton_province_name')
        ]
        verbose_name = "Canton"
        verbose_name_plural = "Cantons"

    def __str__(self):
        return f"{self.name} ({self.province.name})"


class Institution(models.Model):
    """
    Academic or Healthcare Institution catalog (Mapped to catalog.institution).
    """
    institution_id = models.AutoField(primary_key=True, db_column='institution_id')
    acronym = models.CharField(max_length=10, db_column='acronym')
    name = models.CharField(max_length=150, db_column='name')

    class Meta:
        db_table = 'catalog"."institution'
        constraints = [
            models.UniqueConstraint(fields=['acronym'], name='uq_institution_acronym')
        ]
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return f"{self.acronym} - {self.name}"

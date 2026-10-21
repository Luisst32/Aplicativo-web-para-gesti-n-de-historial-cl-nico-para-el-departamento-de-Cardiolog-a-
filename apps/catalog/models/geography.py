from django.db import models


class Country(models.Model):
    """
    Country catalog based on ISO 3166-1 alpha-3 (catalogo.Pais).
    Fiel a bd_final: CodigoIso3166Alfa3 CHAR(3), Nombre VARCHAR(100).
    """
    country_id = models.AutoField(primary_key=True, db_column='country_id')
    iso_alpha3 = models.CharField(max_length=3, db_column='iso_alpha3', help_text="ISO 3166-1 alpha-3 code")
    name = models.CharField(max_length=100, db_column='name')

    class Meta:
        db_table = 'catalog"."country'
        constraints = [
            models.UniqueConstraint(fields=['iso_alpha3'], name='uq_country_iso_alpha3'),
            models.UniqueConstraint(fields=['name'], name='uq_country_name')
        ]
        verbose_name = "Country"
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"{self.name} ({self.iso_alpha3})"


class Province(models.Model):
    """
    Province / State catalog based on ISO 3166-2:EC (catalogo.Provincia).
    """
    province_id = models.AutoField(primary_key=True, db_column='province_id')
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        db_column='country_id',
        related_name='provinces'
    )
    iso_code = models.CharField(max_length=6, db_column='iso_code', help_text="ISO 3166-2 code (e.g., EC-G)")
    name = models.CharField(max_length=100, db_column='name')

    class Meta:
        db_table = 'catalog"."province'
        constraints = [
            models.UniqueConstraint(fields=['country', 'iso_code'], name='uq_province_country_iso_code')
        ]
        verbose_name = "Province"
        verbose_name_plural = "Provinces"

    def __str__(self):
        return f"{self.name} ({self.country.iso_alpha3})"


class Canton(models.Model):
    """
    Canton / Municipality catalog based on Ecuadorian DPA codes (catalogo.Canton).
    """
    canton_id = models.AutoField(primary_key=True, db_column='canton_id')
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        db_column='province_id',
        related_name='cantons'
    )
    dpa_code = models.CharField(max_length=4, db_column='dpa_code', help_text="DPA code (e.g., 0901)")
    name = models.CharField(max_length=100, db_column='name')

    class Meta:
        db_table = 'catalog"."canton'
        constraints = [
            models.UniqueConstraint(fields=['province', 'dpa_code'], name='uq_canton_province_dpa_code')
        ]
        verbose_name = "Canton"
        verbose_name_plural = "Cantons"

    def __str__(self):
        return f"{self.name} ({self.province.name})"


class Institution(models.Model):
    """
    Academic or Healthcare Institution catalog (catalogo.Institucion).
    """
    institution_id = models.AutoField(primary_key=True, db_column='institution_id')
    acronym = models.CharField(max_length=20, db_column='acronym')
    name = models.CharField(max_length=150, db_column='name')

    class Meta:
        db_table = 'catalog"."institution'
        constraints = [
            models.UniqueConstraint(fields=['acronym'], name='uq_institution_acronym'),
            models.UniqueConstraint(fields=['name'], name='uq_institution_name')
        ]
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return f"{self.acronym} - {self.name}"

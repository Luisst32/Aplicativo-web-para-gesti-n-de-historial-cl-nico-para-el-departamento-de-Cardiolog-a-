from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0003_patient_status_visit_status'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE VIEW clinical.v_resumen_paciente_visita AS
            SELECT 
                p.patient_id,
                p.id_card AS cedula,
                CONCAT(p.first_names, ' ', p.last_name1, CASE WHEN p.last_name2 IS NOT NULL AND p.last_name2 <> '' THEN ' ' || p.last_name2 ELSE '' END) AS nombre_completo,
                p.birth_date AS fecha_nacimiento,
                s.name AS sexo,
                p.email AS correo,
                p.phone AS telefono,
                v.visit_id,
                v.study_code AS codigo_estudio,
                v.visit_date AS fecha_visita,
                v.study_year AS anio_estudio,
                v.status AS estado_visita,
                v.faculty AS facultad,
                sc.name AS estamento,
                c.name AS ciudad,
                pr.name AS provincia,
                ant.weight_kg AS peso,
                ant.height_cm AS talla,
                ant.waist_circumference_cm AS perimetro_abdominal,
                ant.bmi AS imc,
                ant.body_surface_area AS asc,
                vs.systolic_bp AS tas,
                vs.diastolic_bp AS tsi,
                vs.oxygen_saturation AS sat_o2,
                vs.heart_rate AS fc,
                CONCAT(u.first_name, ' ', u.last_name) AS evaluador
            FROM clinical.patient p
            LEFT JOIN catalog.sex s ON p.sex_id = s.sex_id
            LEFT JOIN clinical.visit v ON p.patient_id = v.patient_id
            LEFT JOIN catalog.staff_category sc ON v.staff_category_id = sc.staff_category_id
            LEFT JOIN catalog.canton c ON v.residence_canton_id = c.canton_id
            LEFT JOIN catalog.province pr ON c.province_id = pr.province_id
            LEFT JOIN clinical.anthropometry ant ON v.visit_id = ant.visit_id
            LEFT JOIN clinical.vital_signs vs ON v.visit_id = vs.visit_id
            LEFT JOIN security.user u ON v.evaluator_id = u.user_id;
            """,
            reverse_sql="DROP VIEW IF EXISTS clinical.v_resumen_paciente_visita;"
        )
    ]

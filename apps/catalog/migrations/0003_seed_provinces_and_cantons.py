from django.db import migrations


def seed_geography_and_institutions(apps, schema_editor):
    Country = apps.get_model('catalog', 'Country')
    Province = apps.get_model('catalog', 'Province')
    Canton = apps.get_model('catalog', 'Canton')
    Institution = apps.get_model('catalog', 'Institution')

    ecuador, _ = Country.objects.get_or_create(
        iso_alpha3="ECU",
        defaults={"name": "Ecuador"}
    )

    provincias_info = [
        ("EC-A", "Azuay", "01"),
        ("EC-B", "Bolívar", "02"),
        ("EC-F", "Cañar", "03"),
        ("EC-C", "Carchi", "04"),
        ("EC-X", "Cotopaxi", "05"),
        ("EC-H", "Chimborazo", "06"),
        ("EC-O", "El Oro", "07"),
        ("EC-E", "Esmeraldas", "08"),
        ("EC-G", "Guayas", "09"),
        ("EC-I", "Imbabura", "10"),
        ("EC-L", "Loja", "11"),
        ("EC-R", "Los Ríos", "12"),
        ("EC-M", "Manabí", "13"),
        ("EC-S", "Morona Santiago", "14"),
        ("EC-N", "Napo", "15"),
        ("EC-Y", "Pastaza", "16"),
        ("EC-P", "Pichincha", "17"),
        ("EC-T", "Tungurahua", "18"),
        ("EC-Z", "Zamora Chinchipe", "19"),
        ("EC-W", "Galápagos", "20"),
        ("EC-U", "Sucumbíos", "21"),
        ("EC-D", "Orellana", "22"),
        ("EC-SD", "Santo Domingo de los Tsáchilas", "23"),
        ("EC-SE", "Santa Elena", "24"),
    ]

    provincias = {}
    prov_dpa_map = {}
    for iso, nombre, dpa_pref in provincias_info:
        prov, _ = Province.objects.get_or_create(
            country=ecuador, iso_code=iso, defaults={"name": nombre}
        )
        if prov.name != nombre:
            prov.name = nombre
            prov.save()
        provincias[nombre] = prov
        prov_dpa_map[nombre] = dpa_pref

    cantones_dict = {
        'Azuay': ['Cuenca', 'Camilo Ponce Enríquez', 'Chordeleg', 'El Pan', 'Girón', 'Guachapala', 'Gualaceo', 'Nabón', 'Oña', 'Paute', 'Pucará', 'San Fernando', 'Santa Isabel', 'Sevilla de Oro', 'Sígsig'],
        'Bolívar': ['Guaranda', 'Caluma', 'Chillanes', 'Chimbo', 'Echeandía', 'Las Naves', 'San Miguel'],
        'Cañar': ['Azogues', 'Biblián', 'Cañar', 'Déleg', 'El Tambo', 'La Troncal', 'Suscal'],
        'Carchi': ['Tulcán', 'Bolívar', 'Espejo', 'Mira', 'Montúfar', 'San Pedro de Huaca'],
        'Cotopaxi': ['Latacunga', 'La Maná', 'Pangua', 'Pujilí', 'Salcedo', 'Saquisilí', 'Sigchos'],
        'Chimborazo': ['Riobamba', 'Alausí', 'Chambo', 'Chunchi', 'Colta', 'Cumandá', 'Guamote', 'Guano', 'Pallatanga', 'Penipe'],
        'El Oro': ['Machala', 'Arenillas', 'Atahualpa', 'Balsas', 'Chilla', 'El Guabo', 'Huaquillas', 'Las Lajas', 'Marcabelí', 'Pasaje', 'Piñas', 'Portovelo', 'Santa Rosa', 'Zaruma'],
        'Esmeraldas': ['Esmeraldas', 'Atacames', 'Eloy Alfaro', 'Muisne', 'Quinindé', 'Rioverde', 'San Lorenzo'],
        'Galápagos': ['San Cristóbal', 'Isabela', 'Santa Cruz'],
        'Guayas': ['Milagro', 'Guayaquil', 'Alfredo Baquerizo Moreno (Juján)', 'Balao', 'Balzar', 'Colimes', 'Daule', 'Durán', 'El Empalme', 'El Triunfo', 'General Antonio Elizalde (Bucay)', 'Isidro Ayora', 'Lomas de Sargentillo', 'Marcelino Maridueña', 'Naranjal', 'Naranjito', 'Nobol', 'Palestina', 'Pedro Carbo', 'Playas (General Villamil)', 'Salitre (Urbina Jado)', 'Samborondón', 'Santa Lucía', 'Simón Bolívar', 'Yaguachi'],
        'Imbabura': ['Ibarra', 'Antonio Ante', 'Cotacachi', 'Otavalo', 'Pimampiro', 'San Miguel de Urcuquí'],
        'Loja': ['Loja', 'Calvas', 'Catamayo', 'Celica', 'Chaguarpamba', 'Espíndola', 'Gonzanamá', 'Macará', 'Olmedo', 'Paltas', 'Pindal', 'Puyango', 'Quilanga', 'Saraguro', 'Sozoranga', 'Zapotillo'],
        'Los Ríos': ['Babahoyo', 'Baba', 'Buena Fe', 'Mocache', 'Montalvo', 'Palenque', 'Puebloviejo', 'Quevedo', 'Quinsaloma', 'Urdaneta', 'Valencia', 'Ventanas', 'Vinces'],
        'Manabí': ['Portoviejo', 'Bolívar (Calceta)', 'Chone', 'El Carmen', 'Flavio Alfaro', 'Jama', 'Jaramijó', 'Jipijapa', 'Junín', 'Manta', 'Montecristi', 'Olmedo', 'Paján', 'Pedernales', 'Pichincha', 'Puerto López', 'Rocafuerte', 'San Vicente', 'Santa Ana', 'Sucre (Bahía de Caráquez)', 'Tosagua', '24 de Mayo'],
        'Morona Santiago': ['Morona (Macas)', 'Gualaquiza', 'Huamboya', 'Limón Indanza', 'Logroño', 'Pablo Sexto', 'Palora', 'San Juan Bosco', 'Santiago de Méndez', 'Sucúa', 'Taisha', 'Tiwintza'],
        'Napo': ['Tena', 'Archidona', 'Carlos Julio Arosemena Tola', 'El Chaco', 'Quijos (Baeza)'],
        'Orellana': ['Francisco de Orellana (Coca)', 'Aguarico', 'La Joya de los Sachas', 'Loreto'],
        'Pastaza': ['Pastaza (Puyo)', 'Arajuno', 'Mera', 'Santa Clara'],
        'Pichincha': ['Quito', 'Cayambe', 'Mejía', 'Pedro Moncayo', 'Pedro Vicente Maldonado', 'Puerto Quito', 'Rumiñahui', 'San Miguel de Los Bancos'],
        'Santa Elena': ['Santa Elena', 'La Libertad', 'Salinas'],
        'Santo Domingo de los Tsáchilas': ['Santo Domingo', 'La Concordia'],
        'Sucumbíos': ['Lago Agrio (Nueva Loja)', 'Cascales', 'Cuyabeno', 'Gonzalo Pizarro', 'Putumayo', 'Shushufindi', 'Sucumbíos'],
        'Tungurahua': ['Ambato', 'Baños de Agua Santa', 'Cevallos', 'Mocha', 'Patate', 'Quero', 'San Pedro de Pelileo', 'Santiago de Píllaro', 'Tisaleo'],
        'Zamora Chinchipe': ['Zamora', 'Centinela del Cóndor', 'Chinchipe', 'El Pangui', 'Nangaritza', 'Palanda', 'Paquisha', 'Yacuambi', 'Yantzaza']
    }

    for prov_nombre, c_list in cantones_dict.items():
        prov = provincias.get(prov_nombre)
        if not prov:
            continue
        dpa_pref = prov_dpa_map.get(prov_nombre, "99")
        existing_dpas = set(Canton.objects.filter(province=prov).values_list('dpa_code', flat=True))

        for nombre in c_list:
            cant = Canton.objects.filter(province=prov, name=nombre).first()
            if not cant:
                dpa_code = None
                for num in range(1, 100):
                    cand = f"{dpa_pref}{num:02d}"[:4]
                    if cand not in existing_dpas:
                        dpa_code = cand
                        existing_dpas.add(cand)
                        break
                Canton.objects.create(
                    province=prov,
                    dpa_code=dpa_code or f"{dpa_pref}99"[:4],
                    name=nombre
                )

    Institution.objects.get_or_create(
        acronym="UNEMI",
        defaults={"name": "Universidad Estatal de Milagro", "status": "ACTIVE"}
    )
    Institution.objects.get_or_create(
        acronym="ESPOL",
        defaults={"name": "Escuela Superior Politécnica del Litoral", "status": "ACTIVE"}
    )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_answeroption_status_ecgrhythm_status_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_geography_and_institutions, reverse_code=migrations.RunPython.noop),
    ]

"""autorizaciones_maritimas

Adapta el sistema de storage al flujo de Autorizaciones Marítimas de UCVMM
(documento "Documentación requerida para las autorizaciones marítimas").

El storage deja de ser una función aparte y pasa a ser la capa documental del
expediente: `transfers` / `transfer_files` se reemplazan por `solicitudes`,
`solicitud_tripulantes`, `solicitud_documentos` y `solicitud_eventos`. Las
transferencias sueltas que hubiera se eliminan con sus archivos — eran enlaces
de 7 días sin lugar en el modelo nuevo (en el servidor, avisar antes).

Además:
  - Catálogo de trámites (Formulario 3) y documentos requeridos por trámite.
  - Puestos de control (+ funcionarios asignados), agencias navieras (+ sus
    usuarios) y países (con la marca de nacionalidad restringida — ninguna
    viene marcada: la lista oficial la define el administrador).
  - Permiso T-FINALIZAR-PUERTO y rol "Puesto de Control" (no es de sistema).
  - Cuentas locales: intentos fallidos, bloqueo temporal y cambio obligatorio.
  - Valores nuevos del enum de bitácora (no se quitan al bajar: PostgreSQL no
    permite borrarlos sin recrear el tipo, y no estorban).

Revision ID: d4f1a8c27e90
Revises: e2a6b8f3d1c7
Create Date: 2026-10-07

"""
import shutil
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f1a8c27e90'
down_revision: Union[str, None] = 'e2a6b8f3d1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NUEVAS_ACCIONES = [
    'SOLICITUD_CREADA', 'SOLICITUD_CONSULTADA', 'SOLICITUD_CORREGIDA',
    'IMPEDIMENTOS_REGISTRADOS', 'SOLICITUD_DEVUELTA', 'SOLICITUD_APROBADA',
    'SOLICITUD_NEGADA', 'SOLICITUD_COMENTADA', 'SOLICITUD_FINALIZADA',
    'SOLICITUD_EXPIRADA', 'AUTORIZACION_DESCARGADA', 'AUTORIZACION_VERIFICADA',
    'DOCUMENTO_VISTO', 'DOCUMENTO_DESCARGADO',
    'USUARIO_CREADO', 'USUARIO_ACTUALIZADO', 'USUARIO_ELIMINADO',
    'CONTRASENA_CAMBIADA', 'CONTRASENA_RESTABLECIDA', 'CUENTA_BLOQUEADA',
    'ROL_CREADO', 'ROL_ACTUALIZADO', 'ROL_ELIMINADO',
    'PERMISO_CREADO', 'PERMISO_ACTUALIZADO', 'PERMISO_ELIMINADO',
    'PUESTO_CREADO', 'PUESTO_ACTUALIZADO', 'PUESTO_ELIMINADO',
    'AGENCIA_CREADA', 'AGENCIA_ACTUALIZADA', 'AGENCIA_ELIMINADA',
    'PAIS_ACTUALIZADO',
]

ESTADOS = ('review', 'returned', 'approved', 'denied', 'finalized', 'expired')
RANGOS = ('marino', 'militar', 'tecnico', 'supernumerario', 'superintendente')

# ── Catálogo de documentos ───────────────────────────────────────────────────
# (codigo, nombre, descripcion, requiere_libreta)
DOCUMENTOS = [
    ('DOC-VISA-MARINO',           'Visa Especial de Marino',                None,                 False),
    ('DOC-GENERALES-PASAPORTE',   'Generales de Pasaporte',                 None,                 False),
    ('DOC-LIBRETA-MARINO',        'Libreta de Marino',                      None,                 True),
    ('DOC-BOLETO-AEREO',          'Copia de Boleto Aéreo',                  None,                 False),
    ('DOC-LISTA-TRIPULANTES',     'Lista de Tripulantes',                   'Sellada y firmada.', False),
    ('DOC-FORM6-CUSTODIA',        'Formulario No. 6 — Custodia aprobada',
     'Se exige a cada tripulante de nacionalidad restringida.',                                   False),
    ('DOC-FORM7-RESPONSABILIDAD', 'Carta de Responsabilidad (Form. No. 7)', None,                 False),
    ('DOC-CITA-CONSULADO',        'Copia de cita del Consulado',            None,                 False),
    ('DOC-REPORTE-MEDICO',        'Reporte Médico del barco',               'En español.',        False),
]

# ── Tipos de trámite (Formulario 3) ──────────────────────────────────────────
NOTA_RENOVACION = (
    'A su retorno, el agente naviero deberá presentar en el puesto de control '
    'de embarque copia de la Prórroga de Extensión.'
)
# (codigo, nombre, buque, puerto, puerto_desemb, motivo, clinica, valida_vigencia, nota, orden)
TIPOS_TRAMITE = [
    ('F3-EMBARQUE',        'Embarque',                                           True, False, False, False, False, True,  None,            1),
    ('F3-DESEMBARQUE',     'Desembarque',                                        True, False, False, False, False, False, None,            2),
    ('F3-CAMBIO-PUERTO',   'Cambio de Puerto',                                   True, True,  False, False, False, False, None,            3),
    ('F3-CAMBIO-NAVE',     'Cambio de Nave',                                     True, False, False, False, False, False, None,            4),
    ('F3-RENOV-PASAPORTE', 'Renovación de Pasaporte',                            True, False, True,  False, False, False, NOTA_RENOVACION, 5),
    ('F3-TECNICO',         'Autorización de Técnico, Superintendente o Supernumerario',
                                                                                 True, False, False, False, False, False, None,            6),
    ('F3-SHORE-PASS',      'Sellado de Shore Pass',                              True, False, False, True,  False, True,  None,            7),
    ('F3-URGENCIA-MEDICA', 'Urgencias o Atención Médica',                        True, False, True,  False, True,  True,  None,            8),
]

# ── Matriz trámite → documentos (codigo_tramite, codigo_documento, alcance, condicion, orden) ──
MATRIZ = [
    ('F3-EMBARQUE', 'DOC-VISA-MARINO',         'marino', 'siempre',        1),
    ('F3-EMBARQUE', 'DOC-GENERALES-PASAPORTE', 'marino', 'siempre',        2),
    ('F3-EMBARQUE', 'DOC-LIBRETA-MARINO',      'marino', 'solo_panamenos', 3),

    ('F3-DESEMBARQUE', 'DOC-BOLETO-AEREO',        'marino',    'siempre',                  1),
    ('F3-DESEMBARQUE', 'DOC-GENERALES-PASAPORTE', 'marino',    'siempre',                  2),
    ('F3-DESEMBARQUE', 'DOC-LIBRETA-MARINO',      'marino',    'siempre',                  3),
    ('F3-DESEMBARQUE', 'DOC-LISTA-TRIPULANTES',   'solicitud', 'siempre',                  4),
    ('F3-DESEMBARQUE', 'DOC-FORM6-CUSTODIA',      'marino',    'nacionalidad_restringida', 5),

    ('F3-CAMBIO-PUERTO', 'DOC-VISA-MARINO',         'marino', 'siempre', 1),
    ('F3-CAMBIO-PUERTO', 'DOC-GENERALES-PASAPORTE', 'marino', 'siempre', 2),

    ('F3-CAMBIO-NAVE', 'DOC-VISA-MARINO',         'marino', 'siempre', 1),
    ('F3-CAMBIO-NAVE', 'DOC-GENERALES-PASAPORTE', 'marino', 'siempre', 2),

    ('F3-RENOV-PASAPORTE', 'DOC-GENERALES-PASAPORTE',   'marino',    'siempre',                  1),
    ('F3-RENOV-PASAPORTE', 'DOC-FORM7-RESPONSABILIDAD', 'solicitud', 'siempre',                  2),
    ('F3-RENOV-PASAPORTE', 'DOC-LISTA-TRIPULANTES',     'solicitud', 'siempre',                  3),
    ('F3-RENOV-PASAPORTE', 'DOC-CITA-CONSULADO',        'marino',    'siempre',                  4),
    ('F3-RENOV-PASAPORTE', 'DOC-LIBRETA-MARINO',        'marino',    'siempre',                  5),
    ('F3-RENOV-PASAPORTE', 'DOC-FORM6-CUSTODIA',        'marino',    'nacionalidad_restringida', 6),

    ('F3-TECNICO', 'DOC-FORM7-RESPONSABILIDAD', 'solicitud', 'siempre', 1),
    ('F3-TECNICO', 'DOC-GENERALES-PASAPORTE',   'marino',    'siempre', 2),

    ('F3-SHORE-PASS', 'DOC-GENERALES-PASAPORTE', 'marino',    'siempre',                  1),
    ('F3-SHORE-PASS', 'DOC-LISTA-TRIPULANTES',   'solicitud', 'siempre',                  2),
    ('F3-SHORE-PASS', 'DOC-LIBRETA-MARINO',      'marino',    'siempre',                  3),
    ('F3-SHORE-PASS', 'DOC-FORM6-CUSTODIA',      'marino',    'nacionalidad_restringida', 4),

    ('F3-URGENCIA-MEDICA', 'DOC-FORM7-RESPONSABILIDAD', 'solicitud', 'siempre',                  1),
    ('F3-URGENCIA-MEDICA', 'DOC-REPORTE-MEDICO',        'solicitud', 'siempre',                  2),
    ('F3-URGENCIA-MEDICA', 'DOC-GENERALES-PASAPORTE',   'marino',    'siempre',                  3),
    ('F3-URGENCIA-MEDICA', 'DOC-LIBRETA-MARINO',        'marino',    'siempre',                  4),
    ('F3-URGENCIA-MEDICA', 'DOC-FORM6-CUSTODIA',        'marino',    'nacionalidad_restringida', 5),
]

# ISO 3166-1 alfa-3 + códigos ICAO usados en pasaportes (XXA apátrida, RKS Kosovo)
PAISES = [
    ('AFG', 'Afganistán'), ('ALB', 'Albania'), ('DEU', 'Alemania'), ('AND', 'Andorra'),
    ('AGO', 'Angola'), ('AIA', 'Anguila'), ('ATA', 'Antártida'), ('ATG', 'Antigua y Barbuda'),
    ('XXA', 'Apátrida'), ('SAU', 'Arabia Saudita'), ('DZA', 'Argelia'), ('ARG', 'Argentina'),
    ('ARM', 'Armenia'), ('ABW', 'Aruba'), ('AUS', 'Australia'), ('AUT', 'Austria'),
    ('AZE', 'Azerbaiyán'), ('BHS', 'Bahamas'), ('BHR', 'Baréin'), ('BGD', 'Bangladés'),
    ('BRB', 'Barbados'), ('BEL', 'Bélgica'), ('BLZ', 'Belice'), ('BEN', 'Benín'),
    ('BMU', 'Bermudas'), ('BLR', 'Bielorrusia'), ('BOL', 'Bolivia'), ('BIH', 'Bosnia y Herzegovina'),
    ('BWA', 'Botsuana'), ('BRA', 'Brasil'), ('BRN', 'Brunéi'), ('BGR', 'Bulgaria'),
    ('BFA', 'Burkina Faso'), ('BDI', 'Burundi'), ('BTN', 'Bután'), ('CPV', 'Cabo Verde'),
    ('KHM', 'Camboya'), ('CMR', 'Camerún'), ('CAN', 'Canadá'),
    ('BES', 'Caribe Neerlandés (Bonaire, San Eustaquio y Saba)'), ('QAT', 'Catar'),
    ('TCD', 'Chad'), ('CZE', 'Chequia'), ('CHL', 'Chile'), ('CHN', 'China'), ('CYP', 'Chipre'),
    ('COL', 'Colombia'), ('COM', 'Comoras'), ('COG', 'Congo'),
    ('COD', 'Congo (República Democrática del)'), ('PRK', 'Corea del Norte'),
    ('KOR', 'Corea del Sur'), ('CIV', 'Costa de Marfil'), ('CRI', 'Costa Rica'),
    ('HRV', 'Croacia'), ('CUB', 'Cuba'), ('CUW', 'Curazao'), ('DNK', 'Dinamarca'),
    ('DMA', 'Dominica'), ('ECU', 'Ecuador'), ('EGY', 'Egipto'), ('SLV', 'El Salvador'),
    ('ARE', 'Emiratos Árabes Unidos'), ('ERI', 'Eritrea'), ('SVK', 'Eslovaquia'),
    ('SVN', 'Eslovenia'), ('ESP', 'España'), ('USA', 'Estados Unidos'), ('EST', 'Estonia'),
    ('SWZ', 'Esuatini'), ('ETH', 'Etiopía'), ('PHL', 'Filipinas'), ('FIN', 'Finlandia'),
    ('FJI', 'Fiyi'), ('FRA', 'Francia'), ('GAB', 'Gabón'), ('GMB', 'Gambia'),
    ('GEO', 'Georgia'), ('GHA', 'Ghana'), ('GIB', 'Gibraltar'), ('GRD', 'Granada'),
    ('GRC', 'Grecia'), ('GRL', 'Groenlandia'), ('GLP', 'Guadalupe'), ('GUM', 'Guam'),
    ('GTM', 'Guatemala'), ('GUF', 'Guayana Francesa'), ('GGY', 'Guernsey'), ('GIN', 'Guinea'),
    ('GNB', 'Guinea-Bisáu'), ('GNQ', 'Guinea Ecuatorial'), ('GUY', 'Guyana'), ('HTI', 'Haití'),
    ('HND', 'Honduras'), ('HKG', 'Hong Kong'), ('HUN', 'Hungría'), ('IND', 'India'),
    ('IDN', 'Indonesia'), ('IRQ', 'Irak'), ('IRN', 'Irán'), ('IRL', 'Irlanda'),
    ('BVT', 'Isla Bouvet'), ('IMN', 'Isla de Man'), ('CXR', 'Isla de Navidad'),
    ('NFK', 'Isla Norfolk'), ('ISL', 'Islandia'), ('ALA', 'Islas Åland'),
    ('CYM', 'Islas Caimán'), ('CCK', 'Islas Cocos'), ('COK', 'Islas Cook'),
    ('FRO', 'Islas Feroe'), ('SGS', 'Islas Georgias del Sur y Sandwich del Sur'),
    ('HMD', 'Islas Heard y McDonald'), ('FLK', 'Islas Malvinas'),
    ('MNP', 'Islas Marianas del Norte'), ('MHL', 'Islas Marshall'), ('PCN', 'Islas Pitcairn'),
    ('SLB', 'Islas Salomón'), ('TCA', 'Islas Turcas y Caicos'),
    ('UMI', 'Islas Ultramarinas Menores de Estados Unidos'),
    ('VGB', 'Islas Vírgenes Británicas'), ('VIR', 'Islas Vírgenes de los Estados Unidos'),
    ('ISR', 'Israel'), ('ITA', 'Italia'), ('JAM', 'Jamaica'), ('JPN', 'Japón'),
    ('JEY', 'Jersey'), ('JOR', 'Jordania'), ('KAZ', 'Kazajistán'), ('KEN', 'Kenia'),
    ('KGZ', 'Kirguistán'), ('KIR', 'Kiribati'), ('RKS', 'Kosovo'), ('KWT', 'Kuwait'),
    ('LAO', 'Laos'), ('LSO', 'Lesoto'), ('LVA', 'Letonia'), ('LBN', 'Líbano'),
    ('LBR', 'Liberia'), ('LBY', 'Libia'), ('LIE', 'Liechtenstein'), ('LTU', 'Lituania'),
    ('LUX', 'Luxemburgo'), ('MAC', 'Macao'), ('MKD', 'Macedonia del Norte'),
    ('MDG', 'Madagascar'), ('MYS', 'Malasia'), ('MWI', 'Malaui'), ('MDV', 'Maldivas'),
    ('MLI', 'Malí'), ('MLT', 'Malta'), ('MAR', 'Marruecos'), ('MTQ', 'Martinica'),
    ('MUS', 'Mauricio'), ('MRT', 'Mauritania'), ('MYT', 'Mayotte'), ('MEX', 'México'),
    ('FSM', 'Micronesia'), ('MDA', 'Moldavia'), ('MCO', 'Mónaco'), ('MNG', 'Mongolia'),
    ('MNE', 'Montenegro'), ('MSR', 'Montserrat'), ('MOZ', 'Mozambique'), ('MMR', 'Myanmar'),
    ('NAM', 'Namibia'), ('NRU', 'Nauru'), ('NPL', 'Nepal'), ('NIC', 'Nicaragua'),
    ('NER', 'Níger'), ('NGA', 'Nigeria'), ('NIU', 'Niue'), ('NOR', 'Noruega'),
    ('NCL', 'Nueva Caledonia'), ('NZL', 'Nueva Zelanda'), ('OMN', 'Omán'),
    ('NLD', 'Países Bajos'), ('PAK', 'Pakistán'), ('PLW', 'Palaos'), ('PSE', 'Palestina'),
    ('PAN', 'Panamá'), ('PNG', 'Papúa Nueva Guinea'), ('PRY', 'Paraguay'), ('PER', 'Perú'),
    ('PYF', 'Polinesia Francesa'), ('POL', 'Polonia'), ('PRT', 'Portugal'),
    ('PRI', 'Puerto Rico'), ('GBR', 'Reino Unido'), ('CAF', 'República Centroafricana'),
    ('DOM', 'República Dominicana'), ('REU', 'Reunión'), ('RWA', 'Ruanda'),
    ('ROU', 'Rumania'), ('RUS', 'Rusia'), ('ESH', 'Sahara Occidental'), ('WSM', 'Samoa'),
    ('ASM', 'Samoa Americana'), ('BLM', 'San Bartolomé'), ('KNA', 'San Cristóbal y Nieves'),
    ('SMR', 'San Marino'), ('MAF', 'San Martín (parte francesa)'),
    ('SXM', 'San Martín (parte neerlandesa)'), ('SPM', 'San Pedro y Miquelón'),
    ('VCT', 'San Vicente y las Granadinas'), ('SHN', 'Santa Elena, Ascensión y Tristán de Acuña'),
    ('LCA', 'Santa Lucía'), ('STP', 'Santo Tomé y Príncipe'), ('SEN', 'Senegal'),
    ('SRB', 'Serbia'), ('SYC', 'Seychelles'), ('SLE', 'Sierra Leona'), ('SGP', 'Singapur'),
    ('SYR', 'Siria'), ('SOM', 'Somalia'), ('LKA', 'Sri Lanka'), ('ZAF', 'Sudáfrica'),
    ('SDN', 'Sudán'), ('SSD', 'Sudán del Sur'), ('SWE', 'Suecia'), ('CHE', 'Suiza'),
    ('SUR', 'Surinam'), ('SJM', 'Svalbard y Jan Mayen'), ('THA', 'Tailandia'),
    ('TWN', 'Taiwán'), ('TZA', 'Tanzania'), ('TJK', 'Tayikistán'),
    ('IOT', 'Territorio Británico del Océano Índico'), ('ATF', 'Territorios Australes Franceses'),
    ('TLS', 'Timor Oriental'), ('TGO', 'Togo'), ('TKL', 'Tokelau'), ('TON', 'Tonga'),
    ('TTO', 'Trinidad y Tobago'), ('TUN', 'Túnez'), ('TKM', 'Turkmenistán'),
    ('TUR', 'Turquía'), ('TUV', 'Tuvalu'), ('UKR', 'Ucrania'), ('UGA', 'Uganda'),
    ('URY', 'Uruguay'), ('UZB', 'Uzbekistán'), ('VUT', 'Vanuatu'),
    ('VAT', 'Vaticano (Santa Sede)'), ('VEN', 'Venezuela'), ('VNM', 'Vietnam'),
    ('WLF', 'Wallis y Futuna'), ('YEM', 'Yemen'), ('DJI', 'Yibuti'), ('ZMB', 'Zambia'),
    ('ZWE', 'Zimbabue'),
]

FK_USUARIOS_SOLICITUD = [
    'impedimentos_verificados_por_id', 'aprobada_por_id', 'negada_por_id', 'finalizada_por_id',
]


def _lista_sql(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _borrar_carpetas_storage(tokens: list[str]) -> None:
    """Borra del disco las carpetas de las transferencias eliminadas, solo si
    de verdad viven dentro de STORAGE_PATH."""
    from app.core.config import obtener_configuracion

    raiz = Path(obtener_configuracion().STORAGE_PATH).resolve()
    for token in tokens:
        try:
            carpeta = (raiz / token).resolve()
            carpeta.relative_to(raiz)
        except (ValueError, OSError):
            continue
        if carpeta != raiz and carpeta.is_dir():
            shutil.rmtree(carpeta, ignore_errors=True)


def upgrade() -> None:
    # ── 1. Bitácora: valores nuevos del enum ────────────────────────────────
    # ALTER TYPE ... ADD VALUE no puede ir en la misma transacción que los usa;
    # se ejecuta en autocommit (e IF NOT EXISTS lo hace repetible).
    with op.get_context().autocommit_block():
        for valor in NUEVAS_ACCIONES:
            op.execute(f"ALTER TYPE accionauditoria ADD VALUE IF NOT EXISTS '{valor}'")

    conexion = op.get_bind()

    # ── 2. Fuera el storage suelto: sus tablas dan paso a las del expediente ─
    tokens = [fila[0] for fila in conexion.execute(sa.text("SELECT token FROM transfers")).fetchall()]
    op.drop_table('transfer_files')
    op.drop_table('transfers')

    # ── 3. Catálogos ────────────────────────────────────────────────────────
    op.create_table(
        'tipos_tramite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('formulario', sa.String(length=20), nullable=False),
        sa.Column('requiere_buque', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requiere_puerto', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requiere_puerto_desembarque', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requiere_motivo', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requiere_clinica', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('valida_vigencia', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tipos_tramite_id'), 'tipos_tramite', ['id'], unique=False)
    op.create_index(op.f('ix_tipos_tramite_codigo'), 'tipos_tramite', ['codigo'], unique=True)
    op.create_index(op.f('ix_tipos_tramite_formulario'), 'tipos_tramite', ['formulario'], unique=False)

    op.create_table(
        'documentos_requeridos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('requiere_libreta', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documentos_requeridos_id'), 'documentos_requeridos', ['id'], unique=False)
    op.create_index(op.f('ix_documentos_requeridos_codigo'), 'documentos_requeridos', ['codigo'], unique=True)

    op.create_table(
        'tramite_documentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo_tramite_id', sa.Integer(), nullable=False),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('alcance', sa.String(length=20), nullable=False),
        sa.Column('condicion', sa.String(length=30), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tipo_tramite_id'], ['tipos_tramite.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos_requeridos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo_tramite_id', 'documento_id', name='uq_tramite_documento'),
    )
    op.create_index(op.f('ix_tramite_documentos_id'), 'tramite_documentos', ['id'], unique=False)
    op.create_index(op.f('ix_tramite_documentos_tipo_tramite_id'), 'tramite_documentos', ['tipo_tramite_id'], unique=False)
    op.create_index(op.f('ix_tramite_documentos_documento_id'), 'tramite_documentos', ['documento_id'], unique=False)

    op.create_table(
        'puestos_control',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('correo', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_puestos_control_id'), 'puestos_control', ['id'], unique=False)

    op.create_table(
        'usuarios_puestos',
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('puesto_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['puesto_id'], ['puestos_control.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('usuario_id', 'puesto_id'),
    )

    op.create_table(
        'agencias_navieras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('correo', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_index(op.f('ix_agencias_navieras_id'), 'agencias_navieras', ['id'], unique=False)

    op.create_table(
        'paises',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=3), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('nacionalidad_restringida', sa.Boolean(), server_default='false', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_paises_id'), 'paises', ['id'], unique=False)
    op.create_index(op.f('ix_paises_codigo'), 'paises', ['codigo'], unique=True)

    for codigo, nombre in PAISES:
        conexion.execute(sa.text("INSERT INTO paises (codigo, nombre) VALUES (:c, :n)"), {"c": codigo, "n": nombre})
    for codigo, nombre, descripcion, requiere_libreta in DOCUMENTOS:
        conexion.execute(
            sa.text("INSERT INTO documentos_requeridos (codigo, nombre, descripcion, requiere_libreta) "
                    "VALUES (:c, :n, :d, :l)"),
            {"c": codigo, "n": nombre, "d": descripcion, "l": requiere_libreta},
        )
    for (codigo, nombre, buque, puerto, puerto_des, motivo, clinica, vigencia, nota, orden) in TIPOS_TRAMITE:
        conexion.execute(
            sa.text("""
                INSERT INTO tipos_tramite
                    (codigo, nombre, formulario, requiere_buque, requiere_puerto, requiere_puerto_desembarque,
                     requiere_motivo, requiere_clinica, valida_vigencia, nota, orden)
                VALUES (:c, :n, 'formulario_3', :b, :p, :pd, :m, :cl, :v, :nota, :o)
            """),
            {"c": codigo, "n": nombre, "b": buque, "p": puerto, "pd": puerto_des, "m": motivo,
             "cl": clinica, "v": vigencia, "nota": nota, "o": orden},
        )
    for codigo_tramite, codigo_documento, alcance, condicion, orden in MATRIZ:
        conexion.execute(
            sa.text("""
                INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
                SELECT t.id, d.id, :a, :cond, :o
                  FROM tipos_tramite t, documentos_requeridos d
                 WHERE t.codigo = :ct AND d.codigo = :cd
            """),
            {"ct": codigo_tramite, "cd": codigo_documento, "a": alcance, "cond": condicion, "o": orden},
        )

    # ── 4. Usuarios: agencia y endurecimiento de la cuenta local ────────────
    op.add_column('users', sa.Column('agencia_id', sa.Integer(), nullable=True))
    op.create_foreign_key('users_agencia_id_fkey', 'users', 'agencias_navieras', ['agencia_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_users_agencia_id'), 'users', ['agencia_id'], unique=False)
    op.add_column('users', sa.Column('intentos_fallidos', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('bloqueado_hasta', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('debe_cambiar_password', sa.Boolean(), server_default='false', nullable=False))

    # ── 5. Expediente de la solicitud ───────────────────────────────────────
    op.create_table(
        'solicitudes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(length=30), nullable=True),
        sa.Column('agencia_id', sa.Integer(), nullable=False),
        sa.Column('agencia_nombre', sa.String(length=200), nullable=False),
        sa.Column('creada_por_id', sa.Integer(), nullable=False),
        sa.Column('tipo_tramite_id', sa.Integer(), nullable=False),
        sa.Column('puesto_control_id', sa.Integer(), nullable=False),
        sa.Column('puesto_nombre', sa.String(length=200), nullable=False),
        sa.Column('titulo', sa.String(length=255), nullable=False),
        sa.Column('fecha_operacion', sa.Date(), nullable=False),
        sa.Column('cantidad_tripulantes', sa.Integer(), nullable=False),
        sa.Column('nombre_buque', sa.String(length=255), nullable=True),
        sa.Column('imo', sa.String(length=20), nullable=True),
        sa.Column('bandera', sa.String(length=3), nullable=True),
        sa.Column('nombre_puerto', sa.String(length=255), nullable=True),
        sa.Column('puerto_desembarque', sa.String(length=255), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('clinica_hospital', sa.String(length=255), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(length=20), server_default='review', nullable=False),
        sa.Column('enviada_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('veces_devuelta', sa.Integer(), server_default='0', nullable=False),
        sa.Column('impedimentos_verificados', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('comentario_impedimentos', sa.Text(), nullable=True),
        sa.Column('impedimentos_verificados_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('impedimentos_verificados_por_id', sa.Integer(), nullable=True),
        sa.Column('motivo_devolucion', sa.Text(), nullable=True),
        sa.Column('plazo_correccion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('aprobada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('aprobada_por_id', sa.Integer(), nullable=True),
        sa.Column('observacion_aprobacion', sa.Text(), nullable=True),
        sa.Column('vigente_hasta', sa.DateTime(timezone=True), nullable=True),
        sa.Column('codigo_verificacion', sa.String(length=64), nullable=True),
        sa.Column('negada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('negada_por_id', sa.Integer(), nullable=True),
        sa.Column('motivo_negacion', sa.Text(), nullable=True),
        sa.Column('finalizada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalizada_por_id', sa.Integer(), nullable=True),
        sa.Column('comentario_finalizacion', sa.Text(), nullable=True),
        sa.Column('expirada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(f"estado IN ({_lista_sql(ESTADOS)})", name='ck_solicitudes_estado'),
        sa.ForeignKeyConstraint(['agencia_id'], ['agencias_navieras.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['creada_por_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tipo_tramite_id'], ['tipos_tramite.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['puesto_control_id'], ['puestos_control.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['bandera'], ['paises.codigo'], ondelete='RESTRICT'),
        *[sa.ForeignKeyConstraint([c], ['users.id'], ondelete='SET NULL') for c in FK_USUARIOS_SOLICITUD],
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitudes_id'), 'solicitudes', ['id'], unique=False)
    op.create_index(op.f('ix_solicitudes_numero'), 'solicitudes', ['numero'], unique=True)
    op.create_index(op.f('ix_solicitudes_codigo_verificacion'), 'solicitudes', ['codigo_verificacion'], unique=True)
    for columna in ('agencia_id', 'creada_por_id', 'tipo_tramite_id', 'puesto_control_id', 'estado',
                    'enviada_en', 'plazo_correccion', 'aprobada_en', 'vigente_hasta', 'negada_en', 'expirada_en'):
        op.create_index(op.f(f'ix_solicitudes_{columna}'), 'solicitudes', [columna], unique=False)

    op.create_table(
        'solicitud_tripulantes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('solicitud_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('apellido', sa.String(length=150), nullable=False),
        sa.Column('fecha_nacimiento', sa.Date(), nullable=False),
        sa.Column('pais_nacimiento', sa.String(length=3), nullable=False),
        sa.Column('nacionalidad', sa.String(length=3), nullable=False),
        sa.Column('sexo', sa.String(length=1), nullable=False),
        sa.Column('pasaporte', sa.String(length=100), nullable=False),
        sa.Column('pasaporte_expira', sa.Date(), nullable=False),
        sa.Column('libreta_marino', sa.String(length=100), nullable=True),
        sa.Column('libreta_expira', sa.Date(), nullable=True),
        sa.Column('rango', sa.String(length=20), nullable=False),
        sa.Column('ocupacion', sa.String(length=150), nullable=False),
        sa.Column('es_panameno', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('nacionalidad_restringida', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('orden', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("sexo IN ('M', 'F', 'X')", name='ck_solicitud_tripulantes_sexo'),
        sa.CheckConstraint(f"rango IN ({_lista_sql(RANGOS)})", name='ck_solicitud_tripulantes_rango'),
        sa.ForeignKeyConstraint(['solicitud_id'], ['solicitudes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pais_nacimiento'], ['paises.codigo'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['nacionalidad'], ['paises.codigo'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitud_tripulantes_id'), 'solicitud_tripulantes', ['id'], unique=False)
    op.create_index(op.f('ix_solicitud_tripulantes_solicitud_id'), 'solicitud_tripulantes', ['solicitud_id'], unique=False)

    op.create_table(
        'solicitud_documentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('solicitud_id', sa.Integer(), nullable=False),
        sa.Column('tripulante_id', sa.Integer(), nullable=True),
        sa.Column('documento_id', sa.Integer(), nullable=True),
        sa.Column('nombre_original', sa.String(length=500), nullable=False),
        sa.Column('nombre_almacenado', sa.String(length=500), nullable=False),
        sa.Column('ruta', sa.String(length=1000), nullable=False),
        sa.Column('tipo_mime', sa.String(length=255), nullable=True),
        sa.Column('tamano', sa.BigInteger(), nullable=False),
        sa.Column('subido_por_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['solicitud_id'], ['solicitudes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tripulante_id'], ['solicitud_tripulantes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos_requeridos.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subido_por_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitud_documentos_id'), 'solicitud_documentos', ['id'], unique=False)
    for columna in ('solicitud_id', 'tripulante_id', 'documento_id', 'subido_por_id'):
        op.create_index(op.f(f'ix_solicitud_documentos_{columna}'), 'solicitud_documentos', [columna], unique=False)

    op.create_table(
        'solicitud_eventos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('solicitud_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('estado_anterior', sa.String(length=20), nullable=True),
        sa.Column('estado_nuevo', sa.String(length=20), nullable=True),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('usuario_nombre', sa.String(length=255), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['solicitud_id'], ['solicitudes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitud_eventos_id'), 'solicitud_eventos', ['id'], unique=False)
    op.create_index(op.f('ix_solicitud_eventos_solicitud_id'), 'solicitud_eventos', ['solicitud_id'], unique=False)
    op.create_index(op.f('ix_solicitud_eventos_usuario_id'), 'solicitud_eventos', ['usuario_id'], unique=False)

    # ── 6. Permisos y roles del flujo ───────────────────────────────────────
    op.execute(sa.text("""
        INSERT INTO permisos (codigo, nombre, descripcion) VALUES
            ('T-FINALIZAR-PUERTO', 'Finalizar en puesto de control',
             'Ve las autorizaciones aprobadas de los puestos de control que tiene asignados, registra comentarios y las finaliza.')
        ON CONFLICT (codigo) DO NOTHING
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Solicitar autorizaciones',
            descripcion = 'Envía solicitudes de autorización marítima de su agencia, con la ficha de los tripulantes y los documentos requeridos, y las corrige cuando UCVMM las devuelve.'
        WHERE codigo = 'T-CREAR-BASICA'
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Revisar autorizaciones',
            descripcion = 'Revisa las solicitudes de autorización marítima: verifica impedimentos, aprueba, niega o devuelve a corrección.'
        WHERE codigo = 'T-PROCESAR-PACIFICO'
    """))
    op.execute(sa.text("""
        INSERT INTO roles (nombre, descripcion, es_sistema) VALUES
            ('Puesto de Control',
             'Funcionario del puesto de control migratorio: ve las autorizaciones aprobadas de sus puestos, las comenta y las finaliza.',
             FALSE)
        ON CONFLICT (nombre) DO NOTHING
    """))
    op.execute(sa.text("""
        INSERT INTO roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
          FROM roles r
          JOIN permisos p ON p.codigo = 'T-FINALIZAR-PUERTO'
         WHERE r.nombre IN ('Puesto de Control', 'Administrador')
        ON CONFLICT ON CONSTRAINT uq_roles_permisos_rol_permiso DO NOTHING
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Agencia naviera: envía las solicitudes de autorización marítima de su agencia y las corrige cuando UCVMM las devuelve.'
         WHERE nombre = 'Naviera'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Sección de autorizaciones marítimas (UCVMM): revisa, aprueba, niega o devuelve las solicitudes de las navieras.'
         WHERE nombre = 'Sector Pacífico'
    """))

    # ── 7. Al final (ya validado todo lo anterior): archivos del storage suelto
    _borrar_carpetas_storage(tokens)


def downgrade() -> None:
    # Nota: los archivos del storage suelto que se borraron al subir no vuelven;
    # las tablas se recrean vacías, con la forma que tenían en e2a6b8f3d1c7.

    # ── 6. Permisos y roles ─────────────────────────────────────────────────
    op.execute(sa.text("""
        DELETE FROM roles_permisos
         WHERE permiso_id IN (SELECT id FROM permisos WHERE codigo = 'T-FINALIZAR-PUERTO')
    """))
    op.execute(sa.text("DELETE FROM roles WHERE nombre = 'Puesto de Control'"))
    op.execute(sa.text("DELETE FROM permisos WHERE codigo = 'T-FINALIZAR-PUERTO'"))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Subir archivos',
            descripcion = 'Sube archivos con título/mensaje/destinatario opcional. Queda disponible de inmediato.'
        WHERE codigo = 'T-CREAR-BASICA'
    """))
    op.execute(sa.text("""
        UPDATE permisos SET
            nombre = 'Ver todo y descargar',
            descripcion = 'Ve todas las transferencias subidas por las navieras, las previsualiza, descarga y copia el enlace.'
        WHERE codigo = 'T-PROCESAR-PACIFICO'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Sube archivos para el Servicio Nacional de Migración. Quedan disponibles de inmediato con un enlace de descarga.'
         WHERE nombre = 'Naviera'
    """))
    op.execute(sa.text("""
        UPDATE roles SET descripcion = 'Ve, previsualiza y descarga todos los archivos subidos por las navieras.'
         WHERE nombre = 'Sector Pacífico'
    """))

    # ── 5. Expediente ───────────────────────────────────────────────────────
    op.drop_table('solicitud_eventos')
    op.drop_table('solicitud_documentos')
    op.drop_table('solicitud_tripulantes')
    op.drop_table('solicitudes')

    # ── 4. Usuarios ─────────────────────────────────────────────────────────
    op.drop_column('users', 'debe_cambiar_password')
    op.drop_column('users', 'bloqueado_hasta')
    op.drop_column('users', 'intentos_fallidos')
    op.drop_index(op.f('ix_users_agencia_id'), table_name='users')
    op.drop_constraint('users_agencia_id_fkey', 'users', type_='foreignkey')
    op.drop_column('users', 'agencia_id')

    # ── 3. Catálogos ────────────────────────────────────────────────────────
    op.drop_table('paises')
    op.drop_table('agencias_navieras')
    op.drop_table('usuarios_puestos')
    op.drop_table('puestos_control')
    op.drop_table('tramite_documentos')
    op.drop_table('documentos_requeridos')
    op.drop_table('tipos_tramite')

    # ── 2. Storage suelto (vacío) ───────────────────────────────────────────
    op.create_table(
        'transfers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('recipient', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('downloads', sa.Integer(), nullable=False),
        sa.Column('max_downloads', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transfers_expires_at', 'transfers', ['expires_at'], unique=False)
    op.create_index(op.f('ix_transfers_id'), 'transfers', ['id'], unique=False)
    op.create_index(op.f('ix_transfers_status'), 'transfers', ['status'], unique=False)
    op.create_index(op.f('ix_transfers_token'), 'transfers', ['token'], unique=True)
    op.create_index(op.f('ix_transfers_user_id'), 'transfers', ['user_id'], unique=False)

    op.create_table(
        'transfer_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transfer_id', sa.Integer(), nullable=False),
        sa.Column('original_name', sa.String(length=500), nullable=False),
        sa.Column('stored_name', sa.String(length=500), nullable=False),
        sa.Column('path', sa.String(length=1000), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('subido_por_id', sa.Integer(), nullable=True),
        sa.Column('es_original', sa.Boolean(), server_default='true', nullable=False),
        sa.ForeignKeyConstraint(['subido_por_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfer_files_id'), 'transfer_files', ['id'], unique=False)
    op.create_index(op.f('ix_transfer_files_subido_por_id'), 'transfer_files', ['subido_por_id'], unique=False)
    op.create_index(op.f('ix_transfer_files_transfer_id'), 'transfer_files', ['transfer_id'], unique=False)

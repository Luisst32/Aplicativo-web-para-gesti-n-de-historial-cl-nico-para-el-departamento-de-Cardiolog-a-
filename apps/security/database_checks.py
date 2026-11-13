"""Deployment must use a restricted database runtime identity."""
from django.core.checks import Error, register, Tags
from django.db import connection, DatabaseError


@register(Tags.security, deploy=True)
def database_runtime_privileges(app_configs, **kwargs):
    try:
        with connection.cursor() as cursor:
            cursor.execute('''SELECT EXISTS (
                SELECT 1 FROM pg_roles r WHERE
                (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
                AND pg_has_role(current_user, r.oid, 'MEMBER'))''')
            elevated = cursor.fetchone()[0]
            cursor.execute('''SELECT EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname IN ('clinical','security','audit','catalog','ai','public')
                AND c.relkind IN ('r','p') AND pg_has_role(current_user,c.relowner,'MEMBER'))''')
            owner = cursor.fetchone()[0]
            cursor.execute("SELECT has_database_privilege(current_user,current_database(),'CREATE') OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspname IN ('public','clinical','security','audit','catalog','ai') AND has_schema_privilege(current_user,oid,'CREATE'))")
            owner = owner or cursor.fetchone()[0]
        if elevated or owner:
            return [Error('La identidad runtime tiene privilegios elevados o propiedad de tablas. Use un rol DML separado del migrador.', id='security.E009')]
        return []
    except DatabaseError:
        return [Error('No se pudieron verificar los privilegios runtime de PostgreSQL.', id='security.E010')]

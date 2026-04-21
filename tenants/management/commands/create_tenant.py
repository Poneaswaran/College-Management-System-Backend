"""
tenants/management/commands/create_tenant.py

Creates a new tenant (institution) and its primary domain.
Run this every time a new university signs up.

Usage:
    python manage.py create_tenant --schema vels --name "VELS Institute..." --short-name VISTAS --domain vels.localhost
    python manage.py create_tenant --schema public --name "Public" --short-name PUBLIC --domain localhost
"""

from django.core.management.base import BaseCommand, CommandError

from tenants.models import Client, Domain


class Command(BaseCommand):
    help = "Create a new tenant (institution) with a primary domain."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            required=True,
            help="PostgreSQL schema name. Use 'public' for the shared tenant.",
        )
        parser.add_argument(
            "--name",
            type=str,
            required=True,
            help="Full institution name.",
        )
        parser.add_argument(
            "--short-name",
            type=str,
            required=True,
            help="Short / abbreviated institution name (e.g. VISTAS).",
        )
        parser.add_argument(
            "--domain",
            type=str,
            required=True,
            help="Primary domain for this tenant (e.g. vels.localhost).",
        )
        parser.add_argument(
            "--email",
            type=str,
            default="",
            help="Institution contact email.",
        )
        parser.add_argument(
            "--phone",
            type=str,
            default="",
            help="Institution contact phone.",
        )
        parser.add_argument(
            "--address",
            type=str,
            default="",
            help="Institution address.",
        )

    def handle(self, *args, **options):
        schema_name = options["schema"]
        name = options["name"]
        short_name = options["short_name"]
        domain_name = options["domain"]

        # Check if schema already exists
        if Client.objects.filter(schema_name=schema_name).exists():
            raise CommandError(
                f"Tenant with schema '{schema_name}' already exists."
            )

        # Check if domain already exists
        if Domain.objects.filter(domain=domain_name).exists():
            raise CommandError(
                f"Domain '{domain_name}' is already registered."
            )

        # Create the tenant (this auto-creates the PG schema via auto_create_schema=True)
        self.stdout.write(f"Creating tenant '{name}' with schema '{schema_name}'...")
        tenant = Client(
            schema_name=schema_name,
            name=name,
            short_name=short_name,
            email=options.get("email", ""),
            phone=options.get("phone", ""),
            address=options.get("address", ""),
            is_active=True,
        )
        tenant.save()

        # Create the primary domain
        Domain.objects.create(
            domain=domain_name,
            tenant=tenant,
            is_primary=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Tenant created successfully:\n"
            f"  Schema:     {schema_name}\n"
            f"  Name:       {name}\n"
            f"  Short name: {short_name}\n"
            f"  Domain:     {domain_name}\n"
        ))

        if schema_name == "public":
            self.stdout.write(self.style.WARNING(
                "This is the PUBLIC tenant. It shares the public schema.\n"
                "Next: create a real institution tenant."
            ))
        else:
            self.stdout.write(
                f"Schema '{schema_name}' has been created in PostgreSQL.\n"
                f"Run 'python manage.py migrate_schemas' to apply migrations."
            )

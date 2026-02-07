"""
Management command to create an admin (superuser) for QuerySafe.

Usage:
  python manage.py create_admin --name "Ankur Bansal" --email admin@example.com --password YourSecurePassword

On Cloud Run (via gcloud):
  gcloud run jobs execute create-admin --args="--name,Ankur Bansal,--email,admin@example.com,--password,YourPassword"

Or simply run on the deployed container:
  gcloud run jobs create create-admin \
    --image <IMAGE_URL> \
    --command "python" \
    --args "manage.py,create_admin,--name,Ankur Bansal,--email,admin@example.com,--password,YourPassword" \
    --region asia-south1 \
    --add-cloudsql-instances querysafe-dev:asia-south1:querysafe-db \
    --set-env-vars ENVIRONMENT=production \
    --set-secrets=...
"""
from django.core.management.base import BaseCommand, CommandError
from user_querySafe.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create an admin user for QuerySafe'

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True, help='Full name of the admin user')
        parser.add_argument('--email', required=True, help='Email address')
        parser.add_argument('--password', required=True, help='Password (will be hashed)')

    def handle(self, *args, **options):
        name = options['name']
        email = options['email']
        password = options['password']

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            existing = User.objects.get(email=email)
            self.stdout.write(self.style.WARNING(
                f'User with email {email} already exists (user_id={existing.user_id}). Skipping.'
            ))
            return

        user = User(
            name=name,
            email=email,
            password=make_password(password),
            is_active=True,
            registration_status='activated',
            activated_at=timezone.now(),
        )
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Admin user created successfully!\n'
            f'  user_id: {user.user_id}\n'
            f'  name:    {user.name}\n'
            f'  email:   {user.email}\n'
            f'  active:  {user.is_active}'
        ))

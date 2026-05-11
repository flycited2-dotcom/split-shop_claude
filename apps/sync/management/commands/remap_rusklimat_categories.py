from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'DEPRECATED alias for `remap_categories`. '
        'Calls the new command with --source=rusklimat. '
        'Use `python manage.py remap_categories` directly.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'remap_rusklimat_categories is deprecated; use remap_categories instead.'
        ))
        call_command(
            'remap_categories',
            source='rusklimat',
            apply=options['apply'],
        )

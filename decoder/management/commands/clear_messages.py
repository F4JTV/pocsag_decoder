# decoder/management/commands/clear_messages.py
from django.core.management.base import BaseCommand
from decoder.models import PocsagMessage


class Command(BaseCommand):
    help = 'Supprime tous les messages POCSAG de la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '-y', '--yes',
            action='store_true',
            help='Confirmer automatiquement la suppression (sans demander)'
        )
        parser.add_argument(
            '--keep-recent',
            type=int,
            default=0,
            metavar='N',
            help='Conserver les N messages les plus récents'
        )
        parser.add_argument(
            '--older-than',
            type=int,
            default=0,
            metavar='DAYS',
            help='Supprimer uniquement les messages plus vieux que N jours'
        )

    def handle(self, *args, **options):
        auto_confirm = options['yes']
        keep_recent = options['keep_recent']
        older_than_days = options['older_than']

        # Construire la requête de base
        queryset = PocsagMessage.objects.all()
        
        # Filtrer par âge si demandé
        if older_than_days > 0:
            from django.utils import timezone
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=older_than_days)
            queryset = queryset.filter(timestamp__lt=cutoff_date)
            self.stdout.write(
                f'Filtrage: messages antérieurs au {cutoff_date.strftime("%d/%m/%Y %H:%M")}'
            )

        # Exclure les messages récents si demandé
        if keep_recent > 0:
            # Récupérer les IDs des N messages les plus récents
            recent_ids = list(
                PocsagMessage.objects.order_by('-timestamp')
                .values_list('id', flat=True)[:keep_recent]
            )
            queryset = queryset.exclude(id__in=recent_ids)
            self.stdout.write(f'Conservation des {keep_recent} messages les plus récents')

        # Compter les messages à supprimer
        count = queryset.count()
        total = PocsagMessage.objects.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('Aucun message à supprimer.'))
            return

        # Afficher le résumé
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('=' * 50))
        self.stdout.write(self.style.WARNING('  SUPPRESSION DE MESSAGES POCSAG'))
        self.stdout.write(self.style.WARNING('=' * 50))
        self.stdout.write(f'  Messages dans la base : {total}')
        self.stdout.write(f'  Messages à supprimer  : {count}')
        self.stdout.write(f'  Messages conservés    : {total - count}')
        self.stdout.write(self.style.WARNING('=' * 50))
        self.stdout.write('')

        # Demander confirmation
        if not auto_confirm:
            confirm = input('Confirmer la suppression ? (oui/non) : ').strip().lower()
            if confirm not in ['oui', 'o', 'yes', 'y']:
                self.stdout.write(self.style.ERROR('Opération annulée.'))
                return

        # Supprimer les messages
        deleted_count, _ = queryset.delete()

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'✓ {deleted_count} message(s) supprimé(s) avec succès.')
        )
        
        remaining = PocsagMessage.objects.count()
        self.stdout.write(f'  Messages restants : {remaining}')

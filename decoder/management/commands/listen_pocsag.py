# decoder/management/commands/listen_pocsag.py
import subprocess
import re
import threading
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from decoder.models import PocsagMessage, ListenerStatus


class Command(BaseCommand):
    help = 'Écoute et décode les trames POCSAG avec multimon-ng'

    def __init__(self):
        super().__init__()
        self.running = False
        self.heartbeat_thread = None
        self.dedupe_minutes = 3  # Valeur par défaut

    def add_arguments(self, parser):
        """Définition des arguments de la commande"""
        # Configuration RTL-SDR
        parser.add_argument(
            '-f', '--frequency',
            type=str,
            default='173.5125M',
            help='Fréquence d\'écoute (ex: 173.5125M, 466.075M). Défaut: 173.5125M'
        )
        parser.add_argument(
            '-g', '--gain',
            type=float,
            default=49.6,
            help='Gain du récepteur RTL-SDR en dB. Défaut: 49.6'
        )
        parser.add_argument(
            '-T', '--bias-t',
            action='store_true',
            default=False,
            help='Activer le bias-t (alimentation antenne active). Défaut: désactivé'
        )
        parser.add_argument(
            '-s', '--sample-rate',
            type=int,
            default=22050,
            help='Taux d\'échantillonnage en Hz. Défaut: 22050'
        )
        
        # Configuration déduplication
        parser.add_argument(
            '-d', '--dedupe-minutes',
            type=int,
            default=3,
            help='Intervalle en minutes pour considérer un message comme doublon. Défaut: 3'
        )
        
        # Configuration POCSAG
        parser.add_argument(
            '--pocsag-rates',
            type=str,
            default='512,1200,2400',
            help='Débits POCSAG à décoder, séparés par des virgules. Défaut: 512,1200,2400'
        )

    def heartbeat_worker(self):
        """Thread de heartbeat pour maintenir le statut en ligne"""
        while self.running:
            ListenerStatus.heartbeat()
            time.sleep(3)

    def build_rtl_fm_command(self, options):
        """Construit la commande rtl_fm avec les options"""
        cmd_parts = ['rtl_fm']
        
        # Gain
        cmd_parts.extend(['-g', str(options['gain'])])
        
        # Bias-T
        if options['bias_t']:
            cmd_parts.append('-T')
        
        # Fréquence
        cmd_parts.extend(['-f', options['frequency']])
        
        # Sample rate
        cmd_parts.extend(['-s', str(options['sample_rate'])])
        
        # Sortie vers stdout
        cmd_parts.append('-')
        
        return cmd_parts

    def build_multimon_command(self, options):
        """Construit la commande multimon-ng avec les options"""
        cmd_parts = ['multimon-ng', '-t', 'raw']
        
        # Ajouter les débits POCSAG
        rates = options['pocsag_rates'].split(',')
        for rate in rates:
            rate = rate.strip()
            if rate in ['512', '1200', '2400']:
                cmd_parts.extend(['-a', f'POCSAG{rate}'])
        
        # Entrée depuis stdin
        cmd_parts.append('-')
        
        return cmd_parts

    def save_config_to_cache(self, dedupe_minutes):
        """
        Sauvegarde la configuration de déduplication pour que views.py puisse l'utiliser.
        Utilise le cache Django ou un fichier de configuration.
        """
        try:
            from django.core.cache import cache
            cache.set('pocsag_dedupe_minutes', dedupe_minutes, timeout=None)
        except Exception:
            # Fallback: sauvegarder dans un fichier
            import os
            config_path = os.path.join(settings.BASE_DIR, '.pocsag_config')
            with open(config_path, 'w') as f:
                f.write(str(dedupe_minutes))

    def handle(self, *args, **options):
        # Récupérer les options
        frequency = options['frequency']
        gain = options['gain']
        bias_t = options['bias_t']
        sample_rate = options['sample_rate']
        self.dedupe_minutes = options['dedupe_minutes']
        pocsag_rates = options['pocsag_rates']

        # Afficher la configuration
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Configuration POCSAG Listener'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'  Fréquence      : {frequency}')
        self.stdout.write(f'  Gain           : {gain} dB')
        self.stdout.write(f'  Bias-T         : {"Activé" if bias_t else "Désactivé"}')
        self.stdout.write(f'  Sample rate    : {sample_rate} Hz')
        self.stdout.write(f'  Débits POCSAG  : {pocsag_rates}')
        self.stdout.write(f'  Doublons       : {self.dedupe_minutes} minutes')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Sauvegarder la config de déduplication
        self.save_config_to_cache(self.dedupe_minutes)

        # Construire les commandes
        rtl_cmd = self.build_rtl_fm_command(options)
        multimon_cmd = self.build_multimon_command(options)
        
        # Commande complète avec pipe
        full_command = ' '.join(rtl_cmd) + ' | ' + ' '.join(multimon_cmd)
        self.stdout.write(f'\nCommande: {full_command}\n')

        ListenerStatus.set_running(True)
        self.running = True

        self.heartbeat_thread = threading.Thread(target=self.heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()

        try:
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Pattern pour parser les messages POCSAG
            pattern = re.compile(
                r'POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)\s+(?:Alpha:|Numeric:)\s+(.*)'
            )

            self.stdout.write(self.style.SUCCESS('\nDécodage lancé ... (Ctrl+C pour arrêter)\n'))

            for line in iter(process.stdout.readline, ''):
                if not self.running:
                    break

                line = line.strip()

                if not line:
                    continue

                # self.stdout.write(f"Reçu: {line}")

                match = pattern.match(line)
                if match:
                    address = match.group(1)
                    function = match.group(2)
                    message = match.group(3).strip()

                    PocsagMessage.objects.create(
                        address=address,
                        function=function,
                        message=message,
                        raw_data=line
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Message sauvegardé →  '
                        ) + 
                        f"{line}"
                    )

                    # Nettoyage si trop de messages
                    if PocsagMessage.objects.count() > 2000:
                        oldest = PocsagMessage.objects.order_by('timestamp').first()
                        if oldest:
                            oldest.delete()

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\nArrêt du décodage ...'))
            if 'process' in locals():
                process.terminate()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur: {str(e)}'))
        finally:
            self.running = False
            ListenerStatus.set_running(False)
            self.stdout.write(self.style.WARNING('Statut mis à jour'))

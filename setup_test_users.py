import os
import django

# FIXED TYPO: Changed to exactly 'DJANGO_SETTINGS_MODULE'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from thangta.models import CustomUser

def create_users():
    # Admin
    if not CustomUser.objects.filter(username='main_admin').exists():
        CustomUser.objects.create_superuser('main_admin', 'admin@example.com', 'admin123', role='ADMIN')
        print("✅ Admin user created: main_admin / admin123")
    else:
        print("⚡ Admin user already exists.")

    # Judge
    if not CustomUser.objects.filter(username='mat_judge_1').exists():
        CustomUser.objects.create_user('mat_judge_1', 'judge1@example.com', 'judge123', role='JUDGE', district='Nagpur')
        print("✅ Judge user created: mat_judge_1 / judge123")
    else:
        print("⚡ Judge user already exists.")

    # Scorer
    if not CustomUser.objects.filter(username='scorer_1').exists():
        CustomUser.objects.create_user('scorer_1', 'scorer1@example.com', 'scorer123', role='SCORER')
        print("✅ Scorer user created: scorer_1 / scorer123")
    else:
        print("⚡ Scorer user already exists.")

if __name__ == '__main__':
    create_users()
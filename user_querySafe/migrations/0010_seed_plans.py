"""
Data migration to seed initial QSPlan records.
These plans match the local development database.
"""
from django.db import migrations


def seed_plans(apps, schema_editor):
    QSPlan = apps.get_model('user_querySafe', 'QSPlan')

    # Only seed if no plans exist (idempotent)
    if QSPlan.objects.exists():
        return

    # 1. Create non-trial plans first (no parent dependency)
    QSPlan.objects.create(
        plan_id='GSE36',
        plan_name='Private Solo',
        is_trial=False,
        parent_plan=None,
        require_act_code=False,
        no_of_bot=1,
        no_of_query=800,
        no_of_file=2,
        max_file_size=4,
        currency='INR',
        amount=799.00,
        amount_usd=9.00,
        status='public',
        days=30,
    )

    QSPlan.objects.create(
        plan_id='GSE37',
        plan_name='Secure Business',
        is_trial=False,
        parent_plan=None,
        require_act_code=False,
        no_of_bot=3,
        no_of_query=1000,
        no_of_file=5,
        max_file_size=5,
        currency='INR',
        amount=2499.00,
        amount_usd=29.00,
        status='public',
        days=30,
    )

    # 2. Create trial plans (with parent references)
    solo = QSPlan.objects.get(plan_id='GSE36')
    business = QSPlan.objects.get(plan_id='GSE37')

    QSPlan.objects.create(
        plan_id='GSE35',
        plan_name='Private Solo',
        is_trial=True,
        parent_plan=solo,
        require_act_code=False,
        no_of_bot=1,
        no_of_query=800,
        no_of_file=2,
        max_file_size=4,
        currency='INR',
        amount=0.00,
        amount_usd=0.00,
        status='public',
        days=7,
    )

    QSPlan.objects.create(
        plan_id='GSE38',
        plan_name='Secure Business',
        is_trial=True,
        parent_plan=business,
        require_act_code=False,
        no_of_bot=3,
        no_of_query=1000,
        no_of_file=5,
        max_file_size=5,
        currency='INR',
        amount=0.00,
        amount_usd=0.00,
        status='public',
        days=7,
    )


def remove_plans(apps, schema_editor):
    QSPlan = apps.get_model('user_querySafe', 'QSPlan')
    QSPlan.objects.filter(plan_id__in=['GSE35', 'GSE36', 'GSE37', 'GSE38']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user_querySafe', '0009_qsplan_amount_usd_alter_qsplan_amount'),
    ]

    operations = [
        migrations.RunPython(seed_plans, remove_plans),
    ]

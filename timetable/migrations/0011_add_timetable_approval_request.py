from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_section_priority'),
        ('profile_management', '0005_facultyprofile_first_name_facultyprofile_last_name'),
        ('timetable', '0010_add_ai_action_snapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimetableApprovalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_summary', models.TextField()),
                ('note', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='PENDING', max_length=20)),
                ('slots', models.JSONField(blank=True, default=list, help_text='List of proposed timetable slots for UI rendering.')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_approval_requests', to='core.department')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_timetable_approval_requests', to='core.user')),
                ('semester', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timetable_approval_requests', to='profile_management.semester')),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submitted_timetable_approval_requests', to='core.user')),
            ],
            options={
                'verbose_name': 'Timetable Approval Request',
                'verbose_name_plural': 'Timetable Approval Requests',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='timetableapprovalrequest',
            index=models.Index(fields=['department', 'status'], name='timetable_t_departm_8d9f08_idx'),
        ),
        migrations.AddIndex(
            model_name='timetableapprovalrequest',
            index=models.Index(fields=['semester', 'status'], name='timetable_t_semeste_b1453e_idx'),
        ),
        migrations.AddIndex(
            model_name='timetableapprovalrequest',
            index=models.Index(fields=['submitted_by', 'status'], name='timetable_t_submitt_a2b7a2_idx'),
        ),
    ]

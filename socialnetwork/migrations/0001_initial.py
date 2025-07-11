# Generated by Django 4.2.3 on 2025-06-29 11:33

from django.conf import settings
import django.contrib.auth.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('fame', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostExpertiseAreasAndRatings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expertise_area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fame.expertiseareas')),
            ],
            options={
                'db_table': 'post_expertise_areas_and_ratings',
            },
        ),
        migrations.CreateModel(
            name='Posts',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.CharField(max_length=1764)),
                ('submitted', models.DateTimeField(auto_now_add=True)),
                ('published', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'posts',
                'ordering': ['-submitted'],
            },
        ),
        migrations.CreateModel(
            name='SocialNetworkUsers',
            fields=[
                ('fameusers_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('is_banned', models.BooleanField(default=False)),
                ('communities', models.ManyToManyField(blank=True, related_name='community_members', to='fame.expertiseareas')),
                ('follows', models.ManyToManyField(related_name='followed_by', to='socialnetwork.socialnetworkusers')),
            ],
            options={
                'db_table': 'social_network_users',
            },
            bases=('fame.fameusers',),
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='TruthRatings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=42)),
                ('numeric_value', models.IntegerField()),
            ],
            options={
                'db_table': 'truth_ratings',
            },
        ),
        migrations.CreateModel(
            name='UserRatings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField()),
                ('type', models.CharField(choices=[('A', 'Approval'), ('L', 'Like'), ('D', 'Dislike')], default='L', max_length=1)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='socialnetwork.posts')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='socialnetwork.socialnetworkusers')),
            ],
            options={
                'unique_together': {('user', 'post', 'type')},
            },
        ),
        migrations.AddField(
            model_name='posts',
            name='author',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='socialnetwork.socialnetworkusers'),
        ),
        migrations.AddField(
            model_name='posts',
            name='cites',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cited_by', to='socialnetwork.posts'),
        ),
        migrations.AddField(
            model_name='posts',
            name='expertise_area_and_truth_ratings',
            field=models.ManyToManyField(related_name='classified_as', through='socialnetwork.PostExpertiseAreasAndRatings', to='fame.expertiseareas'),
        ),
        migrations.AddField(
            model_name='posts',
            name='replies_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replied_to', to='socialnetwork.posts'),
        ),
        migrations.AddField(
            model_name='posts',
            name='user_ratings',
            field=models.ManyToManyField(related_name='rated_by', through='socialnetwork.UserRatings', to='socialnetwork.socialnetworkusers'),
        ),
        migrations.AddField(
            model_name='postexpertiseareasandratings',
            name='post',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='socialnetwork.posts'),
        ),
        migrations.AddField(
            model_name='postexpertiseareasandratings',
            name='truth_rating',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='socialnetwork.truthratings'),
        ),
        migrations.AlterUniqueTogether(
            name='posts',
            unique_together={('author', 'submitted')},
        ),
    ]

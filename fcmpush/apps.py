from django.apps import AppConfig


class FcmpushConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fcmpush'

    # def ready(self):
    #     from . import firebase_init
    #     firebase_init.init_firebase()

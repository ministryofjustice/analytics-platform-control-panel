
# DJANGO_SETTINGS_MODULE=controlpanel.settings.development 
# python ./controlpanel/utils.py::load_app_conf_from_file

# eval $(python -c "from controlpanel.utils import load_app_conf_from_file; load_app_conf_from_file()")
DJANGO_SETTINGS_MODULE=controlpanel.settings.development celery -A controlpanel.celery:app worker --loglevel=info

"""
Script to perform common operations on remote server from local machine.

Prerequisites:
    pip install fabric
    Create DigitalOcean droplet with Django installation
    Copy private_example.py to private.py and edit in your settings

Usage:
    fab setup
    ---------
        Installs git and package managers (npm, bower)
        Modifies nginx and gunicorn configs to match our directory tree
        Clones github directory and installs python + bower requirements
        Add correct permission to static folder

    fab reboot:mode=prod
    ---------
        (Setup step assumed to be completed.)
        Pull changes from master repo
        Migrate database
        Restart nginx and gunicorn
        Run project using production settings (see wearhacks_website/settings/prod.py)

    fab reboot:mode=dev
    ---------
        (Setup step assumed to be completed.)
        Pull changes from master repo
        Migrate database
        Restart nginx and stop gunicorn
        Run on localhost:9000
        Run project using dev settings (see wearhacks_website/settings/local.py)

    fab get_logs
    ---------
        Copy nginx and gunicorn log files from remote to logs/ directory
"""

import fabtools
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.context_managers import shell_env
import tempfile, os, sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_DJANGO_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

########### DEPLOYMENT OPTIONS
DEFAULT_MODE='prod'
DEFAULT_DEPLOY_TO='alpha'
DEBUG = None

DEPLOYMENT_MODES = ('dev', 'prod')
DEPLOYMENT_PRIVATE_FILES = {
    'alpha': 'alpha_private',
    'beta': 'beta_private',
    'live': 'live_private'
}
DEPLOYMENT_HOSTS = {
    'alpha': ('alpha.wearhacks.eleyine.com',),
    'beta': ('wearhacks.eleyine.com',),
    'live': ('45.55.84.109',)
}
########### END DEPLOYMENT OPTIONS

########### DJANGO SETTINGS
DJANGO_SETTINGS_MODULE = 'wearhacks_website.settings'
########### END DJANGO SETTINGS

########### PROMPT SETTINGS
AUTO_ANSWER_PROMPTS = True  
if AUTO_ANSWER_PROMPTS:
    prompts = {
        'Do you want to continue [Y/n]? ': 'Y',
        '? May bower anonymously report usage statistics to improve the tool over time? (Y/n)': 'Y',
        "Type 'yes' to continue, or 'no' to cancel: ": 'yes',
        'Would you like to create one now? (yes/no): ': 'no'
        }
else:
    prompts = {}
########### END PROMPT SETTINGS

########### PATH AND PROJECT NAME CONFIGURATION
# Should not change if you do not modify this GitHub project
GITHUB_PROJECT = 'https://github.com/eleyine/WearHacks-Website.git'
DJANGO_PROJECT_DIR = '/home/django'
DJANGO_PROJECT_NAME = 'WearHacks-Website'
DJANGO_APP_NAME = 'wearhacks_website'
DJANGO_PROJECT_PATH = os.path.join(DJANGO_PROJECT_DIR, DJANGO_PROJECT_NAME)
########### END PATH AND PROJECT NAME CONFIGURATION

########### ENV VARIABLES ON REMOTE
env.hosts = DEPLOYMENT_HOSTS[DEFAULT_DEPLOY_TO]
ENV_VARIABLES = {
    # 'ENV_USER': env.user
}
########### END ENV VARIABLES

########### FAB ENV
env.user = 'root'
env.colorize_errors = True
########### END FAB ENV

def write_file(local_path, remote_path, options):
    with open(local_path) as f:
        content = f.read()

    for option_name, option_value in options.iteritems():
        content = content.replace(option_name, option_value)

    #  tmp = tempfile.TemporaryFile()
    TMP_PATH = 'tmp.txt'
    with open(TMP_PATH, 'w') as tmp:
        tmp.write(content)

    print 'Overwriting %s' % (remote_path)
    put(TMP_PATH, remote_path)

def setup(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO):
    env.hosts = DEPLOYMENT_HOSTS[deploy_to]

    with settings(warn_only=True):
        with settings(prompts=prompts):
            # Require some Debian/Ubuntu packages
            fabtools.require.deb.packages([
                'git',
                'npm',
                'libpq-dev',
                'python-dev',
                'postgresql',
                'postgresql-contrib',
                'nginx',
                'gunicorn',
                'sqlite3',
                'node-less'
            ])

        try:
            run('ln -s /usr/bin/nodejs /usr/bin/node')
        except:
            pass

        NPM_PACKAGES = (
            'bower', 
            )
        with settings(prompts=prompts, warn_only=True):
            for package in NPM_PACKAGES:
                print 'Installing %s as root...' % (package)
                sudo('npm install -g %s' % (package))


        print 'Making django project directory at %s...' % (DJANGO_PROJECT_DIR)
        run('mkdir -p %s' % (DJANGO_PROJECT_DIR))

        if not os.path.exists(DJANGO_PROJECT_PATH):
            with cd(DJANGO_PROJECT_DIR):
                print 'Cloning Github Project into %s...' % (DJANGO_PROJECT_NAME)
                run('git clone %s %s' % (GITHUB_PROJECT, DJANGO_PROJECT_NAME)) 

        with cd(DJANGO_PROJECT_PATH):
            run('git pull origin master')
            print 'Installing python requirements..'
            run('pip install -r requirements.txt')
            
            print 'Installing bower requirements..'
            run('bower install --allow-root')

        # setup proper permissions
        sudo('chown -R django:django %s' % (os.path.join(DJANGO_PROJECT_PATH, 'static')))

        update_conf_files(deploy_to=deploy_to)

def reset_postgres_db():
    # Require a PostgreSQL server
    # fabtools.require.postgres.server()
    if  fabtools.postgres.user_exists(DB_USER):
        print 'Deleting superuser %s' % (DB_USER)
        fabtools.postgres.drop_user(DB_USER)

    print 'Creating new superuser %s' % (DB_USER)
    try:
        fabtools.postgres.create_user(DB_USER, DB_PASS, 
            superuser=True, createrole=True)
    except:
        fabtools.postgres.create_user(DB_USER, DB_PASS, 
            superuser=True, createrole=False)

    # Remove DB if it exists
    if fabtools.postgres.database_exists(DB_NAME):
        print 'Dropping database %s ' % (DB_NAME)
        fabtools.postgres.drop_database(DB_NAME)

    print 'Creating new database %s' % (DB_NAME)
    fabtools.postgres.create_database(DB_NAME, owner=DB_USER)
    test_models()

def update_conf_files(deploy_to=DEFAULT_DEPLOY_TO):
    env.hosts = DEPLOYMENT_HOSTS[deploy_to]

    print 'Modifying nginx config'
    write_file('nginx.sh', '/etc/nginx/sites-enabled/django',
        {
            'DJANGO_PROJECT_PATH': DJANGO_PROJECT_PATH
        })

    print 'Modifying gunicorn config'
    write_file('gunicorn.sh', '/etc/init/gunicorn.conf',
        {
            'DJANGO_PROJECT_DIR': DJANGO_PROJECT_DIR,
            'DJANGO_PROJECT_NAME': DJANGO_PROJECT_NAME,
            'DJANGO_APP_NAME': DJANGO_APP_NAME
        })
    print 'Restarting nginx'
    sudo('nginx -t')
    sudo('service nginx reload')

    print 'Restarting gunicorn'
    run('service gunicorn restart')

def test_models(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO):
    env_variables = get_env_variables(mode=mode) 
    with cd(DJANGO_PROJECT_PATH):
        with shell_env(**env_variables):
            print 'Check database backend'
            run('echo "from django.db import connection;connection.vendor" | python manage.py shell ')
            # print 'In case you forgot the password, here it is %s' % (env_variables['DB_PASS'])
            run('python manage.py sqlclear registration | python manage.py dbshell ')

            pull_changes()
            migrate(mode=mode)
            run('python manage.py generate_registrations 10 --reset')

def migrate(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO, env_variables=None):
    if not env_variables:
        env_variables = get_env_variables(mode=mode)

    print 'Migrating database'
    
    with shell_env(**env_variables):

        with cd(DJANGO_PROJECT_PATH):
            # run('echo "from django.db import connection; connection.vendor" | python manage.py shell')
            if mode == 'dev':
                run('rm -rf wearhacks_website/db.sqlite3')
            else:
                if deploy_to == 'alpha':
                    run('python manage.py sqlclear registration | python manage.py dbshell ')

                run('service postgresql status')
                run('sudo netstat -nl | grep postgres')

            run('python manage.py makemigrations')
            run('python manage.py migrate')
            run('python manage.py syncdb')

            # create superuser
            try:
                with hide('stderr', 'stdout'):
                    sudo('chmod u+x scripts/createsuperuser.sh')
                    run('./scripts/createsuperuser.sh')
            except:
                pass

def update_requirements():
    with cd(DJANGO_PROJECT_PATH):
        run('git pull origin master')
        print 'Installing python requirements..'
        run('pip install -r requirements.txt')
        
        print 'Installing bower requirements..'
        run('bower install --allow-root')

        # setup proper permissions
        sudo('chown -R django:django %s' % (os.path.join(DJANGO_PROJECT_PATH, 'static')))


def pull_changes(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO):
    print 'Updating %s' % (get_private_settings_file(local=False, deploy_to=deploy_to))
    put(local_path=get_private_settings_file(local=True, deploy_to=deploy_to),
        remote_path=get_private_settings_file(local=False, deploy_to=deploy_to))

    with cd(DJANGO_PROJECT_PATH):
        print 'Pulling changes from master repo'
        run('git pull origin master')
        run('pip install -r requirements.txt')

def get_private_settings_file(deploy_to=DEFAULT_DEPLOY_TO, local=True):
    if deploy_to not in DEPLOYMENT_PRIVATE_FILES.keys():
        print 'Unknown deployment option %s' % (deploy_to)
        print 'Possible options:', DEPLOYMENT_PRIVATE_FILES.keys()
        sys.exit()

    basename = DEPLOYMENT_PRIVATE_FILES[deploy_to]

    if local:
        django_path = LOCAL_DJANGO_PATH
    else:
        django_path = DJANGO_PROJECT_PATH
    return os.path.join(django_path, 'wearhacks_website',
            'settings', basename + '.py')

def get_env_variables(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO):
    ev = dict(ENV_VARIABLES)
    if mode not in DEPLOYMENT_MODES:
        print 'Invalid mode option %s' % (mode)
        print 'Possible options:', DEPLOYMENT_MODES
        sys.exit()
    ev['APP_ENV'] = mode

    if deploy_to not in DEPLOYMENT_PRIVATE_FILES.keys():
        print 'Unknown deployment option %s' % (deploy_to)
        print 'Possible options:', DEPLOYMENT_PRIVATE_FILES.keys()
        sys.exit()
    ev['PRIVATE_APP_ENV'] = DEPLOYMENT_PRIVATE_FILES[deploy_to]
    env.hosts = DEPLOYMENT_HOSTS[deploy_to]
    return ev

def reboot(mode=DEFAULT_MODE, deploy_to=DEFAULT_DEPLOY_TO, env_variables=None):
    if not env_variables:
        env_variables = get_env_variables(mode=mode, deploy_to=deploy_to)
        print env_variables
    
    with cd(DJANGO_PROJECT_PATH):
        print 'Stopping gunicorn' 
        with settings(warn_only=True):
            run('service gunicorn stop')

        pull_changes(mode=mode, deploy_to=deploy_to)
        with shell_env(**env_variables):
            with settings(prompts=prompts):
                run('python manage.py collectstatic')
        sudo('chown -R django:django %s' % (os.path.join(DJANGO_PROJECT_PATH, 'assets')))
        sudo('chown -R django:django %s' % (os.path.join(DJANGO_PROJECT_PATH, 'static')))
        
        print 'Restarting nginx'
        sudo('nginx -t')
        sudo('service nginx reload')

        migrate(mode=mode, deploy_to=deploy_to, env_variables=env_variables)

        if mode == 'prod':

            if deploy_to == 'alpha':
                with shell_env(**env_variables):
                    print 'Generating 3 random registration...'
                    run('python manage.py generate_registrations 3')

            print 'Restarting gunicorn'
            run('service gunicorn restart')

        elif mode == 'dev':

            with shell_env(**env_variables):
                # run('python manage.py sqlclear registration | python manage.py dbshell ')
                print 'Running on localhost'
                run('python manage.py generate_registrations 10 --reset')
                run('python manage.py runserver localhost:9000')
        else:
            print 'Invalid mode %s' % (mode)
    
    get_logs()


def get_logs(deploy_to=DEFAULT_DEPLOY_TO):
    print 'Copying logs to logs/'
    log_dir = os.path.join(LOCAL_DJANGO_PATH, 'server_files', 'logs', deploy_to)
    if not os.path.exists(log_dir):
        local('mkdir -p %s' % (log_dir))
    with settings(warn_only=True): 
        get(remote_path="%s/server_files/logs/local/django.debug.log" % (DJANGO_PROJECT_PATH), local_path="%s/django.debug.log" % (log_dir))
        # get(remote_path="/var/log/upstart/gunicorn.log", local_path="%s/gunicorn.log" % (log_dir))
        # get(remote_path="/var/log/nginx/error.log", local_path="%s/nginx.error.log" % (log_dir))
        # get(remote_path="/var/log/postgresql/postgresql-9.3-main.log", local_path="%s/psql.main.log" % (log_dir))


def all():
    setup()
    reboot()

def do_nothing():
    # check for compile errors
    pass
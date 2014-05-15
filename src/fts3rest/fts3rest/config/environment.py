#   Copyright notice:
#   Copyright © Members of the EMI Collaboration, 2010.
# 
#   See www.eu-emi.eu for details on the copyright holders
# 
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
# 
#       http://www.apache.org/licenses/LICENSE-2.0
# 
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Pylons environment configuration"""
import os

from pylons import config
from sqlalchemy import engine_from_config

import fts3rest.lib.app_globals as app_globals
import fts3rest.lib.helpers
from fts3rest.lib.helpers import fts3_config
from fts3rest.config.routing import make_map
from fts3rest.model import init_model


def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config``
    object
    """
    # Pylons paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = dict(root=root,
                 controllers=os.path.join(root, 'controllers'),
                 static_files=os.path.join(root, 'public'),
                 templates=[os.path.join(root, 'templates')])

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package='fts3rest', paths=paths)

    config['routes.map'] = make_map(config)
    config['pylons.app_globals'] = app_globals.Globals(config)
    config['pylons.h'] = fts3rest.lib.helpers

    # Setup cache object as early as possible
    import pylons
    pylons.cache._push_object(config['pylons.app_globals'].cache)

    # If fts3.config is set, load configuration from there
    fts3_config_file = config.get('fts3.config')
    if config.get('fts3.config'):
        fts3cfg = fts3_config.fts3_config_load(fts3_config_file)
        config.update(fts3cfg)

    # Setup the SQLAlchemy database engine
    engine = engine_from_config(config, 'sqlalchemy.', pool_recycle = 7200)
    init_model(engine)

    # CONFIGURATION OPTIONS HERE (note: all config options will override
    # any Pylons config options)
    return config

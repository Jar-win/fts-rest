#   Copyright notice:
#   Copyright  Members of the EMI Collaboration, 2013.
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

"""SQLAlchemy Metadata and Session object"""
import sqlalchemy
from sqlalchemy.orm import scoped_session, sessionmaker

__all__ = ['Base', 'Session']

# SQLAlchemy session manager. Updated by model.init_model()
Session = scoped_session(sessionmaker())

# Log the version
import logging
logging.getLogger(__name__).info('Using SQLAlchemy %s' % sqlalchemy.__version__)

# The declarative Base
from fts3.model.base import Base

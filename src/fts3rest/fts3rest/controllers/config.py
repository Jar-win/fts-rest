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

import json
import logging

from datetime import datetime
from numbers import Number
from pylons import request
from fts3.model import *
from fts3rest.lib.api import doc
from fts3rest.lib.base import BaseController, Session
from fts3rest.lib.helpers import jsonify, to_json
from fts3rest.lib.http_exceptions import *
from fts3rest.lib.middleware.fts3auth import authorize
from fts3rest.lib.middleware.fts3auth.constants import *


log = logging.getLogger(__name__)


def _audit_configuration(action, config):
    """
    Logs and stores in the DB a configuration action
    """
    audit = ConfigAudit(
        datetime=datetime.utcnow(),
        dn=request.environ['fts3.User.Credentials'].user_dn,
        config=config,
        action=action
    )
    Session.add(audit)
    log.info(action)


def _get_input_as_dict(request, from_query=False):
    """
    Return a valid dictionary from the request imput
    """
    if from_query:
        input_dict = request.params
    elif request.content_type == 'application/json':
        try:
            input_dict = json.loads(request.body)
        except Exception:
            raise HTTPBadRequest('Malformed input')
    else:
        raise HTTPBadRequest('Expecting application/json')

    if not hasattr(input_dict, '__getitem__'):
        raise HTTPBadRequest('Expecting a dictionary')
    return input_dict


def _validate_type(Type, key, value):
    """
    Validate that value is of a suitable type of the attribute key of the type Type
    """
    column = Type.__table__.columns.get(key, None)
    if column is None:
        raise HTTPBadRequest('Field %s unknown' % key)

    type_map = {
        Integer: int,
        String: basestring,
        Flag: bool,
        DateTime: basestring,
        Float: Number,
    }

    expected_type = type_map.get(type(column.type), str)
    if not isinstance(value, expected_type):
        raise HTTPBadRequest('Field %s is expected to be %s' % (key, expected_type.__name__))


class ConfigController(BaseController):
    """
    Operations on the config audit
    """

    @doc.return_type(array_of=ConfigAudit)
    @authorize(CONFIG)
    @jsonify
    def audit(self):
        """
        Returns the last 100 entries of the config audit tables
        """
        return Session.query(ConfigAudit).limit(100).all()

    @doc.response(403, 'The user is not allowed to change the configuration')
    @authorize(CONFIG)
    @jsonify
    def set_debug(self):
        """
        Sets the debug level status for a storage
        """
        input_dict = _get_input_as_dict(request)

        source = input_dict.get('source', None)
        destin = input_dict.get('destination', None)
        try:
            level  = int(input_dict.get('level', 1))
        except:
            raise HTTPBadRequest('Invalid parameters')

        if source:
            source = str(source)
            if level:
                src_debug = DebugConfig(
                    source_se=source,
                    dest_se='',
                    debug_level=level
                )
                Session.merge(src_debug)
                _audit_configuration(
                    'debug', 'Set debug for source %s to level %d' % (src_debug.source_se, src_debug.debug_level)
                )
            else:
                Session.query(DebugConfig).filter(DebugConfig.source_se == source).delete()
                _audit_configuration(
                    'debug', 'Delete debug for source %s' % (source)
                )
        if destin:
            destin = str(destin)
            if level:
                dst_debug = DebugConfig(
                    source_se='',
                    dest_se=destin,
                    debug_level=level
                )
                Session.merge(dst_debug)
                _audit_configuration(
                    'debug', 'Set debug for destination %s to level %d' % (dst_debug.dest_se, dst_debug.debug_level)
                )
            else:
                Session.query(DebugConfig).filter(DebugConfig.dest_se == destin).delete()
                _audit_configuration('debug', 'Delete debug for destination %s' % (destin))

        try:
            Session.commit()
        except:
            Session.rollback()
            raise
        return input_dict

    @doc.response(403, 'The user is not allowed to change the configuration')
    @authorize(CONFIG)
    def delete_debug(self, start_response):
        """
        Removes a debug entry
        """
        input_dict = _get_input_as_dict(request, from_query=True)

        source = input_dict.get('source', None)
        destin = input_dict.get('destination', None)

        if source:
            source = str(source)
            debug = Session.query(DebugConfig).get((source, ''))
            Session.delete(debug)
            _audit_configuration('debug', 'Delete debug for source %s' % (source))
        if destin:
            destin = str(destin)
            debug = Session.query(DebugConfig).get(('', destin))
            Session.delete(debug)
            _audit_configuration('debug', 'Delete debug for destination %s' % (destin))

        try:
            Session.commit()
        except:
            Session.rollback()
            raise

        start_response('204 No Content', [])
        return ['']

    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def list_debug(self):
        """
        Return the debug settings
        """
        return Session.query(DebugConfig).all()

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def set_global_config(self):
        """
        Set the global configuration
        """
        cfg = _get_input_as_dict(request)

        vo_name = cfg.get('vo_name', '*')
        db_cfg = Session.query(ServerConfig).get(vo_name)
        if not db_cfg:
            db_cfg = ServerConfig(vo_name=vo_name)

        if vo_name == '*' and 'optimizer_mode' in cfg:
            opt = OptimizerConfig(mode=cfg.pop('optimizer_mode'))
            Session.merge(opt)

        for key, value in cfg.iteritems():
            _validate_type(ServerConfig, key, value)
            setattr(db_cfg, key, value)

        Session.merge(db_cfg)
        _audit_configuration('set-globals', to_json(db_cfg, indent=None))
        try:
            Session.commit()
        except:
            Session.rollback()
            raise

        return self.get_global_config()

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_global_config(self):
        """
        Get the global configuration
        """
        # Only retry, is bound to VO, the others are global (no VO)
        rows = Session.query(ServerConfig).all()
        result = dict()
        for r in rows:
            if r:
                if r.vo_name in (None, '*'):
                    result['*'] = r
                else:
                    result[r.vo_name] = dict(retry=r.retry)
        return result

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to modify the configuration')
    @authorize(CONFIG)
    @jsonify
    def set_optimizer_mode(self):
        """
        Set the optimizer mode
        """
        try:
            mode = int(request.body)
        except:
            raise HTTPBadRequest('Expecting an integer')
        Session.query(OptimizerConfig).delete()
        opt = OptimizerConfig(mode=mode)
        Session.merge(opt)
        try:
            Session.commit()
        except:
            Session.rollback()
            raise
        return mode

    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_optimizer_mode(self):
        """
        Get the optimizer mode
        """
        opt = Session.query(OptimizerConfig).first()
        if not opt:
            return None
        else:
            return opt.mode

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def add_to_group(self):
        """
        Add a SE to a group
        """
        input_dict = _get_input_as_dict(request)

        member = input_dict.get('member', None)
        groupname = input_dict.get('groupname', None)

        if not member or not groupname:
            raise HTTPBadRequest('Missing values')

        new_member = Member(groupname=groupname, member=member)
        _audit_configuration('member-add', 'Added member %s to %s' % (member, groupname))
        try:
            Session.merge(new_member)
            Session.commit()
        except:
            Session.rollback()
            raise
        return new_member

    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_all_groups(self):
        """
        Get a list with all group names
        """
        return [g.groupname for g in Session.query(Group).all()]

    @doc.response(403, 'The user is not allowed to query the configuration')
    @doc.response(404, 'The group does not exist')
    @authorize(CONFIG)
    @jsonify
    def get_group(self, group_name):
        """
        Get the members of a group
        """
        members = Session.query(Member).filter(Member.groupname == group_name).all()
        if len(members) == 0:
            raise HTTPNotFound('Group %s does not exist' % group_name)
        return [m.member for m in members]

    @doc.query_arg('member', 'Storage to remove. All group if left empty or absent', required=False)
    @doc.response(204, 'Member removed')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @doc.response(404, 'The group or the member does not exist')
    @authorize(CONFIG)
    def delete_from_group(self, group_name, start_response):
        """
        Delete a member from a group. If the group is left empty, the group will be removed
        """
        input_dict = _get_input_as_dict(request, from_query=True)

        storage = input_dict.get('member', None)
        if storage:
            Session.query(Member).filter((Member.groupname == group_name) & (Member.member == storage)).delete()
            _audit_configuration('group-delete', 'Member %s removed from group %s' % (storage, group_name))
        else:
            Session.query(Member).filter(Member.groupname == group_name).delete()
            _audit_configuration('group-delete', 'Group %s removed' % group_name)

        try:
            Session.commit()
        except:
            Session.rollback()
            raise

        start_response('204 No Content', [])
        return ['']

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def set_link_config(self):
        """
        Set the configuration for a given link
        """
        input_dict = _get_input_as_dict(request)

        source = input_dict.get('source', '*')
        destination = input_dict.get('destination', '*')
        symbolicname = input_dict.get('symbolicname', None)
        if not symbolicname:
            raise HTTPBadRequest('Missing symbolicname')
        if source == '*' and destination == '*':
            raise HTTPBadRequest('Can not use wildcard for both source and destination')

        link_cfg = Session.query(LinkConfig).get((source, destination))
        if not link_cfg:
            link_cfg = LinkConfig(
                source=source,
                destination=destination,
                symbolicname=symbolicname
            )

        for key, value in input_dict.iteritems():
            _validate_type(LinkConfig, key, value)
            setattr(link_cfg, key, value)

        _audit_configuration('link', json.dumps(input_dict))

        Session.merge(link_cfg)
        try:
            Session.commit()
        except:
            Session.rollback()
            raise

        return link_cfg

    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_all_link_configs(self):
        """
        Get a list of all the links configured
        """
        links = Session.query(LinkConfig).all()
        return [l.symbolicname for l in links]

    @doc.response(403, 'The user is not allowed to query the configuration')
    @doc.response(404, 'The group or the member does not exist')
    @authorize(CONFIG)
    @jsonify
    def get_link_config(self, sym_name):
        """
        Get the existing configuration for a given link
        """
        link = Session.query(LinkConfig).filter(LinkConfig.symbolicname == sym_name).first()
        if not link:
            raise HTTPNotFound('Link %s does not exist' % sym_name)
        return link

    @doc.response(204, 'Link removed')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @doc.response(404, 'The group or the member does not exist')
    @authorize(CONFIG)
    @jsonify
    def delete_link_config(self, sym_name, start_response):
        """
        Deletes an existing link configuration
        """
        try:
            Session.query(LinkConfig).filter(LinkConfig.symbolicname == sym_name).delete()
            _audit_configuration('link-delete', 'Link %s has been deleted' % sym_name)
            Session.commit()
        except:
            Session.rollback()
            raise
        start_response('204 No Content', [])
        return ['']

    @doc.response(403, 'The user is not allowed to modify the configuration')
    @authorize(CONFIG)
    @jsonify
    def fix_active(self):
        """
        Fixes the number of actives for a pair
        """
        input_dict = _get_input_as_dict(request)
        source = input_dict.get('source')
        destination = input_dict.get('destination')
        active = input_dict.get('active')

        if not source or not destination:
            raise HTTPBadRequest('Missing source and/or destination')
        if not active:
            raise HTTPBadRequest('Missing active')

        opt_active = Session.query(OptimizerActive).get((source, destination))
        if not opt_active:
            opt_active = OptimizerActive(
                source_se=source,
                dest_se=destination
            )

        try:
            if active > 0:
                opt_active.active = active
                opt_active.fixed = True
                _audit_configuration('fix-active', '%s => %s actives fixed to %s' % (source, destination, active))
            else:
                opt_active.active = 2
                opt_active.fixed = False
                _audit_configuration('fix-active', '%s => %s actives unfixed' % (source, destination))
            Session.merge(opt_active)
            Session.commit()
        except:
            Session.rollback()
            raise
        return opt_active

    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_fixed_active(self):
        """
        Gets the fixed pairs
        """
        input_dict = _get_input_as_dict(request, from_query=True)
        source = input_dict.get('source')
        destination = input_dict.get('destination')

        fixed = Session.query(OptimizerActive).filter(OptimizerActive.fixed == True)
        if source:
            fixed = fixed.filter(OptimizerActive.source_se == source)
        if destination:
            fixed = fixed.filter(OptimizerActive.dest_se == destination)

        return fixed.all()

    @doc.response(400, 'Invalid values passed in the request')
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def set_se_config(self):
        """
        Set the configuration parameters for a given SE
        """
        input_dict = _get_input_as_dict(request)

        try:
            for storage, cfg in input_dict.iteritems():
                # As source
                as_source_new = cfg.get('as_source', None)
                if as_source_new:
                    as_source = Session.query(Optimize).filter(Optimize.source_se == storage).first()
                    if not as_source:
                        as_source = Optimize(source_se=storage)
                    for key, value in as_source_new.iteritems():
                        _validate_type(Optimize, key, value)
                        setattr(as_source, key, value)
                    _audit_configuration('set-se-config', 'Set config as source %s: %s' % (storage, json.dumps(cfg)))
                    Session.merge(as_source)
                # As destination
                as_dest_new = cfg.get('as_destination', None)
                if as_dest_new:
                    as_dest = Session.query(Optimize).filter(Optimize.dest_se == storage).first()
                    if not as_dest:
                        as_dest = Optimize(dest_se=storage)
                    for key, value in as_dest_new.iteritems():
                        _validate_type(Optimize, key, value)
                        setattr(as_dest, key, value)
                    _audit_configuration('set-se-config', 'Set config as destination %s: %s' % (storage, json.dumps(cfg)))
                    Session.merge(as_dest)
                # Operation limits
                operations = cfg.get('operations', None)
                if operations:
                    for vo, limits in operations.iteritems():
                        for op, limit in limits.iteritems():
                            new_limit = Session.query(OperationConfig).get((vo, storage, op))
                            if not new_limit:
                                new_limit = OperationConfig(
                                    vo_name=vo, host=storage, operation=op
                                )
                            new_limit.concurrent_ops = limit
                            Session.merge(new_limit)
                    _audit_configuration('set-se-limits', 'Set limits for %s: %s' % (storage, json.dumps(operations)))
            Session.commit()
        except:
            Session.rollback()
            raise
        return None

    @doc.query_arg('se', 'Storage element', required=False)
    @doc.response(403, 'The user is not allowed to query the configuration')
    @authorize(CONFIG)
    @jsonify
    def get_se_config(self):
        """
        Get the configurations status for a given SE
        """
        se = request.params.get('se', None)
        from_optimize = Session.query(Optimize)
        from_ops = Session.query(OperationConfig)
        if se:
            from_optimize = from_optimize.filter((Optimize.source_se == se) | (Optimize.dest_se == se))
            from_ops = from_ops.filter(OperationConfig.host == se)

        # Merge both
        response = dict()
        for opt in from_optimize:
            se = opt.source_se if opt.source_se else opt.dest_se
            config = response.get(se, dict())
            link_config = dict()
            for attr in ['active', 'throughput', 'udt', 'ipv6']:
                link_config[attr] = getattr(opt, attr)
            if opt.source_se:
                config['as_source'] = link_config
            else:
                config['as_destination'] = link_config
            response[se] = config

        for op in from_ops:
            config = response.get(op.host, dict())
            if 'operations' not in config:
                config['operations'] = dict()
            if op.vo_name not in config['operations']:
                config['operations'][op.vo_name] = dict()
            config['operations'][op.vo_name][op.operation] = op.concurrent_ops
            response[op.host] = config

        return response

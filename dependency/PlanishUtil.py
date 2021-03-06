#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
#
# Copyright (c) 2015 Baidu.com, Inc. All Rights Reserved
#
################################################################################
"""
utility function for planishing dependent modules
Authors: zhousongsong(doublesongsong@gmail.com)
Date:    2015-09-15 14:13:44
"""
import os
import sys

broc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, broc_dir)
from dependency import BrocModule_pb2
from util import RepoUtil

class PlanishError(Exception):
    """
    Planish Exception 
    """
    def __init__(self, msg):
        """
        Args:
            msg : the error msg
        """
        self._msg = msg

    def __str__(self):
        """
        """
        return self._msg

    
def GetConfigsFromBroc(pathname):
    """
    get all config tags from BROC file
    Args:
        pathname : the abs path of BROC file
    Returns:
        set["xx@xx", "xx@xx@xx", "xx@xx@xx",...] 
        if pathname doesn't exist, raise PlanishError 
    """
    configs = set()
    try:
        with open(pathname, 'r') as f:
            for line in f.readlines():
                if line.strip().startswith("CONFIGS"):
                    # remove "CONFIGS(" and ")" in line
                    configs.add(line.strip()[9:-2])
    except IOError as e:
        raise PlanishError(e)

    return configs


def ParseConfigs(configs,
                 workspace,
                 dep_level,
                 repo_kind, 
                 repo_domain,
                 postfix_branch,
                 postfix_tag):
    """
    Parse tag CONFIGS
    Args:
        configs : set([xx@xx, xx@xx@xx, xx@xx@xx, ...])
        workspace : the abs path of worksapce, ie $WORKSPACE
        repo_kind : a enum value in BrocModule_pb2.Module.EnumRepo
        dep_level : int value presenting dependent level
        repo_domain : the domain name of repository
        postfix_branch : the branch postfix, for example 'BRANCH'
        postfix_tag : the tag postfix, for example 'PD_BL'
    Returns:
        list of BrocModule_pb2.BrocModule object
    """
    modules = []
    for item in configs:
        module = ParseConfig(item, 
                             workspace, 
                             dep_level,
                             repo_kind, 
                             repo_domain,
                             postfix_branch,
                             postfix_tag)
        modules.append(module)
    return modules
            
def ParseConfig(config, 
                workspace, 
                dep_level,
                repo_kind, 
                repo_domain,
                postfix_branch,
                postfix_tag):
    """
    parse tag CONFIGS' content and create a BrocModule_pb2.Module object
    Args:
        config : the dependent module's info whose format can be xx@xx, xx@xx@xx
        workspace : the abs path of worksapce, ie $WORKSPACE
        dep_level : int value representing dependent level
        repo_kind : a enum value in BrocModule_pb2.Module.EnumRepo
        repo_domain : the domain name of repository server
        postfix_branch : the branch postfix, for example 'BRANCH'
        postfix_tag : the tag postfix, for example 'PD_BL'
    Returns:
        return a BrocModule_pb2.Module object, but if config is illegal raise PlanishError
    """
    if repo_kind is BrocModule_pb2.Module.SVN:
        return CreateSvnModule(config, dep_level, workspace, repo_domain, repo_kind,
                               postfix_branch, postfix_tag)
    else:
        return CreateGitModule(config, dep_level, workspace, repo_domain)


def CreateSvnModule(config, dep_level, workspace, repo_domain, 
                    repo_kind, postfix_branch, postfix_tag):
    """
    to create a BrocModule_pb2.Module object whose repo_kind is BrocModule_pb2.Module.SVN
    Args:
        config : a str object whose format just like xx@xx, xx@xx@xx
        dep_level : int value representing dependent level
        workspace : the abs path of worksapce, ie $WORKSPACE
        repo_domain : the domain name of repository server
        postfix_branch : the branch postfix, for example 'BRANCH'
        postfix_tag : the tag postfix, for example 'PD_BL'
    Returns:
        return a BrocModule_pb2.Module object 
    Raise:
        PlanishError exception
    """
    # infos = [module cvs path, branch name, version or tag name] 
    infos = config.split('@')
    if len(infos) < 2:
        raise PlanishError("%s is illegal" % config)

    module = BrocModule_pb2.Module()
    module_cvspath = infos[0]
    module_branch = infos[1]
    module_version = None

    module.name = module_cvspath.split('/')[-1]
    module.module_cvspath = module_cvspath
    module.broc_cvspath = os.path.join(module_cvspath, 'BROC')
    module.is_main = False
    module.repo_kind = repo_kind
    module.dep_level = dep_level
    module.workspace = workspace
    module.root_path = os.path.join(workspace, module_cvspath)
    module.origin_config = config
    try:
        module.br_kind = ParseBranch(module_branch, 
                                     repo_kind, 
                                     postfix_branch, 
                                     postfix_tag)
    except PlanishError:
        raise  PlanishError("%s is illegal" % config)

    # check revision
    if len(infos) == 3:
        module.revision = infos[2]
    else:
        # default revision is empty
        module.revision = ''
    cvs_prefix = '/'.join(module_cvspath.split('/')[:-1])
    if module.br_kind == BrocModule_pb2.Module.TAG:
        module.tag_name = module_branch
        module.url = os.path.join(repo_domain, 
                                  cvs_prefix, 
                                  'tags',
                                  module.name,
                                  module_branch) 
    else:
        module.br_name = module_branch
        if module_branch == 'trunk':
            module.url = os.path.join(repo_domain, 
                                      cvs_prefix,
                                      'trunk',
                                      module.name)
        else: 
            module.url = os.path.join(repo_domain, 
                                      cvs_prefix, 
                                      'branches',
                                      module.name,
                                      module_branch)
    return module


def CreateGitModule(config, dep_level, workspace, repo_domain):
    """
    to create a BrocModule_pb2.Module object whose repo_kind is BrocModule_pb2.Module.GIT
    Args:
        config : a str object whose format is cvspath@branch_name@key_word_branch or cvspath@tag_name@key_word_tag
        dep_level : int value representing dependent level
        workspace : the abs path of worksapce, ie $WORKSPACE
        repo_domain : the domain name of repository server
    Returns:
        return a BrocModule_pb2.Module object 
    Raise:
        PlanishError exception
    """
    infos = config.split('@')
    if len(infos) < 3 or infos[2] not in['branch', 'tag']:
        raise PlanishError("%s is illegal" % config)
   
    module = BrocModule_pb2.Module()
    # if 'ub' is module name, infos[0] format can be 'ub', 'xx/ub' or 'xx/xx/ub', ...
    module.module_cvspath = infos[0]
    module.name = infos[0].split('/')[-1]
    module.repo_kind = BrocModule_pb2.Module.GIT
    module.is_main = False
    module.broc_cvspath = os.path.join(module.module_cvspath, 'BROC')
    module.dep_level = dep_level
    module.workspace = workspace
    module.root_path = os.path.join(workspace, module.module_cvspath)
    module.url = os.path.join(repo_domain, infos[0])
    module.origin_config = config
    if infos[2] == 'branch':
        module.br_kind = BrocModule_pb2.Module.BRANCH
        module.br_name = infos[1]
    else:
        module.br_kind = BrocModule_pb2.Module.TAG
        module.tag_name = infos[1]

    return module


def ParseBranch(branch, repo_kind, postfix_branch, postfix_tag):
    """
    Parse branch and return branch name, branch kind infos
    the example for Svn:
        branch : sky_1-0-0-0_BRANCH
        tag    : sky_1-0-0-0_PD_BL
    the exmple for Git:
        master : master
        branch : dev
    Args:
        branch : the name of branch
        repo_kind : BrocModule_pb2.Module.EnumRepo
        postfix_branch : the branch postfix, for example 'BRANCH'
        postfix_tag : the tag postfix, for example 'PD_BL'
    Returns:
        return BrocModule_pb2.Module.EnumBR
        otherwise raise PlanishError
    """
    br_kind = None
    if repo_kind == BrocModule_pb2.Module.SVN:
        if branch == 'trunk' or branch.endswith(postfix_branch):
            br_kind = BrocModule_pb2.Module.BRANCH
        elif branch.endswith(postfix_tag):
            br_kind = BrocModule_pb2.Module.TAG
        else:
            raise PlanishError("don't recognize dependent module's branch name(%s)" % branch)
    elif repo_kind == BrocModule_pb2.Module.GIT:
        br_kind = BrocModule_pb2.Module.BRANCH
    else:
        raise PlanishError("don't support repo kind %d" % repo_kind)

    return br_kind


def CreateBrocModuleFromDir(target_path, 
                            repo_domain, 
                            postfix_branch,
                            postfix_tag,
                            logger):
    """
    create one BrocModule_pb2.Module object from a existing directory 
    Args:
        target_path : the abs path of a directory
        repo_domain : the domain name of repository
        postfix_branch : a string object representint the postfix of branch
        postfix_tag : a string object representint the postfix of tag
        logger : the object of Log.Log
    Returns:
        return a BrocModule_pb2.Module object when creating successfully, 
        if fail to create, PlanishError is raised
    """
    # check BROC file
    broc_file = os.path.normpath(os.path.join(target_path, 'BROC'))
    if not os.path.exists(broc_file):
        raise PlanishError("No BROC file founded in %s" % target_path)

    # get infos form directory target_path
    repo_kind = None
    module_infos = None
    if RepoUtil.IsUnderSvnControl(target_path):
        repo_kind = BrocModule_pb2.Module.SVN
        module_infos = RepoUtil.GetSvnUrlInfos(target_path, 
                                               postfix_branch,
                                               postfix_tag,
                                               ['trunk', 'branches', 'tags'],
                                               repo_domain,
                                               logger)
    elif RepoUtil.IsUnderGitControl(target_path):
        repo_kind = BrocModule_pb2.Module.GIT
        module_infos = RepoUtil.GetGitUrlInfos(target_path, 
                                               repo_domain,
                                               logger)
    else:
        raise PlanishError("%s is not under version control" % target_path)

    if not module_infos['result']:
        raise PlanishError("get module infos from dir(%s) failed" % target_path)
    
    module = BrocModule_pb2.Module()
    module.name =  module_infos['name']
    module.module_cvspath = module_infos['module_cvspath']
    module.broc_cvspath = module_infos['broc_cvspath']
    module.workspace = module_infos['workspace']
    module.root_path = module_infos['root_path']
    # default is not main module
    module.is_main = True
    module.repo_kind = repo_kind
    module.url =  module_infos['url']
    if module_infos['br_kind'] in ['TRUNK', 'BRANCH']:
        module.br_kind = BrocModule_pb2.Module.BRANCH
    else:
        module.br_kind = BrocModule_pb2.Module.TAG
    module.br_name = module_infos['br_name']
    module.tag_name = module_infos['tag_name']
    if repo_kind == BrocModule_pb2.Module.GIT:
        module.commit_id = module_infos['commit_id']
    else:
        module.revision = module_infos['revision']
        module.last_changed_rev = module_infos['last_changed_rev']
    # main module don't care the following infos
    module.origin_config = ""
    module.highest_version = ""
    module.lowest_version = ""
    return module

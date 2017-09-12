import os
import sys
import shutil
#import config.config as config
import config as config
import yaml
import pwd
from datetime import datetime, timedelta
import subprocess
import re
from pprint import pprint

def addUser(username, access, users_file_path):
  tab = '    '
  if not os.path.exists(users_file_path):
    #create users file if not existing
    users_file = open(users_file_path, 'w')
    #set permissions
    os.chmod(users_file_path, 0o700)
    #add start of file
    users_file.write('---\n')
    users_file.close()

  users_file = open(users_file_path, 'r')

  #check username exists
  try:
    user_details = pwd.getpwnam(username)
  except KeyError as e:
    print('(addUser) username {} not found'.format(username))
    raise e

  try:
    users = yaml.load(users_file)
    users_file.close()
  except Exception as e:
    print('(addUser) error processing users file ({})'.format(str(e)))
    raise e

  #if nothing returned from yaml, set users to be empty dict
  if users is None:
    users = {}

  #if user_details already present, do nothing
  if user_details[0] not in users.items():
    #otherwise if user not present
    #add username
    now = datetime.now()
    users[user_details[0]] = {
      'pid': user_details[2],
      'datasets': [],
      'added_date': now.strftime('%Y-%m-%d'),
      'expiry_date': (now + timedelta(days=30)).strftime('%Y-%m-%d'),
    }

    #save file
    users_file = open(users_file_path, 'w')
    yaml.dump(users, users_file)

  return users

def setAccess(target_collection, users_file_path, access_level):

  #check users file and target collection exist
  if not os.path.exists(target_collection):
    print('(setAccess) target_collection does not appear to exist')
    raise ValueError('(setAccess) target_collection does not appear to exist')

  try:
    users_file = open(users_file_path, 'r')
    users = yaml.load(users_file)
    users_file.close()
  except Exception as e:
    print('(addUser) error processing users file ({})'.format(str(e)))
    raise e

  #go through users 
  for username, user_access in users.items():
    #check username exists
    try:
      user_details = pwd.getpwnam(username)
    except KeyError as e:
      print('(addUser) username {} not found'.format(username))
      raise e

    #check that expiry date not passed
    expiry_date = datetime.strptime(user_access['expiry_date'], '%Y-%m-%d')
    if expiry_date < datetime.now():
      #remove user from acl
      for subdir in config.access_levels[access_level]['dirs']:
        setfacl_result = subprocess.call('setfacl', '-R -x u:{} {}'.format(user_details[2], os.path.join(target_collection,subdir)))
        if setfacl_result != 0:
          e = '(setAccess) error, setfacl returned {} when trying to set the acl for user {} path {}'.format(setfacl_result, username, os.path.join(target_collection,subdir))
          print(e)
          raise SystemError(e)
    else:
      #add user to acl
      for subdir in config.access_levels[access_level]['dirs']:
        setfacl_result = subprocess.call('setfacl', '-R -m u:{}:{} {}'.format(user_details[2], config.access_levels[access_level]['permissions'], os.path.join(target_collection,subdir)))
        if setfacl_result != 0:
          e = '(setAccess) error, setfacl returned {} when trying to set the acl for user {} path {}'.format(setfacl_result, username, os.path.join(target_collection,subdir))
          print(e)
          raise SystemError(e)


def genPath(rel_path, root):
  if not os.path.exists(root):
    raise ValueError('(genPath) Root path does not exist')

  path_now = root

  for location in rel_path:
    if not os.path.exists(os.path.join(path_now,location)):
      os.mkdir(os.path.join(path_now,location))

def chmod_rec(permissions, current_path, target_path):
  for root, dirs, files in os.path.join(current_path,target_path):
    os.chmod(root, permissions)
    for d in dirs:
      chmod_rec(permissions, root, d)

def setCoreAccess(target_path):
  if not os.path.exists(target_path):
    raise ValueError('(setCoreAccess) target_path does not exist')

  for dev_path in config.dev_only_paths:
    try:
      for root, dirs, files in os.walk(target_path,dev_path):
        os.chmod(root, 0o700)
        for f in files:
          os.chmod(os.path.join(root,f), 0o700)
    except:
      print('(setCoreAccess) Unable to lock down path {}/{}'.format(target_path,dev_path))
      exit(0)

  for ro_path in config.read_only_paths:
    try:
      for root, dirs, files in os.walk(target_path,ro_path):
        os.chmod(root, 0o750)
        for f in files:
          os.chmod(os.path.join(root,f), 0o750)
    except:
      print('(setCoreAccess) Unable to set to read only path {}/{}'.format(target_path,ro_path))
      exit(0)

def copyTemplate(template_dir, target_path):
  if not os.path.exists(template_dir):
    raise ValueError('(copyTemplate) template_dir does not exist')
  if not os.path.exists(os.path.join(*target_path[:-1])):
    raise ValueError('(copyTemplate) core target_path does not exist (omitting final directory)')

  target_dir = target_path[-1]

  try:
    shutil.copytree(template_dir, target_dir)
  except:
    print('(copyTemplate) Error copying template directory')
    exit(0)

def processStructureFile(dir_structure_file):
  # process dir_structure_file
  # this uses placeholders for project/dataset names
  # e.g. 
  # {project}:
  #   data:
  #     {dataset}:
  #       - raw
  #       - dev
  #       - release
  dir_structure = yaml.load(dir_structure_file)
  return dir_structure

def genStructure(target_location, dir_structure, **kwargs):

  if not os.path.exists(target_location):
    raise ValueError('(genStructure) target_location does not exist')

  try:
    current_path = os.path.split(target_location)

    # if it's a list, convert to a dict
    if isinstance(dir_structure, list):
      dir_structure = {index_val[1]: index_val[0] for index_val in enumerate(dir_structure)}
    
    for directory, contents in dir_structure.items():

      # see if one of the kwargs matches a placeholder
      # if so, replace
      placeholder_match = re.search('\{([a-z0-9_A-Z\-]+)?\}', directory)
      try:
        if placeholder_match is not None and placeholder_match.groups(1) is not None:
          #directory.format_map(kwargs)
          for kw, val in kwargs.items():
            if kw == placeholder_match.groups(1)[0]:
              directory = directory.format(**{kw: val})
              break
          else:
            # if no match, remove the {} to use the default placeholder name
            directory = placeholder_match.groups(1)[0]
      except IndexError:
        pass

      new_path = current_path + (directory,)

      # now create dir if not existing
      if not os.path.exists(os.path.join(*new_path)):
        os.mkdir(os.path.join(*new_path))

      if isinstance(contents, list) or isinstance(contents, dict):
        genStructure(os.path.join(*new_path), contents, **kwargs)

  except Exception as e:
    raise e

        



  

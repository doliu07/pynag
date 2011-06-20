# -*- coding: utf-8 -*-
#
# Copyright 2010, Pall Sigurdsson <palli@opensource.is>
#
# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This script is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module provides a high level Object-Oriented wrapper around pynag.Parsers.config.

example usage:

from pynag.Parsers import Service,Host

all_services = Service.objects.all
my_service=all_service[0]
print my_service.host_name

example_host = Host.objects.filter(host_name="host.example.com")
canadian_hosts = Host.objects.filter(host_name__endswith=".ca")

for i in canadian_hosts:
    i.alias = "this host is located in Canada"
    i.save()
"""

__author__ = "Pall Sigurdsson"
__copyright__ = "Copyright 2011, Pall Sigurdsson"
__credits__ = ["Pall Sigurdsson"]
__license__ = "GPL"
__version__ = "0.3"
__maintainer__ = "Pall Sigurdsson"
__email__ = "palli@opensource.is"
__status__ = "Development"


import sys
import os
import re
sys.path.insert(1, '/opt/pynag')
from pynag import Parsers
from macros import _standard_macros


import time


# Path To Nagios configuration file
cfg_file = '/etc/nagios/nagios.cfg'

config = None
# TODO: Make this a lazy load, so config is only parsed when it needs to be.
config = Parsers.config(cfg_file)
config.parse()


#: eventhandlers -- A list of Model.EventHandelers object.
# Event handler is responsible for passing notification whenever something important happens in the model
# For example FileLogger class is an event handler responsible for logging to file whenever something has been written.
eventhandlers = []

def debug(text):
    debug = True
    if debug: print text



def contains(str1, str2):
    'Returns True if str1 contains str2'
    if str1.find(str2) > -1: return True

def not_contains(str1, str2):
    'Returns True if str1 does not contain str2'
    return not contains(str1, str2)

def has_field(str1, str2):
    '''Returns True if str2 is a field in str1
    
    For this purpose the string 'example' is a field in '+this,is,an,example'
    '''
    str1 = str1.strip('+')
    str1 = str1.split(',')
    if str2 in str1: return True
    return False
class ObjectFetcher(object):
    '''
    This class is a wrapper around pynag.Parsers.config. Is responsible for fetching dict objects
    from config.data and turning into high ObjectDefinition objects
    '''
    def __init__(self, object_type):
        self.object_type = object_type
        self.objects = []
    @property
    def all(self):
        " Return all object definitions of specified type"
        if self.objects != []:
            return self.objects
        if self.object_type != None:
            key_name = "all_%s" % (self.object_type)
            if not config.data.has_key(key_name):
                return []
            objects = config.data[ key_name ]
        else:
            # If no object type was requested
            objects = []
            for v in config.data.values():
                objects += v
        for i in objects:
            Class = string_to_class[ i['meta']['object_type'] ]
            i = Class(item=i)
            self.objects.append(i)
        return self.objects
    def get_by_id(self, id):
        ''' Get one specific object
        
        Returns:
            ObjectDefinition
        Raises:
            ValueError if object is not found
        '''
        id = str(id)
        for item in self.all:
            if str(item['id']) == id:
                return item
        raise ValueError('No object with ID=%s found'% (id))
    def get_by_shortname(self, shortname):
        ''' Get one specific object by its shortname (i.e. host_name for host, etc)
        
        Returns:
            ObjectDefinition
        Raises:
            ValueError if object is not found
        '''
        attribute_name = "%s_name" % (self.object_type)
        for item in self.all:
            if item[attribute_name] == shortname:
                return item
        raise ValueError('No %s with %s=%s found' % (self.object_type, attribute_name,shortname))
    def filter(self, **kwargs):
        '''
        Returns all objects that match the selected filter
        
        Examples:
        # Get all services where host_name is examplehost.example.com
        Service.objects.filter(host_name='examplehost.example.com')
        
        # Get service with host_name=examplehost.example.com and service_description='Ping'
        Service.objects.filter(host_name='examplehost.example.com',service_description='Ping')
        
        # Get all services that are registered but without a host_name
        Service.objects.filter(host_name=None,register='1')

        # Get all hosts that start with 'exampleh'
        Host.objects.filter(host_name__startswith='exampleh')
        
        # Get all hosts that end with 'example.com'
        Service.objects.filter(host_name__endswith='example.com')
        
        # Get all contactgroups that contain 'dba'
        Contactgroup.objects.filter(host_name__contains='dba')

        # Get all hosts that are not in the 'testservers' hostgroup
        Host.objects.filter(hostgroup_name__notcontains='testservers')
        # Get all services with non-empty name
        Service.objects.filter(name__isnot=None)
        '''
        # TODO: Better testing of these cases:
        # register = 1
        # id attribute
        # any attribute = None or 'None'
        result = []
        # Lets convert all values to str()
        tmp = {}
        for k,v in kwargs.items():
            k = str(k)
            if v != None: v = str(v)
            tmp[k] = v
        kwargs = tmp
        for i in self.all:
            object_matches = True
            for k, v in kwargs.items():
                if k.endswith('__startswith'):
                    k = k[:-12]
                    match_function = str.startswith
                elif k.endswith('__endswith'):
                    k = k[:-10]
                    match_function = str.endswith
                elif k.endswith('__isnot'):
                    k = k[:-7]
                    match_function = str.__ne__
                elif k.endswith('__contains'):
                    k = k[:-10]
                    match_function = contains
                elif k.endswith('__has_field'):
                    k = k[:-11]
                    match_function = has_field
                elif k.endswith('__notcontains'):
                    k = k[:-13]
                    match_function = not_contains
                else:
                    match_function = str.__eq__
                if k == 'id' and str(v) == str(i.get_id()):
                    object_matches = True
                    break
                if k == 'register' and v == '1' and not i.has_key(k):
                    'not defined means item is registered'
                    continue
                if v == None and i.has_key(k):
                    object_matches = False
                    break
                if not i.has_key(k):
                    if v == None: continue # if None was the search attribute
                    object_matches = False
                    break
                if not match_function(i[k], v):
                    object_matches = False
                    break
            if object_matches:
                result.append(i)
        return result        

    
class ObjectDefinition(object):
    '''
    Holds one instance of one particular Object definition
    Example usage:
        objects = ObjectDefinition.objects.all
        my_object ObjectDefinition( dict ) # dict = hash map of configuration attributes
    '''
    object_type = None
    objects = ObjectFetcher(None)
    def __init__(self, item=None):
        if item == None:
            item = config.get_new_item(object_type=self.object_type, filename=None)
        self.object_type = item['meta']['object_type']
        
        # self.objects is a convenient way to access more objects of the same type
        self.objects = ObjectFetcher(self.object_type)
        # self.data -- This dict stores all effective attributes of this objects
        self._original_attributes = item
        
        #: _changes - This dict contains any changed (but yet unsaved) attributes of this object 
        self._changes = {}
        
        #: _defined_attributes - All attributes that this item has defined
        self._defined_attributes = item['meta']['defined_attributes']
        
        #: _inherited_attributes - All attributes that this object has inherited via 'use'
        self._inherited_attributes = item['meta']['inherited_attributes']
        
        #: _meta - Various metadata about the object
        self._meta = item['meta']
        
        #: _macros - A dict object that resolves any particular Nagios Macro (i.e. $HOSTADDR$)
        self._macros = {}
        
        #: __argument_macros - A dict object that resolves $ARG* macros
        self.__argument_macros = {}
        # Lets create dynamic convenience properties for each item
        for k in self._original_attributes.keys():
            if k == 'meta': continue
            self._add_property(k)
    
    def _add_property(self, name):
        ''' Creates dynamic properties for every attribute of out definition.
        
        i.e. this makes sure host_name attribute is accessable as self.host_name
        
        Returns: None
        '''
        fget = lambda self: self.get_attribute(name)
        fset = lambda self, value: self.set_attribute(name, value)
        setattr( self.__class__, name, property(fget,fset))
    def get_attribute(self, attribute_name):
        'Get one attribute from our object definition'
        return self[attribute_name]
    def set_attribute(self, attribute_name, attribute_value):
        'Set (but does not save) one attribute in our object'
        self[attribute_name] = attribute_value
        self._event(level="debug", message="attribute changed: %s = %s" % (attribute_name, attribute_value))
    def is_dirty(self):
        "Returns true if any attributes has been changed on this object, and therefore it needs saving"
        return len(self._changes.keys()) == 0
    def __setitem__(self, key, item):
        self._changes[key] = item
    def __getitem__(self, key):
        if key == 'id':
            return self.get_id()
        if key == 'description':
            return self.get_description()
        if key == 'register' and not self._defined_attributes.has_key('register'):
            return "1"
        if key == 'meta':
            return self._meta
        if self._changes.has_key(key):
            return self._changes[key]
        elif self._defined_attributes.has_key(key):
            return self._defined_attributes[key]
        elif self._inherited_attributes.has_key(key):
            return self._inherited_attributes[key]
        elif self._meta.has_key(key):
            return self._meta[key]
        else:
            return None
    def has_key(self, key):
        if key in self.keys():
            return True
        if key in self._meta.keys():
            return True
        return False
    def keys(self):
        all_keys = ['meta']
        for k in self._changes.keys():
            if k not in all_keys: all_keys.append(k)
        for k in self._defined_attributes.keys():
            if k not in all_keys: all_keys.append(k)
        for k in self._inherited_attributes.keys():
            if k not in all_keys: all_keys.append(k)
        #for k in self._meta.keys():
        #    if k not in all_keys: all_keys.append(k)
        return all_keys
    def get_id(self):
        """ Return a unique ID for this object"""
        #return self.__str__().__hash__()
        object_type = self['object_type']
        shortname = self.get_description()
        object_name = self['name']
        filename = self['filename']
        id = "%s-%s-%s-%s" % ( object_type, shortname, object_name, filename)
        import md5
        return md5.new(id).hexdigest()
        return id
    def save(self):
        """Saves any changes to the current object to its configuration file
        
        Returns:
            Number of changes made to the object
        """
        number_of_changes = 0
        for field_name, new_value in self._changes.items():
            save_result = config.item_edit_field(item=self._original_attributes, field_name=field_name, new_value=new_value)
            if save_result == True:
                self._event(level='write', message="%s changed from '%s' to '%s'" % (field_name, self._original_attributes[field_name], new_value))
                self._defined_attributes[field_name] = new_value
                self._original_attributes[field_name] = new_value
                del self._changes[field_name]
                number_of_changes += 1
        return number_of_changes
    def rewrite(self, str_new_definition=None):
        """ Rewrites this Object Definition in its configuration files.
        
        Arguments:
            str_new_definition = the actual string that will be written in the configuration file
            if str_new_definition is None, then we will use self.__str__()
        Returns: 
            True on success
        """
        if str_new_definition == None:
            str_new_definition = self['meta']['raw_definition']
        config.item_rewrite(self._original_attributes, str_new_definition)
        self._event(level='write', message="Object definition rewritten")
        return True
    def delete(self, cascade=False):
        """ Deletes this object definition from its configuration files.
        
        Arguments:
            Cascade: If True, look for items that depend on this object and delete them as well
            (for example, if you delete a host, delete all its services as well)
        """
        if cascade == True:
            raise NotImplementedError()
        else:
            result = config.item_remove(self._original_attributes)
            self._event(level="write", message="Object was deleted")
            return result
    def get_related_objects(self):
        """ Returns a list of ObjectDefinition that depend on this object
        
        Object can "depend" on another by a 'use' or 'host_name' or similar attribute
        
        Returns:
            List of ObjectDefinition objects
        """
        result = []
        if self['name'] != None:
            tmp = ObjectDefinition.objects.filter(use__has_field=self['name'], object_type=self['object_type'])
            for i in tmp: result.append(i)
        return result
    def __str__(self):
        return_buffer = "define %s {\n" % (self.object_type)
        fields = self.keys()
        fields.sort()
        interesting_fields = ['service_description', 'use', 'name', 'host_name']
        for i in interesting_fields:
            if i in fields:
                fields.remove(i)
                fields.insert(0, i)           
        for key in fields:
            if key == 'meta' or key in self['meta'].keys(): continue
            value = self[key]
            return_buffer = return_buffer + "  %-30s %s\n" % (key, value)
        return_buffer = return_buffer + "}\n"
        return return_buffer
    def __repr__(self):
        return "%s: %s" % (self['object_type'], self.get_shortname())
        result = ""
        result += "%s: " % self.__class__.__name__
        for i in  ['object_type', 'host_name', 'name', 'use', 'service_description']:
            if self.has_key(i):
                result += " %s=%s " % (i, self[i])
            else:
                result += "%s=None " % (i)
        return result
    def get_description(self):
        raise NotImplementedError()
    def get_shortname(self):
        return self.get_description()
    def get_macro(self, macroname ):
        # TODO: This function is incomplete and untested
        if macroname.startswith('$ARG'):
            'Command macros handled in a special function'
            return self._get_command_macro(macroname)
        if macroname.startswith('$USER'):
            '$USERx$ macros are supposed to be private, but we will display them anyway'
            for mac,val in config.resource_values:
                if macroname == mac:
                    return val
            return ''
        if macroname.startswith('$HOST') or macroname.startswith('$_HOST'):
            return self._get_host_macro(macroname)
        if macroname.startswith('$SERVICE') or macroname.startswith('$_SERVICE'):
            return self._get_service_macro(macroname)
        if _standard_macros.has_key( macroname ):
            attr = _standard_macros[ macroname ]
            return self[ attr ]
        return ''
    def get_all_macros(self):
        "Returns {macroname:macrovalue} hash map of this object's macros"
        # TODO: This function is incomplete and untested
        if self['check_command'] == None: return None
        c = self['check_command']
        c = c.split('!')
        command_name = c.pop(0)
        command = Command.objects.get_by_shortname(command_name)
        regex = re.compile("(\$\w+\$)")
        macronames = regex.findall( command['command_line'] )
        result = {}
        for i in macronames:
            result[i] = self.get_macro(i)
        return result
    def get_effective_command_line(self):
        "Return a string of this objects check_command with all macros (i.e. $HOSTADDR$) resolved"
        # TODO: This function is incomplete and untested
        if self['check_command'] == None: return None
        c = self['check_command']
        c = c.split('!')
        command_name = c.pop(0)
        try:
            command = Command.objects.get_by_shortname(command_name)
        except ValueError:
            return None
        regex = re.compile("(\$\w+\$)")
        get_macro = lambda x: self.get_macro(x.group())
        result = regex.sub(get_macro, command['command_line'])
        return result
    def _get_command_macro(self, macroname):
        "Resolve any command argument ($ARG1$) macros from check_command"
        # TODO: This function is incomplete and untested
        a = self.__argument_macros
        if a == {}:
            c = self['check_command'].split('!')
            c.pop(0) # First item is the command, we dont need it
            for i, v in enumerate( c ):
                tmp = i+1
                if v.startswith('$') and v.endswith('$') and not v.startswith('$ARG'):
                    v = self.get_macro(v)
                a['$ARG%s$' % tmp] = v
        if a.has_key( macroname ):
            return a[ macroname ]
        else:
            return '' # Return empty string if macro is invalid.
    def _get_service_macro(self,macroname):
        # TODO: This function is incomplete and untested
        if macroname.startswith('$_SERVICE'):
            'If this is a custom macro'
            name = macroname[9:-1]
            return self["_%s" % name]
        if _standard_macros.has_key( macroname ):
            attr = _standard_macros[ macroname ]
            return self[ attr ]
        return ''
    def _get_host_macro(self, macroname):
        # TODO: This function is incomplete and untested
        if macroname.startswith('$_HOST'):
            'if this is a custom macro'
            name = macroname[6:-1]
            return self["_%s" % name]
        if _standard_macros.has_key( macroname ):
            attr = _standard_macros[ macroname ]
            return self[ attr ]
        return ''
    def get_effective_parents(self, recursive=False):
        """ Get all objects that this one inherits via "use" attribute
        
        Arguments:
            recursive - If true include grandparents in list to be returned
        Returns:
            a list of ObjectDefinition objects
        """
        # TODO: This function is incomplete and untested
        if not self.has_key('use'):
            return []
        results = []
        use = self['use'].split(',')
        for parent_name in use:
            results.append( self.objects.filter(name=parent_name)[0] )
        if recursive is True:
            grandparents = []
            for i in results:
                grandparents.append( i.get_effective_parents(recursive=True))
            results += grandparents
        return results
    def get_effective_hostgroups(self):
        """Get all hostgroups that this object belongs to (not just the ones it defines on its own
        
        How can a hostgroup be linked to this object:
            1) This object has hostgroups defined via "hostgroups" attribute
            2) This object inherits hostgroups attribute from a parent
            3) A hostgroup names this object via members attribute
            4) A hostgroup names another hostgroup via hostgroup_members attribute
            5) A hostgroup inherits (via use) from a hostgroup who names this host
        """
        # TODO: This function is incomplete and untested
        # TODO: Need error handling when object defines hostgroups but hostgroup does not exist
        result = []
        hostgroup_list = []
        # Case 1 and Case 2:
        tmp = self._get_effective_attribute('hostgroups')
        for i in tmp.split(','):
            if i == '': continue
            i = Hostgroup.objects.get_by_shortname(i)
            if not i in result: result.append(i)
        '''
        # Case 1
        if self.has_key('hostgroups'):
            grp = self['hostgroups']
            grp = grp.split(',')
            for i in grp:
                i = i.strip('+')
                i = Hostgroup.objects.get_by_shortname(i)
                if not i in result: result.append(i)
        # Case 2:
        if not self.has_key('hostgroups') or self['hostgroups'].startswith('+'):
            parents = self.get_effective_parents()
            for parent in parents:
                parent_results += parent.get_effective_hostgroups()
        '''
        # Case 3:
        if self.has_key('host_name'):
            # We will use hostgroup_list in case 4 and 5 as well
            hostgroup_list = Hostgroup.objects.filter(members__has_field=self['host_name'])
            for hg in hostgroup_list:
                    if hg not in result:
                        result.append( hg )
        # Case 4:    
        for hg in hostgroup_list:
            if not hg.has_key('hostgroup_name'): continue
            grp = Hostgroup.objects.filter(hostgroup_members__has_field=hg['hostgroup_name'])
            for i in grp:
                if i not in result:
                    result.append(i )
        # Case 5:
        for hg in hostgroup_list:
            if not hg.has_key('hostgroup_name'): continue
            grp = Hostgroup.objects.filter(use__has_field=hg['hostgroup_name'])
            for i in grp:
                if i not in result:
                    result.append(i )
        
        return result
    def get_effective_contactgroups(self):
        # TODO: This function is incomplete and untested
        raise NotImplementedError()
    def get_effective_hosts(self):
        # TODO: This function is incomplete and untested
        raise NotImplementedError()
    def get_attribute_tuple(self):
        """ Returns all relevant attributes in the form of:
        
        (attribute_name,defined_value,inherited_value)
        """
        result = []
        for k in self.keys():
            inher = defin = None 
            if self._inherited_attributes.has_key(k):
                inher = self._inherited_attributes[k]
            if self._defined_attributes.has_key(k):
                defin = self._defined_attributes[k]
            result.append((k, defin, inher))
        return result
    def get_parents(self):
        "Returns an ObjectDefinition list of all parents (via use attribute)"
        result = []
        if not self['use']: return result
        for parent_name in self['use'].split(','):
            parent = self.objects.filter(name=parent_name)[0]
            result.append(parent)
        return result
    def get_effective_contact_groups(self):
        "Returns a list of all contactgroups that belong to this service"
        result = []
        contactgroups = self._get_effective_attribute('contact_groups')
        for c in contactgroups.split(','):
            if c == '': continue
            group = Contactgroup.objects.get_by_shortname(c)
            result.append( group )
        return result
    def get_effective_contacts(self):
        "Returns a list of all contacts that belong to this service"
        result = []
        contacts = self._get_effective_attribute('contacts')
        for c in contacts.split(','):
            if c == '': continue
            contact = Contact.objects.get_by_shortname(c)
            result.append( contact )
        return result
    def _get_effective_attribute(self, attribute_name):
        """This helper function returns specific attribute, from this object or its templates
        
        This is handy for fields that effectively are many_to_many values.
        for example, "contactroups +group1,group2,group3"
        
        Fields that are known to use this format are:
            contacts, contactgroups, hostgroups, servicegroups, members,contactgroup_members
        """
        result = []
        tmp = self[attribute_name]
        if tmp != None:
            result.append( tmp )
        if tmp == None or tmp.startswith('+'):
            for parent in self.get_parents():
                result.append( parent._get_effective_attribute(attribute_name) )
                if parent[attribute_name] != None and not parent[attribute_name].startswith('+'):
                    break
        return_value = []
        for value in  result :
            value = value.strip('+')
            if value == '': continue
            if value not in return_value:
                return_value.append( value )
        tmp = ','.join( return_value )
        tmp = tmp.replace(',,',',')
        return tmp
    def _event(self, level=None, message=None):
        """ Pass informational message about something that has happened within the Model """
        for i in eventhandlers:
            if level == 'write':
                i.write( object_definition=self, message=message )
            else:
                i.debug( object_definition=self, message=message )
            
                
                    
                
        
        
class Host(ObjectDefinition):
    object_type = 'host'
    objects = ObjectFetcher('host')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['host_name']
    def get_effective_services(self):
        """ Returns a list of all services that belong to this Host """
        result = []
        if self['host_name'] != None:
            tmp = Service.objects.filter(host_name=self['host_name'])
            for i in tmp:
                if i not in result:
                    result.append(i)
        for hostgroup in self.get_effective_hostgroups():
            tmp = Service.objects.filter(hostgroups=hostgroup)
            for i in tmp:
                if i not in result:
                    result.append(i)
        return result
    def get_related_objects(self):
        result = super(self.__class__, self).get_related_objects()
        if self['host_name'] != None:
            tmp = Service.objects.filter(host_name=self['host_name'])
            for i in tmp: result.append( i )
        return result
class Service(ObjectDefinition):
    object_type = 'service'
    objects = ObjectFetcher('service')
    def get_description(self):
        """ Returns a friendly description of the object """
        return "%s/%s" % (self['host_name'], self['service_description'])
    def _get_host_macro(self, macroname):
        if self['host_name'] == None:
            return None
        myhost = Host.objects.get_by_shortname(self['host_name'])
        return myhost._get_host_macro(macroname)     

            
class Command(ObjectDefinition):
    object_type = 'command'
    objects = ObjectFetcher('command')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['command_name']
class Contact(ObjectDefinition):
    object_type = 'contact'
    objects = ObjectFetcher('contact')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['contact_name']
    def get_effective_contact_groups(self):
        "Contact uses contactgroups instead of contact_groups"
        return self.get_effective_contactgroups()
    def get_effective_contactgroups(self):
        ''' Get a list of all contactgroups that are hooked to this contact '''
        result = []
        contactgroups = self._get_effective_attribute('contactgroups')
        for c in contactgroups.split(','):
            if c == '': continue
            group = Contactgroup.objects.get_by_shortname(c)
            if group not in result: result.append( group )
        # Additionally, check for contactgroups that define this contact as a member
        if self['contact_name'] == None: return result
        
        for cgroup in Contactgroup.objects.filter( members__has_field=self['contact_name'] ):
            if cgroup not in result: result.append( cgroup )
        return result
class Contactgroup(ObjectDefinition):
    object_type = 'contactgroup'
    objects = ObjectFetcher('contactgroup')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['contactgroup_name']
    def get_effective_members(self):
        """ Returns a list of all Contacts that are in this contactgroup """
        """
        How can a contact belong to a group:
        1) contact.contact_name is mentioned in contactgroup.members
        2) contactgroup.contactgroup_name is mentioned in contact.contactgroups
        3) contact belongs to contactgroup.use
        4) contact belongs to contactgroup.countactgroup.use
        """
        result = []
        # Case 1 and 3
        for i in self._get_effective_attribute('members').split(','):
            if i == '': continue
            contact = Contact.objects.get_by_shortname(i)
            if contact not in result: result.append( contact )
        # Case 2
        for i in self._get_effective_attribute('contactgroup_members').split(','):
            if i == '': continue
            contactgroup = Contactgroup.objects.get_by_shortname(i)
            for c in contactgroup.get_effective_members():
                if c not in result: result.append( c)
        # Case 4
        if self['contactgroup_name'] is not None:
            for i in Contact.objects.all:
                groups = i.get_effective_contact_groups()
                for group in groups:
                    if self.get_shortname() == group.get_shortname():
                        if i not in result: result.append( i )
        return result
             
   
class Hostgroup(ObjectDefinition):
    object_type = 'hostgroup'
    objects = ObjectFetcher('hostgroup')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['hostgroup_name']
class Servicegroup(ObjectDefinition):
    object_type = 'servicegroup'
    objects = ObjectFetcher('servicegroup')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['servicegroup_name']
class Timeperiod(ObjectDefinition):
    object_type = 'timeperiod'
    objects = ObjectFetcher('timeperiod')
    def get_description(self):
        """ Returns a friendly description of the object """
        return self['timeperiod_name']

string_to_class = {}
string_to_class['contact'] = Contact
string_to_class['service'] = Service
string_to_class['host'] = Host
string_to_class['hostgroup'] = Hostgroup
string_to_class['contactgroup'] = Contactgroup
string_to_class['servicegroup'] = Servicegroup
string_to_class['timeperiod'] = Timeperiod
string_to_class['command'] = Command
string_to_class[None] = ObjectDefinition



def _test_get_by_id():
    'Do a quick unit test of the ObjectDefinition.get_by_id'
    hosts = Host.objects.all
    for h in hosts:
        id = h.get_id()
        h2 = Host.objects.get_by_id(id)
        if h.get_id() != h2.get_id():
            return False
    return True


if __name__ == '__main__':
    s = Host.objects.all
    for host in s:
        print host.get_effective_parents(recursive=False)
        continue
        print host['host_name']
        for i in host.get_effective_services():
            print "\t", i['service_description']
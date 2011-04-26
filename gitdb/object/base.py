# base.py
# Copyright (C) 2008, 2009 Michael Trier (mtrier@gmail.com) and contributors
#
# This module is part of GitPython and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php
from util import get_object_type_by_name
from gitdb.util import (
							hex_to_bin,
							bin_to_hex,
							dirname,
							basename, 
							LazyMixin, 
							join_path_native, 
							stream_copy
						)

from gitdb.typ import ObjectType
	
_assertion_msg_format = "Created object %r whose python type %r disagrees with the acutal git object type %r"

__all__ = ("Object", "IndexObject")

class Object(LazyMixin):
	"""Implements an Object which may be Blobs, Trees, Commits and Tags"""
	NULL_HEX_SHA = '0'*40
	NULL_BIN_SHA = '\0'*20
	
	TYPES = (ObjectType.blob, ObjectType.tree, ObjectType.commit, ObjectType.tag)
	__slots__ = ("odb", "binsha", "size" )
	
	type = None			# to be set by subclass
	type_id = None		# to be set by subclass
	
	def __init__(self, odb, binsha):
		"""Initialize an object by identifying it by its binary sha. 
		All keyword arguments will be set on demand if None.
		
		:param odb: repository this object is located in
			
		:param binsha: 20 byte SHA1"""
		super(Object,self).__init__()
		self.odb = odb
		self.binsha = binsha
		assert len(binsha) == 20, "Require 20 byte binary sha, got %r, len = %i" % (binsha, len(binsha))

	@classmethod
	def new(cls, odb, id):
		"""
		:return: New Object instance of a type appropriate to the object type behind 
			id. The id of the newly created object will be a binsha even though 
			the input id may have been a Reference or Rev-Spec
			
		:param id: reference, rev-spec, or hexsha
			
		:note: This cannot be a __new__ method as it would always call __init__
			with the input id which is not necessarily a binsha."""
		return odb.rev_parse(str(id))
		
	@classmethod
	def new_from_sha(cls, odb, sha1):
		"""
		:return: new object instance of a type appropriate to represent the given 
			binary sha1
		:param sha1: 20 byte binary sha1"""
		if sha1 == cls.NULL_BIN_SHA:
			# the NULL binsha is always the root commit
			return get_object_type_by_name('commit')(odb, sha1)
		#END handle special case
		oinfo = odb.info(sha1)
		inst = get_object_type_by_name(oinfo.type)(odb, oinfo.binsha)
		inst.size = oinfo.size
		return inst 
	
	def _set_cache_(self, attr):
		"""Retrieve object information"""
		if attr	 == "size":
			oinfo = self.odb.info(self.binsha)
			self.size = oinfo.size
			# assert oinfo.type == self.type, _assertion_msg_format % (self.binsha, oinfo.type, self.type)
		else:
			super(Object,self)._set_cache_(attr)
		
	def __eq__(self, other):
		""":return: True if the objects have the same SHA1"""
		return self.binsha == other.binsha
		
	def __ne__(self, other):
		""":return: True if the objects do not have the same SHA1 """
		return self.binsha != other.binsha
		
	def __hash__(self):
		""":return: Hash of our id allowing objects to be used in dicts and sets"""
		return hash(self.binsha)
		
	def __str__(self):
		""":return: string of our SHA1 as understood by all git commands"""
		return bin_to_hex(self.binsha)
		
	def __repr__(self):
		""":return: string with pythonic representation of our object"""
		return '<git.%s "%s">' % (self.__class__.__name__, self.hexsha)

	@property
	def hexsha(self):
		""":return: 40 byte hex version of our 20 byte binary sha"""
		return bin_to_hex(self.binsha)

	@property
	def data_stream(self):
		""" :return:  File Object compatible stream to the uncompressed raw data of the object
		:note: returned streams must be read in order"""
		return self.odb.stream(self.binsha)

	def stream_data(self, ostream):
		"""Writes our data directly to the given output stream
		:param ostream: File object compatible stream object.
		:return: self"""
		istream = self.odb.stream(self.binsha)
		stream_copy(istream, ostream)
		return self
		

class IndexObject(Object):
	"""Base for all objects that can be part of the index file , namely Tree, Blob and
	SubModule objects"""
	__slots__ = ("path", "mode")
	
	# for compatability with iterable lists
	_id_attribute_ = 'path'
	
	def __init__(self, odb, binsha, mode=None, path=None):
		"""Initialize a newly instanced IndexObject
		:param odb: is the object database we are located in
		:param binsha: 20 byte sha1
		:param mode: is the stat compatible file mode as int, use the stat module
			to evaluate the infomration
		:param path:
			is the path to the file in the file system, relative to the git repository root, i.e.
			file.ext or folder/other.ext
		:note:
			Path may not be set of the index object has been created directly as it cannot
			be retrieved without knowing the parent tree."""
		super(IndexObject, self).__init__(odb, binsha)
		if mode is not None:
			self.mode = mode
		if path is not None:
			self.path = path
	
	def __hash__(self):
		""":return:
			Hash of our path as index items are uniquely identifyable by path, not 
			by their data !"""
		return hash(self.path)
	
	def _set_cache_(self, attr):
		if attr in IndexObject.__slots__:
			# they cannot be retrieved lateron ( not without searching for them )
			raise AttributeError( "path and mode attributes must have been set during %s object creation" % type(self).__name__ )
		else:
			super(IndexObject, self)._set_cache_(attr)
		# END hanlde slot attribute
	
	@property
	def name(self):
		""":return: Name portion of the path, effectively being the basename"""
		return basename(self.path)
		
	@property
	def abspath(self):
		"""
		:return:
			Absolute path to this index object in the file system ( as opposed to the 
			.path field which is a path relative to the git repository ).
			
			The returned path will be native to the system and contains '\' on windows. """
		assert False, "Only works if repository is not bare - provide this check in an interface"
		return join_path_native(dirname(self.odb.root_path()), self.path)
		

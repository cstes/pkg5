#!/usr/bin/python
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright (c) 2007, 2011, Oracle and/or its affiliates. All rights reserved.
#

import M2Crypto as m2
import atexit
import copy
import datetime
import errno
import os
import platform
import shutil
import simplejson as json
import stat
import tempfile
import time
import urllib

from contextlib import contextmanager
from pkg.client import global_settings
logger = global_settings.logger

import pkg.actions
import pkg.catalog
import pkg.client.api_errors            as apx
import pkg.client.bootenv               as bootenv
import pkg.client.history               as history
import pkg.client.imageconfig           as imageconfig
import pkg.client.imageplan             as imageplan
import pkg.client.linkedimage           as li
import pkg.client.pkgdefs               as pkgdefs
import pkg.client.pkgplan               as pkgplan
import pkg.client.progress              as progress
import pkg.client.publisher             as publisher
import pkg.client.sigpolicy             as sigpolicy
import pkg.client.transport.transport   as transport
import pkg.config                       as cfg
import pkg.fmri
import pkg.lockfile                     as lockfile
import pkg.manifest                     as manifest
import pkg.misc                         as misc
import pkg.nrlock
import pkg.pkgsubprocess                as subprocess
import pkg.portable                     as portable
import pkg.server.catalog
import pkg.smf                          as smf
import pkg.version

from pkg.client.debugvalues import DebugValues
from pkg.client.imagetypes import IMG_USER, IMG_ENTIRE
from pkg.misc import EmptyI, EmptyDict

img_user_prefix = ".org.opensolaris,pkg"
img_root_prefix = "var/pkg"

IMG_PUB_DIR = "publisher"

class Image(object):
        """An Image object is a directory tree containing the laid-down contents
        of a self-consistent graph of Packages.

        An Image has a root path.

        An Image of type IMG_ENTIRE does not have a parent Image.  Other Image
        types must have a parent Image.  The external state of the parent Image
        must be accessible from the Image's context, or duplicated within the
        Image (IMG_PARTIAL for zones, for instance).

        The parent of a user Image can be a partial Image.  The parent of a
        partial Image must be an entire Image.

        An Image of type IMG_USER stores its external state at self.root +
        ".org.opensolaris,pkg".

        An Image of type IMG_ENTIRE or IMG_PARTIAL stores its external state at
        self.root + "/var/pkg".

        An Image needs to be able to have a different repository set than the
        system's root Image.

        For image format details, see section 5.3 of doc/on-disk-format.txt
        in the pkg(5) gate.
        """

        # Class constants
        CURRENT_VERSION = 4
        IMG_CATALOG_KNOWN = "known"
        IMG_CATALOG_INSTALLED = "installed"

        # This is a transitory state used for temporary package sources to
        # indicate that the package entry should be removed if it does not
        # also have PKG_STATE_INSTALLED.  This state must not be written
        # to disk.
        PKG_STATE_ALT_SOURCE = 99

        # Please note that the values of these PKG_STATE constants should not
        # be changed as it would invalidate existing catalog data stored in the
        # image.  This means that if a constant is removed, the values of the
        # other constants should not change, etc.

        # This state indicates that a package is present in a repository
        # catalog.
        PKG_STATE_KNOWN = 0

        # This is a transitory state used to indicate that a package is no
        # longer present in a repository catalog; it is only used to clear
        # PKG_STATE_KNOWN.
        PKG_STATE_UNKNOWN = 1

        # This state indicates that a package is installed.
        PKG_STATE_INSTALLED = 2

        # This is a transitory state used to indicate that a package is no
        # longer installed; it is only used to clear PKG_STATE_INSTALLED.
        PKG_STATE_UNINSTALLED = 3
        PKG_STATE_UPGRADABLE = 4

        # These states are used to indicate the package's related catalog
        # version.  This is helpful to consumers of the catalog data so that
        # they can be aware of what metadata may not immediately available
        # (require manifest retrieval) based on the catalog version.
        PKG_STATE_V0 = 6
        PKG_STATE_V1 = 7

        PKG_STATE_OBSOLETE = 8
        PKG_STATE_RENAMED = 9

        # These states are used to indicate why a package was rejected and
        # is not available for packaging operations.
        PKG_STATE_UNSUPPORTED = 10      # Package contains invalid or
                                        # unsupported metadata.

        def __init__(self, root, user_provided_dir=False, progtrack=None,
            should_exist=True, imgtype=None, force=False,
            augment_ta_from_parent_image=True, allow_ondisk_upgrade=None,
            allow_ambiguous=False, props=misc.EmptyDict, cmdpath=None,
            runid=-1):

                if should_exist:
                        assert(imgtype is None)
                        assert(not force)
                else:
                        assert(imgtype is not None)

                # Alternate package sources.
                self.__alt_pkg_pub_map = None
                self.__alt_pubs = None
                self.__alt_known_cat = None
                self.__alt_pkg_sources_loaded = False

                if (runid < 0):
                        runid = os.getpid()
                self.runid = runid

                # Determine identity of client executable if appropriate.
                if cmdpath == None:
                        cmdpath = misc.api_cmdpath()
                self.cmdpath = cmdpath

                if self.cmdpath != None:
                        self.__cmddir = os.path.dirname(cmdpath)

                # prevent brokeness in the test suite
                if self.cmdpath and \
                    "PKG_NO_RUNPY_CMDPATH" in os.environ and \
                    self.cmdpath.endswith(os.sep + "run.py"):
                        raise RuntimeError, """
An Image object was allocated from within ipkg test suite and
cmdpath was not explicitly overridden.  Please make sure to
explicitly set cmdpath when allocating an Image object, or
override cmdpath when allocating an Image object by setting PKG_CMDPATH
in the environment or by setting simulate_cmdpath in DebugValues."""

                self.linked = None

                # Indicates whether automatic image format upgrades of the
                # on-disk format are allowed.
                self.allow_ondisk_upgrade = allow_ondisk_upgrade
                self.allow_ambiguous = allow_ambiguous
                self.__upgraded = False

                # Must happen after upgraded assignment.
                self.__init_catalogs()

                self.attrs = { "Build-Release": "5.11" } # XXX real data needed
                self.blocking_locks = False
                self.cfg = None
                self.history = history.History()
                self.imageplan = None
                self.img_prefix = None
                self.imgdir = None
                self.index_dir = None
                self.plandir = None
                self.root = root
                self.version = -1

                # Can have multiple read cache dirs...
                self.__read_cache_dirs = []

                # ...but only one global write cache dir and incoming write dir.
                self.__write_cache_dir = None
                self.__user_cache_dir = None
                self._incoming_cache_dir = None

                # Set if write_cache is actually a tree like /var/pkg/publisher
                # instead of a flat cache.
                self.__write_cache_root = None

                self.__lock = pkg.nrlock.NRLock()
                self.__lockfile = None
                self.__sig_policy = None
                self.__trust_anchors = None

                # cache for presence of boot-archive
                self.__boot_archive = None

                # When users and groups are added before their database files
                # have been installed, the actions store them temporarily in the
                # image, in these members.
                self._users = set()
                self._groups = set()
                self._usersbyname = {}
                self._groupsbyname = {}

                # Set of pkg stems being avoided
                self.__avoid_set = None
                self.__avoid_set_altered = False

                # set of pkg stems subject to group
                # dependency but removed because obsolete
                self.__group_obsolete = None

                self.__property_overrides = { "property": props }

                # Transport operations for this image
                self.transport = transport.Transport(
                    transport.ImageTransportCfg(self))

                self.linked = li.LinkedImage(self)

                if should_exist:
                        self.find_root(self.root, user_provided_dir,
                            progtrack)
                else:
                        if not force and self.image_type(self.root) != None:
                                raise apx.ImageAlreadyExists(self.root)
                        if not force and os.path.exists(self.root):
                                # ignore .zfs snapdir if it's present
                                snapdir = os.path.join(self.root, ".zfs")
                                listdir = set(os.listdir(self.root))
                                if os.path.isdir(snapdir):
                                        listdir -= set([".zfs"])
                                if len(listdir) > 0:
                                        raise apx.CreatingImageInNonEmptyDir(
                                            self.root)
                        self.__set_dirs(root=self.root, imgtype=imgtype,
                            progtrack=progtrack, purge=True)

                # right now we don't explicitly set dir/file modes everywhere;
                # set umask to proper value to prevent problems w/ overly
                # locked down umask.
                os.umask(0022)

                self.augment_ta_from_parent_image = augment_ta_from_parent_image

        @staticmethod
        def alloc(*args, **kwargs):
                return Image(*args, **kwargs)

        def __catalog_loaded(self, name):
                """Returns a boolean value indicating whether the named catalog
                has already been loaded.  This is intended to be used as an
                optimization function to determine which catalog to request."""

                return name in self.__catalogs

        def __init_catalogs(self):
                """Initializes default catalog state.  Actual data is provided
                on demand via get_catalog()"""

                if self.__upgraded and self.version < 3:
                        # Ignore request; transformed catalog data only exists
                        # in memory and can't be reloaded from disk.
                        return

                # This is used to cache image catalogs.
                self.__catalogs = {}
                self.__alt_pkg_sources_loaded = False

        @property
        def signature_policy(self):
                """Returns the signature policy for this image."""

                if self.__sig_policy is not None:
                        return self.__sig_policy
                txt = self.cfg.get_policy_str(imageconfig.SIGNATURE_POLICY)
                names = self.cfg.get_property("property",
                    "signature-required-names")
                self.__sig_policy = sigpolicy.Policy.policy_factory(txt, names)
                return self.__sig_policy

        @property
        def trust_anchors(self):
                """Return a dictionary mapping subject hashes for certificates
                this image trusts to those certs.  The image trusts those
                trust anchors in its trust_anchor_dir and those in the from
                which pkg was run."""

                if self.__trust_anchors is not None:
                        return self.__trust_anchors

                user_set_ta_loc = True
                rel_dir = self.get_property("trust-anchor-directory")
                if rel_dir[0] == "/":
                        rel_dir = rel_dir[1:]
                trust_anchor_loc = os.path.join(self.root, rel_dir)
                loc_is_dir = os.path.isdir(trust_anchor_loc)
                pkg_trust_anchors = {}
                if self.__cmddir and self.augment_ta_from_parent_image:
                        pkg_trust_anchors = Image(self.__cmddir,
                            augment_ta_from_parent_image=False,
                            allow_ambiguous=True,
                            cmdpath=self.cmdpath).trust_anchors
                if not loc_is_dir and os.path.exists(trust_anchor_loc):
                        raise apx.InvalidPropertyValue(_("The trust "
                            "anchors for the image were expected to be found "
                            "in %s, but that is not a directory.  Please set "
                            "the image property 'trust-anchor-directory' to "
                            "the correct path.") % trust_anchor_loc)
                self.__trust_anchors = {}
                if loc_is_dir:
                        for fn in os.listdir(trust_anchor_loc):
                                pth = os.path.join(trust_anchor_loc, fn)
                                if os.path.islink(pth):
                                        continue
                                trusted_ca = m2.X509.load_cert(pth)
                                # M2Crypto's subject hash doesn't match
                                # openssl's subject hash so recompute it so all
                                # hashes are in the same universe.
                                s = trusted_ca.get_subject().as_hash()
                                self.__trust_anchors.setdefault(s, [])
                                self.__trust_anchors[s].append(trusted_ca)
                for s in pkg_trust_anchors:
                        if s not in self.__trust_anchors:
                                self.__trust_anchors[s] = pkg_trust_anchors[s]
                return self.__trust_anchors

        @property
        def locked(self):
                """Returns a boolean value indicating whether the image is
                currently locked."""

                return self.__lock and self.__lock.locked

        @contextmanager
        def locked_op(self, op, allow_unprivileged=False, new_history_op=True):
                """Helper method for executing an image-modifying operation
                that needs locking.  It automatically handles calling
                log_operation_start and log_operation_end by default.  Locking
                behaviour is controlled by the blocking_locks image property.

                'allow_unprivileged' is an optional boolean value indicating
                that permissions-related exceptions should be ignored when
                attempting to obtain the lock as the related operation will
                still work correctly even though the image cannot (presumably)
                be modified.

                'new_history_op' indicates whether we should handle history
                operations.
                """

                error = None
                self.lock(allow_unprivileged=allow_unprivileged)
                try:
                        be_name, be_uuid = \
                            bootenv.BootEnv.get_be_name(self.root)
                        if new_history_op:
                                self.history.log_operation_start(op,
                                    be_name=be_name, be_uuid=be_uuid)
                        yield
                except apx.ImageLockedError, e:
                        # Don't unlock the image if the call failed to
                        # get the lock.
                        error = e
                        raise
                except Exception, e:
                        error = e
                        self.unlock()
                        raise
                else:
                        self.unlock()
                finally:
                        if new_history_op:
                                self.history.log_operation_end(error=error)

        def lock(self, allow_unprivileged=False):
                """Locks the image in preparation for an image-modifying
                operation.  Raises an ImageLockedError exception on failure.
                Locking behaviour is controlled by the blocking_locks image
                property.

                'allow_unprivileged' is an optional boolean value indicating
                that permissions-related exceptions should be ignored when
                attempting to obtain the lock as the related operation will
                still work correctly even though the image cannot (presumably)
                be modified.
                """

                blocking = self.blocking_locks

                # First, attempt to obtain a thread lock.
                if not self.__lock.acquire(blocking=blocking):
                        raise apx.ImageLockedError()

                try:
                        # Attempt to obtain a file lock.
                        self.__lockfile.lock(blocking=blocking)
                except EnvironmentError, e:
                        exc = None
                        if e.errno == errno.ENOENT:
                                return
                        if e.errno == errno.EACCES:
                                exc = apx.PermissionsException(e.filename)
                        elif e.errno == errno.EROFS:
                                exc = apx.ReadOnlyFileSystemException(
                                    e.filename)
                        else:
                                self.__lock.release()
                                raise

                        if exc and not allow_unprivileged:
                                self.__lock.release()
                                raise exc
                except:
                        # If process lock fails, ensure thread lock is released.
                        self.__lock.release()
                        raise

        def unlock(self):
                """Unlocks the image."""

                try:
                        if self.__lockfile:
                                self.__lockfile.unlock()
                finally:
                        self.__lock.release()

        def image_type(self, d):
                """Returns the type of image at directory: d; or None"""
                rv = None

                def is_image(sub_d, prefix):
                        # First check for new image configuration file.
                        if os.path.isfile(os.path.join(sub_d, prefix,
                            "pkg5.image")):
                                # Regardless of directory structure, assume
                                # this is an image for now.
                                return True

                        if not os.path.isfile(os.path.join(sub_d, prefix,
                            "cfg_cache")):
                                # For older formats, if configuration is
                                # missing, this can't be an image.
                                return False

                        # Configuration exists, but for older formats,
                        # all of these directories have to exist.
                        for n in ("state", "pkg"):
                                if not os.path.isdir(os.path.join(sub_d, prefix,
                                    n)):
                                        return False

                        return True

                if os.path.isdir(os.path.join(d, img_user_prefix)) and \
                    is_image(d, img_user_prefix):
                        rv = IMG_USER
                elif os.path.isdir(os.path.join(d, img_root_prefix)) and \
                    is_image(d, img_root_prefix):
                        rv = IMG_ENTIRE
                return rv

        def find_root(self, d, exact_match=False, progtrack=None):
                # Ascend from the given directory d to find first
                # encountered image.  If exact_match is true, if the
                # image found doesn't match startd, raise an
                # ImageNotFoundException.

                startd = d
                # eliminate problem if relative path such as "." is passed in
                d = os.path.realpath(d)

                while True:
                        imgtype = self.image_type(d)
                        if imgtype in (IMG_USER, IMG_ENTIRE):
                                if exact_match and \
                                    os.path.realpath(startd) != \
                                    os.path.realpath(d):
                                        raise apx.ImageNotFoundException(
                                            exact_match, startd, d)
                                live_root = misc.liveroot()
                                if not exact_match and d != live_root and \
                                    not self.allow_ambiguous and \
                                    portable.osname == "sunos":
                                        # On Solaris, consider an image found
                                        # somewhere other than the live root an
                                        # an error if an exact match wasn't
                                        # requested.  (This prevents accidental
                                        # use of nested images.) It is not
                                        # desirable to do this on other
                                        # platforms as non-root images are the
                                        # norm.
                                        raise apx.ImageLocationAmbiguous(d,
                                            live_root=live_root)
                                self.__set_dirs(imgtype=imgtype, root=d,
                                    startd=startd, progtrack=progtrack)
                                return

                        # XXX follow symlinks or not?
                        oldpath = d
                        d = os.path.normpath(os.path.join(d, os.path.pardir))

                        # Make sure we are making progress and aren't in an
                        # infinite loop.
                        #
                        # (XXX - Need to deal with symlinks here too)
                        if d == oldpath:
                                raise apx.ImageNotFoundException(
                                    exact_match, startd, d)

        def __load_config(self):
                """Load this image's cached configuration from the default
                location.  This function should not be called anywhere other
                than __set_dirs()."""

                # XXX Incomplete with respect to doc/image.txt description of
                # configuration.

                if self.root == None:
                        raise RuntimeError("self.root must be set")

                version = None
                if self.version > -1:
                        if self.version >= 3:
                                # Configuration version is currently 3
                                # for all v3 images and newer.
                                version = 3
                        else:
                                version = self.version

                self.cfg = imageconfig.ImageConfig(self.__cfgpathname,
                    self.root, version=version,
                    overrides=self.__property_overrides)

                if self.__upgraded:
                        self.cfg = imageconfig.BlendedConfig(self.cfg,
                            self.get_catalog(self.IMG_CATALOG_INSTALLED).\
                                get_package_counts_by_pub(),
                            self.imgdir, self.transport,
                            self.cfg.get_policy("use-system-repo"))

        def save_config(self):
                # First, create the image directories if they haven't been, so
                # the configuration file can be written.
                self.mkdirs()
                self.cfg.write()
                if self.is_liveroot() and \
                    smf.get_state(
                        "svc:/application/pkg/system-repository:default") in \
                    (smf.SMF_SVC_TMP_ENABLED, smf.SMF_SVC_ENABLED):
                        smf.refresh([
                            "svc:/application/pkg/system-repository:default"])

                # This ensures all old transport configuration is thrown away.
                self.transport = transport.Transport(
                    transport.ImageTransportCfg(self))

        def mkdirs(self, root=None, version=None):
                """Create any missing parts of the image's directory structure.

                'root' is an optional path to a directory to create the new
                image structure in.  If not provided, the current image
                directory is the default.

                'version' is an optional integer value indicating the version
                of the structure to create.  If not provided, the current image
                version is the default.
                """

                if not root:
                        root = self.imgdir
                if not version:
                        version = self.version

                if version == self.CURRENT_VERSION:
                        img_dirs = ["cache/index", "cache/publisher",
                            "cache/tmp", "gui_cache", "history", "license",
                            "lost+found", "publisher", "ssl", "state/installed",
                            "state/known"]
                else:
                        img_dirs = ["download", "file", "gui_cache", "history",
                            "index", "lost+found", "pkg", "publisher",
                            "state/installed", "state/known", "tmp"]

                for sd in img_dirs:
                        try:
                                misc.makedirs(os.path.join(root, sd))
                        except EnvironmentError, e:
                                raise apx._convert_error(e)

        def __set_dirs(self, imgtype, root, startd=None, progtrack=None,
            purge=False):
                # Ensure upgraded status is reset.
                self.__upgraded = False

                if not self.__allow_liveroot() and root == misc.liveroot():
                        if startd == None:
                                startd = root
                        raise RuntimeError, \
                           "Live root image access is disabled but was \
                           attempted.\nliveroot: %s\nimage path: %s" % \
                           (misc.liveroot(), startd)

                self.type = imgtype
                self.root = root
                if self.type == IMG_USER:
                        self.img_prefix = img_user_prefix
                else:
                        self.img_prefix = img_root_prefix

                # Use a new Transport object every time location is changed.
                self.transport = transport.Transport(
                    transport.ImageTransportCfg(self))

                # cleanup specified path
                if os.path.isdir(root):
                        cwd = os.getcwd()
                        os.chdir(root)
                        self.root = os.getcwd()
                        os.chdir(cwd)

                # If current image is locked, then it should be unlocked
                # and then relocked after the imgdir is changed.  This
                # ensures that alternate BE scenarios work.
                relock = self.imgdir and self.locked
                if relock:
                        self.unlock()

                # Must set imgdir first.
                self.imgdir = os.path.join(self.root, self.img_prefix)

                # Force a reset of version.
                self.version = -1

                # Assume version 4+ configuration location.
                self.__cfgpathname = os.path.join(self.imgdir, "pkg5.image")

                # In the case of initial image creation, purge is specified
                # to ensure that when an image is created over an existing
                # one, any old data is removed first.
                if purge and os.path.exists(self.imgdir):
                        for entry in os.listdir(self.imgdir):
                                if entry == "ssl":
                                        # Preserve certs and keys directory
                                        # as a special exception.
                                        continue
                                epath = os.path.join(self.imgdir, entry)
                                try:
                                        if os.path.isdir(epath):
                                                shutil.rmtree(epath)
                                        else:
                                                portable.remove(epath)
                                except EnvironmentError, e:
                                        raise apx._convert_error(e)
                elif not purge:
                        # Determine if the version 4 configuration file exists.
                        if not os.path.exists(self.__cfgpathname):
                                self.__cfgpathname = os.path.join(self.imgdir,
                                    "cfg_cache")

                # Load the image configuration.
                self.__load_config()

                if not purge:
                        try:
                                self.version = int(self.cfg.get_property("image",
                                    "version"))
                        except (cfg.PropertyConfigError, ValueError):
                                # If version couldn't be read from
                                # configuration, then allow fallback
                                # path below to set things right.
                                self.version = -1

                if self.version <= 0:
                        # If version doesn't exist, attempt to determine version
                        # based on structure.
                        pub_root = os.path.join(self.imgdir, IMG_PUB_DIR)
                        if purge:
                                # This is a new image.
                                self.version = self.CURRENT_VERSION
                        elif os.path.exists(pub_root):
                                cache_root = os.path.join(self.imgdir, "cache")
                                if os.path.exists(cache_root):
                                        # The image must be corrupted, as the
                                        # version should have been loaded from
                                        # configuration.  For now, raise an
                                        # exception.  In the future, this
                                        # behaviour should probably be optional
                                        # so that pkg fix or pkg verify can
                                        # still use the image.
                                        raise apx.UnsupportedImageError(
                                            self.root)
                                else:
                                        # Assume version 3 image.
                                        self.version = 3

                                # Reload image configuration again now that
                                # version has been determined so that property
                                # definitions match.
                                self.__load_config()
                        elif os.path.exists(os.path.join(self.imgdir,
                            "catalog")):
                                self.version = 2

                                # Reload image configuration again now that
                                # version has been determined so that property
                                # definitions match.
                                self.__load_config()
                        else:
                                # Format is too old or invalid.
                                raise apx.UnsupportedImageError(self.root)

                if self.version > self.CURRENT_VERSION or self.version < 2:
                        # Image is too new or too old.
                        raise apx.UnsupportedImageError(self.root)

                # Ensure image version matches determined one; this must
                # be set *after* the version checks above.
                self.cfg.set_property("image", "version", self.version)

                # Remaining dirs may now be set.
                if self.version == self.CURRENT_VERSION:
                        self.__tmpdir = os.path.join(self.imgdir, "cache",
                            "tmp")
                else:
                        self.__tmpdir = os.path.join(self.imgdir, "tmp")
                self._statedir = os.path.join(self.imgdir, "state")
                self.plandir = os.path.join(self.__tmpdir, "plan")
                self.update_index_dir()

                self.history.root_dir = self.imgdir
                self.__lockfile = lockfile.LockFile(os.path.join(self.imgdir,
                    "lock"), set_lockstr=lockfile.client_lock_set_str,
                    get_lockstr=lockfile.client_lock_get_str,
                    failure_exc=apx.ImageLockedError,
                    provide_mutex=False)

                if relock:
                        self.lock()

                # Setup cache directories.
                self.__read_cache_dirs = []
                self._incoming_cache_dir = None
                self.__user_cache_dir = None
                self.__write_cache_dir = None
                self.__write_cache_root = None
                # The user specified cache is used as an additional place to
                # read cache data from, but as the only place to store new
                # cache data.
                if "PKG_CACHEROOT" in os.environ:
                        # If set, cache is structured like /var/pkg/publisher.
                        # get_cachedirs() will build paths for each publisher's
                        # cache using this directory.
                        self.__user_cache_dir = os.path.normpath(
                            os.environ["PKG_CACHEROOT"])
                        self.__write_cache_root = self.__user_cache_dir
                elif "PKG_CACHEDIR" in os.environ:
                        # If set, cache is a flat structure that is used for
                        # all publishers.
                        self.__user_cache_dir = os.path.normpath(
                            os.environ["PKG_CACHEDIR"])
                        self.__write_cache_dir = self.__user_cache_dir
                        # Since the cache structure is flat, add it to the
                        # list of global read caches.
                        self.__read_cache_dirs.append(self.__user_cache_dir)
                if self.__user_cache_dir:
                        self._incoming_cache_dir = os.path.join(
                            self.__user_cache_dir,
                            "incoming-%d" % os.getpid())

                if self.version < 4:
                        self.__action_cache_dir = self.temporary_dir()
                else:
                        self.__action_cache_dir = os.path.join(self.imgdir,
                            "cache")

                if self.version < 4:
                        if not self.__user_cache_dir:
                                self.__write_cache_dir = os.path.join(
                                    self.imgdir, "download")
                                self._incoming_cache_dir = os.path.join(
                                    self.__write_cache_dir,
                                    "incoming-%d" % os.getpid())
                        self.__read_cache_dirs.append(os.path.normpath(
                            os.path.join(self.imgdir, "download")))
                elif not self._incoming_cache_dir:
                        # Only a global incoming cache exists for newer images.
                        self._incoming_cache_dir = os.path.join(self.imgdir,
                            "cache", "incoming-%d" % os.getpid())

                # Test if we have the permissions to create the cache
                # incoming directory in this hierarchy.  If not, we'll need to
                # move it somewhere else.
                try:
                        os.makedirs(self._incoming_cache_dir)
                except EnvironmentError, e:
                        if e.errno == errno.EACCES or e.errno == errno.EROFS:
                                self.__write_cache_dir = tempfile.mkdtemp(
                                    prefix="download-%d-" % os.getpid())
                                self._incoming_cache_dir = os.path.normpath(
                                    os.path.join(self.__write_cache_dir,
                                    "incoming-%d" % os.getpid()))
                                self.__read_cache_dirs.append(
                                    self.__write_cache_dir)
                                # There's no image cleanup hook, so we'll just
                                # remove this directory on process exit.
                                atexit.register(shutil.rmtree,
                                    self.__write_cache_dir, ignore_errors=True)
                else:
                        os.removedirs(self._incoming_cache_dir)

                # Forcibly discard image catalogs so they can be re-loaded
                # from the new location if they are already loaded.  This
                # also prevents scribbling on image state information in
                # the wrong location.
                self.__init_catalogs()

                # Upgrade the image's format if needed.
                self.update_format(allow_unprivileged=True,
                    progtrack=progtrack)

                # If we haven't loaded the system publisher configuration, do
                # that now.
                if isinstance(self.cfg, imageconfig.ImageConfig):
                        self.cfg = imageconfig.BlendedConfig(self.cfg,
                            self.get_catalog(self.IMG_CATALOG_INSTALLED).\
                                get_package_counts_by_pub(),
                            self.imgdir, self.transport,
                            self.cfg.get_policy("use-system-repo"))

                        # Check to see if any system publishers have been
                        # removed.  If they have, remove their metadata and
                        # rebuild the catalogs.
                        changed = False
                        for p in self.cfg.removed_pubs:
                                p.meta_root = self._get_publisher_meta_root(
                                    p.prefix)
                                try:
                                        self.remove_publisher_metadata(p,
                                            rebuild=False)
                                        changed = True
                                except apx.PermissionsException:
                                        pass
                        if changed:
                                self.__rebuild_image_catalogs()

                if purge:
                        # Configuration shouldn't be written again unless this
                        # is an image creation operation (hence the purge).
                        self.save_config()

                # Let the linked image subsystem know that root is moving
                self.linked._init_root()

                # load image avoid pkg set
                self.__avoid_set_load()

        def update_format(self, allow_unprivileged=False, progtrack=None):
                """Transform the existing image structure and its data to
                the newest format.  Callers are responsible for locking.

                'allow_unprivileged' is an optional boolean indicating
                whether a fallback to an in-memory only upgrade should
                be performed if a PermissionsException is encountered
                during the operation.

                'progtrack' is an optional ProgressTracker object.
                """

                if self.version == self.CURRENT_VERSION:
                        # Already upgraded.
                        self.__upgraded = True

                        # If pre-upgrade data still exists; fire off a
                        # process to dump it so execution can continue.
                        orig_root = self.imgdir + ".old"
                        nullf = open(os.devnull, "w")
                        if os.path.exists(orig_root):
                                # Ensure all output is discarded; it really
                                # doesn't matter if this succeeds.
                                subprocess.Popen("rm -rf %s" % orig_root,
                                    shell=True, stdout=nullf, stderr=nullf)
                        return False

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                # Not technically 'caching', but close enough ...
                progtrack.cache_catalogs_start()

                # Upgrade catalog data if needed.
                self.__upgrade_catalogs()

                # Data conversion finished.
                self.__upgraded = True

                # Determine if on-disk portion of the upgrade is allowed.
                if self.allow_ondisk_upgrade == False:
                        return True

                if self.allow_ondisk_upgrade is None and self.type != IMG_USER:
                        if not self.is_liveroot() and not self.is_zone():
                                # By default, don't update image format if it
                                # is not the live root, and is not for a zone.
                                self.allow_ondisk_upgrade = False
                                return True

                # The logic to perform the on-disk upgrade is in its own
                # function so that it can easily be wrapped with locking logic.
                with self.locked_op("update-format",
                    allow_unprivileged=allow_unprivileged):
                        self.__upgrade_image_format(progtrack,
                            allow_unprivileged=allow_unprivileged)

                progtrack.cache_catalogs_done()
                return True

        def __upgrade_catalogs(self):
                """Private helper function for update_format."""

                if self.version >= 3:
                        # Nothing to do.
                        return

                def installed_file_publisher(filepath):
                        """Find the pkg's installed file named by filepath.
                        Return the publisher that installed this package."""

                        f = file(filepath)
                        try:
                                flines = f.readlines()
                                version, pub = flines
                                version = version.strip()
                                pub = pub.strip()
                                f.close()
                        except ValueError:
                                # If ValueError occurs, the installed file is of
                                # a previous format.  For upgrades to work, it's
                                # necessary to assume that the package was
                                # installed from the highest ranked publisher.
                                # Here, the publisher is setup to record that.
                                if flines:
                                        pub = flines[0]
                                        pub = pub.strip()
                                        newpub = "%s_%s" % (
                                            pkg.fmri.PREF_PUB_PFX, pub)
                                else:
                                        newpub = "%s_%s" % (
                                            pkg.fmri.PREF_PUB_PFX,
                                            self.get_highest_ranked_publisher())
                                pub = newpub
                        assert pub
                        return pub

                # First, load the old package state information.
                installed_state_dir = "%s/state/installed" % self.imgdir

                # If the state directory structure has already been created,
                # loading information from it is fast.  The directory is
                # populated with files, named by their (url-encoded) FMRI,
                # which point to the "installed" file in the corresponding
                # directory under /var/pkg.
                installed = {}
                def add_installed_entry(f):
                        path = "%s/pkg/%s/installed" % \
                            (self.imgdir, f.get_dir_path())
                        pub = installed_file_publisher(path)
                        f.set_publisher(pub)
                        installed[f.pkg_name] = f

                for pl in os.listdir(installed_state_dir):
                        fmristr = "%s" % urllib.unquote(pl)
                        f = pkg.fmri.PkgFmri(fmristr)
                        add_installed_entry(f)

                # Create the new image catalogs.
                kcat = pkg.catalog.Catalog(batch_mode=True,
                    manifest_cb=self._manifest_cb, sign=False)
                icat = pkg.catalog.Catalog(batch_mode=True,
                    manifest_cb=self._manifest_cb, sign=False)

                # XXX For backwards compatibility, 'upgradability' of packages
                # is calculated and stored based on whether a given pkg stem
                # matches the newest version in the catalog.  This is quite
                # expensive (due to overhead), but at least the cost is
                # consolidated here.  This comparison is also cross-publisher,
                # as it used to be.
                newest = {}
                old_pub_cats = []
                for pub in self.gen_publishers():
                        try:
                                old_cat = pkg.server.catalog.ServerCatalog(
                                    pub.meta_root, read_only=True,
                                    publisher=pub.prefix)

                                old_pub_cats.append((pub, old_cat))
                                for f in old_cat.fmris():
                                        nver = newest.get(f.pkg_name, None)
                                        newest[f.pkg_name] = max(nver,
                                            f.version)

                        except EnvironmentError, e:
                                # If a catalog file is just missing, ignore it.
                                # If there's a worse error, make sure the user
                                # knows about it.
                                if e.errno != errno.ENOENT:
                                        raise

                # Next, load the existing catalog data and convert it.
                pub_cats = []
                for pub, old_cat in old_pub_cats:
                        new_cat = pub.catalog
                        new_cat.batch_mode = True
                        new_cat.sign = False
                        if new_cat.exists:
                                new_cat.destroy()

                        # First convert the old publisher catalog to
                        # the new format.
                        for f in old_cat.fmris():
                                new_cat.add_package(f)

                                # Now populate the image catalogs.
                                states = [self.PKG_STATE_KNOWN,
                                    self.PKG_STATE_V0]
                                mdata = { "states": states }
                                if f.version != newest[f.pkg_name]:
                                        states.append(self.PKG_STATE_UPGRADABLE)

                                inst_fmri = installed.get(f.pkg_name, None)
                                if inst_fmri and \
                                    inst_fmri.version == f.version and \
                                    pkg.fmri.is_same_publisher(f.publisher,
                                    inst_fmri.publisher):
                                        states.append(self.PKG_STATE_INSTALLED)
                                        if inst_fmri.preferred_publisher():
                                                # Strip the PREF_PUB_PFX.
                                                inst_fmri.set_publisher(
                                                    inst_fmri.get_publisher())
                                        icat.add_package(f, metadata=mdata)
                                        del installed[f.pkg_name]
                                kcat.add_package(f, metadata=mdata)

                        # Normally, the Catalog's attributes are automatically
                        # populated as a result of catalog operations.  But in
                        # this case, the new Catalog's attributes should match
                        # those of the old catalog.
                        old_lm = old_cat.last_modified()
                        if old_lm:
                                # Can be None for empty v0 catalogs.
                                old_lm = pkg.catalog.ts_to_datetime(old_lm)
                        new_cat.last_modified = old_lm
                        new_cat.version = 0

                        # Add to the list of catalogs to save.
                        new_cat.batch_mode = False
                        pub_cats.append(new_cat)

                # Discard the old catalog objects.
                old_pub_cats = None

                for f in installed.values():
                        # Any remaining FMRIs need to be added to all of the
                        # image catalogs.
                        states = [self.PKG_STATE_INSTALLED, self.PKG_STATE_V0]
                        mdata = { "states": states }
                        # This package may be installed from a publisher that
                        # is no longer known or has been disabled.
                        if f.pkg_name in newest and \
                            f.version != newest[f.pkg_name]:
                                states.append(self.PKG_STATE_UPGRADABLE)

                        if f.preferred_publisher():
                                # Strip the PREF_PUB_PFX.
                                f.set_publisher(f.get_publisher())

                        icat.add_package(f, metadata=mdata)
                        kcat.add_package(f, metadata=mdata)

                for cat in pub_cats + [kcat, icat]:
                        cat.finalize()

                # Cache converted catalogs so that operations can function as
                # expected if the on-disk format of the catalogs isn't upgraded.
                self.__catalogs[self.IMG_CATALOG_KNOWN] = kcat
                self.__catalogs[self.IMG_CATALOG_INSTALLED] = icat

        def __upgrade_image_format(self, progtrack, allow_unprivileged=False):
                """Private helper function for update_format."""

                try:
                        # Ensure Image directory structure is valid.
                        self.mkdirs()
                except apx.PermissionsException, e:
                        if not allow_unprivileged:
                                raise
                        # An unprivileged user is attempting to use the
                        # new client with an old image.  Since none of
                        # the changes can be saved, warn the user and
                        # then return.
                        #
                        # Raising an exception here would be a decidedly
                        # bad thing as it would disrupt find_root, etc.
                        return

                # This has to be done after the permissions check above.
                # First, create a new temporary root to store the converted
                # image metadata.
                tmp_root = self.imgdir + ".new"
                try:
                        shutil.rmtree(tmp_root)
                except EnvironmentError, e:
                        if e.errno in (errno.EROFS, errno.EPERM) and \
                            allow_unprivileged:
                                # Bail.
                                return
                        if e.errno != errno.ENOENT:
                                raise apx._convert_error(e)

                try:
                        self.mkdirs(root=tmp_root, version=self.CURRENT_VERSION)
                except apx.PermissionsException, e:
                        # Same handling needed as above; but not after this.
                        if not allow_unprivileged:
                                raise
                        return

                def linktree(src_root, dest_root):
                        if not os.path.exists(src_root):
                                # Nothing to do.
                                return

                        for entry in os.listdir(src_root):
                                src = os.path.join(src_root, entry)
                                dest = os.path.join(dest_root, entry)
                                if os.path.isdir(src):
                                        # Recurse into directory to link
                                        # its contents.
                                        misc.makedirs(dest)
                                        linktree(src, dest)
                                        continue
                                # Link source file into target dest.
                                assert os.path.isfile(src)
                                try:
                                        os.link(src, dest)
                                except EnvironmentError, e:
                                        raise apx._convert_error(e)

                # Next, link history data into place.
                linktree(self.history.path, os.path.join(tmp_root,
                    "history"))

                # Next, link index data into place.
                linktree(self.index_dir, os.path.join(tmp_root,
                    "cache", "index"))

                # Next, link ssl data into place.
                linktree(os.path.join(self.imgdir, "ssl"),
                    os.path.join(tmp_root, "ssl"))

                # Next, write state data into place.
                if self.version < 3:
                        # Image state and publisher metadata
                        tmp_state_root = os.path.join(tmp_root, "state")

                        # Update image catalog locations.
                        kcat = self.get_catalog(self.IMG_CATALOG_KNOWN)
                        icat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                        kcat.meta_root = os.path.join(tmp_state_root,
                            self.IMG_CATALOG_KNOWN)
                        icat.meta_root = os.path.join(tmp_state_root,
                            self.IMG_CATALOG_INSTALLED)

                        # Assume that since mkdirs succeeded that the remaining
                        # data can be saved and the image structure can be
                        # upgraded.  But first, attempt to save the image
                        # catalogs.
                        for cat in icat, kcat:
                                misc.makedirs(cat.meta_root)
                                cat.save()
                else:
                        # For version 3 and newer images, just link existing
                        # state information into place.
                        linktree(self._statedir, os.path.join(tmp_root,
                            "state"))

                # Reset each publisher's meta_root and ensure its complete
                # directory structure is intact.  Then either link in or
                # write out the metadata for each publisher.
                for pub in self.gen_publishers():
                        old_root = pub.meta_root
                        old_cat_root = pub.catalog_root
                        old_cert_root = pub.cert_root
                        pub.meta_root = os.path.join(tmp_root,
                            IMG_PUB_DIR, pub.prefix)
                        pub.create_meta_root()

                        if self.version < 3:
                                # Should be loaded in memory and transformed
                                # already, so just need to be written out.
                                pub.catalog.save()
                                continue

                        # Now link any catalog or cert files from the old root
                        # into the new root.
                        linktree(old_cat_root, pub.catalog_root)
                        linktree(old_cert_root, pub.cert_root)

                        # Finally, create a directory for the publisher's
                        # manifests to live in.
                        misc.makedirs(os.path.join(pub.meta_root, "pkg"))

                # Next, link licenses and manifests of installed packages into
                # new image dir.
                for pfmri in self.gen_installed_pkgs():
                        # Link licenses.
                        mdir = self.get_manifest_dir(pfmri)
                        for entry in os.listdir(mdir):
                                if not entry.startswith("license."):
                                        continue
                                src = os.path.join(mdir, entry)
                                if os.path.isdir(src):
                                        # Ignore broken licenses.
                                        continue

                                # For conversion, ensure destination link uses
                                # encoded license name to match how new image
                                # format stores licenses.
                                dest = os.path.join(tmp_root, "license",
                                    pfmri.get_dir_path(stemonly=True),
                                    urllib.quote(entry, ""))
                                misc.makedirs(os.path.dirname(dest))
                                try:
                                        os.link(src, dest)
                                except EnvironmentError, e:
                                        raise apx._convert_error(e)

                        # Link manifest.
                        src = self.get_manifest_path(pfmri)
                        dest = os.path.join(tmp_root, "publisher",
                            pfmri.publisher, "pkg", pfmri.get_dir_path())
                        misc.makedirs(os.path.dirname(dest))
                        try:
                                os.link(src, dest)
                        except EnvironmentError, e:
                                raise apx._convert_error(e)

                # Next, copy the old configuration into the new location using
                # the new name.  The configuration is copied instead of being
                # linked so that any changes to configuration as a result of
                # the upgrade won't be written into the old image directory.
                src = os.path.join(self.imgdir, "disabled_auth")
                if os.path.exists(src):
                        dest = os.path.join(tmp_root, "disabled_auth")
                        portable.copyfile(src, dest)

                src = self.cfg.target
                dest = os.path.join(tmp_root, "pkg5.image")
                try:
                        portable.copyfile(src, dest)
                except EnvironmentError, e:
                        raise apx._convert_error(e)

                # Update the new configuration's version information and then
                # write it out again.
                newcfg = imageconfig.ImageConfig(dest, tmp_root,
                    version=3, overrides={ "image": {
                    "version": self.CURRENT_VERSION } })
                newcfg._version = 3
                newcfg.write()

                # Now reload configuration and write again to configuration data
                # reflects updated version information.
                newcfg.reset()
                newcfg.write()

                # Finally, rename the old package metadata directory, then
                # rename the new one into place, and then reinitialize.  The
                # old data will be dumped during initialization.
                orig_root = self.imgdir + ".old"
                try:
                        portable.rename(self.imgdir, orig_root)
                        portable.rename(tmp_root, self.imgdir)

                        # /var/pkg/repo is renamed into place instead of being
                        # linked piece-by-piece for performance reasons.
                        # Crawling the entire tree structure of a repository is
                        # far slower than simply renaming the top level
                        # directory (since it often has thousands or millions
                        # of objects).
                        old_repo = os.path.join(orig_root, "repo")
                        if os.path.exists(old_repo):
                                new_repo = os.path.join(tmp_root, "repo")
                                portable.rename(old_repo, new_repo)
                except EnvironmentError, e:
                        raise apx._convert_error(e)
                self.find_root(self.root, exact_match=True, progtrack=progtrack)

        def create(self, pubs, facets=EmptyDict, is_zone=False,  progtrack=None,
            props=EmptyDict, refresh_allowed=True, variants=EmptyDict):
                """Creates a new image with the given attributes if it does not
                exist; should not be used with an existing image.

                'is_zone' is a boolean indicating whether the image is a zone.

                'pubs' is a list of Publisher objects to configure the image
                with.

                'refresh_allowed' is an optional boolean indicating that
                network operations (such as publisher data retrieval) are
                allowed.

                'progtrack' is an optional ProgressTracker object.

                'props' is an option dictionary mapping image property names to
                values.

                'variants' is an optional dictionary of variant names and
                values.

                'facets' is an optional dictionary of facet names and values.
                """

                for p in pubs:
                        p.meta_root = self._get_publisher_meta_root(p.prefix)
                        p.transport = self.transport

                # Override any initial configuration information.
                self.set_properties(props)

                # Start the operation.
                self.history.log_operation_start("image-create")

                # Determine and add the default variants for the image.
                if is_zone:
                        self.cfg.variants["variant.opensolaris.zone"] = \
                            "nonglobal"
                else:
                        self.cfg.variants["variant.opensolaris.zone"] = \
                            "global"

                self.cfg.variants["variant.arch"] = \
                    variants.get("variant.arch", platform.processor())

                # After setting up the default variants, add any overrides or
                # additional variants or facets specified.
                self.cfg.variants.update(variants)
                self.cfg.facets.update(facets)

                # Now everything is ready for publisher configuration.
                # Since multiple publishers are allowed, they are all
                # added at once without any publisher data retrieval.
                # A single retrieval is then performed afterwards, if
                # allowed, to minimize the amount of work the client
                # needs to perform.
                for p in pubs:
                        self.add_publisher(p, refresh_allowed=False,
                            progtrack=progtrack)

                if refresh_allowed:
                        self.refresh_publishers(progtrack=progtrack)
                else:
                        # initialize empty catalogs on disk
                        self.__rebuild_image_catalogs(progtrack=progtrack)

                self.cfg.set_property("property", "publisher-search-order",
                    [p.prefix for p in pubs])

                # Ensure publisher search order is written.
                self.save_config()

                self.history.log_operation_end()

        @staticmethod
        def __allow_liveroot():
                """Check if we're allowed to access the current live root
                image."""

                # if we're simulating a live root then allow access to it
                if DebugValues.get_value("simulate_live_root") or \
                    "PKG_LIVE_ROOT" in os.environ:
                        return True

                # check if the user disabled access to the live root
                if DebugValues.get_value("simulate_no_live_root"):
                        return False
                if "PKG_NO_LIVE_ROOT" in os.environ:
                        return False

                # by default allow access to the live root
                return True

        def is_liveroot(self):
                return bool(self.root == misc.liveroot())

        def is_zone(self):
                return self.cfg.variants["variant.opensolaris.zone"] == \
                    "nonglobal"

        def get_arch(self):
                return self.cfg.variants["variant.arch"]

        def has_boot_archive(self):
                """Returns True if a boot_archive is present in this image"""
                if self.__boot_archive is not None:
                        return self.__boot_archive

                for p in ["platform/i86pc/amd64/boot_archive",
                          "platform/i86pc/boot_archive",
                          "platform/sun4u/boot_archive",
                          "platform/sun4v/boot_archive"]:
                        if os.path.isfile(os.path.join(self.root, p)):
                                self.__boot_archive = True
                                break
                else:
                        self.__boot_archive = False
                return self.__boot_archive

        def get_ramdisk_filelist(self):
                """return the filelist... add the filelist so we rebuild
                boot archive if it changes... append trailing / to
                directories that are really there"""

                p = "boot/solaris/filelist.ramdisk"
                f = os.path.join(self.root, p)

                def addslash(path):
                        if os.path.isdir(os.path.join(self.root, path)):
                                return path + "/"
                        return path

                if not os.path.isfile(f):
                        return []

                return [ addslash(l.strip()) for l in file(f) ] + [p]

        def get_cachedirs(self):
                """Returns a list of tuples of the form (dir, readonly, pub)
                where 'dir' is the absolute path of the cache directory,
                'readonly' is a boolean indicating whether the cache can
                be written to, and 'pub' is the prefix of the publisher that
                the cache directory should be used for.  If 'pub' is None, the
                cache directory is intended for all publishers.
                """

                # Get all readonly cache directories.
                cdirs = [
                    (cdir, True, None)
                    for cdir in self.__read_cache_dirs
                ]

                # Get global write cache directory.
                if self.__write_cache_dir:
                        cdirs.append((self.__write_cache_dir, False, None))

                # For images newer than version 3, file data can be stored
                # in the publisher's file root.
                if self.version == self.CURRENT_VERSION:
                        for pub in self.gen_publishers(inc_disabled=True):
                                froot = os.path.join(pub.meta_root, "file")
                                readonly = False
                                if self.__write_cache_dir or \
                                    self.__write_cache_root:
                                        readonly = True
                                cdirs.append((froot, readonly, pub.prefix))

                                if self.__write_cache_root:
                                        # Cache is a tree structure like
                                        # /var/pkg/publisher.
                                        froot = os.path.join(
                                            self.__write_cache_root, pub.prefix,
                                            "file")
                                        cdirs.append((froot, False, pub.prefix))

                return cdirs

        def get_root(self):
                return self.root

        def get_last_modified(self):
                """Returns a UTC datetime object representing the time the
                image's state last changed or None if unknown."""

                # Always get last_modified time from known catalog.  It's
                # retrieved from the catalog itself since that is accurate
                # down to the micrsecond (as opposed to the filesystem which
                # has an OS-specific resolution).
                return self.__get_catalog(self.IMG_CATALOG_KNOWN).last_modified

        def gen_publishers(self, inc_disabled=False):
                if not self.cfg:
                        raise apx.ImageCfgEmptyError(self.root)

                alt_pubs = {}
                if self.__alt_pkg_pub_map:
                        alt_src_pubs = dict(
                            (p.prefix, p)
                            for p in self.__alt_pubs
                        )

                        for pfx in self.__alt_known_cat.publishers():
                                # Include alternate package source publishers
                                # in result, and temporarily enable any
                                # disabled publishers that already exist in
                                # the image configuration.
                                try:
                                        img_pub = self.cfg.publishers[pfx]

                                        if not img_pub.disabled:
                                                # No override needed.
                                                continue
                                        new_pub = copy.copy(img_pub)
                                        new_pub.disabled = False

                                        # Discard origins and mirrors to prevent
                                        # their accidental use.
                                        repo = new_pub.repository
                                        repo.reset_origins()
                                        repo.reset_mirrors()
                                except KeyError:
                                        new_pub = alt_src_pubs[pfx]

                                alt_pubs[pfx] = new_pub

                publishers = [
                    alt_pubs.get(p.prefix, p)
                    for p in self.cfg.publishers.values()
                ]
                publishers.extend((
                    p for p in alt_pubs.values()
                    if p not in publishers
                ))

                for pub in publishers:
                        # Prepare publishers for transport usage; this must be
                        # done each time so that information reflects current
                        # image state.  This is done whether or not the
                        # publisher is returned so that in-memory state is
                        # always current.
                        pub.meta_root = self._get_publisher_meta_root(
                            pub.prefix)
                        pub.transport = self.transport
                        if inc_disabled or not pub.disabled:
                                yield pub

        def get_publisher_ranks(self):
                """Return dictionary of configured + enabled publishers and
                unconfigured publishers which still have packages installed.

                Each entry contains a tuple of search order index starting at
                0, and a boolean indicating whether or not this publisher is
                "sticky", and a boolean indicating whether or not the
                publisher is enabled"""

                pubs = self.get_sorted_publishers(inc_disabled=False)
                ret = dict([
                    (pubs[i].prefix, (i, pubs[i].sticky, True))
                    for i in range(0, len(pubs))
                ])

                # Add any publishers for pkgs that are installed,
                # but have been deleted. These publishers are implicitly
                # not-sticky and disabled.
                for pub in self.get_installed_pubs():
                        i = len(ret)
                        ret.setdefault(pub, (i, False, False))
                return ret

        def get_highest_ranked_publisher(self):
                """Return the highest ranked publisher."""

                pubs = self.cfg.get_property("property",
                    "publisher-search-order")
                if pubs:
                        return self.get_publisher(prefix=pubs[0])
                for p in self.gen_publishers():
                        return p
                for p in self.get_installed_pubs():
                        return p
                return None

        def check_cert_validity(self):
                """Look through the publishers defined for the image.  Print
                a message and exit with an error if one of the certificates
                has expired.  If certificates are getting close to expiration,
                print a warning instead."""

                for p in self.gen_publishers():
                        r = p.repository
                        for uri in r.origins:
                                if uri.ssl_cert:
                                        misc.validate_ssl_cert(
                                            uri.ssl_cert,
                                            prefix=p.prefix, uri=uri)
                return True

        def has_publisher(self, prefix=None, alias=None):
                """Returns a boolean value indicating whether a publisher
                exists in the image configuration that matches the given
                prefix or alias."""
                for pub in self.gen_publishers(inc_disabled=True):
                        if prefix == pub.prefix or (alias and
                            alias == pub.alias):
                                return True
                return False

        def remove_publisher(self, prefix=None, alias=None, progtrack=None):
                """Removes the publisher with the matching identity from the
                image."""

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                with self.locked_op("remove-publisher"):
                        pub = self.get_publisher(prefix=prefix,
                            alias=alias)

                        self.cfg.remove_publisher(pub.prefix)
                        self.remove_publisher_metadata(pub, progtrack=progtrack)
                        self.save_config()

        def get_publishers(self, inc_disabled=True):
                """Return a dictionary of configured publishers.  This doesn't
                include unconfigured publishers which still have packages
                installed."""

                return dict(
                    (p.prefix, p)
                    for p in self.gen_publishers(inc_disabled=inc_disabled)
                )

        def get_sorted_publishers(self, inc_disabled=True):
                """Return a list of configured publishers sorted by rank.
                This doesn't include unconfigured publishers which still have
                packages installed."""

                d = self.get_publishers(inc_disabled=inc_disabled)
                names = self.cfg.get_property("property",
                    "publisher-search-order")

                #
                # If someone has been editing the config file we may have
                # unranked publishers.  Also, as publisher come and go via the
                # sysrepo we can end up with configured but unranked
                # publishers.  In either case just sort unranked publishers
                # alphabetically.
                #
                unranked = set(d) - set(names)
                ret = [
                    d[n]
                    for n in names
                    if n in d
                ] + [
                    d[n]
                    for n in sorted(unranked)
                ]
                return ret

        def get_publisher(self, prefix=None, alias=None, origin=None):
                for pub in self.gen_publishers(inc_disabled=True):
                        if prefix and prefix == pub.prefix:
                                return pub
                        elif alias and alias == pub.alias:
                                return pub
                        elif origin and pub.repository and \
                            pub.repository.has_origin(origin):
                                return pub
                raise apx.UnknownPublisher(max(prefix, alias, origin))

        def pub_search_before(self, being_moved, staying_put):
                """Moves publisher "being_moved" to before "staying_put"
                in search order.

                The caller is responsible for locking the image."""

                self.cfg.change_publisher_search_order(being_moved, staying_put,
                    after=False)

        def pub_search_after(self, being_moved, staying_put):
                """Moves publisher "being_moved" to after "staying_put"
                in search order.

                The caller is responsible for locking the image."""

                self.cfg.change_publisher_search_order(being_moved, staying_put,
                    after=True)

        def __apply_alt_pkg_sources(self, img_kcat):
                pkg_pub_map = self.__alt_pkg_pub_map
                if not pkg_pub_map or self.__alt_pkg_sources_loaded:
                        # No alternate sources to merge.
                        return

                # Temporarily merge the package metadata in the alternate
                # known package catalog for packages not listed in the
                # image's known catalog.
                def merge_check(alt_kcat, pfmri, new_entry):
                        states = new_entry["metadata"]["states"]
                        if self.PKG_STATE_INSTALLED in states:
                                # Not interesting; already installed.
                                return False, None
                        img_entry = img_kcat.get_entry(pfmri=pfmri)
                        if not img_entry is None:
                                # Already in image known catalog.
                                return False, None
                        return True, new_entry

                img_kcat.append(self.__alt_known_cat, cb=merge_check)
                img_kcat.finalize()

                self.__alt_pkg_sources_loaded = True
                self.transport.cfg.pkg_pub_map = self.__alt_pkg_pub_map
                self.transport.cfg.alt_pubs = self.__alt_pubs
                self.transport.cfg.reset_caches()

        def __cleanup_alt_pkg_certs(self):
                """Private helper function to cleanup package certificate
                information after use of temporary package data."""

                if not self.__alt_pubs:
                        return

                # Cleanup publisher cert information; any certs not retrieved
                # retrieved during temporary publisher use need to be expunged
                # from the image configuration.
                for pub in self.__alt_pubs:
                        try:
                                ipub = self.cfg.publishers[pub.prefix]
                        except KeyError:
                                # Nothing to do.
                                continue

        def set_alt_pkg_sources(self, alt_sources):
                """Specifies an alternate source of package metadata to be
                temporarily merged with image state so that it can be used
                as part of packaging operations."""

                if not alt_sources:
                        self.__init_catalogs()
                        self.__alt_pkg_pub_map = None
                        self.__alt_pubs = None
                        self.__alt_known_cat = None
                        self.__alt_pkg_sources_loaded = False
                        self.transport.cfg.pkg_pub_map = None
                        self.transport.cfg.alt_pubs = None
                        self.transport.cfg.reset_caches()
                        return
                elif self.__alt_pkg_sources_loaded:
                        # Ensure existing alternate package source data
                        # is not part of temporary image state.
                        self.__init_catalogs()

                pkg_pub_map, alt_pubs, alt_kcat, ignored = alt_sources
                self.__alt_pkg_pub_map = pkg_pub_map
                self.__alt_pubs = alt_pubs
                self.__alt_known_cat = alt_kcat

        def set_highest_ranked_publisher(self, prefix=None, alias=None,
            pub=None):
                """Sets the preferred publisher for packaging operations.

                'prefix' is an optional string value specifying the name of
                a publisher; ignored if 'pub' is provided.

                'alias' is an optional string value specifying the alias of
                a publisher; ignored if 'pub' is provided.

                'pub' is an optional Publisher object identifying the
                publisher to set as the preferred publisher.

                One of the above parameters must be provided.

                The caller is responsible for locking the image."""

                if not pub:
                        pub = self.get_publisher(prefix=prefix, alias=alias)
                if not self.cfg.allowed_to_move(pub):
                        raise apx.ModifyingSyspubException(_("Publisher '%s' "
                            "is a system publisher and cannot be moved.") % pub)

                pubs = self.get_sorted_publishers()
                relative = None
                for p in pubs:
                        # If we've gotten to the publisher we want to make
                        # highest ranked, then there's nothing to do because
                        # it's already as high as it can be.
                        if p == pub:
                                return
                        if self.cfg.allowed_to_move(p):
                                relative = p
                                break
                assert relative, "Expected %s to already be part of the " + \
                    "search order:%s" % (relative, ranks)
                self.cfg.change_publisher_search_order(pub.prefix,
                    relative.prefix, after=False)

        def set_property(self, prop_name, prop_value):
                with self.locked_op("set-property"):
                        self.cfg.set_property("property", prop_name,
                            prop_value)
                        self.save_config()

        def set_properties(self, properties):
                properties = { "property": properties }
                with self.locked_op("set-property"):
                        self.cfg.set_properties(properties)
                        self.save_config()

        def get_property(self, prop_name):
                return self.cfg.get_property("property", prop_name)

        def has_property(self, prop_name):
                try:
                        self.cfg.get_property("property", prop_name)
                        return True
                except cfg.ConfigError:
                        return False

        def delete_property(self, prop_name):
                with self.locked_op("unset-property"):
                        self.cfg.remove_property("property", prop_name)
                        self.save_config()

        def add_property_value(self, prop_name, prop_value):
                with self.locked_op("add-property-value"):
                        self.cfg.add_property_value("property", prop_name,
                            prop_value)
                        self.save_config()

        def remove_property_value(self, prop_name, prop_value):
                with self.locked_op("remove-property-value"):
                        self.cfg.remove_property_value("property", prop_name,
                            prop_value)
                        self.save_config()

        def destroy(self):
                """Destroys the image; image object should not be used
                afterwards."""

                if not self.imgdir or not os.path.exists(self.imgdir):
                        return

                if os.path.abspath(self.imgdir) == "/":
                        # Paranoia.
                        return

                try:
                        shutil.rmtree(self.imgdir)
                except EnvironmentError, e:
                        raise apx._convert_error(e)

        def properties(self):
                if not self.cfg:
                        raise apx.ImageCfgEmptyError(self.root)
                return self.cfg.get_index()["property"].keys()

        def add_publisher(self, pub, refresh_allowed=True, progtrack=None,
            approved_cas=EmptyI, revoked_cas=EmptyI, search_after=None,
            search_before=None, search_first=None, unset_cas=EmptyI):
                """Adds the provided publisher object to the image
                configuration.

                'refresh_allowed' is an optional, boolean value indicating
                whether the publisher's metadata should be retrieved when adding
                it to the image's configuration.

                'progtrack' is an optional ProgressTracker object."""

                with self.locked_op("add-publisher"):
                        return self.__add_publisher(pub,
                            refresh_allowed=refresh_allowed,
                            progtrack=progtrack, approved_cas=EmptyI,
                            revoked_cas=EmptyI, search_after=search_after,
                            search_before=search_before,
                            search_first=search_first, unset_cas=EmptyI)

        def __update_publisher_catalogs(self, pub, progtrack=None,
            refresh_allowed=True):
                # Ensure that if the publisher's meta directory already
                # exists for some reason that the data within is not
                # used.
                self.remove_publisher_metadata(pub, progtrack=progtrack,
                    rebuild=False)

                repo = pub.repository
                if refresh_allowed and repo.origins:
                        try:
                                # First, verify that the publisher has a
                                # valid pkg(5) repository.
                                self.transport.valid_publisher_test(pub)
                                pub.validate_config()
                                self.refresh_publishers(pubs=[pub],
                                    progtrack=progtrack)
                        except Exception, e:
                                # Remove the newly added publisher since
                                # it is invalid or the retrieval failed.
                                if not pub.sys_pub:
                                        self.cfg.remove_publisher(pub.prefix)
                                raise
                        except:
                                # Remove the newly added publisher since
                                # the retrieval failed.
                                if not pub.sys_pub:
                                        self.cfg.remove_publisher(pub.prefix)
                                raise

        def __add_publisher(self, pub, refresh_allowed=True, progtrack=None,
            approved_cas=EmptyI, revoked_cas=EmptyI, search_after=None,
            search_before=None, search_first=None, unset_cas=EmptyI):
                """Private version of add_publisher(); caller is responsible
                for locking."""

                assert (not search_after and not search_before) or \
                    (not search_after and not search_first) or \
                    (not search_before and not search_first)

                if self.version < self.CURRENT_VERSION:
                        raise apx.ImageFormatUpdateNeeded(self.root)

                for p in self.cfg.publishers.values():
                        if pub.prefix == p.prefix or \
                            pub.prefix == p.alias or \
                            pub.alias and (pub.alias == p.alias or
                            pub.alias == p.prefix):
                                raise apx.DuplicatePublisher(pub)

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                # Must assign this first before performing operations.
                pub.meta_root = self._get_publisher_meta_root(
                    pub.prefix)
                pub.transport = self.transport
                self.cfg.publishers[pub.prefix] = pub

                self.__update_publisher_catalogs(pub, progtrack=progtrack,
                    refresh_allowed=refresh_allowed)

                for ca in approved_cas:
                        try:
                                ca = os.path.abspath(ca)
                                fh = open(ca, "rb")
                                s = fh.read()
                                fh.close()
                        except EnvironmentError, e:
                                if e.errno == errno.ENOENT:
                                        raise apx.MissingFileArgumentException(
                                            ca)
                                raise apx._convert_error(e)
                        pub.approve_ca_cert(s, manual=True)

                for hsh in revoked_cas:
                        pub.revoke_ca_cert(hsh)

                for hsh in unset_cas:
                        pub.unset_ca_cert(hsh)

                if search_first:
                        self.set_highest_ranked_publisher(prefix=pub.prefix)
                elif search_before:
                        self.pub_search_before(pub.prefix, search_before)
                elif search_after:
                        self.pub_search_after(pub.prefix, search_after)

                # Only after success should the configuration be saved.
                self.save_config()

        def verify(self, fmri, progresstracker, **kwargs):
                """Generator that returns a tuple of the form (action, errors,
                warnings, info) if there are any error, warning, or other
                messages about an action contained within the specified
                package.  Where the returned messages are lists of strings
                indicating fatal problems, potential issues (that can be
                ignored), or extra information to be displayed respectively.

                'fmri' is the fmri of the package to verify.

                'progresstracker' is a ProgressTracker object.

                'kwargs' is a dict of additional keyword arguments to be passed
                to each action verification routine."""

                try:
                        pub = self.get_publisher(prefix=fmri.publisher)
                except apx.UnknownPublisher:
                        # Since user removed publisher, assume this is the same
                        # as if they had set signature-policy ignore for the
                        # publisher.
                        sig_pol = None
                else:
                        sig_pol = self.signature_policy.combine(
                            pub.signature_policy)

                manf = self.get_manifest(fmri, all_variants=True)
                sigs = list(manf.gen_actions_by_type("signature",
                    self.list_excludes()))
                if sig_pol and (sigs or sig_pol.name != "ignore"):
                        # Only perform signature verification logic if there are
                        # signatures or if signature-policy is not 'ignore'.
                        try:
                                # Signature verification must be done using all
                                # the actions from the manifest, not just the
                                # ones for this image's variants.
                                sig_pol.process_signatures(sigs,
                                    manf.gen_actions(), pub, self.trust_anchors)
                        except apx.SigningException, e:
                                e.pfmri = fmri
                                yield e.sig, [e], [], []
                        except apx.InvalidResourceLocation, e:
                                yield [], [e], [], []

                for act in manf.gen_actions(
                    self.list_excludes()):
                        errors, warnings, info = act.verify(self, pfmri=fmri,
                            **kwargs)
                        progresstracker.verify_add_progress(fmri)
                        actname = act.distinguished_name()
                        if errors:
                                progresstracker.verify_yield_error(actname,
                                    errors)
                        if warnings:
                                progresstracker.verify_yield_warning(actname,
                                    warnings)
                        if info:
                                progresstracker.verify_yield_info(actname,
                                    info)
                        if errors or warnings or info:
                                yield act, errors, warnings, info

        def image_config_update(self, new_variants, new_facets):
                """update variants in image config"""

                if new_variants is not None:
                        self.cfg.variants.update(new_variants)
                if new_facets is not None:
                        self.cfg.facets = new_facets
                self.cfg.write()

        def repair(self, *args, **kwargs):
                """Repair any actions in the fmri that failed a verify."""

                # prune off any new_history_op keyword argument, used for
                # locked_op(), but not for __repair()
                need_history_op = kwargs.pop("new_history_op", True)

                with self.locked_op("fix", new_history_op=need_history_op):
                        try:
                                return self.__repair(*args, **kwargs)
                        except apx.ActionExecutionError, e:
                                raise
                        except pkg.actions.ActionError, e:
                                raise apx.InvalidPackageErrors([e])

        def __repair(self, repairs, progtrack, accept=False,
            show_licenses=False):
                """Private repair method; caller is responsible for locking."""

                if self.version < self.CURRENT_VERSION:
                        raise apx.ImageFormatUpdateNeeded(self.root)

                ilm = self.get_last_modified()

                # Allow garbage collection of previous plan.
                self.imageplan = None

                reason = "The following packages needed to be repaired:\n    %s"
                self.history.operation_start_state = \
                    reason % "\n    ".join(str(fmri)
                    for fmri, failed in repairs)

                # XXX: This (lambda x: False) is temporary until we move pkg fix
                # into the api and can actually use the
                # api::__check_cancel() function.
                pps = []
                for fmri, actions in repairs:
                        logger.info("Repairing: %-50s" % fmri.get_pkg_stem())
                        m = self.get_manifest(fmri)
                        pp = pkgplan.PkgPlan(self, progtrack, lambda: False)
                        pp.propose_repair(fmri, m, actions)
                        pp.evaluate(self.list_excludes(), self.list_excludes())
                        pps.append(pp)

                ip = imageplan.ImagePlan(self, progtrack, lambda: False)
                ip._image_lm = ilm
                ip._planned_op = ip.PLANNED_FIX
                self.imageplan = ip

                ip.update_index = False
                ip.state = imageplan.EVALUATED_PKGS
                progtrack.evaluate_start()

                # Always start with most current (on-disk) state information.
                self.__init_catalogs()

                ip.pkg_plans = pps

                ip.evaluate()
                if ip.reboot_needed() and self.is_liveroot():
                        raise apx.RebootNeededOnLiveImageException()

                logger.info("\n")
                for pp in ip.pkg_plans:
                        for lic, entry in pp.get_licenses():
                                dest = entry["dest"]
                                lic = dest.attrs["license"]
                                if show_licenses or dest.must_display:
                                        # Display license if required.
                                        logger.info("-" * 60)
                                        logger.info(_("Package: %s") % \
                                            pp.destination_fmri)
                                        logger.info(_("License: %s\n") % lic)
                                        logger.info(dest.get_text(self,
                                            pp.destination_fmri))
                                        logger.info("\n")

                                # Mark license as having been displayed.
                                pp.set_license_status(lic, displayed=True)

                                if dest.must_accept and accept:
                                        # Mark license as accepted if
                                        # required and requested.
                                        pp.set_license_status(lic,
                                            accepted=accept)

                ip.preexecute()
                ip.execute()

                return True

        def has_manifest(self, pfmri):
                return os.path.exists(self.get_manifest_path(pfmri))

        def get_license_dir(self, pfmri):
                """Return path to package license directory."""
                if self.version == self.CURRENT_VERSION:
                        # Newer image format stores license files per-stem,
                        # instead of per-stem and version, so that transitions
                        # between package versions don't require redelivery
                        # of license files.
                        return os.path.join(self.imgdir, "license",
                            pfmri.get_dir_path(stemonly=True))
                # Older image formats store license files in the manifest cache
                # directory.
                return self.get_manifest_dir(pfmri)

        def __get_installed_pkg_publisher(self, pfmri):
                """Returns the publisher for the FMRI of an installed package
                or None if the package is not installed.
                """
                for f in self.gen_installed_pkgs():
                        if f.pkg_name == pfmri.pkg_name:
                                return f.publisher
                return None

        def get_manifest_dir(self, pfmri):
                """Return path to on-disk manifest cache directory."""
                if not pfmri.publisher:
                        # Needed for consumers such as search that don't provide
                        # publisher information.
                        pfmri = pfmri.copy()
                        pfmri.publisher = self.__get_installed_pkg_publisher(
                            pfmri)
                assert pfmri.publisher
                if self.version == self.CURRENT_VERSION:
                        root = self._get_publisher_cache_root(pfmri.publisher)
                else:
                        root = self.imgdir
                return os.path.join(root, "pkg", pfmri.get_dir_path())

        def get_manifest_path(self, pfmri):
                """Return path to on-disk manifest file."""
                if not pfmri.publisher:
                        # Needed for consumers such as search that don't provide
                        # publisher information.
                        pfmri = pfmri.copy()
                        pfmri.publisher = self.__get_installed_pkg_publisher(
                            pfmri)
                assert pfmri.publisher
                if self.version == self.CURRENT_VERSION:
                        root = os.path.join(self._get_publisher_meta_root(
                            pfmri.publisher))
                        return os.path.join(root, "pkg", pfmri.get_dir_path())
                return os.path.join(self.get_manifest_dir(pfmri),
                    "manifest")

        def __get_manifest(self, fmri, excludes=EmptyI, intent=None,
            alt_pub=None):
                """Find on-disk manifest and create in-memory Manifest
                object.... grab from server if needed"""

                try:
                        ret = manifest.FactoredManifest(fmri,
                            self.get_manifest_dir(fmri),
                            excludes=excludes,
                            pathname=self.get_manifest_path(fmri))

                        # if we have a intent string, let depot
                        # know for what we're using the cached manifest
                        if intent:
                                alt_repo = None
                                if alt_pub:
                                        alt_repo = alt_pub.repository
                                try:
                                        self.transport.touch_manifest(fmri,
                                            intent, alt_repo=alt_repo)
                                except (apx.UnknownPublisher,
                                    apx.TransportError):
                                        # It's not fatal if we can't find
                                        # or reach the publisher.
                                        pass
                except KeyError:
                        ret = self.transport.get_manifest(fmri, excludes,
                            intent, pub=alt_pub)
                return ret

        def get_manifest(self, fmri, all_variants=False, intent=None,
            alt_pub=None):
                """return manifest; uses cached version if available.
                all_variants controls whether manifest contains actions
                for all variants"""

                # Normally elide other arch variants, facets

                if all_variants:
                        excludes = EmptyI
                else:
                        excludes = [ self.cfg.variants.allow_action ]

                try:
                        m = self.__get_manifest(fmri, excludes=excludes,
                            intent=intent, alt_pub=alt_pub)
                except apx.ActionExecutionError, e:
                        raise
                except pkg.actions.ActionError, e:
                        raise apx.InvalidPackageErrors([e])

                return m

        def update_pkg_installed_state(self, pkg_pairs, progtrack):
                """Sets the recorded installed state of each package pair in
                'pkg_pairs'.  'pkg_pair' should be an iterable of tuples of
                the format (added, removed) where 'removed' is the FMRI of the
                package that was uninstalled, and 'added' is the package
                installed for the operation.  These pairs are representative of
                the destination and origin package for each part of the
                operation."""

                if self.version < self.CURRENT_VERSION:
                        raise apx.ImageFormatUpdateNeeded(self.root)

                kcat = self.get_catalog(self.IMG_CATALOG_KNOWN)
                icat = self.get_catalog(self.IMG_CATALOG_INSTALLED)

                added = set()
                removed = set()
                for add_pkg, rem_pkg in pkg_pairs:
                        if add_pkg == rem_pkg:
                                continue
                        if add_pkg:
                                added.add(add_pkg)
                        if rem_pkg:
                                removed.add(rem_pkg)

                combo = added.union(removed)
                progtrack.item_set_goal(_("Package State Update Phase"),
                    len(combo))

                for pfmri in combo:
                        entry = kcat.get_entry(pfmri)
                        mdata = entry.get("metadata", {})
                        states = set(mdata.get("states", set()))
                        if pfmri in removed:
                                icat.remove_package(pfmri)
                                states.discard(self.PKG_STATE_INSTALLED)

                        if pfmri in added:
                                states.add(self.PKG_STATE_INSTALLED)
                                if self.PKG_STATE_ALT_SOURCE in states:
                                        states.discard(
                                            self.PKG_STATE_UPGRADABLE)
                                        states.discard(
                                            self.PKG_STATE_ALT_SOURCE)
                                        states.discard(
                                            self.PKG_STATE_KNOWN)
                        elif self.PKG_STATE_KNOWN not in states:
                                # This entry is no longer available and has no
                                # meaningful state information, so should be
                                # discarded.
                                kcat.remove_package(pfmri)
                                progtrack.item_add_progress()
                                continue

                        if (self.PKG_STATE_INSTALLED in states and
                            self.PKG_STATE_UNINSTALLED in states) or (
                            self.PKG_STATE_KNOWN in states and
                            self.PKG_STATE_UNKNOWN in states):
                                raise apx.ImagePkgStateError(pfmri,
                                    states)

                        # Catalog format only supports lists.
                        mdata["states"] = list(states)

                        # Now record the package state.
                        kcat.update_entry(mdata, pfmri=pfmri)

                        # If the package is being marked as installed,
                        # then  it shouldn't already exist in the
                        # installed catalog and should be added.
                        if pfmri in added:
                                icat.append(kcat, pfmri=pfmri)

                        entry = mdata = states = None
                        progtrack.item_add_progress()
                progtrack.item_done()

                # Discard entries for alternate source packages that weren't
                # installed as part of the operation.
                if self.__alt_pkg_pub_map:
                        for pfmri in self.__alt_known_cat.fmris():
                                if pfmri in added:
                                        # Nothing to do.
                                        continue

                                entry = kcat.get_entry(pfmri)
                                if not entry:
                                        # The only reason that the entry should
                                        # not exist in the 'known' part is
                                        # because it was removed during the
                                        # operation.
                                        assert pfmri in removed
                                        continue

                                states = entry.get("metadata", {}).get("states",
                                    EmptyI)
                                if self.PKG_STATE_ALT_SOURCE in states:
                                        kcat.remove_package(pfmri)

                        # Now add the publishers of packages that were installed
                        # from temporary sources that did not previously exist
                        # to the image's configuration.  (But without any
                        # origins, sticky, and enabled.)
                        cfgpubs = set(self.cfg.publishers.keys())
                        instpubs = set(f.publisher for f in added)
                        altpubs = self.__alt_known_cat.publishers()

                        # List of publishers that need to be added is the
                        # intersection of installed and alternate minus
                        # the already configured.
                        newpubs = (instpubs & altpubs) - cfgpubs
                        for pfx in newpubs:
                                npub = publisher.Publisher(pfx,
                                    repository=publisher.Repository())
                                self.__add_publisher(npub,
                                    refresh_allowed=False)

                        # Ensure image configuration reflects new information.
                        self.__cleanup_alt_pkg_certs()
                        self.save_config()

                # Remove manifests of packages that were removed from the
                # system.  Some packages may have only had facets or
                # variants changed, so don't remove those.
                progtrack.item_set_goal(_("Package Cache Update Phase"),
                    len(removed))
                for pfmri in removed:
                        manifest.FactoredManifest.clear_cache(
                            self.get_manifest_dir(pfmri))
                        try:
                                portable.remove(self.get_manifest_path(pfmri))
                        except EnvironmentError, e:
                                if e.errno != errno.ENOENT:
                                        raise apx._convert_error(e)
                        progtrack.item_add_progress()
                progtrack.item_done()

                # Temporarily redirect the catalogs to a different location,
                # so that if the save is interrupted, the image won't be left
                # with invalid state, and then save them.
                tmp_state_root = self.temporary_dir()

                progtrack.item_set_goal(_("Image State Update Phase"), 2)
                try:
                        for cat, name in ((kcat, self.IMG_CATALOG_KNOWN),
                            (icat, self.IMG_CATALOG_INSTALLED)):
                                cpath = os.path.join(tmp_state_root, name)

                                # Must copy the old catalog data to the new
                                # destination as only changed files will be
                                # written.
                                shutil.copytree(cat.meta_root, cpath)
                                cat.meta_root = cpath
                                cat.finalize(pfmris=added)
                                cat.save()
                                progtrack.item_add_progress()

                        del cat, name
                        self.__init_catalogs()

                        # copy any other state files from current state
                        # dir into new state dir.
                        for p in os.listdir(self._statedir):
                                fp = os.path.join(self._statedir, p)
                                if os.path.isfile(fp):
                                        portable.copyfile(fp, os.path.join(tmp_state_root, p))

                        # Next, preserve the old installed state dir, rename the
                        # new one into place, and then remove the old one.
                        orig_state_root, ignored = self.salvage(self._statedir)
                        portable.rename(tmp_state_root, self._statedir)
                        shutil.rmtree(orig_state_root, True)
                except EnvironmentError, e:
                        # shutil.Error can contains a tuple of lists of errors.
                        # Some of the error entries may be a tuple others will
                        # be a string due to poor error handling in shutil.
                        if isinstance(e, shutil.Error) and \
                            type(e.args[0]) == list:
                                msg = ""
                                for elist in e.args:
                                        for entry in elist:
                                                if type(entry) == tuple:
                                                        msg += "%s\n" % \
                                                            entry[-1]
                                                else:
                                                        msg += "%s\n" % entry
                                raise apx.UnknownErrors(msg)
                        raise apx._convert_error(e)
                finally:
                        # Regardless of success, the following must happen.
                        self.__init_catalogs()
                        if os.path.exists(tmp_state_root):
                                shutil.rmtree(tmp_state_root, True)
                progtrack.item_done()

        def get_catalog(self, name):
                """Returns the requested image catalog.

                'name' must be one of the following image constants:
                    IMG_CATALOG_KNOWN
                        The known catalog contains all of packages that are
                        installed or available from a publisher's repository.

                    IMG_CATALOG_INSTALLED
                        The installed catalog is a subset of the 'known'
                        catalog that only contains installed packages."""

                if not self.imgdir:
                        raise RuntimeError("self.imgdir must be set")

                cat = None
                try:
                        cat = self.__catalogs[name]
                except KeyError:
                        pass


                if not cat:
                        cat = self.__get_catalog(name)
                        self.__catalogs[name] = cat

                if name == self.IMG_CATALOG_KNOWN:
                        # Apply alternate package source data every time that
                        # the known catalog is requested.
                        self.__apply_alt_pkg_sources(cat)

                return cat

        def _manifest_cb(self, cat, f):
                # Only allow lazy-load for packages from non-v1 sources.
                # Assume entries for other sources have all data
                # required in catalog.  This prevents manifest retrieval
                # for packages that don't have any related action data
                # in the catalog because they don't have any related
                # action data in their manifest.
                entry = cat.get_entry(f)
                states = entry["metadata"]["states"]
                if self.PKG_STATE_V1 not in states:
                        return self.get_manifest(f, all_variants=True)
                return

        def __get_catalog(self, name):
                """Private method to retrieve catalog; this bypasses the
                normal automatic caching (unless the image hasn't been
                upgraded yet)."""

                if self.__upgraded and self.version < 3:
                        # Assume the catalog is already cached in this case
                        # and can't be reloaded from disk as it doesn't exist
                        # on disk yet.
                        return self.__catalogs[name]

                croot = os.path.join(self._statedir, name)
                try:
                        os.makedirs(croot)
                except EnvironmentError, e:
                        if e.errno in (errno.EACCES, errno.EROFS):
                                # Allow operations to work for
                                # unprivileged users.
                                croot = None
                        elif e.errno != errno.EEXIST:
                                raise

                # batch_mode is set to True here as any operations that modify
                # the catalogs (add or remove entries) are only done during an
                # image upgrade or metadata refresh.  In both cases, the catalog
                # is resorted and finalized so this is always safe to use.
                cat = pkg.catalog.Catalog(batch_mode=True,
                    manifest_cb=self._manifest_cb, meta_root=croot, sign=False)
                return cat

        def __remove_catalogs(self):
                """Removes all image catalogs and their directories."""

                self.__init_catalogs()
                for name in (self.IMG_CATALOG_KNOWN,
                    self.IMG_CATALOG_INSTALLED):
                        shutil.rmtree(os.path.join(self._statedir, name))

        def get_version_installed(self, pfmri):
                """Returns an fmri of the installed package matching the
                package stem of the given fmri or None if no match is found."""

                cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                for ver, fmris in cat.fmris_by_version(pfmri.pkg_name):
                        return fmris[0]
                return None

        def has_version_installed(self, fmri):
                """Check that the version given in the FMRI or a successor is
                installed in the current image."""

                v = self.get_version_installed(fmri)

                if v and not fmri.publisher:
                        fmri.set_publisher(v.get_publisher_str())
                elif not fmri.publisher:
                        fmri.set_publisher(self.get_highest_ranked_publisher(),
                            True)

                if v and v.is_successor(fmri):
                        return True
                return False

        def get_pkg_repo(self, pfmri):
                """Returns the repository object containing the origins that
                should be used to retrieve the specified package or None if
                it can be retrieved from all sources or is not a known package.
                """

                assert pfmri.publisher
                cat = self.get_catalog(self.IMG_CATALOG_KNOWN)
                entry = cat.get_entry(pfmri)
                if entry is None:
                        # Package not known.
                        return

                try:
                        slist = entry["metadata"]["sources"]
                except KeyError:
                        # Can be retrieved from any source.
                        return
                else:
                        if not slist:
                                # Can be retrieved from any source.
                                return

                pub = self.get_publisher(prefix=pfmri.publisher)
                repo = copy.copy(pub.repository)
                norigins = [
                    o for o in repo.origins
                    if o.uri in slist
                ]

                if not norigins:
                        # Known sources don't match configured; return so that
                        # caller can fallback to default behaviour.
                        return

                repo.origins = norigins
                return repo

        def get_pkg_state(self, pfmri):
                """Returns the list of states a package is in for this image."""

                cat = self.get_catalog(self.IMG_CATALOG_KNOWN)
                entry = cat.get_entry(pfmri)
                if entry is None:
                        return []
                return entry["metadata"]["states"]

        def is_pkg_installed(self, pfmri):
                """Returns a boolean value indicating whether the specified
                package is installed."""

                # Avoid loading the installed catalog if the known catalog
                # is already loaded.  This is safe since the installed
                # catalog is a subset of the known, and a specific entry
                # is being retrieved.
                if not self.__catalog_loaded(self.IMG_CATALOG_KNOWN):
                        cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                else:
                        cat = self.get_catalog(self.IMG_CATALOG_KNOWN)

                entry = cat.get_entry(pfmri)
                if entry is None:
                        return False
                states = entry["metadata"]["states"]
                return self.PKG_STATE_INSTALLED in states

        def list_excludes(self, new_variants=None, new_facets=None):
                """Generate a list of callables that each return True if an
                action is to be included in the image using the currently
                defined variants & facets for the image, or an updated set if
                new_variants or new_facets are specified."""

                if new_variants:
                        new_vars = self.cfg.variants.copy()
                        new_vars.update(new_variants)
                        var_call = new_vars.allow_action
                else:
                        var_call = self.cfg.variants.allow_action
                if new_facets:
                        fac_call = new_facets.allow_action
                else:
                        fac_call = self.cfg.facets.allow_action

                return [var_call, fac_call]

        def get_variants(self):
                """ return a copy of the current image variants"""
                return self.cfg.variants.copy()

        def get_facets(self):
                """ Return a copy of the current image facets"""
                return self.cfg.facets.copy()

        def __rebuild_image_catalogs(self, progtrack=None):
                """Rebuilds the image catalogs based on the available publisher
                catalogs."""

                if self.version < 3:
                        raise apx.ImageFormatUpdateNeeded(self.root)

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                progtrack.cache_catalogs_start()

                publist = list(self.gen_publishers())

                be_name, be_uuid = bootenv.BootEnv.get_be_name(self.root)
                self.history.log_operation_start("rebuild-image-catalogs",
                    be_name=be_name, be_uuid=be_uuid)

                # Mark all operations as occurring at this time.
                op_time = datetime.datetime.utcnow()

                # The image catalogs need to be updated, but this is a bit
                # tricky as previously known packages must remain known even
                # if PKG_STATE_KNOWN is no longer true if any other state
                # information is present.  This is to allow freezing, etc. of
                # package states on a permanent basis even if the package is
                # no longer available from a publisher repository.  However,
                # this is only True of installed packages.
                old_icat = self.get_catalog(self.IMG_CATALOG_INSTALLED)

                # batch_mode is set to True here since without it, catalog
                # population time is almost doubled (since the catalog is
                # re-sorted and stats are generated for every operation).
                # In addition, the new catalog is first created in a new
                # temporary directory so that it can be moved into place
                # at the very end of this process (to minimize the chance
                # that failure or interruption will cause the image to be
                # left in an inconsistent state).
                tmp_state_root = self.temporary_dir()

                # Copy any regular files placed in the state directory
                for p in os.listdir(self._statedir):
                        fp = os.path.join(self._statedir, p)
                        if os.path.isfile(fp):
                                portable.copyfile(fp, os.path.join(tmp_state_root, p))

                kcat = pkg.catalog.Catalog(batch_mode=True,
                    meta_root=os.path.join(tmp_state_root,
                    self.IMG_CATALOG_KNOWN), sign=False)

                # XXX if any of the below fails for any reason, the old 'known'
                # catalog needs to be re-loaded so the client is in a consistent
                # state.

                # All enabled publisher catalogs must be processed.
                pub_cats = [(pub.prefix, pub.catalog) for pub in publist]

                # XXX For backwards compatibility, 'upgradability' of packages
                # is calculated and stored based on whether a given pkg stem
                # matches the newest version in the catalog.  This is quite
                # expensive (due to overhead), but at least the cost is
                # consolidated here.  This comparison is also cross-publisher,
                # as it used to be.  In the future, it could likely be improved
                # by usage of the SAT solver.
                newest = {}
                for pfx, cat in [(None, old_icat)] + pub_cats:
                        for f in cat.fmris(last=True, pubs=[pfx]):
                                nver, snver = newest.get(f.pkg_name, (None,
                                    None))
                                if f.version > nver:
                                        newest[f.pkg_name] = (f.version,
                                            str(f.version))

                # Next, copy all of the entries for the catalog parts that
                # currently exist into the image 'known' catalog.

                # Iterator for source parts.
                sparts = (
                   (pfx, cat, name, cat.get_part(name, must_exist=True))
                   for pfx, cat in pub_cats
                   for name in cat.parts
                )

                # Build list of installed packages based on actual state
                # information just in case there is a state issue from an
                # older client.
                inst_stems = {}
                for t, entry in old_icat.tuple_entries():
                        states = entry["metadata"]["states"]
                        if self.PKG_STATE_INSTALLED not in states:
                                continue
                        pub, stem, ver = t
                        inst_stems.setdefault(pub, {})
                        inst_stems[pub].setdefault(stem, {})
                        inst_stems[pub][stem][ver] = False

                # Create the new installed catalog in a temporary location.
                icat = pkg.catalog.Catalog(batch_mode=True,
                    meta_root=os.path.join(tmp_state_root,
                    self.IMG_CATALOG_INSTALLED), sign=False)

                excludes = self.list_excludes()
                for pfx, cat, name, spart in sparts:
                        # 'spart' is the source part.
                        if spart is None:
                                # Client hasn't retrieved this part.
                                continue

                        # New known part.
                        nkpart = kcat.get_part(name)
                        nipart = icat.get_part(name)
                        base = name.startswith("catalog.base.")

                        # Avoid accessor overhead since these will be
                        # used for every entry.
                        cat_ver = cat.version
                        dp = cat.get_part("catalog.dependency.C",
                            must_exist=True)

                        for t, sentry in spart.tuple_entries(pubs=[pfx]):
                                pub, stem, ver = t

                                installed = False
                                if pub in inst_stems and \
                                    stem in inst_stems[pub] and \
                                    ver in inst_stems[pub][stem]:
                                        installed = True
                                        inst_stems[pub][stem][ver] = True

                                # copy() is too slow here and catalog entries
                                # are shallow so this should be sufficient.
                                entry = dict(sentry.iteritems())
                                if not base:
                                        # Nothing else to do except add the
                                        # entry for non-base catalog parts.
                                        nkpart.add(metadata=entry,
                                            op_time=op_time, pub=pub, stem=stem,
                                            ver=ver)
                                        if installed:
                                                nipart.add(metadata=entry,
                                                    op_time=op_time, pub=pub,
                                                    stem=stem, ver=ver)
                                        continue

                                # Only the base catalog part stores package
                                # state information and/or other metadata.
                                mdata = entry.setdefault("metadata", {})
                                states = mdata.setdefault("states", [])
                                states.append(self.PKG_STATE_KNOWN)

                                if cat_ver == 0:
                                        states.append(self.PKG_STATE_V0)
                                elif self.PKG_STATE_V0 not in states:
                                        # Assume V1 catalog source.
                                        states.append(self.PKG_STATE_V1)

                                if installed:
                                        states.append(self.PKG_STATE_INSTALLED)

                                nver, snver = newest.get(stem, (None, None))
                                if snver is not None and ver != snver:
                                        states.append(self.PKG_STATE_UPGRADABLE)

                                # Determine if package is obsolete or has been
                                # renamed and mark with appropriate state.
                                dpent = None
                                if dp is not None:
                                        dpent = dp.get_entry(pub=pub, stem=stem,
                                            ver=ver)
                                if dpent is not None:
                                        for a in dpent["actions"]:
                                                # Constructing action objects
                                                # for every action would be a
                                                # lot slower, so a simple string
                                                # match is done first so that
                                                # only interesting actions get
                                                # constructed.
                                                if not a.startswith("set"):
                                                        continue
                                                if not ("pkg.obsolete" in a or \
                                                    "pkg.renamed" in a):
                                                        continue

                                                try:
                                                        act = pkg.actions.fromstr(a)
                                                except pkg.actions.ActionError:
                                                        # If the action can't be
                                                        # parsed or is not yet
                                                        # supported, continue.
                                                        continue

                                                if act.attrs["value"].lower() != "true":
                                                        continue

                                                if act.attrs["name"] == "pkg.obsolete":
                                                        states.append(
                                                            self.PKG_STATE_OBSOLETE)
                                                elif act.attrs["name"] == "pkg.renamed":
                                                        if not act.include_this(
                                                            excludes):
                                                                continue
                                                        states.append(
                                                            self.PKG_STATE_RENAMED)

                                mdata["states"] = states

                                # Add base entries.
                                nkpart.add(metadata=entry, op_time=op_time,
                                    pub=pub, stem=stem, ver=ver)
                                if installed:
                                        nipart.add(metadata=entry,
                                            op_time=op_time, pub=pub, stem=stem,
                                            ver=ver)

                # Now add installed packages to list of known packages using
                # previous state information.  While doing so, track any
                # new entries as the versions for the stem of the entry will
                # need to be passed to finalize() for sorting.
                final_fmris = []
                for name in old_icat.parts:
                        # Old installed part.
                        ipart = old_icat.get_part(name, must_exist=True)

                        # New known part.
                        nkpart = kcat.get_part(name)

                        # New installed part.
                        nipart = icat.get_part(name)

                        base = name.startswith("catalog.base.")

                        mdata = None
                        for t, entry in ipart.tuple_entries():
                                pub, stem, ver = t

                                if pub not in inst_stems or \
                                    stem not in inst_stems[pub] or \
                                    ver not in inst_stems[pub][stem] or \
                                    inst_stems[pub][stem][ver]:
                                        # Entry is no longer valid or is already
                                        # known.
                                        continue

                                if base:
                                        mdata = entry["metadata"]
                                        states = set(mdata["states"])
                                        states.discard(self.PKG_STATE_KNOWN)

                                        nver, snver = newest.get(stem, (None,
                                            None))
                                        if snver is not None and ver == snver:
                                                states.discard(
                                                    self.PKG_STATE_UPGRADABLE)
                                        elif snver is not None:
                                                states.add(
                                                    self.PKG_STATE_UPGRADABLE)
                                        mdata["states"] = list(states)

                                # Add entries.
                                nkpart.add(metadata=entry, op_time=op_time,
                                    pub=pub, stem=stem, ver=ver)
                                nipart.add(metadata=entry, op_time=op_time,
                                    pub=pub, stem=stem, ver=ver)
                                final_fmris.append(pkg.fmri.PkgFmri(
                                    "%s@%s" % (stem, ver), publisher=pub))

                # Save the new catalogs.
                for cat in kcat, icat:
                        misc.makedirs(cat.meta_root)
                        cat.finalize(pfmris=final_fmris)
                        cat.save()

                # Next, preserve the old installed state dir, rename the
                # new one into place, and then remove the old one.
                orig_state_root, ignored = self.salvage(self._statedir)
                portable.rename(tmp_state_root, self._statedir)
                shutil.rmtree(orig_state_root, True)

                # Ensure in-memory catalogs get reloaded.
                self.__init_catalogs()

                progtrack.cache_catalogs_done()
                self.history.log_operation_end()

        def refresh_publishers(self, full_refresh=False, immediate=False,
            pubs=None, progtrack=None):
                """Refreshes the metadata (e.g. catalog) for one or more
                publishers.  Callers are responsible for locking the image.

                'full_refresh' is an optional boolean value indicating whether
                a full retrieval of publisher metadata (e.g. catalogs) or only
                an update to the existing metadata should be performed.  When
                True, 'immediate' is also set to True.

                'immediate' is an optional boolean value indicating whether the
                a refresh should occur now.  If False, a publisher's selected
                repository will only be checked for updates if the update
                interval period recorded in the image configuration has been
                exceeded.

                'pubs' is a list of publisher prefixes or publisher objects
                to refresh.  Passing an empty list or using the default value
                implies all publishers."""

                if self.version < 3:
                        raise apx.ImageFormatUpdateNeeded(self.root)

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                be_name, be_uuid = bootenv.BootEnv.get_be_name(self.root)
                self.history.log_operation_start("refresh-publishers",
                    be_name=be_name, be_uuid=be_uuid)

                # Verify validity of certificates before attempting network
                # operations.
                try:
                        self.check_cert_validity()
                except apx.ExpiringCertificate, e:
                        logger.error(str(e))

                pubs_to_refresh = []

                if not pubs:
                        # Omit disabled publishers.
                        pubs = [p for p in self.gen_publishers()]

                if not pubs:
                        self.__rebuild_image_catalogs(progtrack=progtrack)
                        return

                for pub in pubs:
                        p = pub
                        if not isinstance(p, publisher.Publisher):
                                p = self.get_publisher(prefix=p)
                        if p.disabled:
                                e = apx.DisabledPublisher(p)
                                self.history.log_operation_end(error=e)
                                raise e
                        pubs_to_refresh.append(p)

                if not pubs_to_refresh:
                        self.history.log_operation_end(
                            result=history.RESULT_NOTHING_TO_DO)
                        return

                try:
                        # Ensure Image directory structure is valid.
                        self.mkdirs()
                except Exception, e:
                        self.history.log_operation_end(error=e)
                        raise

                progtrack.refresh_start(len(pubs_to_refresh))

                failed = []
                total = 0
                succeeded = set()
                updated = 0
                for pub in pubs_to_refresh:
                        total += 1
                        progtrack.refresh_progress(pub.prefix)
                        try:
                                if pub.refresh(full_refresh=full_refresh,
                                    immediate=immediate):
                                        updated += 1
                        except apx.PermissionsException, e:
                                failed.append((pub, e))
                                # No point in continuing since no data can
                                # be written.
                                break
                        except apx.ApiException, e:
                                failed.append((pub, e))
                                continue
                        succeeded.add(pub.prefix)
                progtrack.refresh_done()

                if updated:
                        self.__rebuild_image_catalogs(progtrack=progtrack)

                if failed:
                        e = apx.CatalogRefreshException(failed, total,
                            len(succeeded))
                        self.history.log_operation_end(error=e)
                        raise e

                if not updated:
                        self.history.log_operation_end(
                            result=history.RESULT_NOTHING_TO_DO)
                        return
                self.history.log_operation_end()

        def _get_publisher_meta_dir(self):
                if self.version >= 3:
                        return IMG_PUB_DIR
                return "catalog"

        def _get_publisher_cache_root(self, prefix):
                return os.path.join(self.imgdir, "cache", "publisher", prefix)

        def _get_publisher_meta_root(self, prefix):
                return os.path.join(self.imgdir, self._get_publisher_meta_dir(),
                    prefix)

        def remove_publisher_metadata(self, pub, progtrack=None, rebuild=True):
                """Removes the metadata for the specified publisher object,
                except data for installed packages.

                'pub' is the object of the publisher to remove the data for.

                'progtrack' is an optional ProgressTracker object.

                'rebuild' is an optional boolean specifying whether image
                catalogs should be rebuilt after removing the publisher's
                metadata.
                """

                if self.version < 4:
                        # Older images don't require fine-grained deletion.
                        pub.remove_meta_root()
                        if rebuild:
                                self.__rebuild_image_catalogs(
                                    progtrack=progtrack)
                        return

                # Build a list of paths that shouldn't be removed because they
                # belong to installed packages.
                excluded = [
                    self.get_manifest_path(f)
                    for f in self.gen_installed_pkgs()
                    if f.publisher == pub.prefix
                ]

                if not excluded:
                        pub.remove_meta_root()
                else:
                        try:
                                # Discard all publisher metadata except
                                # package manifests as a first pass.
                                for entry in os.listdir(pub.meta_root):
                                        if entry == "pkg":
                                                continue

                                        target = os.path.join(pub.meta_root,
                                            entry)
                                        if os.path.isdir(target):
                                                shutil.rmtree(target)
                                        else:
                                                portable.remove(target)

                                # Build the list of directories that can't be
                                # removed.
                                exdirs = [os.path.dirname(e) for e in excluded]

                                # Now try to discard only package manifests
                                # that aren't for installed packages.
                                mroot = os.path.join(pub.meta_root, "pkg")
                                for pdir in os.listdir(mroot):
                                        proot = os.path.join(mroot, pdir)
                                        if proot not in exdirs:
                                                # This removes all manifest data
                                                # for a given package stem.
                                                shutil.rmtree(proot)
                                                continue

                                        # Remove only manifest data for packages
                                        # that are not installed.
                                        for mname in os.listdir(proot):
                                                mpath = os.path.join(proot,
                                                    mname)
                                                if mpath not in excluded:
                                                        portable.remove(mpath)

                                # Finally, dump any cache data for this
                                # publisher if possible.
                                shutil.rmtree(self._get_publisher_cache_root(
                                    pub.prefix), ignore_errors=True)
                        except EnvironmentError, e:
                                raise apx._convert_error(e)

                if rebuild:
                        self.__rebuild_image_catalogs(progtrack=progtrack)

        def gen_installed_pkg_names(self, anarchy=True):
                """A generator function that produces FMRI strings as it
                iterates over the list of installed packages.  This is
                faster than gen_installed_pkgs when only the FMRI string
                is needed."""

                cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                for f in cat.fmris(objects=False):
                        if anarchy:
                                # Catalog entries always have publisher prefix.
                                yield "pkg:/%s" % f[6:].split("/", 1)[-1]
                                continue
                        yield f

        def gen_installed_pkgs(self):
                """Return an iteration through the installed packages."""

                cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                for f in cat.fmris():
                        yield f

        def gen_tracked_stems(self):
                """Return an iteration through all the tracked pkg stems
                in the set of currently installed packages.  Return value
                is group pkg fmri, stem"""
                cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                excludes = self.list_excludes()

                for f in cat.fmris():
                        for a in cat.get_entry_actions(f,
                            [pkg.catalog.Catalog.DEPENDENCY], excludes=excludes):
                                if a.name == "depend" and a.attrs["type"] == "group":
                                        yield (f, self.strtofmri(
                                            a.attrs["fmri"]).pkg_name)

        def _create_fast_lookups(self):
                """Create an on-disk database mapping action name and key
                attribute value to the action string comprising the unique
                attributes of the action, for all installed actions.  This is
                done with a file mapping the tuple to an offset into a second
                file, where those actions are kept.  Once the offsets are loaded
                into memory, it is simple to seek into the second file to the
                given offset and read until you hit an action that doesn't
                match."""

                stripped_path = os.path.join(self.__action_cache_dir,
                    "actions.stripped")
                offsets_path = os.path.join(self.__action_cache_dir,
                    "actions.offsets")

                excludes = self.list_excludes()
                heap = []

                from heapq import heappush, heappop

                for pfmri in self.gen_installed_pkgs():
                        m = self.get_manifest(pfmri, all_variants=True)
                        for act in m.gen_actions(excludes):
                                if not act.globally_identical:
                                        continue
                                for key in act.attrs.keys():
                                        if (act.unique_attrs and
                                            key not in act.unique_attrs and
                                            not (act.name == "file" and
                                                key == "overlay")) or \
                                            key.startswith("variant.") or \
                                            key.startswith("facet."):
                                                del act.attrs[key]
                                heappush(heap, (act.name,
                                    act.attrs[act.key_attr], pfmri, act))

                # Don't worry if we can't write the temporary files.
                try:
                        actdict = {}
                        sf, sp = self.temporary_file(close=False)
                        of, op = self.temporary_file(close=False)

                        sf = os.fdopen(sf, "wb")
                        of = os.fdopen(of, "wb")

                        # We need to make sure the files are coordinated.
                        t = int(time.time())
                        sf.write("VERSION 1\n%s\n" % t)
                        of.write("VERSION 1\n%s\n" % t)

                        last_name, last_key = None, None
                        while heap:
                                item = heappop(heap)
                                fmri, act = item[2:]
                                offset = sf.tell()
                                sf.write("%s %s\n" % (fmri, act))
                                key = act.attrs[act.key_attr]
                                if act.name != last_name or key != last_key:
                                        of.write("%s %s %s\n" % (act.name, offset, key))
                                        actdict[(act.name, key)] = offset
                                        last_name, last_key = act.name, key
                        sf.close()
                        of.close()
                        os.chmod(sp, misc.PKG_FILE_MODE)
                        os.chmod(op, misc.PKG_FILE_MODE)
                except BaseException, e:
                        try:
                                os.unlink(sp)
                                os.unlink(op)
                        except:
                                if isinstance(e, KeyboardInterrupt):
                                        raise
                                return actdict
                        if isinstance(e, KeyboardInterrupt):
                                raise
                        return

                # Finally, rename the temporary files into their final place.
                # If we have any problems, do our best to remove them, and we'll
                # try to recreate them on the read-side.
                try:
                        portable.rename(sp, stripped_path)
                        portable.rename(op, offsets_path)
                        return actdict
                except EnvironmentError, e:
                        if e.errno == errno.EACCES or e.errno == errno.EROFS:
                                self.__action_cache_dir = self.temporary_dir()
                                stripped_path = os.path.join(
                                    self.__action_cache_dir, "actions.stripped")
                                offsets_path = os.path.join(
                                    self.__action_cache_dir, "actions.offsets")
                                portable.rename(sp, stripped_path)
                                portable.rename(op, offsets_path)
                                return actdict
                        try:
                                os.unlink(stripped_path)
                                os.unlink(offsets_path)
                        except:
                                pass

        def _load_actdict(self):
                """Read the file of offsets created in _create_fast_lookups()
                and return the dictionary mapping action name and key value to
                offset."""

                actdict = {}

                try:
                        of = open(os.path.join(self.__action_cache_dir,
                            "actions.offsets"), "rb")
                except IOError, e:
                        if e.errno != errno.ENOENT:
                                raise

                        actdict = self._create_fast_lookups()
                        if actdict is not None:
                                return actdict

                # Make sure the files are paired, and try to create them if not.
                oversion = of.readline().rstrip()
                otimestamp = of.readline().rstrip()
                sversion, stimestamp = self._get_stripped_actions_file(internal=True)

                # If we recognize neither file's version or their timestamps
                # don't match, then we blow them away and try again.
                if oversion != "VERSION 1" or sversion != "VERSION 1" or \
                    stimestamp != otimestamp:
                        of.close()
                        actdict = self._create_fast_lookups()
                        if actdict is not None:
                                return actdict
                        of = file(os.path.join(self.__action_cache_dir,
                            "actions.offsets"), "rb")
                        oversion = of.readline().rstrip()
                        otimestamp = of.readline().rstrip()

                for line in of:
                        actname, offset, key_attr = line.rstrip().split(None, 2)
                        actdict[(actname, key_attr)] = int(offset)

                of.close()
                return actdict

        def _get_stripped_actions_file(self, internal=False):
                """Open the actions file described in _create_fast_lookups() and
                return the corresponding file object."""

                sf = file(os.path.join(self.__action_cache_dir,
                    "actions.stripped"), "rb")
                sversion = sf.readline().rstrip()
                stimestamp = sf.readline().rstrip()
                if internal:
                        sf.close()
                        return sversion, stimestamp

                return sf

        def gen_installed_actions_bytype(self, atype, implicit_dirs=False):
                """Iterates through the installed actions of type 'atype'.  If
                'implicit_dirs' is True and 'atype' is 'dir', then include
                directories only implicitly defined by other filesystem
                actions."""

                if implicit_dirs and atype != "dir":
                        implicit_dirs = False

                excludes = self.list_excludes()

                for pfmri in self.gen_installed_pkgs():
                        m = self.get_manifest(pfmri)
                        dirs = set()
                        for act in m.gen_actions_by_type(atype, excludes):
                                if implicit_dirs:
                                        dirs.add(act.attrs["path"])
                                yield act, pfmri
                        if implicit_dirs:
                                da = pkg.actions.directory.DirectoryAction
                                for d in m.get_directories(excludes):
                                        if d not in dirs:
                                                yield da(path=d, implicit="true"), pfmri

        def get_installed_pubs(self):
                """Returns a set containing the prefixes of all publishers with
                installed packages."""

                cat = self.get_catalog(self.IMG_CATALOG_INSTALLED)
                return cat.publishers()

        def strtofmri(self, myfmri):
                return pkg.fmri.PkgFmri(myfmri, self.attrs["Build-Release"])

        def strtomatchingfmri(self, myfmri):
                return pkg.fmri.MatchingPkgFmri(myfmri,
                    self.attrs["Build-Release"])

        def get_user_by_name(self, name):
                uid = self._usersbyname.get(name, None)
                if uid is not None:
                        return uid
                return portable.get_user_by_name(name, self.root,
                    self.type != IMG_USER)

        def get_name_by_uid(self, uid, returnuid = False):
                # XXX What to do about IMG_PARTIAL?
                try:
                        return portable.get_name_by_uid(uid, self.root,
                            self.type != IMG_USER)
                except KeyError:
                        if returnuid:
                                return uid
                        else:
                                raise

        def get_group_by_name(self, name):
                gid = self._groupsbyname.get(name, None)
                if gid is not None:
                        return gid
                return portable.get_group_by_name(name, self.root,
                    self.type != IMG_USER)

        def get_name_by_gid(self, gid, returngid = False):
                try:
                        return portable.get_name_by_gid(gid, self.root,
                            self.type != IMG_USER)
                except KeyError:
                        if returngid:
                                return gid
                        else:
                                raise

        def update_index_dir(self, postfix="index"):
                """Since the index directory will not reliably be updated when
                the image root is, this should be called prior to using the
                index directory.
                """
                if self.version == self.CURRENT_VERSION:
                        self.index_dir = os.path.join(self.imgdir, "cache",
                            postfix)
                else:
                        self.index_dir = os.path.join(self.imgdir, postfix)

        def cleanup_downloads(self):
                """Clean up any downloads that were in progress but that
                did not successfully finish."""

                shutil.rmtree(self._incoming_cache_dir, True)

        def cleanup_cached_content(self):
                """Delete the directory that stores all of our cached
                downloaded content.  This may take a while for a large
                directory hierarchy.  Don't clean up caches if the
                user overrode the underlying setting using PKG_CACHEDIR or
                PKG_CACHEROOT. """

                if self.cfg.get_policy(imageconfig.FLUSH_CONTENT_CACHE):
                        logger.info("Deleting content cache")
                        for path, readonly, pub in self.get_cachedirs():
                                if readonly or (self.__user_cache_dir and
                                    path.startswith(self.__user_cache_dir)):
                                        continue
                                shutil.rmtree(path, True)

        def salvage(self, path):
                """Called when unexpected file or directory is found during
                package operations; returns a tuple of the path of the salvage
                directory where the item was stored and the new path of the
                salvaged item.  path is rooted in /...."""

                # This ensures that if the path is already rooted in the image,
                # that it will be stored in lost+found (due to os.path.join
                # behaviour with absolute path components).
                if path.startswith(self.root):
                        path = path.replace(self.root, "", 1)

                if os.path.isabs(path):
                        # If for some reason the path wasn't rooted in the
                        # image, but it is an absolute one, then strip the
                        # absolute part so that it will be stored in lost+found
                        # (due to os.path.join behaviour with absolute path
                        # components).
                        path = os.path.splitdrive(path)[-1].lstrip(os.path.sep)

                sdir = os.path.normpath(
                    os.path.join(self.imgdir, "lost+found",
                    path + "-" + time.strftime("%Y%m%dT%H%M%SZ")))

                parent = os.path.dirname(sdir)
                if not os.path.exists(parent):
                        misc.makedirs(parent)

                orig = os.path.normpath(os.path.join(self.root, path))
                shutil.move(orig, sdir)
                return sdir, os.path.join(sdir, sdir)

        def temporary_dir(self):
                """Create a temp directory under the image directory for various
                purposes.  If the process is unable to create a directory in the
                image's temporary directory, a replacement location is found."""

                try:
                        misc.makedirs(self.__tmpdir)
                except (apx.PermissionsException,
                    apx.ReadOnlyFileSystemException):
                        self.__tmpdir = tempfile.mkdtemp(prefix="pkg5tmp-")
                        atexit.register(shutil.rmtree,
                            self.__tmpdir, ignore_errors=True)
                        return self.temporary_dir()

                try:
                        rval = tempfile.mkdtemp(dir=self.__tmpdir)

                        # Force standard mode.
                        os.chmod(rval, misc.PKG_DIR_MODE)
                        return rval
                except EnvironmentError, e:
                        if e.errno == errno.EACCES or e.errno == errno.EROFS:
                                self.__tmpdir = tempfile.mkdtemp(prefix="pkg5tmp-")
                                atexit.register(shutil.rmtree,
                                    self.__tmpdir, ignore_errors=True)
                                return self.temporary_dir()
                        raise apx._convert_error(e)

        def temporary_file(self, close=True):
                """Create a temporary file under the image directory for various
                purposes.  If 'close' is True, close the file descriptor;
                otherwise leave it open.  If the process is unable to create a
                file in the image's temporary directory, a replacement is
                found."""

                try:
                        misc.makedirs(self.__tmpdir)
                except (apx.PermissionsException,
                    apx.ReadOnlyFileSystemException):
                        self.__tmpdir = tempfile.mkdtemp(prefix="pkg5tmp-")
                        atexit.register(shutil.rmtree,
                            self.__tmpdir, ignore_errors=True)
                        return self.temporary_file(close=close)

                try:
                        fd, name = tempfile.mkstemp(dir=self.__tmpdir)
                        if close:
                                os.close(fd)
                except EnvironmentError, e:
                        if e.errno == errno.EACCES or e.errno == errno.EROFS:
                                self.__tmpdir = tempfile.mkdtemp(prefix="pkg5tmp-")
                                atexit.register(shutil.rmtree,
                                    self.__tmpdir, ignore_errors=True)
                                return self.temporary_file(close=close)
                        raise apx._convert_error(e)

                if close:
                        return name
                else:
                        return fd, name

        def __filter_install_matches(self, matches):
                """Attempts to eliminate redundant matches found during
                packaging operations:

                    * First, stems of installed packages for publishers that
                      are now unknown (no longer present in the image
                      configuration) are dropped.

                    * Second, if multiple matches are still present, stems of
                      of installed packages, that are not presently in the
                      corresponding publisher's catalog, are dropped.

                    * Finally, if multiple matches are still present, all
                      stems except for those in state PKG_STATE_INSTALLED are
                      dropped.

                Returns a list of the filtered matches, along with a dict of
                their unique names."""

                olist = []
                onames = set()

                # First eliminate any duplicate matches that are for unknown
                # publishers (publishers which have been removed from the image
                # configuration).
                publist = set(p.prefix for p in self.get_publishers().values())
                for m, st in matches:
                        if m.publisher in publist:
                                onames.add(m.get_pkg_stem())
                                olist.append((m, st))

                # Next, if there are still multiple matches, eliminate matches
                # belonging to publishers that no longer have the FMRI in their
                # catalog.
                found_state = False
                if len(onames) > 1:
                        mlist = []
                        mnames = set()
                        for m, st in olist:
                                if not st["in_catalog"]:
                                        continue
                                if st["state"] == self.PKG_STATE_INSTALLED:
                                        found_state = True
                                mnames.add(m.get_pkg_stem())
                                mlist.append((m, st))
                        olist = mlist
                        onames = mnames

                # Finally, if there are still multiple matches, and a known
                # stem is installed, then eliminate any stems that do not
                # have an installed version.
                if found_state and len(onames) > 1:
                        mlist = []
                        mnames = set()
                        for m, st in olist:
                                if st["state"] == self.PKG_STATE_INSTALLED:
                                        mnames.add(m.get_pkg_stem())
                                        mlist.append((m, st))
                        olist = mlist
                        onames = mnames

                return olist, onames

        def avoid_pkgs(self, pat_list, progtrack, check_cancel):
                """Avoid the specified packages... use pattern matching on
                names; ignore versions."""

                with self.locked_op("avoid"):
                        ip = imageplan.ImagePlan(self, progtrack, check_cancel,
                            noexecute=False)

                        self._avoid_set_save(self.avoid_set_get() |
                            set(ip.match_user_stems(pat_list, ip.MATCH_UNINSTALLED)))

        def unavoid_pkgs(self, pat_list, progtrack, check_cancel):
                """Unavoid the specified packages... use pattern matching on
                names; ignore versions."""

                with self.locked_op("unavoid"):

                        ip = imageplan.ImagePlan(self, progtrack, check_cancel,
                            noexecute=False)
                        unavoid_set = set(ip.match_user_stems(pat_list, ip.MATCH_ALL))
                        current_set = self.avoid_set_get()
                        not_avoided = unavoid_set - current_set
                        if not_avoided:
                                raise apx.PlanCreationException(not_avoided=not_avoided)

                        would_install = [
                            a
                            for f, a in self.gen_tracked_stems()
                            if a in unavoid_set
                        ]

                        if would_install:
                                raise apx.PlanCreationException(would_install=would_install)

                        self._avoid_set_save(current_set - unavoid_set)

        def get_avoid_dict(self):
                """ return dict of lists (avoided stem, pkgs w/ group
                dependencies on this pkg)"""
                ret = dict((a, list()) for a in self.avoid_set_get())
                for fmri, group in self.gen_tracked_stems():
                        if group in ret:
                                ret[group].append(fmri.pkg_name)
                return ret

        def __call_imageplan_evaluate(self, ip):
                # A plan can be requested without actually performing an
                # operation on the image.
                if self.history.operation_name:
                        self.history.operation_start_state = ip.get_plan()

                try:
                        ip.evaluate()
                except apx.ConflictingActionErrors:
                        # Image plan evaluation can fail because of duplicate
                        # action discovery, but we still want to be able to
                        # display and log the solved FMRI changes.
                        self.imageplan = ip
                        if self.history.operation_name:
                                self.history.operation_end_state = \
                                    "Unevaluated: merged plan had errors\n" + \
                                    ip.get_plan(full=False)
                        raise

                self.imageplan = ip

                if self.history.operation_name:
                        self.history.operation_end_state = \
                            ip.get_plan(full=False)

        def __make_plan_common(self, _op, _progtrack, _check_cancel,
            _ip_mode, _noexecute, _ip_noop=False,
            **kwargs):
                """Private helper function to perform base plan creation and
                cleanup.
                """

                # Allow garbage collection of previous plan.
                self.imageplan = None

                ip = imageplan.ImagePlan(self, _progtrack, _check_cancel,
                    noexecute=_noexecute, mode=_ip_mode)

                _progtrack.evaluate_start()

                # Always start with most current (on-disk) state information.
                self.__init_catalogs()

                try:
                        try:
                                if _ip_noop:
                                        ip.plan_noop()
                                elif _op in [
                                    pkgdefs.API_OP_ATTACH,
                                    pkgdefs.API_OP_DETACH,
                                    pkgdefs.API_OP_SYNC]:
                                        ip.plan_sync(**kwargs)
                                elif _op in [
                                    pkgdefs.API_OP_CHANGE_FACET,
                                    pkgdefs.API_OP_CHANGE_VARIANT]:
                                        ip.plan_change_varcets(**kwargs)
                                elif _op == pkgdefs.API_OP_INSTALL:
                                        ip.plan_install(**kwargs)
                                elif _op == pkgdefs.API_OP_REVERT:
                                        ip.plan_revert(**kwargs)
                                elif _op == pkgdefs.API_OP_UNINSTALL:
                                        ip.plan_uninstall(**kwargs)
                                elif _op == pkgdefs.API_OP_UPDATE:
                                        ip.plan_update(**kwargs)
                                else:
                                        raise RuntimeError(
                                            "Unknown api op: %s" % _op)

                        except apx.ActionExecutionError, e:
                                raise
                        except pkg.actions.ActionError, e:
                                raise apx.InvalidPackageErrors([e])
                        except apx.ApiException:
                                raise
                        try:
                                self.__call_imageplan_evaluate(ip)
                        except apx.ActionExecutionError, e:
                                raise
                        except pkg.actions.ActionError, e:
                                raise apx.InvalidPackageErrors([e])
                finally:
                        self.__cleanup_alt_pkg_certs()

        def make_install_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute, pkgs_inst=None, reject_list=None):
                """Take a list of packages, specified in pkgs_inst, and attempt
                to assemble an appropriate image plan.  This is a helper
                routine for some common operations in the client.
                """

                self.__make_plan_common(op, progtrack, check_cancel,
                    ip_mode, noexecute, pkgs_inst=pkgs_inst,
                    reject_list=reject_list)

        def make_change_varcets_plan(self, op, progtrack, check_cancel,
            ip_mode, noexecute, facets=None, reject_list=None,
            variants=None):
                """Take a list of variants and/or facets and attempt to
                assemble an image plan which changes them.  This is a helper
                routine for some common operations in the client."""

                # compute dict of changing variants
                if variants:
                        new = set(variants.iteritems())
                        cur = set(self.cfg.variants.iteritems())
                        variants = dict(new - cur)

                self.__make_plan_common(op, progtrack, check_cancel, ip_mode,
                    noexecute, new_variants=variants, new_facets=facets,
                    reject_list=reject_list)

        def make_sync_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute, li_pkg_updates=True, reject_list=None):
                """Attempt to create an appropriate image plan to bring an
                image in sync with it's linked image constraints.  This is a
                helper routine for some common operations in the client."""

                self.__make_plan_common(op, progtrack, check_cancel, ip_mode,
                    noexecute, reject_list=reject_list,
                    li_pkg_updates=li_pkg_updates)

        def make_uninstall_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute, pkgs_to_uninstall):
                """Create uninstall plan to remove the specified packages."""

                self.__make_plan_common(op, progtrack, check_cancel,
                    ip_mode, noexecute, pkgs_to_uninstall=pkgs_to_uninstall)

        def make_update_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute, pkgs_update=None, reject_list=None):
                """Create a plan to update all packages or the specific ones as
                far as possible.  This is a helper routine for some common
                operations in the client.
                """

                self.__make_plan_common(op, progtrack, check_cancel,
                    ip_mode, noexecute, pkgs_update=pkgs_update,
                    reject_list=reject_list)

        def make_revert_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute, args, tagged):
                """Revert the specified files, or all files tagged as specified
                in args to their manifest definitions.
                """

                self.__make_plan_common(op, progtrack, check_cancel,
                    ip_mode, noexecute, args=args, tagged=tagged)

        def make_noop_plan(self, op, progtrack, check_cancel, ip_mode,
            noexecute):
                """Create an image plan that doesn't update the image in any
                way."""

                self.__make_plan_common(op, progtrack, check_cancel,
                    ip_mode, noexecute, _ip_noop=True)

        def ipkg_is_up_to_date(self, check_cancel, noexecute,
            refresh_allowed=True, progtrack=None):
                """Test whether the packaging system is updated to the latest
                version known to be available for this image."""

                #
                # This routine makes the distinction between the "target image",
                # which will be altered, and the "running image", which is
                # to say whatever image appears to contain the version of the
                # pkg command we're running.
                #

                #
                # There are two relevant cases here:
                #     1) Packaging code and image we're updating are the same
                #        image.  (i.e. 'pkg update')
                #
                #     2) Packaging code's image and the image we're updating are
                #        different (i.e. 'pkg update -R')
                #
                # In general, we care about getting the user to run the
                # most recent packaging code available for their build.  So,
                # if we're not in the liveroot case, we create a new image
                # which represents "/" on the system.
                #

                if not progtrack:
                        progtrack = progress.QuietProgressTracker()

                img = self

                if self.__cmddir and not img.is_liveroot():
                        #
                        # Find the path to ourselves, and use that
                        # as a way to locate the image we're in.  It's
                        # not perfect-- we could be in a developer's
                        # workspace, for example.
                        #
                        newimg = Image(self.__cmddir,
                            allow_ondisk_upgrade=False, allow_ambiguous=True,
                            progtrack=progtrack, cmdpath=self.cmdpath)
                        useimg = True
                        if refresh_allowed:
                                # If refreshing publisher metadata is allowed,
                                # then perform a refresh so that a new packaging
                                # system package can be discovered.
                                newimg.lock(allow_unprivileged=True)
                                try:
                                        newimg.refresh_publishers(
                                            progtrack=progtrack)
                                except (apx.ImageFormatUpdateNeeded,
                                    apx.PermissionsException):
                                        # Can't use the image to perform an
                                        # update check and it would be wrong
                                        # to prevent the operation from
                                        # continuing in these cases.
                                        useimg = False
                                except apx.CatalogRefreshException, cre:
                                        cre.errmessage = \
                                            _("pkg(5) update check failed.")
                                        raise
                                finally:
                                        newimg.unlock()

                        if useimg:
                                img = newimg

                # XXX call to progress tracker that the package is being
                # refreshed
                img.make_install_plan(pkgdefs.API_OP_INSTALL, progtrack,
                    check_cancel, pkgdefs.API_STAGE_DEFAULT, noexecute,
                    pkgs_inst=["pkg:/package/pkg"])

                return img.imageplan.nothingtodo()

        # avoid set implementation uses simplejson to store a
        # set of pkg_stems being avoided, and a set of tracked
        # stems that are obsolete.
        #
        # format is (version, dict((pkg stem, "avoid" or "obsolete"))

        __AVOID_SET_VERSION = 1

        def avoid_set_get(self):
                """Return copy of avoid set"""
                return self.__avoid_set.copy()

        def obsolete_set_get(self):
                """Return copy of tracked obsolete pkgs"""
                return self.__group_obsolete.copy()

        def __avoid_set_load(self):
                """Load avoid set fron image state directory"""
                state_file = os.path.join(self._statedir, "avoid_set")
                self.__avoid_set = set()
                self.__group_obsolete = set()
                if os.path.isfile(state_file):
                        version, d = json.load(file(state_file))
                        assert version == self.__AVOID_SET_VERSION
                        for stem in d:
                                if d[stem] == "avoid":
                                        self.__avoid_set.add(stem)
                                elif d[stem] == "obsolete":
                                        self.__group_obsolete.add(stem)
                                else:
                                        logger.warn("Corrupted avoid list - ignoring")
                                        self.__avoid_set = set()
                                        self.__group_obsolete = set()
                                        self.__avoid_set_altered = True
                else:
                        self.__avoid_set_altered = True

        def _avoid_set_save(self, new_set=None, obsolete=None):
                """Store avoid set to image state directory"""
                if new_set is not None:
                        self.__avoid_set_altered = True
                        self.__avoid_set = new_set

                if obsolete is not None:
                        self.__group_obsolete = obsolete
                        self.__avoid_set_altered = True

                if not self.__avoid_set_altered:
                        return


                state_file = os.path.join(self._statedir, "avoid_set")
                tmp_file   = os.path.join(self._statedir, "avoid_set.new")
                tf = file(tmp_file, "w")

                d = dict((a, "avoid") for a in self.__avoid_set)
                d.update((a, "obsolete") for a in self.__group_obsolete)

                try:
                        json.dump((self.__AVOID_SET_VERSION, d), tf)
                        tf.close()
                        portable.rename(tmp_file, state_file)

                except Exception, e:
                        logger.warn("Cannot save avoid list: %s" % str(e))
                        return

                self.__avoid_set_altered = False

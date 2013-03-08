#!/usr/bin/env python
# -*- mode: python; encoding: utf-8 -*-

# Copyright 2011 Google Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test the filesystem related flows."""

import os

from grr.lib import aff4
from grr.lib import rdfvalue
from grr.lib import test_lib
from grr.lib import utils


class TestFilesystem(test_lib.FlowTestsBaseclass):
  """Test the interrogate flow."""

  def testListDirectory(self):
    """Test that the ListDirectory flow works."""
    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")

    # Deliberately specify incorrect casing for the image name.
    pb = rdfvalue.RDFPathSpec(
        path=os.path.join(self.base_path, "test_img.dd"),
        pathtype=rdfvalue.RDFPathSpec.Enum("OS"))

    # Nest inside the image using TSK.
    pb.Append(path="test directory",
              pathtype=rdfvalue.RDFPathSpec.Enum("TSK"))

    for _ in test_lib.TestFlowHelper(
        "ListDirectory", client_mock, client_id=self.client_id,
        pathspec=pb, token=self.token):
      pass

    # Check the output file is created
    output_path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/tsk").Add(pb.first.path)

    fd = aff4.FACTORY.Open(output_path, token=self.token)
    children = list(fd.OpenChildren())
    self.assertEqual(len(children), 1)
    child = children[0]
    # Check that the object is stored with the correct casing.
    self.assertEqual(
        os.path.basename(utils.SmartUnicode(child.urn)), "Test Directory")

    # And the wrong object is not there
    self.assertRaises(IOError, fd.OpenMember,
                      output_path.Add("test directory"))

    # This directory does exist
    aff4.FACTORY.Open(output_path.Add("Test Directory"), token=self.token)

  def testUnicodeListDirectory(self):
    """Test that the ListDirectory flow works on unicode directories."""

    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")

    # Deliberately specify incorrect casing
    pb = rdfvalue.RDFPathSpec(
        path=os.path.join(self.base_path, "test_img.dd"),
        pathtype=rdfvalue.RDFPathSpec.Enum("OS"))

    pb.Append(path=u"入乡随俗 海外春节别样过法",
              pathtype=rdfvalue.RDFPathSpec.Enum("TSK"))

    for _ in test_lib.TestFlowHelper(
        "ListDirectory", client_mock, client_id=self.client_id,
        pathspec=pb, token=self.token):
      pass

    # Check the output file is created
    output_path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/tsk").Add(pb.CollapsePath())

    fd = aff4.FACTORY.Open(output_path, token=self.token)
    children = list(fd.OpenChildren())
    self.assertEqual(len(children), 1)
    child = children[0]
    self.assertEqual(
        os.path.basename(utils.SmartUnicode(child.urn)), u"入乡随俗.txt")

  def testSlowGetFile(self):
    """Test that the SlowGetFile flow works."""
    client_mock = test_lib.ActionMock("ReadBuffer", "HashFile", "StatFile")

    # Deliberately specify incorrect casing
    pb = rdfvalue.RDFPathSpec(
        path=os.path.join(self.base_path, "test_img.dd"),
        pathtype=rdfvalue.RDFPathSpec.Enum("OS"))

    pb.Append(path="test directory/NumBers.txt",
              pathtype=rdfvalue.RDFPathSpec.Enum("TSK"))

    for _ in test_lib.TestFlowHelper(
        "SlowGetFile", client_mock, client_id=self.client_id,
        pathspec=pb, token=self.token):
      pass

    # Check the output file is created
    output_path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/tsk").Add(pb.first.path.replace("\\", "/")).Add(
            "Test Directory").Add("numbers.txt")

    fd = aff4.FACTORY.Open(output_path, token=self.token)
    self.assertEqual(fd.Read(10), "1\n2\n3\n4\n5\n")
    self.assertEqual(fd.size, 3893)

    # And the wrong object is not there
    client = aff4.FACTORY.Open(self.client_id, token=self.token)
    self.assertRaises(IOError, client.OpenMember, pb.first.path)

    # Check that the hash is recorded correctly.
    self.assertEqual(
        str(fd.Get(fd.Schema.HASH)),
        "67d4ff71d43921d5739f387da09746f405e425b07d727e4c69d029461d1f051f")

  def testGlob(self):
    """Test that glob works properly."""

    # Add some usernames we can interpolate later.
    client = aff4.FACTORY.Open(self.client_id, mode="rw", token=self.token)
    client.Set(client.Schema.USERNAMES("test syslog"))
    client.Close()

    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")

    # This glob selects all files which start with the username on this system.
    path = os.path.join(self.base_path, "%%Usernames%%*")

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "Glob", client_mock, client_id=self.client_id,
        paths=[path], pathtype=rdfvalue.RDFPathSpec.Enum("OS"),
        token=self.token):
      pass

    output_path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/os").Add(self.base_path.replace("\\", "/"))

    count = 0
    fd = aff4.FACTORY.Open(output_path, token=self.token)
    for child in fd.ListChildren():
      childname = child.Basename()
      self.assertTrue(childname.startswith("test") or
                      childname.startswith("syslog"))
      count += 1

    # We should find some files.
    self.assertTrue(count >= 6)

  def testGlobDirectory(self):
    """Test that glob expands directories."""

    # Add some usernames we can interpolate later.
    client = aff4.FACTORY.Open(self.client_id, mode="rw", token=self.token)
    user_attribute = client.Schema.USER()

    user_record = rdfvalue.User()
    user_record.special_folders.app_data = "test_data/index.dat"
    user_attribute.Append(user_record)

    user_record = rdfvalue.User()
    user_record.special_folders.app_data = "test_data/History"
    user_attribute.Append(user_record)

    # This is a record which means something to the interpolation system. We
    # should not process this especially.
    user_record = rdfvalue.User()
    user_record.special_folders.app_data = "%%PATH%%"
    user_attribute.Append(user_record)

    client.Set(user_attribute)

    client.Close()

    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")

    # This glob selects all files which start with the username on this system.
    path = os.path.join(os.path.dirname(self.base_path),
                        "%%Users.special_folders.app_data%%")

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "Glob", client_mock, client_id=self.client_id,
        paths=[path], token=self.token):
      pass

    path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/os").Add(self.base_path).Add("index.dat")

    aff4.FACTORY.Open(path, required_type="VFSFile", token=self.token)

    path = aff4.ROOT_URN.Add(self.client_id).Add(
        "fs/os").Add(self.base_path).Add("index.dat")

    aff4.FACTORY.Open(path, required_type="VFSFile", token=self.token)

  def testGlobGrouping(self):
    """Test that glob expands directories."""

    pattern = "test_data/{ntfs_img.dd,*.log,*.raw}"

    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")
    path = os.path.join(os.path.dirname(self.base_path), pattern)

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "Glob", client_mock, client_id=self.client_id,
        paths=[path], token=self.token):
      pass

  def testIllegalGlob(self):
    """Test that illegal globs raise."""

    pattern = "Test/%%Weird_illegal_attribute%%"

    client_mock = test_lib.ActionMock("ListDirectory", "StatFile")
    path = os.path.join(os.path.dirname(self.base_path), pattern)

    # Run the flow - we expect an AttributeError error to be raised from the
    # flow since Weird_illegal_attribute is not a valid client attribute.
    self.assertRaises(AttributeError, list, test_lib.TestFlowHelper(
        "Glob", client_mock, client_id=self.client_id,
        paths=[path], token=self.token))

  def testGlobAndDownload(self):

    pattern = "test_data/*.log"

    client_mock = test_lib.ActionMock("ListDirectory", "TransferBuffer",
                                      "StatFile")
    path = os.path.join(os.path.dirname(self.base_path), pattern)

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "GlobAndDownload", client_mock, client_id=self.client_id,
        paths=[path], token=self.token):
      pass

    for f in "auth.log dpkg.log dpkg_false.log".split():
      fd = aff4.FACTORY.Open(rdfvalue.RDFURN(self.client_id).Add("/fs/os").Add(
          os.path.join(os.path.dirname(self.base_path), "test_data", f)),
                             token=self.token)
      # Make sure that some data was downloaded.
      self.assertTrue(fd.Get(fd.Schema.SIZE) > 100)

  def testGlobAndGrep(self):
    pattern = "test_data/*.log"

    client_mock = test_lib.ActionMock("ListDirectory", "Grep", "StatFile")
    path = os.path.join(os.path.dirname(self.base_path), pattern)

    args = {"request": rdfvalue.GrepSpec(
        target=rdfvalue.RDFPathSpec(),
        literal="session opened for user dearjohn",
        mode=rdfvalue.GrepSpec.Enum("ALL_HITS")
        ),
            "output": "analysis/grep/testing"}

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "GlobAndGrep", client_mock, client_id=self.client_id,
        paths=[path], token=self.token, **args):
      pass

    fd = aff4.FACTORY.Open(
        rdfvalue.RDFURN(self.client_id).Add("/analysis/grep/testing"),
        token=self.token)
    # Make sure that there is a hit.
    hits = fd.Get(fd.Schema.HITS)
    self.assertTrue(hits is not None)
    hits = list(hits)
    self.assertEqual(len(hits), 1)
    self.assertEqual(hits[0].offset, 350)
    self.assertEqual(hits[0].data,
                     "session): session opened for user dearjohn by (uid=0")

  def testGlobAndListDirectory(self):

    fd = aff4.FACTORY.Open(rdfvalue.RDFURN(self.client_id).Add("/fs/os").Add(
        os.path.join(os.path.dirname(self.base_path), "test_data")),
                           token=self.token)
    self.assertEqual(len(list(fd.ListChildren())), 0)

    pattern = "test_*"

    client_mock = test_lib.ActionMock("ListDirectory", "TransferBuffer",
                                      "StatFile")
    path = os.path.join(os.path.dirname(self.base_path), pattern)

    # Run the flow.
    for _ in test_lib.TestFlowHelper(
        "GlobAndListDirectory", client_mock, client_id=self.client_id,
        paths=[path], token=self.token):
      pass

    fd = aff4.FACTORY.Open(rdfvalue.RDFURN(self.client_id).Add("/fs/os").Add(
        os.path.join(os.path.dirname(self.base_path), "test_data")),
                           token=self.token)

    children = list(fd.ListChildren())
    self.assertGreater(len(children), 30)
    filenames = [os.path.basename(str(f)) for f in children]

    for f in "auth.log dpkg.log dpkg_false.log".split():
      self.assertIn(f, filenames)
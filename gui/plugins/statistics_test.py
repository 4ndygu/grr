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

"""Test the statistics viewer."""


from google.protobuf import text_format

from grr.lib import access_control
from grr.lib import aff4
from grr.lib import test_lib
from grr.proto import analysis_pb2


class TestStats(test_lib.GRRSeleniumTest):
  """Test the statistics interface."""

  @staticmethod
  def PopulateData():
    """Populates data into the stats object."""
    data = """
title: "%(number)s day actives"
data {
  label: "Windows"
  y_value: %(win)s
}
data {
  label: "Linux"
  y_value: %(lin)s
}
"""
    token = access_control.ACLToken("test", "fixture")

    fd = aff4.FACTORY.Create("cron:/OSBreakDown", "OSBreakDown", token=token)
    now = 1321057655

    for i in range(10, 15):
      histogram = fd.Schema.OS_HISTOGRAM(
          age=int((now + i*60*60*24) * 1e6))

      for number in [1, 7, 14, 30]:
        d = data % dict(win=i+number, lin=i*2+number, number=number)
        graph = analysis_pb2.Graph()
        text_format.Merge(d, graph)
        histogram.Append(graph)

      fd.AddAttribute(histogram)
    fd.Close()

  def testStats(self):
    """Test the statistics interface.

    Unfortunately this test is pretty lame because we can not look into the
    canvas object with selenium.
    """
    sel = self.selenium
    sel.open("/")

    self.WaitUntil(sel.is_element_present, "client_query")

    # Make sure the foreman is not there (we are not admin yet)
    self.assert_(not sel.is_element_present("css=a[grrtarget=ManageForeman]"))

    # Make "test" user an admin
    self.MakeUserAdmin("test")

    sel.open("/")

    self.WaitUntil(sel.is_element_present, "client_query")

    # Make sure that now we can see this option.
    self.WaitUntil(sel.is_element_present, "css=a[grrtarget=ManageForeman]")
    self.assert_(sel.is_element_present("css=a[grrtarget=ManageForeman]"))

    # Go to Statistics
    sel.click("css=a:contains('Statistics')")

    self.WaitUntil(sel.is_element_present, "css=#_Clients")
    sel.click("css=#_Clients ins.jstree-icon")

    self.WaitUntil(sel.is_element_present, "css=#_Clients-OS_20Breakdown")
    sel.click("css=#_Clients-OS_20Breakdown ins.jstree-icon")

    self.WaitUntil(sel.is_element_present,
                   "css=#_Clients-OS_20Breakdown-_207_20Day_20Active")
    sel.click("css=li[path='/Clients/OS Breakdown/ 7 Day Active'] a")

    self.WaitUntilEqual(u"No data Available",
                        sel.get_text, "css=#main_rightPane h3")

    self.PopulateData()
    sel.click("css=li[path='/Clients/OS Breakdown/ 7 Day Active'] a")

    self.WaitUntilEqual(u"Operating system break down.",
                        sel.get_text, "css=#main_rightPane h3")
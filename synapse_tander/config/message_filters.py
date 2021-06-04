# -*- coding: utf-8 -*-
# Copyright 2017 Openmarket
#
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

from ._base import Config, ConfigError

import importlib


class MessageFilterConfig(Config):
    section = "message_filters"
    def read_config(self, config, **kwargs):
        self.message_filters = []

        filters = config.get("message_filters", [])
        for filter in filters:
            # We need to import the module, and then pick the class out of
            # that, so we split based on the last dot.
            module, clz = filter['module'].rsplit(".", 1)
            module = importlib.import_module(module)
            try:
	            filter_class = getattr(module, clz)
            except AttributeError:
                raise ConfigError(
                    "No such filter %s in module %s" % (clz, filter['module'].rsplit(".", 1)[0])
                )

            try:
                filter_config = filter_class.parse_config(filter["config"])
            except Exception as e:
                raise ConfigError(
                    "Failed to parse config for %r: %r" % (filter['module'], e)
                )
            self.message_filters.append((filter_class, filter_config))

    def default_config(self, **kwargs):
        return """\
        # message_filters:
        #     - module: "matrix_message_filter.ExampleFilter"
        #       config:
        #         enabled: true
        """


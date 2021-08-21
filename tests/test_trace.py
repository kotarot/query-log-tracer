# Copyright 2021 Kotaro Terada
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

import query_log_tracer as qlt


def test_trace():
    histories = qlt.search_from_file(filename='./tests/files/general-query.log', target_table='dtb_customer', target_column='point', filter_column='id', filter_value='1')

    assert len(histories) == 13

    assert histories[0]['log_date'] == '2020-02-02T07:19:51.127168Z'
    assert histories[0]['log_id'] == '22'
    assert histories[0]['value'] == "'0'"
    assert histories[0]['increment'] is None

    assert histories[-1]['log_date'] == '2020-02-02T07:33:41.745400Z'
    assert histories[-1]['log_id'] == '126'
    assert histories[-1]['value'] is None
    assert histories[-1]['increment'] == 500

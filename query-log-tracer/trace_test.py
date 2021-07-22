#!/usr/bin/env python3

import trace


def test_trace():
    histories = trace.search_from_file(filename='./tests/files/general-query.log', target_table='dtb_customer', target_column='point', filter_column='id', filter_value='1')

    assert len(histories) == 13

    assert histories[0]['log_date'] == '2020-02-02T07:19:51.127168Z'
    assert histories[0]['log_id'] == '22'
    assert histories[0]['value'] == "'0'"
    assert histories[0]['increment'] is None

    assert histories[-1]['log_date'] == '2020-02-02T07:33:41.745400Z'
    assert histories[-1]['log_id'] == '126'
    assert histories[-1]['value'] is None
    assert histories[-1]['increment'] == 500

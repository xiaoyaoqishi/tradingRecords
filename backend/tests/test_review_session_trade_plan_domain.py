from datetime import date


def _create_trade(client, symbol='IF', contract='IF2506', status='open', trade_date='2026-04-01'):
    payload = {
        'trade_date': trade_date,
        'instrument_type': '期货',
        'symbol': symbol,
        'contract': contract,
        'direction': '做多',
        'open_time': f'{trade_date}T09:00:00',
        'open_price': 3500,
        'quantity': 1,
        'status': status,
    }
    if status == 'closed':
        payload['close_time'] = f'{trade_date}T15:00:00'
        payload['close_price'] = 3510
        payload['pnl'] = 10
    resp = client.post('/api/trades', json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()['id']


def test_review_session_requires_selection_basis_and_review_goal(app_client):
    bad_payload = {
        'title': 'session',
        'review_kind': 'theme',
        'review_scope': 'themed',
        'selection_mode': 'manual',
    }
    bad = app_client.post('/api/review-sessions', json=bad_payload)
    assert bad.status_code == 422, bad.text

    t1 = _create_trade(app_client)
    ok_payload = {
        'title': 'session',
        'review_kind': 'theme',
        'review_scope': 'themed',
        'selection_mode': 'manual',
        'selection_basis': 'same setup sample',
        'review_goal': 'verify repeated execution quality',
        'trade_links': [{'trade_id': t1, 'role': 'representative_trade'}],
    }
    ok = app_client.post('/api/review-sessions', json=ok_payload)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body['selection_basis'] == 'same setup sample'
    assert body['review_goal'] == 'verify repeated execution quality'
    assert body['linked_trade_ids'] == [t1]


def test_filter_snapshot_materialization_full_filtered_default(app_client):
    t1 = _create_trade(app_client, symbol='IF', contract='IF2506', trade_date='2026-04-01')
    t2 = _create_trade(app_client, symbol='IF', contract='IF2509', trade_date='2026-04-02')
    _create_trade(app_client, symbol='IC', contract='IC2506', trade_date='2026-04-03')

    resp = app_client.post(
        '/api/review-sessions/create-from-selection',
        json={
            'title': 'if slice',
            'review_kind': 'symbol',
            'review_scope': 'themed',
            'selection_mode': 'filter_snapshot',
            'selection_basis': 'symbol IF',
            'review_goal': 'evaluate IF sample consistency',
            'filter_params': {'symbol': 'IF'},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body['linked_trade_ids']) == sorted([t1, t2])
    assert body['filter_snapshot_json'] is not None


def test_reviews_alias_maps_to_review_session(app_client):
    create = app_client.post(
        '/api/reviews',
        json={
            'review_type': 'weekly',
            'review_scope': 'themed',
            'review_date': '2026-04-04',
            'title': 'legacy alias',
            'focus_topic': 'legacy selected sample',
            'summary': 'legacy goal',
        },
    )
    assert create.status_code == 200, create.text
    review_id = create.json()['id']

    session_get = app_client.get(f'/api/review-sessions/{review_id}')
    assert session_get.status_code == 200, session_get.text
    session = session_get.json()
    assert session['selection_basis'] == 'legacy selected sample'
    assert session['review_goal'] == 'legacy goal'


def test_trade_plan_status_transition_and_links(app_client):
    t1 = _create_trade(app_client)

    created = app_client.post(
        '/api/trade-plans',
        json={
            'title': 'plan-a',
            'plan_date': str(date.today()),
            'status': 'draft',
            'trade_links': [{'trade_id': t1}],
        },
    )
    assert created.status_code == 200, created.text
    plan = created.json()
    assert plan['linked_trade_ids'] == [t1]

    invalid = app_client.put(f"/api/trade-plans/{plan['id']}", json={'status': 'executed'})
    assert invalid.status_code == 400, invalid.text

    active = app_client.put(f"/api/trade-plans/{plan['id']}", json={'status': 'active'})
    assert active.status_code == 200, active.text
    triggered = app_client.put(f"/api/trade-plans/{plan['id']}", json={'status': 'triggered'})
    assert triggered.status_code == 200, triggered.text
    executed = app_client.put(f"/api/trade-plans/{plan['id']}", json={'status': 'executed'})
    assert executed.status_code == 200, executed.text
    reviewed = app_client.put(f"/api/trade-plans/{plan['id']}", json={'status': 'reviewed'})
    assert reviewed.status_code == 200, reviewed.text

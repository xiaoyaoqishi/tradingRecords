import uuid


def test_user_module_visibility_and_readonly(admin_login):
    client = admin_login
    username = f"perm_{uuid.uuid4().hex[:8]}"

    create_user = client.post('/api/admin/users', json={'username': username, 'password': 'u123456'})
    assert create_user.status_code == 200
    user_id = create_user.json()['id']

    update_perm = client.put(
        f'/api/admin/users/{user_id}',
        json={
            'module_permissions': ['notes'],
            'data_permissions': {'notes': 'read_only', 'trading': 'read_only', 'ledger': 'read_only'},
        },
    )
    assert update_perm.status_code == 200

    client.post('/api/auth/logout')
    login_user = client.post('/api/auth/login', json={'username': username, 'password': 'u123456'})
    assert login_user.status_code == 200

    check = client.get('/api/auth/check')
    assert check.status_code == 200
    payload = check.json()
    assert payload['module_permissions'] == ['notes']
    assert payload['data_permissions']['notes'] == 'read_only'

    # hidden module
    ledger_list = client.get('/api/ledger/import-batches')
    assert ledger_list.status_code == 403

    # visible module read
    notes_list = client.get('/api/notebooks')
    assert notes_list.status_code == 200

    # visible module write blocked by read_only
    notes_create = client.post('/api/notebooks', json={'name': 'readonly-notebook'})
    assert notes_create.status_code == 403
